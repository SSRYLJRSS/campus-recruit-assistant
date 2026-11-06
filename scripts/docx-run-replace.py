#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""docx 文本修正：run 级替换，保留原排版（证件照/页眉页脚/样式不动）。

场景：用户交付的排版好的最终版 docx 里有笔误（如实习时间写错），
只需改文字、不能破坏格式。python-docx 打开即改 run.text 可保留样式；
若目标文本被拆在多个 run 里，本脚本仅报 WARN 不瞎改，提示手动处理。

用法（Windows 路径，python-docx 不吃 MSYS 路径）：
    python docx-run-replace.py <src.docx> <dst.docx> <旧文本> <新文本>
    python docx-run-replace.py input.docx output.docx "2026.9" "2025.9"

验证：保存后重开 dst，确认旧文本无残留、新文本存在（exit 0/2/3）。
2026-08 实测：示例简历里某段实习时间 2025.6-2026.9 → 2025.6-2025.9，单 run 内替换成功。
"""
import sys

import docx


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 1
    src, dst, old, new = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

    d = docx.Document(src)
    changed = 0
    for p in d.paragraphs:
        if old in p.text:
            for r in p.runs:
                if old in r.text:
                    r.text = r.text.replace(old, new)
                    changed += 1
                    print(f"fixed run: {r.text!r}")

    if changed == 0:
        print(f"WARN: 未找到含「{old}」的可替换 run（文本可能跨 run 拆分，需手动处理段落）")
        return 2

    d.save(dst)
    d2 = docx.Document(dst)
    old_left = any(old in p.text for p in d2.paragraphs)
    new_ok = any(new in p.text for p in d2.paragraphs)
    print(f"changed runs: {changed} | 旧文本残留: {old_left} | 新文本存在: {new_ok}")
    if not old_left and new_ok:
        print(f"OK -> {dst}")
        return 0
    print("ERROR: 验证未通过")
    return 3


if __name__ == "__main__":
    sys.exit(main())
