#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 v2.2 包目录的版本身份（README/NOTICE/MANIFEST）预同步到 2.2
（= 正式打包流程里 pack_v13.py 在打闸门前会做的那一步）。

🔴 目的：让 `--dry-run` 能真实反映「能不能打」（dry-run 不写文件 ⇒
   若不同步，版本标识闸门必 FAIL ⇒ 看不到**其它**闸门的结果）。
"""
import os, sys
REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
sys.path.insert(0, REPO)
import pack_v13 as P

PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.2'
rc = P.sync_version_identity(
    PKG,
    changelog_zh=os.path.join(REPO, 'live_caption', 'release_notes', 'v2.2_zh.md'),
    changelog_en=os.path.join(REPO, 'live_caption', 'release_notes', 'v2.2_en.md'))
print('sync_version_identity rc =', rc)
rc2 = P.sync_manifest_version(PKG, '2.2')
print('sync_manifest_version rc =', rc2)
sys.exit(rc or rc2)
