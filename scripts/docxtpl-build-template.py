# -*- coding: utf-8 -*-
"""docxtpl 模板改造（一次性）：把用户 docx 模板改造为 {{var}} 占位符模板。

用法：
1. 运行：python docxtpl-build-template.py <母版.docx> <母版_占位符版.docx>（原版存档，勿动）
2. 按下方「占位符布局」把动态文字改 {{var}}、循环块加 {%p for %}/{%p endfor %}、引导语删除
3. 跑本脚本生成占位符版 → WPS 打开目检占位符是否完整（应全部为单 run）
4. 之后每次生成只用 render 脚本填 context，不再碰模板

关键模式（2026-08-11 实测）：
- find_all() 先收集全部同前缀段落再按序赋值——find() 对「三个『开始时间-结束时间』行」会误命中第一个
- set_text 整段合并为单 run（保留首 run 样式）：docxtpl 要求占位符独占 run，WPS 拆 run 会导致渲染异常
- 循环标签段 deepcopy 循环体首段的样式（pPr 继承）
- 空段落（版式间距）留在循环体外，不插任何标签
"""
import sys

# 强制 UTF-8 输出，避免 Windows 控制台默认 GBK 造成中文乱码/UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from docx import Document

# 共用 helper（与 docx-template-fill.py 复用，源见 scripts/_docx_common.py）
from _docx_common import make_helpers

# 路径参数化：命令行传入 <母版.docx> <母版_占位符版.docx>，或自行改占位（不含本机绝对盘符/用户名）
if len(sys.argv) >= 3:
    SRC, OUT = sys.argv[1], sys.argv[2]
else:
    SRC = '<母版.docx 路径>'            # 母版副本（原始母版不动）
    OUT = '<母版_占位符版.docx 路径>'    # 输出占位符模板

doc = Document(SRC)

# 绑定到当前 doc 的 helper（find / find_all / next_p / set_text / delete / insert_after / insert_before）
find, find_all, next_p, set_text, delete, insert_after, insert_before = make_helpers(doc)

# ===== 占位符布局（按模板实际段落调整，参考通用模板） =====
# 头部：姓名留死 / 邮箱等单值 {{ }}；模块标题固定不动
# 循环块：{%p for exp in work_exps %} + 条目段落 + {%p endfor %}
#   - 条目段 = 时间+名称行（{{ exp.time }}\t{{ exp.org }}）→ 角色行 → 描述段
#   - 描述段建议单段叙述（≤2 行），循环体内空段落保留作条目间距
# 引导语（"详细描述你的职责范围…"等提示文字）→ delete()

# ---- 示例：教育/工作/项目三组时间行同前缀的处理模式 ----
# time_rows = find_all('开始时间-结束时间')
# assert len(time_rows) == 3, f'期望3个时间行，实际{len(time_rows)}'
# p_edu_time, p_work_time, p_proj_time = time_rows
# set_text(p_edu_time, '{{ edu_time }}\t{{ school }}')
# insert_before(p_work_time, p_work_time, '{%p for exp in work_exps %}')
# set_text(p_work_time, '{{ exp.time }}\t{{ exp.org }}')
# insert_after(p_work_desc, p_work_desc, '{%p endfor %}')

doc.save(OUT)
print('SAVED:', OUT)

# 读回验证：打印全部段落，人工确认占位符完整、循环标签成对
for i, para in enumerate(Document(OUT).paragraphs):
    if para.text.strip():
        print(f'[{i:02d}] {para.text[:60]}')
