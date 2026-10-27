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
from typing import Dict, List, Optional

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

    ★ EXT-006：真实引擎模式下的**余量统计**是 P1 的核心验收量 ——
      「原声结束 → TTS 就绪」的余量分布、余量 < 0 的句数、累计滞后。
    """

    def __init__(self, token: str, *, delay_sec: float = 10.0,
                 engine=None) -> None:
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
        # ★ 已消耗（已切走）的样本数 —— 段的时间基点必须相对**会话起点**，
        #   不能相对「当前缓冲区」。见 _process_segment 的说明。
        self._consumed_samples = 0
        self._engine = engine if engine is not None else ENGINE_ADAPTER
        # ── EXT-006 余量统计 ──────────────────────────────────
        #   margin_sec = (TTS 就绪时刻) − (该段原声结束时刻)
        #   负数 ⇒ 配音来不及在原声结束前就绪 ⇒ 滞后累积
        self._seg_orig_end: Dict[str, float] = {}   # seg_id → 原声结束（会话秒）
        self._seg_ready: Dict[str, float] = {}      # seg_id → TTS 就绪（会话秒）
        self.margins: List[dict] = []               # 每句一条
        self.engine_calls: List[dict] = []          # 引擎各阶段耗时

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
        ready = list(segs[:-1])
        if not ready:
            return None
        tasks = []
        # ★ 段索引是相对**当前缓冲区**的 ⇒ 换算成会话绝对样本偏移。
        #   旧实现每处理一段就把 self._buf 裁掉前段，却继续用旧的 (s0, s1)
        #   去切下一个段 ⇒ 索引错位（第二段起音频被切错），且 t_start 归零
        #   ⇒ 全部段的时间基点漂移。EXT-006 P1 要按时间表落盘配音，
        #   这个错位会直接污染「同步误差」指标。
        for (s0, s1) in ready:
            seg_audio = self._buf[s0:s1]
            abs0 = self._consumed_samples + s0
            abs1 = self._consumed_samples + s1
            tasks.extend(self._process_segment(seq, abs0, abs1, seg_audio))
        # 一次性裁掉所有已处理的段，并把基准点推进
        cut = ready[-1][1]
        self._buf = self._buf[cut:]
        self._consumed_samples += cut
        return tasks or None

    # ── 处理一段 → 配音任务 ──────────────────────────────────────
    def flush(self) -> list:
        """把缓冲区里的**尾段**也处理掉（EXT-006 P1：时间表要完整）。

        流式服务默认把最后一段留在缓冲区等后续音频（正常直播场景正确）。
        但 P1 验收要「配音 wav 和时间表落盘」⇒ 喂完最后一批音频后，
        客户端会发一条 `flush` ⇒ 这里把剩余缓冲切成一段并处理。

        Returns
        -------
        list
            配音任务列表（通常 0 或 1 条；缓冲区太短则 0 条）。
        """
        if self._buf.shape[0] < int(1.0 * C.SAMPLE_RATE):
            # 尾部不足 1 s ⇒ 没有有意义的语音段，丢弃（不计为段）
            self._buf = np.zeros((0,), dtype=np.float32)
            return []
        # ★ 绝对偏移：尾段同样要相对**会话起点**，不能归零
        #   （否则会重现「段起始时间基点归零」那个缺陷）。
        abs0 = self._consumed_samples
        abs1 = self._consumed_samples + self._buf.shape[0]
        seg_audio = self._buf
        tasks = self._process_segment(0, abs0, abs1, seg_audio)
        self._buf = np.zeros((0,), dtype=np.float32)
        self._consumed_samples += seg_audio.shape[0]
        return tasks

    def _process_segment(self, seq: int, s0: int, s1: int,
                         audio: np.ndarray) -> list:
        t_start = s0 / C.SAMPLE_RATE
        t_end = s1 / C.SAMPLE_RATE
        seg_id = f"seg_{s0}"

        # ★ EXT-006：原声结束时刻（会话秒）—— 余量的基准
        orig_end = self.t0 + t_end
        self._seg_orig_end[seg_id] = orig_end

        # ASR 定稿：引擎未接入时留空（不猜内容）
        text = ""
        t_asr = time.perf_counter()
        if self._engine is not None:
            try:
                text = self._engine.asr(audio, t_start, t_end) or ""
            except Exception as e:
                _log(f"ASR 失败（段 {seg_id}）: {e}")
        asr_s = time.perf_counter() - t_asr

        # spk：EXT-002 —— 定稿先出，spk 可能为 None
        spk = self.tracker.spk_for_final(seg_id, t_start, t_end)
        self.tracker.register_pending(seg_id, spk, t_start, t_end)
        voice = self.tracker.voice_for(spk)

        # 译文
        tgt = ""
        t_mt = time.perf_counter()
        if self._engine is not None and text:
            try:
                tgt = self._engine.mt(text) or ""
            except Exception as e:
                _log(f"MT 失败（段 {seg_id}）: {e}")
        mt_s = time.perf_counter() - t_mt

        # TTS
        pcm24k = None
        speech_sec = 0.0
        t_tts = time.perf_counter()
        if self._engine is not None:
            try:
                pcm24k, speech_sec = self._engine.tts(tgt or text, voice=voice)
            except Exception as e:
                _log(f"TTS 失败（段 {seg_id}）: {e}")
        tts_s = time.perf_counter() - t_tts

        # ★ EXT-006：TTS 就绪时刻 + 余量
        ready_at = time.perf_counter()
        self._seg_ready[seg_id] = ready_at
        # EXT-006 原文要的余量：「原声结束 → TTS 就绪」
        margin = ready_at - orig_end
        # ★ 另一个**决定能不能跟上**的口径：**排程截止余量**
        #   插件把这段配音排在 `t0 + t_start + D`（EXT-001 A 节）⇒
        #   配音必须在那一刻**之前**就绪，否则要么来不及、要么被钳位到「立刻播」。
        #   deadline_margin = (t0 + t_start + D) − ready_at
        #   ⇒ 负数 ⇒ 这句配音**赶不上**自己的播放时刻（真正的滞后）。
        deadline = self.t0 + t_start + self.delay_sec
        deadline_margin = deadline - ready_at
        self.margins.append({
            "id": seg_id,
            "t_start": round(t_start, 3),
            "t_end": round(t_end, 3),
            "orig_end": round(orig_end, 3),
            "ready_at": round(ready_at, 3),
            "margin_sec": round(margin, 4),
            "deadline": round(deadline, 3),
            "deadline_margin_sec": round(deadline_margin, 4),
            "asr_sec": round(asr_s, 4),
            "mt_sec": round(mt_s, 4),
            "tts_sec": round(tts_s, 4),
            "speech_sec": round(speech_sec, 4),
            "src_len": len(text or ""),
            "tgt_len": len(tgt or ""),
            "has_tts": pcm24k is not None,
        })
        self.engine_calls.append({
            "id": seg_id, "asr_sec": round(asr_s, 4),
            "mt_sec": round(mt_s, 4), "tts_sec": round(tts_s, 4)})

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
            # ★ EXT-006 P1：把排程截止余量带给客户端 ⇒
            #   客户端可按 EXT-001 口径算「实际播放起点 − 原声起点 + D」，
            #   不必自己猜就绪时刻。
            "deadline_margin_sec": round(deadline_margin, 4),
            "margin_sec": round(margin, 4),
            "speech_sec": round(speech_sec, 4),
            "tts_ready_at": round(ready_at, 3),
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
            "margin": self.margin_summary(),
        }

    def margin_summary(self) -> dict:
        """★ EXT-006 P1 核心验收量。

        「原声结束 → TTS 就绪」的余量分布、余量 < 0 的句数、累计滞后。

        * `margin_sec` 负数 ⇒ 配音**来不及**在该段原声结束前就绪
          ⇒ 播放时该段配音会**压后**（顺延），连续负值 ⇒ 滞后累积。
        * `cumulative_lag_sec` = 负余量的**累计**（不抵消），
          近似「5 分钟结束时的累计滞后」。
        * `deadline` 一组 = **排程截止余量**（EXT-001 的实际排程时刻
          `t0 + t_start + D` 减去就绪时刻）⇒ 负数 = 这句**赶不上自己的播放时刻**
          ⇒ 这是比 `margin_sec` 更贴近「用户能不能听上配音」的口径。
        """
        ms = [m["margin_sec"] for m in self.margins]
        neg = [m for m in ms if m < 0]
        cum = 0.0
        peak = 0.0
        for v in ms:
            cum += min(0.0, v)
            peak = min(peak, cum)
        out = {
            "n_segments": len(ms),
            "n_negative": len(neg),
            "cumulative_lag_sec": round(cum, 4),
            "peak_lag_sec": round(peak, 4),
        }
        if ms:
            s = sorted(ms)
            def _pct(p):
                k = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
                return round(s[k], 4)
            out.update({
                "min": round(s[0], 4),
                "p50": _pct(0.50),
                "p95": _pct(0.95),
                "max": round(s[-1], 4),
                "mean": round(sum(ms) / len(ms), 4),
            })
        # ── 排程截止余量 ──────────────────────────────────────
        dl = [m.get("deadline_margin_sec") for m in self.margins
              if m.get("deadline_margin_sec") is not None]
        if dl:
            sd = sorted(dl)
            cum_d = 0.0
            peak_d = 0.0
            for v in dl:
                cum_d += min(0.0, v)
                peak_d = min(peak_d, cum_d)

            def _pct_d(p):
                k = min(len(sd) - 1, max(0, int(round(p * (len(sd) - 1)))))
                return round(sd[k], 4)
            out["deadline"] = {
                "n_negative": sum(1 for v in dl if v < 0),
                "cumulative_lag_sec": round(cum_d, 4),
                "peak_lag_sec": round(peak_d, 4),
                "min": round(sd[0], 4),
                "p50": _pct_d(0.50),
                "p95": _pct_d(0.95),
                "max": round(sd[-1], 4),
                "mean": round(sum(dl) / len(dl), 4),
            }
        return out


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
                    echo_mode: bool, engine=None,
                    session_holder: Optional[dict] = None) -> None:
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
        session = Session(token, delay_sec=delay_sec, engine=engine)
        if session_holder is not None:
            session_holder["session"] = session
        await _handle_messages(websocket, session=session,
                               first=first, echo_mode=echo_mode, delay_sec=delay_sec)
        return
    if not tokens.verify(token):
        _log("拒绝连接：token 不匹配")
        await websocket.close(code=1008, reason="bad token")
        return

    _log(f"已连接（origin={origin}）")
    session = Session(token, delay_sec=delay_sec, engine=engine)
    if session_holder is not None:
        session_holder["session"] = session
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
            if mtype == "flush":
                # ★ EXT-006 P1：客户端说「音频喂完了」⇒ 把**尾段**也处理掉。
                #   流式服务默认把最后一段留在缓冲区（等后续音频），
                #   但 P1 要求「配音 wav 和时间表落盘」⇒ 尾段必须出，
                #   否则时间表缺最后一段，reviewer 回转写时对不上。
                #   回声模式不适用（echo 是逐帧原样返回，无需切段）。
                if not echo_mode:
                    out = session.flush()
                    if out:
                        for task in out:
                            await websocket.send(json.dumps(task))
                continue
    except Exception as e:
        _log(f"连接异常: {e}")
    finally:
        _log("连接关闭")


async def serve(host: str, port: int, *, delay_sec: float, echo_mode: bool,
                token_path: str, engine=None, margin_out: Optional[str] = None,
                session_holder: Optional[dict] = None) -> None:
    import websockets

    tokens = TokenStore(token_path)
    _log(f"token 文件：{token_path}")
    _log(f"监听 ws://{host}:{port}（echo={echo_mode}, D={delay_sec}s）")
    async with websockets.serve(
        lambda ws: handle_ws(ws, tokens=tokens, delay_sec=delay_sec,
                              echo_mode=echo_mode, engine=engine,
                              session_holder=session_holder),
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
    # ── EXT-006：真实引擎（P1） ──────────────────────────────
    ap.add_argument("--real", action="store_true",
                    help="接入真实引擎（ASR→MT→TTS），EXT-006 P1")
    ap.add_argument("--target-lang", default="en",
                    help="目标语言（en/zh/ja/...），TTS 会显式传给它")
    ap.add_argument("--margin-out", default=None,
                    help="把余量统计与时间表落盘到这个 JSON")
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

    # ── EXT-006：注入真实引擎 ────────────────────────────────
    engine = None
    if args.real:
        try:
            from .engines import load_runtime_engine
            engine = load_runtime_engine(target_lang=args.target_lang)
            _log(f"真实引擎已接线：ASR(R2T2 INT8@{C.DEVICE_ASR}) → "
                 f"MT(Hy-MT2 INT8@{C.DEVICE_MT}) → "
                 f"TTS(Qwen3-TTS@{C.DEVICE_TTS})，目标语言={args.target_lang}")
        except Exception as e:
            # ★ 不静默回落到回声模式 —— 否则 P1 验收会拿到假数据
            _log(f"❌ 真实引擎接线失败：{type(e).__name__}: {e}")
            return 4
    else:
        _log("回声模式（未接引擎）—— 仅供 P0 ③ 自测")

    holder: dict = {}
    try:
        asyncio.run(serve(args.host, args.port, delay_sec=args.delay,
                          echo_mode=args.echo, token_path=token_path,
                          engine=engine, margin_out=args.margin_out,
                          session_holder=holder))
    except KeyboardInterrupt:
        _log("已停止")
    finally:
        _dump_margin(holder, args.margin_out, engine)
    return 0


def _dump_margin(holder: dict, out_path: Optional[str], engine) -> None:
    """把余量统计与逐句时间表落盘（EXT-006 P1 验收要求）。"""
    if not out_path:
        return
    sess = holder.get("session")
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_lang": getattr(engine, "target_lang", None),
        "margin_summary": (sess.margin_summary() if sess else {}),
        "per_segment": (sess.margins if sess else []),
        "engine_calls": (sess.engine_calls if sess else []),
        "engine_stats": (engine.stats() if engine is not None else {}),
    }
    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _log(f"余量统计已落盘：{out_path}")
    except Exception as e:
        _log(f"余量统计落盘失败：{e}")


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
