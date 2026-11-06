# -*- coding: utf-8 -*-
r"""以用户简历 docx 为模板生成定制版（保留样式，替换/插入/删除段落）。

用法：
1. 运行：python docx-template-fill.py <用户模板.docx> <输出.docx>（不传则用占位符，运行时提示）
2. 用 find() 定位要改的段落，set_text() 改文字，insert_after() 插条目，delete() 删条目
3. 运行后必须用 docx.Document(OUT) 读回验证段落顺序与内容

原理：python-docx 打开用户 docx → 段落 XML 就地编辑（样式/页眉页脚/装饰全部保留）。
关键点：
- 段落定位用文字前缀 find()，绝不用列表索引（插入/删除后索引全变）
- insert_after 返回新 Paragraph，链式使用；同一参考点重复 addnext 会逆序
- next_p 带 skip_empty 跳过模板里的空段落
- _p 属性只在 Paragraph 上，CT_P 对象用 hasattr 兼容

验证页数：生成 PDF 后用 `re.findall(rb'/Count (\d+)', open(pdf,'rb').read())` 检查 =1。（docstring 用 r 前缀转 raw，`\d` 不触发 SyntaxWarning）
"""
import sys

# 强制 UTF-8 输出，避免 Windows 控制台默认 GBK 造成中文乱码/UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from docx import Document

# 共用 helper（与 docxtpl-build-template.py 复用，源见 scripts/_docx_common.py）
from _docx_common import make_helpers

# 路径参数化：命令行传入，或自行修改默认占位（不含本机绝对盘符/用户名）
if len(sys.argv) >= 3:
    SRC, OUT = sys.argv[1], sys.argv[2]
else:
    SRC = '<用户模板.docx 路径>'
    OUT = '<输出.docx 路径>'

doc = Document(SRC)

# 绑定到当前 doc 的 helper（find / find_all / next_p / set_text / delete / insert_after / insert_before）
find, find_all, next_p, set_text, delete, insert_after, insert_before = make_helpers(doc)


# ===== 使用示例（按需改写） =====
# p = find('主要掌握')                      # 定位
# set_text(p, '新描述文字')
# t = insert_after(p, p, '时间\t名称')      # 插条目（用 p 作样式模板）
# r = insert_after(t, next_p(p), '角色')    # 角色行（next_p 取 p 的下一非空兄弟作模板）
# insert_after(r, p, '描述文字')
# delete(find('旧条目前缀'))                 # 删条目

doc.save(OUT)
print('SAVED:', OUT)
