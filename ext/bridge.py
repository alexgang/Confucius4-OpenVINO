"""bridge.py — EXT-001 B 节：本地桥接服务（dub_server.py 的核心）

职责：
  * 只绑 127.0.0.1，WebSocket；
  * 安全：校验 Origin = chrome-extension://<本插件 id>，并用首次配对生成的 token 鉴权；
  * 管线：PCM（带 sample_index）→ 分段（R2T2 原有断句，EXT-002）→ ASR 定稿段
    → MT → TTS（按说话人选音色）→ 时长适配 → 下发 {id, t_start, t_end, src, tgt, spk, pcm24k}。

复用边界（EXT-001 总原则）：
  * ASR / MT / TTS 引擎**只 import 现有交付版本**，不改它们的文件；
  * 引擎未接入时，桥接服务仍可启动并完成**回声自测**（P0 ③）：
    服务端把收到的音频原样延迟 D 后发回，插件按 t_start + D 排程播放。

调用方式：
    python -m ext.bridge --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import secrets
import struct
import time
from typing import Optional

import numpy as np

from . import config as C
from .duration import fit_duration
from .segmenter import plan_segments, describe as describe_segmenter
from .speaker import SpeakerTracker

# ── 引擎接入点（复用现有交付版本；此处只做延迟 import，不改对方文件） ──
ENGINE_ADAPTER = None  # 由 main() 注入：见 ext/engines.py


def _log(msg: str) -> None:
    print(f"[bridge {time.strftime('%H:%M:%S')}] {msg}", flush=True)


class TokenStore:
    """首次配对生成的 token（落盘在项目目录，只读给插件）。"""

    def __init__(self, path: str) -> None:
        self.path = path
        self.token = self._load_or_create()

    def _load_or_create(self) -> str:
        if os.path.isfile(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
        t = secrets.token_urlsafe(24)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(t)
        return t

    def verify(self, candidate: str) -> bool:
        return bool(candidate) and secrets.compare_digest(candidate, self.token)


def check_origin(origin: Optional[str]) -> bool:
    """校验 Origin 必须是 chrome-extension://<id>。"""
    if not origin:
        return False
    return origin.startswith(C.ALLOWED_ORIGIN_PREFIX)


class Session:
    """一次配音会话。

    音频上行帧格式：{seq, sample_index, pcm(base64 PCM16 16k mono)}
    时间戳用**累计采样数**换算，不用墙钟，避免漂移（EXT-001 A 节）。
    """

    def __init__(self, token: str, *, delay_sec: float = 10.0) -> None:
        self.token = token
        self.delay_sec = delay_sec
        self.t0 = time.perf_counter()
        self.sample_index = 0
        self._buf = np.zeros((0,), dtype=np.float32)
        self.tracker = SpeakerTracker(
            clean_sec_required=C.SPK_CLEAN_SEC_REQUIRED,
            max_late_lag_sec=C.SPK_LATE_UPDATE_MAX_LAG_SEC,
            preset_voice=C.PRESET_VOICE,
        )
        self.n_frames = 0
        self.n_dropped = 0
        self._pending_sp: Optional[int] = None
        self._engine = ENGINE_ADAPTER

    # ── 接收一帧 ────────────────────────────────────────────────
    def on_pcm_frame(self, msg: dict) -> Optional[dict]:
        """处理一帧上行 PCM。

        Returns
        -------
        dict or None
            若该帧触发了「一段音频够长可分段」，返回待下发的配音任务列表；
            否则返回 None。
        """
        try:
            seq = int(msg.get("seq", 0))
            sidx = int(msg.get("sample_index", -1))
            pcm_b64 = msg.get("pcm") or ""
        except Exception:
            return None

        raw = base64.b64decode(pcm_b64) if pcm_b64 else b""
        if len(raw) < 2:
            return None
        # 连续性检查：sample_index 必须与上一帧接得上
        if self._pending_sp is not None and sidx != self._pending_sp:
            self.n_dropped += 1
            _log(f"帧不连续: 期望 {self._pending_sp} 实际 {sidx}（丢 {sidx - self._pending_sp} 样本）")
        arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        self._pending_sp = sidx + len(arr)

        self._buf = np.concatenate([self._buf, arr])
        self.n_frames += 1

        # 分段：以 R2T2 原有断句为准（EXT-002）
        segs = plan_segments(self._buf)
        if len(segs) <= 1:
            return None
        # 只处理已完整落在 [min, max] 内的段，最后一段留在缓冲区里等后续音频
        ready = [s for s in segs[:-1]]
        if not ready:
            return None
        tasks = []
        for (s0, s1) in ready:
            seg_audio = self._buf[s0:s1]
            self._buf = self._buf[s1:]
            tasks.extend(self._process_segment(seq, s0, s1, seg_audio))
        return tasks or None

    # ── 处理一段 → 配音任务 ──────────────────────────────────────
    def _process_segment(self, seq: int, s0: int, s1: int,
                         audio: np.ndarray) -> list:
        t_start = s0 / C.SAMPLE_RATE
        t_end = s1 / C.SAMPLE_RATE
        seg_id = f"seg_{s0}"

        # ASR 定稿：引擎未接入时留空（不猜内容）
        text = ""
        if self._engine is not None:
            try:
                text = self._engine.asr(audio, t_start, t_end) or ""
            except Exception as e:
                _log(f"ASR 失败（段 {seg_id}）: {e}")

        # spk：EXT-002 —— 定稿先出，spk 可能为 None
        spk = self.tracker.spk_for_final(seg_id, t_start, t_end)
        self.tracker.register_pending(seg_id, spk, t_start, t_end)
        voice = self.tracker.voice_for(spk)

        # 译文
        tgt = ""
        if self._engine is not None and text:
            try:
                tgt = self._engine.mt(text) or ""
            except Exception as e:
                _log(f"MT 失败（段 {seg_id}）: {e}")

        # TTS
        pcm24k = None
        speech_sec = 0.0
        if self._engine is not None:
            try:
                pcm24k, speech_sec = self._engine.tts(tgt or text, voice=voice)
            except Exception as e:
                _log(f"TTS 失败（段 {seg_id}）: {e}")

        fit = fit_duration(seg_id, t_start=t_start, t_end=t_end,
                           speech_sec=speech_sec, max_rate=C.TTS_RATE_MAX)

        return [{
            "type": "tts",
            "id": seg_id,
            "t_start": round(t_start, 3),
            "t_end": round(t_end, 3),
            "src": text,
            "tgt": tgt,
            "spk": spk,
            "voice": voice,
            "pcm24k": (base64.b64encode(pcm24k).decode("ascii")
                       if pcm24k is not None else None),
            "fit": fit.to_dict(),
            "delay_sec": self.delay_sec,
        }]

    # ── P0 ③ 回声测试：原样延迟 D 发回 ────────────────────────────
    def echo(self, msg: dict) -> Optional[dict]:
        """回声模式：把收到的音频原样延迟 D 后发回。"""
        raw = base64.b64decode(msg.get("pcm") or "")
        if not raw:
            return None
        sidx = int(msg.get("sample_index", 0))
        t_start = sidx / C.SAMPLE_RATE
        return {
            "type": "echo",
            "id": f"echo_{sidx}",
            "seq": int(msg.get("seq", 0)),
            "t_start": round(t_start, 3),
            "t_end": round(t_start + len(raw) / 2 / C.SAMPLE_RATE, 3),
            # ★ 回声原样 16 kHz PCM16；插件按 t_start + D 排程播放
            "pcm24k": base64.b64encode(raw).decode("ascii"),
            "sample_rate": C.SAMPLE_RATE,
            "delay_sec": self.delay_sec,
        }

    def stats(self) -> dict:
        return {
            "n_frames": self.n_frames,
            "n_dropped": self.n_dropped,
            "buffered_sec": round(self._buf.shape[0] / C.SAMPLE_RATE, 2),
            "speaker": self.tracker.stats(),
        }


def _get_header(websocket, name: str) -> Optional[str]:
    """跨 websockets 版本取请求头。

    websockets 10.x/11.x 旧 asyncio API：``websocket.request_headers``；
    websockets 12+ 新 asyncio API：``websocket.request.headers``。
    两种都兼容，缺 header 返回 None。
    """
    try:
        hdrs = getattr(websocket, "request_headers", None)
        if hdrs is None:
            req = getattr(websocket, "request", None)
            hdrs = getattr(req, "headers", None)
        if hdrs is None:
            return None
        return hdrs.get(name, None)
    except Exception:
        return None


async def handle_ws(websocket, *, tokens: TokenStore, delay_sec: float,
                    echo_mode: bool) -> None:
    """单连接的握手与消息循环。"""
    origin = _get_header(websocket, "Origin") or ""
    if not check_origin(origin):
        _log(f"拒绝连接：Origin 非法 ({origin!r})")
        await websocket.close(code=1008, reason="bad origin")
        return

    # token 通过请求头或首个消息给出
    token = _get_header(websocket, "X-Bridge-Token")
    if not token:
        # ★ 浏览器端 WebSocket **不能自定义请求头** ⇒ 允许 token 放在
        #   首个 hello 消息里（EXT-003 P0①③ 的插件侧就是这么连的）。
        #   安全口径不变：token 必须正确，且 Origin 必须是 chrome-extension://。
        first = await _recv_first(websocket)
        if first is None:
            _log("拒绝连接：缺少 token")
            await websocket.close(code=1008, reason="no token")
            return
        token = str(first.get("token") or "")
        if not token:
            _log("拒绝连接：缺少 token")
            await websocket.close(code=1008, reason="no token")
            return
        if not tokens.verify(token):
            _log("拒绝连接：token 不匹配")
            await websocket.close(code=1008, reason="bad token")
            return
        _log(f"已通过首个 hello 消息鉴权（role={first.get('role')}）")
        await _handle_messages(websocket, session=Session(token, delay_sec=delay_sec),
                               first=first, echo_mode=echo_mode, delay_sec=delay_sec)
        return
    if not tokens.verify(token):
        _log("拒绝连接：token 不匹配")
        await websocket.close(code=1008, reason="bad token")
        return

    _log(f"已连接（origin={origin}）")
    session = Session(token, delay_sec=delay_sec)
    await _handle_messages(websocket, session=session, first=None,
                           echo_mode=echo_mode, delay_sec=delay_sec)


async def _recv_first(websocket) -> Optional[dict]:
    """读第一条消息并解析成 dict（用于 hello 帧里的 token 鉴权）。"""
    try:
        raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
    except Exception:
        return None
    try:
        msg = json.loads(raw)
    except Exception:
        return None
    return msg if isinstance(msg, dict) else None


async def _handle_messages(websocket, *, session: "Session", first: Optional[dict],
                           echo_mode: bool, delay_sec: float) -> None:
    """消息循环。`first` 若已读过则先处理它。"""
    try:
        pending = [first] if first else []
        it = pending.pop() if pending else None
        while True:
            if it is not None:
                msg = it
                it = None
            else:
                raw = await websocket.recv()
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
            if not isinstance(msg, dict):
                continue
            mtype = msg.get("type")
            if mtype == "hello":
                await websocket.send(json.dumps({
                    "type": "hello_ack",
                    "delay_sec": delay_sec,
                    "sample_rate": C.SAMPLE_RATE,
                    "segmentation": describe_segmenter(),
                }))
                continue
            if mtype == "stats":
                await websocket.send(json.dumps({"type": "stats", **session.stats()}))
                continue
            if mtype == "pcm":
                out = session.echo(msg) if echo_mode else session.on_pcm_frame(msg)
                if out:
                    for task in (out if isinstance(out, list) else [out]):
                        await websocket.send(json.dumps(task))
                continue
    except Exception as e:
        _log(f"连接异常: {e}")
    finally:
        _log("连接关闭")


async def serve(host: str, port: int, *, delay_sec: float, echo_mode: bool,
                token_path: str) -> None:
    import websockets

    tokens = TokenStore(token_path)
    _log(f"token 文件：{token_path}")
    _log(f"监听 ws://{host}:{port}（echo={echo_mode}, D={delay_sec}s）")
    async with websockets.serve(
        lambda ws: handle_ws(ws, tokens=tokens, delay_sec=delay_sec,
                              echo_mode=echo_mode),
        host, port,
        origins=None,
        max_size=32 * 1024 * 1024,
    ):
        await asyncio.Future()   # 永久运行


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT 桥接服务")
    ap.add_argument("--host", default=C.BRIDGE_HOST)
    ap.add_argument("--port", type=int, default=C.BRIDGE_PORT)
    ap.add_argument("--delay", type=float, default=10.0, help="延迟 D（秒）")
    ap.add_argument("--echo", action="store_true", help="P0 ③ 回声自测模式")
    ap.add_argument("--token-file", default=C.BRIDGE_TOKEN_FILE)
    args = ap.parse_args(argv)

    try:
        import websockets  # noqa: F401
    except Exception:
        _log("缺少依赖：websockets（pip install websockets）")
        return 2

    # 互斥检查（EXT-001 总原则）：实时字幕 App 在运行就拒绝启动
    if _caption_app_running():
        _log("检测到实时字幕 App 在运行，拒绝启动（设备互斥）")
        return 3

    token_path = args.token_file
    if not os.path.isabs(token_path):
        token_path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), token_path)

    try:
        asyncio.run(serve(args.host, args.port, delay_sec=args.delay,
                          echo_mode=args.echo, token_path=token_path))
    except KeyboardInterrupt:
        _log("已停止")
    return 0


def _caption_app_running() -> bool:
    """检测实时字幕 App 是否在运行（互斥铁律）。"""
    try:
        import psutil  # type: ignore
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(p.info.get("cmdline") or [])
                if "live_caption" in cmd.lower() and "ext.bridge" not in cmd.lower():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


if __name__ == "__main__":
    raise SystemExit(main())
