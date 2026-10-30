// _app104_write_status.js —— §104：把 §104 章节**追加**到 `status/app/STATUS_APP.md`。
// 🔴 用 **node**（不是 python）⇒ 持锁中的 TTS 计时作业的「外部 python 进程」判据不受影响。
// 铁律：只追加 / 纯 CRLF / 头部字段限定在头部区 / 最近更新 ≤15 行 / 写后四项校验。
'use strict';
const fs = require('fs');

const STATUS = 'C:\\Users\\Trekker-PTL\\confucius4-openvino\\status\\app\\STATUS_APP.md';
const NOW = '2026-10-30 10:52';

const APPEND_BODY = fs.readFileSync(
  'C:\\Users\\Trekker-PTL\\confucius4-openvino\\live_caption\\_app104_body.md',
  'utf8').replace(/\r\n/g, '\n').replace(/\n$/, '');

const NEW_TASK = ['**§104 🔴🔴🔳 「开工即查出 §103 声称已入库、实际未入库」的半交付 ⇒ 已补交入库；zip 仍半交付（锁被 TTS 持有）**',
'（巡检：`CORRECTIONS_APP.md` 44 条 = `last_ack: APP-044` ⇒ **无新纠偏条目**，第 30 次同一口径复核）',
'⇒ 🔴🔴🔴 **开工自查查出 4 个证据文件「STATUS 里写了、实际没入库」**',
'（`app160_app102_zip_evidence_v1.11.json` / `app149_app042_worker_side_speed_evidence.json` / `app157_app043_thread_env_gate_evidence_pkg.json` / `app157_follow_speaker_regression_evidence_pkg.json`）',
'⇒ 根因 = §103 两次 commit **只提了脚本、没提配套证据 JSON** ⇒ ✅ **已补交入库**（commit `c82f7e9`，4 files / +390）',
'⇒ 🔴 **另 2 个已入库产物被复跑覆盖**（`app158_..._pkg.json` / `app154_...json`）⇒ **内容等价、结论未变**（PASS 数与 verdict 未变）⇒ **归属未判定 ⇒ 本轮不动**',
'⇒ 🔴🔴🔴 **归纳「半交付」第四层判据**：① zip 旧 ② 包目录内容不合规 ③ 包目录代码 ≠ 仓库 ④ 🆕 **产物本身没进仓库**',
'⇒ ✅ **第 ③ 层已闭合**（9/9 文件归一化 SHA 逐字节一致，仓库 HEAD ⇄ 包目录全 MATCH）',
'⇒ 🔴 **锁仍被 TTS 持有**（pid 28892 / `OpenProcess` 判 alive exit 259）⇒ **不抢锁**',
'⇒ ✅ **重打 v1.12 的作业已在排队**（PID 23320/37168，10:26:35 起，仍在等锁）',
'⇒ 🔴 **本轮不写「已交付」**（zip 层面）⇒ 🔴 **本条需等 reviewer 复核**'].join('');

const NEW_BLOCK = ['① 🔴 **zip 半交付仍未闭环**：需等 TTS 释放锁后重打 v1.12 （含 §100 修复 ＋ §101 回归修复 ＋ APP-044 的 16 MB 资产 ＋ §102 脱敏）⇒ **必须显式 `--version 1.12`** ⇒ **本轮不抢锁、不写「已交付」**；',
'② 🔴 **锁被 TTS 持有**（pid 28892 / 10:25:39 / `OpenProcess` 判 alive exit 259）⇒ **重打作业已在排队**（PID 23320/37168，等锁中）⇒ 锁一释放后需跑 `app160 1.12` 到 0 FAIL 才可写「已交付」；',
'③ 🔴 **§104.3 的 2 个「复跑产物」是否入库请裁定**（`app158_..._pkg.json` / `app154_...json`，内容等价、结论未变）；',
'④ 🔴 **§104.9① 的 v1/v2 证据口径请以 v2 为准**（`app149` 3 437 B 是 v2/PASS=11，§97.2.2 记的 2 104 B 是 v1/PASS=8）；',
'⑤ 🔴 **§104.9③ 「产物没进仓库」是否纳入常设巡检项请裁定**；',
'⑥ 🔴 **§104.8① 的 6 个遗留同步脚本「已被后继覆盖 ⇒ 不入库」口径请确认**；',
'⑦ 🔴 **§103.1 的 V7 特征集请 reviewer 确认**（`clone_mode and not` / `bool(self._spk_voices)` / `voice_kind` 是否会被无关重构误伤）；',
'⑧ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；',
'⑨ 🔴 **用户实听 3 段 1.2–1.3× 配音未做**；',
'⑩ 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；',
'⑪ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）；',
'⑫ 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换未做**（仅离线 `app150`/`app155`/`app157`/`app159`）；',
'⑬ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读）'].join('');

function setField(head, key, value) {
  if (value.startsWith(key + ': ')) throw new Error('value 不得自带 key 前缀: ' + key);
  let cnt = 0;
  const out = head.map((ln) => {
    if (ln.startsWith(key + ': ')) { cnt++; return key + ': ' + value; }
    return ln;
  });
  if (cnt !== 1) throw new Error('字段 ' + key + ' 命中 ' + cnt + ' 次（应恰好 1 次）');
  return out;
}

const raw = fs.readFileSync(STATUS);
const crlf = raw.toString('binary').split('\r\n').length - 1;
const lf = raw.toString('binary').split('\n').length - 1;
if (crlf !== lf) throw new Error('STATUS 存在裸 LF ⇒ 中止');
const text = raw.toString('utf8');
const lines = text.split('\r\n');

let iS1 = lines.findIndex((ln) => ln.startsWith('## §1 '));
if (iS1 < 0) throw new Error('找不到 `## §1 ` 锚点');
let head = lines.slice(0, iS1);
const body = lines.slice(iS1);
const nBefore = body.filter((ln) => ln.startsWith('## §')).length;
if (nBefore !== 103) throw new Error('章节数 ' + nBefore + '（预期 103）');

head = setField(head, 'last_ack', 'APP-044');
head = setField(head, '更新时间', NOW);
head = setField(head, '当前任务', NEW_TASK);
head = setField(head, '阻塞 / 待用户决定', NEW_BLOCK);

const iRecent = head.findIndex((ln) => ln.startsWith('## ## 最近更新'));
if (iRecent < 0) throw new Error('找不到「最近更新」区块');
const recent = [];
for (let i = iRecent + 1; i < head.length; i++) {
  const ln = head[i];
  if (!ln.trim()) continue;
  if (ln.startsWith('## ')) break;
  recent.push(ln);
}
const newRecent = '2026-10-30 10:52 §104 🔴🔴🔳 **开工即查出「§103 声称已入库、实际未入库」的半交付 ⇒ 已补交入库**' +
  '（4 个证据文件：`app160_..._v1.11.json` / `app149_..._speed_evidence.json` / `app157_..._thread_env_gate_evidence_pkg.json` / `app157_..._follow_speaker_..._pkg.json`）' +
  '⇒ 根因 = §103 两次 commit **只提脚本、没提配套证据 JSON** ⇒ ✅ **已补交入库**（`c82f7e9`，4 files / +390）' +
  '⇒ 🔴 **另 2 个已入库产物被复跑覆盖**（内容等价、结论未变）⇒ **不动**' +
  '⇒ 🔴🔴🔴 **归纳「半交付」第四层判据**：④ 🆕 **产物本身没进仓库**' +
  '⇒ ✅ **第 ③ 层已闭合**（9/9 归一化 SHA 全 MATCH，仓库 HEAD ⇄ 包目录一致）' +
  '⇒ 🔴 **锁仍被 TTS 持有**（pid 28892 alive）⇒ **不抢锁**、重打作业已在排队（PID 23320/37168）' +
  '⇒ 🔴 **zip 仍半交付 ⇒ 不写「已交付」** ⇒ 🔴 **本条需等 reviewer 复核**';
const merged = [newRecent].concat(recent);
while (merged.length > 15) merged.pop();

const newHead = head.slice(0, iRecent + 1).concat(merged, ['', '']);
const newBody = body.concat([''], APPEND_BODY.split('\n'));
const outLines = newHead.concat(newBody);
const out = outLines.join('\r\n');

fs.writeFileSync(STATUS, Buffer.from(out, 'utf8'));

// ── 写后校验 ──
const v = fs.readFileSync(STATUS);
const vb = v.toString('binary');
if (vb.split('\n').length - 1 !== vb.split('\r\n').length - 1) throw new Error('写后不是纯 CRLF');
const vt = v.toString('utf8');
const vl = vt.split('\r\n');
const nAfter = vl.filter((ln) => ln.startsWith('## §')).length;
if (nAfter !== 104) throw new Error('章节数 ' + nAfter + '（预期 104）');
// 🔴 旧正文**逐字未变**的判据 = 「旧正文整块在新文件里原样出现」
//    （**不是** endsWith —— 追加块前面多了一个空行 ⇒ endsWith 会误报「旧正文被改动」）。
const oldBodyText = body.join('\r\n');
if (vt.indexOf(oldBodyText) < 0) throw new Error('旧正文被改动');
if (vt.indexOf(APPEND_BODY) < 0) throw new Error('新章节未落盘');
const iR2 = vl.findIndex((ln) => ln.startsWith('## ## 最近更新'));
let cnt = 0;
for (let i = iR2 + 1; i < vl.length; i++) {
  if (!vl[i].trim()) continue;
  if (vl[i].startsWith('## §1 ')) break;
  cnt++;
}
if (cnt > 15) throw new Error('最近更新 ' + cnt + ' 行 > 15');
console.log('OK bytes ' + raw.length + ' -> ' + v.length +
  '  章节 ' + nBefore + ' -> ' + nAfter + '  纯CRLF  最近更新 ' + cnt + ' 行');
console.log(vl.filter((l) => l.startsWith('last_ack:')).join(''));
console.log(vl.filter((l) => l.startsWith('更新时间:')).join(''));
console.log('§104 章节存在:', vl.some((l) => l.startsWith('## §104 ')));
