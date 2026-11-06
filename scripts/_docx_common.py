# -*- coding: utf-8 -*-
"""共享 docx 段落编辑 helper。

被 `docx-template-fill.py` 与 `docxtpl-build-template.py` 复用，消除两份逐字重复的
find / find_all / next_p / set_text / delete / insert_after（/ insert_before）实现。

设计要点（不改原脚本用法）：
- 所有函数不依赖模块级全局 `doc`，需要文档的函数显式传入 `doc`。
- `make_helpers(doc)` 返回一组"绑定到该 doc"的函数：`find('前缀')`、`find_all('前缀')`
  等仍按单参方式调用，等价于原脚本里的局部函数。
- 段落定位用文字前缀，绝不用列表索引（插入/删除后索引全变）。
- insert_after / insert_before 返回新 Paragraph；同一参考点重复 addnext 会逆序。
- set_text 整段合并为单 run 并保留首个 run 样式（字号/颜色/占位符单 run 需求）。
"""
import copy
from functools import partial

from docx.text.paragraph import Paragraph

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def _el(p):
    """兼容 Paragraph 与底层 CT_P 元素。"""
    return p._p if hasattr(p, '_p') else p


def find(doc, prefix):
    """按文字前缀定位段落（唯一事实定位方式）。"""
    for p in doc.paragraphs:
        if p.text.strip().startswith(prefix):
            return p
    raise ValueError('未找到段落: ' + prefix)


def find_all(doc, prefix):
    """收集全部以 prefix 开头的段落（同前缀多段时按序处理，勿用 find）。"""
    return [p for p in doc.paragraphs if p.text.strip().startswith(prefix)]


def next_p(p, skip_empty=False):
    """取下一个兄弟段落；skip_empty=True 时跳过空段落（定位描述行用）。"""
    nxt = _el(p).getnext()
    while nxt is not None:
        if nxt.tag == W + 'p':
            if not skip_empty:
                return nxt
            texts = nxt.findall('.//' + W + 't')
            if texts and any(t.text and t.text.strip() for t in texts):
                return nxt
        nxt = nxt.getnext()
    return None


def set_text(p, text):
    """替换段落文字，保留第一个 run 的格式（字号/颜色），删除多余 runs。"""
    runs = p.runs
    if runs:
        runs[0].text = text
        for r in runs[1:]:
            r._element.getparent().remove(r._element)
    else:
        p.add_run(text)


def delete(p):
    """删除段落（兼容 Paragraph 与 CT_P）。"""
    el = _el(p)
    el.getparent().remove(el)


def insert_after(ref_p, template_p, text):
    """在 ref_p 后插入新段落，deepcopy template_p 的样式，返回新 Paragraph。"""
    new = copy.deepcopy(_el(template_p))
    _el(ref_p).addnext(new)
    np = Paragraph(new, ref_p._parent)
    set_text(np, text)
    return np


def insert_before(ref_p, template_p, text):
    """在 ref_p 前插入新段落，deepcopy template_p 的样式，返回新 Paragraph。"""
    new = copy.deepcopy(_el(template_p))
    _el(ref_p).addprevious(new)
    np = Paragraph(new, ref_p._parent)
    set_text(np, text)
    return np


def make_helpers(doc):
    """返回绑定到给定 doc 的一组 helper（保持原脚本单参调用风格）。

    返回顺序：find, find_all, next_p, set_text, delete, insert_after, insert_before
    """
    return (
        partial(find, doc),
        partial(find_all, doc),
        next_p,
        set_text,
        delete,
        insert_after,
        insert_before,
    )
