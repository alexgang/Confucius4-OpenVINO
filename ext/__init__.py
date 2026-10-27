"""ext — EXT 模块（Chrome 实时翻译配音插件）核心库

模块边界（EXT-001 总原则）：
- 本包只做 EXT 自己的管线与适配层。
- ASR / MT / TTS 引擎一律**复用现有交付版本**，不改其他模块的文件；
  只在 import 或复制适配层的范围内复用。
- 引擎若需改动，写进 status/STATUS_EXT.md，由主会话转给对应模块。
"""
__all__ = ["config", "segmenter", "speaker", "duration", "pipeline"]
