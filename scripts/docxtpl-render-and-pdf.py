# -*- coding: utf-8 -*-
"""docxtpl 渲染 + 跨平台转 PDF（每次投递只改 context）。

链路：占位符模板 → context 字典 → render() → docx → 转 PDF → 页数校验

隐私警告（2026-08-18 修订）：
- 本脚本 context 示例已全部脱敏为占位符（<手机号>/<邮箱>/<学校名> 等）。
- 运行前必须从母版实际数据覆盖，严禁把占位符或历史 PII 投出。
- 母版含真实个人信息，本技能包分享/上传前务必确认无硬编码 PII
  （历史事故：曾硬编码真实手机/邮箱/学校，2026-08-18 已清除，privacy scan 为准）。

跨平台 PDF 转换策略（按可用性自动降级）：
1) 首选 LibreOffice / soffice headless（Windows/macOS/Linux 均可用，跨平台、不依赖 COM）：
   soffice --headless --convert-to pdf --outdir <dir> <docx>
2) 可选分支 WPS COM（仅 Windows）：若本机装了 WPS 且未装 LibreOffice，可用
   --engine wps 走 `Kwps.Application`（注意是 Kwps，不是 wps，后者报「无效的类字符串」）；
   ExportAsFixedFormat 第二参 17 = wdExportFormatPDF。失败时给清晰中文报错。
3) pymupdf 仅用于读取转换后的 PDF 做页数校验（PyMuPDF 不能把 docx 转成 PDF）；
   调用处 try/except，未安装提示 `pip install pymupdf`。

用法：
  python docxtpl-render-and-pdf.py <模板.docx> --context context.json \
      [-o out.docx] [--pdf out.pdf] [--engine auto|libreoffice|wps|none] [--no-pdf]

context.json 为 JSON 对象（UTF-8）；不传 --context 时打印骨架示例并退出，避免误投占位符。
"""
import sys

# 强制 UTF-8 输出，避免 Windows 控制台默认 GBK 造成中文乱码/UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import argparse
import json
import os
import shutil
import subprocess

from docxtpl import DocxTemplate

# 占位符示例骨架（脱敏；禁止直接投递）
CONTEXT_SKELETON = {
    'position': '<求职意向，如：商品管理岗>',
    'phone': '<手机号>',
    'email': '<求职邮箱>',
    'gender': '<男/女>',
    'age': '<年龄>',
    'city': '<意向城市>',
    'salary_expect': '<薪资区间，如：面议 / X-Yk/月>',
    'job_type': '全职（校招）',
    'edu_time': '<入学.09-毕业.06>',
    'school': '<学校名>',
    'edu_major': '<专业名>',
    'edu_degree': '<本科/硕士>',
    'work_exps': [
        # 时间倒序；desc 单段叙述 ≤2 行（约 55-70 字），超了 1 页压不住
        {'time': '<起止时间>', 'org': '<公司>',
         'role': '<岗位>', 'industry': '<行业>', 'salary': '实习',
         'desc': '<1-2 行叙述式描述：动作+方法+量化结果>'},
    ],
    'projects': [
        {'time': '<时间>', 'name': '<项目名>', 'role': '<角色>',
         'desc': '<1-2 行叙述式描述>'},
    ],
    'self_eval': '<单行自我评价：差异化价值主张，≤100 字>',
}


def _find_soffice():
    """探测 LibreOffice soffice 可执行文件（跨平台，不写死用户盘符/用户名）。"""
    for name in ('soffice', 'soffice.exe', 'libreoffice'):
        p = shutil.which(name)
        if p:
            return p
    candidates = []
    # Windows：从环境变量拼标准安装目录，避免硬编码盘符
    for env in ('ProgramFiles', 'ProgramFiles(x86)'):
        root = os.environ.get(env)
        if root:
            candidates.append(os.path.join(root, 'LibreOffice', 'program', 'soffice.exe'))
    # macOS / Linux 常见位置
    candidates += [
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
        '/usr/bin/soffice', '/usr/local/bin/soffice',
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def convert_with_libreoffice(docx_path, out_pdf):
    """用 LibreOffice headless 转 PDF（跨平台）。成功返回 True。"""
    soffice = _find_soffice()
    if not soffice:
        return False
    outdir = os.path.dirname(os.path.abspath(out_pdf)) or '.'
    try:
        subprocess.run(
            [soffice, '--headless', '--convert-to', 'pdf', '--outdir', outdir, docx_path],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180,
        )
    except Exception as e:
        print('⚠️ LibreOffice 转换失败：%s' % e, file=sys.stderr)
        return False
    produced = os.path.join(outdir,
                            os.path.splitext(os.path.basename(docx_path))[0] + '.pdf')
    if not os.path.isfile(produced):
        return False
    if os.path.abspath(produced) != os.path.abspath(out_pdf):
        shutil.move(produced, out_pdf)
    return True


def convert_with_wps(docx_path, out_pdf):
    """可选分支：WPS COM（仅 Windows）。失败给清晰中文报错并返回 False。"""
    try:
        import win32com.client  # noqa: F401  仅 Windows 可用
    except ImportError:
        print('⚠️ 未安装 pywin32，无法使用 WPS COM 分支（Windows 可 pip install pywin32）。',
              file=sys.stderr)
        return False
    try:
        app = win32com.client.Dispatch('Kwps.Application')  # 注意是 Kwps，不是 wps
    except Exception as e:
        print('⚠️ 启动 WPS COM 失败（类字符串应使用 Kwps.Application）：%s' % e,
              file=sys.stderr)
        return False
    doc = None
    try:
        app.Visible = False
        doc = app.Documents.Open(os.path.abspath(docx_path), ReadOnly=True)
        doc.ExportAsFixedFormat(os.path.abspath(out_pdf), 17)  # 17 = wdExportFormatPDF
        return True
    except Exception as e:
        print('⚠️ WPS 导出 PDF 失败：%s' % e, file=sys.stderr)
        return False
    finally:
        try:
            if doc is not None:
                doc.Close(False)
        except Exception:
            pass
        try:
            app.Quit()
        except Exception:
            pass


def convert_pdf(docx_path, out_pdf, engine='auto'):
    """按引擎顺序尝试转 PDF。成功 True；全部失败给清晰报错并返回 False。"""
    if engine == 'none':
        return False
    order = {
        'auto': ['libreoffice', 'wps'],
        'libreoffice': ['libreoffice'],
        'wps': ['wps'],
    }.get(engine, ['libreoffice', 'wps'])
    for eng in order:
        if eng == 'libreoffice':
            if convert_with_libreoffice(docx_path, out_pdf):
                return True
        elif eng == 'wps' and sys.platform.startswith('win'):
            if convert_with_wps(docx_path, out_pdf):
                return True
    print('❌ 未能把 docx 转为 PDF：请安装 LibreOffice（跨平台），'
          '或在 Windows 装 WPS+pywin32 后用 --engine wps。', file=sys.stderr)
    return False


def check_pages(pdf_path):
    """pymupdf 读页数（1 页铁律校验）；未安装则提示并跳过。"""
    try:
        try:
            import pymupdf  # PyMuPDF >= 1.24
        except ImportError:
            import fitz as pymupdf  # 旧版包名兼容
    except ImportError:
        print('⚠️ 未安装 pymupdf，跳过页数校验（pip install pymupdf）。', file=sys.stderr)
        return
    try:
        d = pymupdf.open(pdf_path)
    except Exception as e:
        print('⚠️ 打开 PDF 失败，跳过页数校验：%s' % e, file=sys.stderr)
        return
    n = len(d)
    print('页数:', n)
    if n > 1:
        try:
            tail = [l[:30] for l in d[-1].get_text().split('\n') if l.strip()][:3]
        except Exception:
            tail = []
        print('WARN: 超页! 末页内容:', tail)
        print('处理：压缩 desc（删括号解释/删并列示例/数字保留），勿动模板')
    d.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description='docxtpl 渲染 + 跨平台转 PDF')
    ap.add_argument('template', nargs='?', help='占位符模板 .docx 路径')
    ap.add_argument('--context', help='context JSON 文件（UTF-8）；缺省则打印骨架')
    ap.add_argument('-o', '--out-docx', help='输出 docx 路径（默认模板名 + _filled.docx）')
    ap.add_argument('--pdf', help='输出 PDF 路径（默认与 docx 同名 .pdf）')
    ap.add_argument('--engine', choices=['auto', 'libreoffice', 'wps', 'none'], default='auto')
    ap.add_argument('--no-pdf', action='store_true', help='只渲染 docx，不转 PDF')
    args = ap.parse_args(argv)

    if not args.template:
        ap.print_help()
        return 2
    if not os.path.isfile(args.template):
        print('❌ 模板不存在：%s' % args.template, file=sys.stderr)
        return 2

    base = os.path.splitext(os.path.abspath(args.template))[0]
    out_docx = args.out_docx or (base + '_filled.docx')
    out_pdf = args.pdf or (os.path.splitext(out_docx)[0] + '.pdf')

    if not args.context:
        print('未提供 --context，下面是 context 骨架（脱敏占位，禁止直接投递）：')
        print(json.dumps(CONTEXT_SKELETON, ensure_ascii=False, indent=2))
        return 1

    with open(args.context, 'r', encoding='utf-8') as f:
        context = json.load(f)

    tpl = DocxTemplate(args.template)
    tpl.render(context)
    tpl.save(out_docx)
    print('DOCX SAVED:', out_docx)

    if args.no_pdf:
        return 0
    if convert_pdf(out_docx, out_pdf, args.engine):
        print('PDF SAVED:', out_pdf, os.path.getsize(out_pdf))
        check_pages(out_pdf)
    return 0


if __name__ == '__main__':
    sys.exit(main())
