# -*- coding: utf-8 -*-
"""docx 保真度校验：对比模板与产物的每个部件 md5。

原理：docxtpl/python-docx 都是「就地编辑」——未触碰的部件应逐字节一致。
通过标准（2026-08 实测 33/35）：
- styles.xml / header*.xml / footer*.xml / media/* / theme / settings / fontTable / rels 全部一致
- 仅 word/document.xml（正文替换）+ docProps/core.xml（时间戳）变化 = 保真通过
- 若 header/footer/media 也变了 → 模板被意外改写，立即停止排查

用法：python docx-fidelity-check.py <模板.docx> <产物.docx>
"""
import sys
import zipfile
import hashlib


def parts(path):
    z = zipfile.ZipFile(path)
    d = {}
    for n in z.namelist():
        if not n.endswith('/'):
            d[n] = hashlib.md5(z.read(n)).hexdigest()
    return d


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    tpl, out = sys.argv[1], sys.argv[2]
    a, b = parts(tpl), parts(out)

    same, diff, missing = [], [], []
    for k in a:
        if k not in b:
            missing.append(k)
        elif a[k] == b[k]:
            same.append(k)
        else:
            diff.append(k)

    print(f'完全一致: {len(same)} 个部件')
    print(f'变化: {len(diff)} 个: {diff}')
    print(f'缺失: {len(missing)} 个: {missing}')

    # 核心：正文变化是预期，装饰类变化是事故
    ok_diff = {d for d in diff if d in ('word/document.xml', 'docProps/core.xml')}
    bad_diff = set(diff) - ok_diff
    if not bad_diff and not missing:
        print('PASS: 保真通过（仅正文/元数据变化）')
        sys.exit(0)
    else:
        print('FAIL: 装饰部件被改写，检查模板改造/渲染流程')
        sys.exit(2)


if __name__ == '__main__':
    main()
