#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""campus-recruit-assistant 自检脚本

用途：每次改完技能跑一次，防止规则漂移、引用断裂、结构退化。
用法：python scripts/check-skill.py        （在技能根目录或任意位置均可）
退出码：0 全部通过（允许 WARN）；1 有 FAIL

设计依据（每条检查都对应一次真实事故）：
  - 引用检查：2026-11-05 重编号后出现 5 处死链，靠手工 grep 才发现
  - 重复检查：自我评价字数曾在 8 个文件里各写一份，改一处漏七处
  - 清单检查：曾有 3 份并行自检清单，互有重叠与遗漏
  - TOC 检查：官方要求 >100 行的参考文件带目录
  - 控制台检查：Windows GBK 控制台遇到 ✓/✗ 等非 GBK 字符会 UnicodeEncodeError 崩溃，
    故输出图标一律用 ASCII（[OK]/[WARN]/[FAIL]），并把 stdout 重设为 UTF-8。
"""
import json
import os
import re
import sys

# ---------- 控制台编码兜底：GBK/cp936 控制台也不能崩 ----------
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "SKILL.md")
REF_DIR = os.path.join(ROOT, "references")
PROF_DIR = os.path.join(ROOT, "profiles")
SCR_DIR = os.path.join(ROOT, "scripts")
CFG_EXAMPLE = os.path.join(ROOT, "config.example.json")
EXPORT_README = os.path.join(ROOT, "EXPORT-README.md")
SELF = os.path.basename(os.path.abspath(__file__))

results = []


def add(level, title, detail=""):
    results.append((level, title, detail))


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def list_files(directory, exts):
    if not os.path.isdir(directory):
        return []
    return [os.path.join(directory, f) for f in sorted(os.listdir(directory))
            if f.endswith(exts)]


REF_FILES = list_files(REF_DIR, ".md")
PROF_FILES = list_files(PROF_DIR, ".md")
SCRIPT_FILES = list_files(SCR_DIR, (".py", ".sh"))
MD_TARGETS = [p for p in ([SKILL] + REF_FILES + PROF_FILES) if os.path.exists(p)]
OTHER_TARGETS = [p for p in (CFG_EXAMPLE, EXPORT_README) if os.path.exists(p)]
TEXT_TARGETS = MD_TARGETS + OTHER_TARGETS + SCRIPT_FILES

GATE_DEF = {
    "standard": {"reviewRounds": 2, "passScore": 8},
    "strict": {"reviewRounds": 3, "passScore": 9},
    "off": {"reviewRounds": 0, "passScore": 0},
}

# ---------- 1. frontmatter ----------
txt = read(SKILL)
m = re.match(r"^---\n(.*?)\n---\n", txt, re.S)
if not m:
    add("FAIL", "SKILL.md frontmatter 缺失或格式错误")
else:
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)", fm, re.M)
    desc = re.search(r"^description:\s*(.+)", fm, re.M)
    if not name:
        add("FAIL", "frontmatter 缺 name")
    elif name.group(1) != os.path.basename(ROOT):
        # 分发场景下安装目录可能被平台改名，不算错误，仅提示
        add("WARN", f"name 与目录名不一致: {name.group(1)} != {os.path.basename(ROOT)}",
            "仅影响可读性；如平台要求目录名与 name 一致请改名")
    else:
        add("PASS", f"name = {name.group(1)}")
    if not desc:
        add("FAIL", "frontmatter 缺 description")
    else:
        d = desc.group(1)
        if len(d) > 1024:
            add("FAIL", f"description 超长 {len(d)} > 1024")
        elif len(d) < 60:
            add("WARN", f"description 偏短（{len(d)} 字符），触发可能不准")
        else:
            add("PASS", f"description {len(d)} 字符")

# ---------- 2. SKILL.md 体量 ----------
lines = txt.splitlines()
if len(lines) > 500:
    add("FAIL", f"SKILL.md {len(lines)} 行 > 500 上限")
elif len(lines) > 400:
    add("WARN", f"SKILL.md {len(lines)} 行，接近 500 上限")
else:
    add("PASS", f"SKILL.md {len(lines)} 行")

# ---------- 3. SKILL.md 引用完整性 + 孤儿文件 ----------
refs_used = set(re.findall(r"references/[^\s`|)、，]+\.md", txt))
missing = [r for r in refs_used if not os.path.exists(os.path.join(ROOT, r))]
if missing:
    add("FAIL", "SKILL.md 引用了不存在的文件", "; ".join(sorted(missing)))
else:
    add("PASS", f"SKILL.md 引用的 {len(refs_used)} 个文件全部存在")

actual = ["references/" + os.path.basename(p) for p in REF_FILES]
orphan = [a for a in actual if a not in refs_used]
if orphan:
    add("FAIL", "存在未被 SKILL.md 索引的文件", "; ".join(orphan))
else:
    add("PASS", f"references 共 {len(actual)} 份，无孤儿")

# ---------- 4. 单一事实源（重复定义） ----------
EXCLUSIVE = {
    "140-180": ["16-自我评价.md"],
    "0.6×": ["12-匹配评分.md"],
}
for token, allowed in EXCLUSIVE.items():
    hits = []
    for p in MD_TARGETS:
        if token in read(p):
            hits.append(os.path.basename(p))
    illegal = [h for h in hits if h not in allowed]
    if illegal:
        add("FAIL", f"口径 `{token}` 出现在非权威文件", "; ".join(illegal))
    else:
        add("PASS", f"口径 `{token}` 只在 {len(hits)} 处（授权范围内）")

# ---------- 5. 自检清单唯一性 ----------
CHECKLIST_OWNER = "44-自检清单.md"
RESUME_SCOPE = ("投递前", "结构红线", "头部三行", "ATS")
owners = []
for p in REF_FILES:
    f = os.path.basename(p)
    body = read(p)
    n = len(re.findall(r"^- \[ \]", body, re.M))
    if n >= 8 and any(k in body for k in RESUME_SCOPE):
        owners.append((f, n))
extra = [f for f, _ in owners if f != CHECKLIST_OWNER]
if extra:
    add("FAIL", "存在第二份简历自检清单（应合并进 44）",
        "; ".join(f"{f}({n}项)" for f, n in owners))
else:
    add("PASS", f"简历自检清单唯一：{CHECKLIST_OWNER}")

# ---------- 6. 长文件 TOC ----------
no_toc = []
for p in REF_FILES:
    body = read(p)
    n = len(body.splitlines())
    if n > 100 and not re.search(r"^## (目录|Contents)", body, re.M):
        no_toc.append(f"{os.path.basename(p)}({n}行)")
if no_toc:
    add("WARN", "超过 100 行但无目录", "; ".join(no_toc))
else:
    add("PASS", "所有长文件均带目录")

# ---------- 7. 旧命名残留 ----------
LEGACY_PAT = re.compile(
    r"(?<![\d\-])(02-建库/|03-定制/|04-面试/|05-岗位知识库/|07-调研存档/"
    r"|建库SOP\.md|定制SOP\.md|写作指导方案_校招\.md|输出格式红线\.md"
    r"|输出与命名规范\.md|去AI味清单\.md"
    r"|cloud-sales-career\.md|game-publishing-career\.md"
    r"|cross-domain-tailoring-cases\.md|retail-store-management-career\.md"
    r"|ai-recorded-interview\.md)"
)
stale = []
for p in [SKILL] + REF_FILES:
    if os.path.basename(p) == "01-口径总表.md":
        continue  # 该文件用于记录旧→新对照
    for mm in LEGACY_PAT.finditer(read(p)):
        stale.append(f"{os.path.basename(p)}:{mm.group(1)}")
if stale:
    add("FAIL", "残留旧文件名/旧目录引用", "; ".join(sorted(set(stale))[:8]))
else:
    add("PASS", "无旧命名残留")

# ---------- 8. 路径别名一致性 ----------
ALIASES = ["[档案]", "[JDK]", "[定制]", "[台账]", "[面试]"]
undefined = [a for a in ALIASES if a not in txt]
if undefined:
    add("FAIL", "SKILL.md 未定义别名", "; ".join(undefined))
else:
    add("PASS", f"五个路径别名均已在 SKILL.md 定义（{len(ALIASES)} 个）")

# ---------- 9. 脚本存在性 ----------
mentioned = set(re.findall(r"`([\w\-]+\.(?:py|sh))`", txt))
miss_scr = [s for s in sorted(mentioned) if not os.path.exists(os.path.join(SCR_DIR, s))]
if miss_scr:
    add("FAIL", "SKILL.md 提到的脚本不存在", "; ".join(miss_scr))
else:
    add("PASS", f"SKILL.md 提到的 {len(mentioned)} 个脚本均存在")

# ---------- 10. 交叉引用完整性（references/ 内 + profiles/SKILL 里的 NN-xxx.md） ----------
cross_bad = []
for p in MD_TARGETS:
    me = os.path.basename(p)
    body = read(p)
    for mm in re.finditer(r"`?(\d{2}-[\u4e00-\u9fa5A-Za-z0-9\-]+\.md)`?", body):
        target = mm.group(1)
        if target != me and not os.path.exists(os.path.join(REF_DIR, target)):
            cross_bad.append(f"{me} → {target}")
    for mm in re.finditer(r"references/([A-Za-z0-9_\u4e00-\u9fa5.\-]+\.md)", body):
        target = mm.group(1)
        if not os.path.exists(os.path.join(REF_DIR, target)):
            cross_bad.append(f"{me} → references/{target}（文件不存在）")
if cross_bad:
    add("FAIL", "交叉引用指向不存在的 .md（悬空引用）", "; ".join(sorted(set(cross_bad))[:10]))
else:
    add("PASS", "交叉引用全部有效（含 NN-xxx.md 与 references/ 前缀写法）")

# ---------- 11. 已知错误引用串（旧文件名/错名，必须清零） ----------
STALE_STRINGS = [
    "02_经历挖掘_问题库",      # 应为 11-经历挖掘.md
    "02_数据字典",            # 应为 02_教育背景.md
    "02_JD分析",             # 应为 01_JD库
    "04_复盘规则",            # 应为 23-复盘规则.md
    "docx-tpl-render-and-pdf",  # 应为 docxtpl-render-and-pdf
]
stale_ref = []
for p in TEXT_TARGETS:
    base = os.path.basename(p)
    if base == SELF:
        continue
    body = read(p)
    for s in STALE_STRINGS:
        if s in body:
            stale_ref.append(f"{base}:{s}")
if stale_ref:
    add("FAIL", "残留旧/错引用串（悬空或错名）", "; ".join(sorted(set(stale_ref))[:10]))
else:
    add("PASS", "无旧/错引用串（02_数据字典/02_JD分析/04_复盘规则 等均已清除）")

# ---------- 12. 可分享性：隐私/PII 红线 ----------
# 检测器自身豁免：脚本里必须写出这些模式与黑名单字符串才能检测，故跳过 SELF。
GEN_PAT = [
    (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "手机号"),
    (re.compile(r"[\w.+-]+@(?:qq|163|126|gmail|foxmail|sina)\.com", re.I), "个人邮箱"),
    # 通用：任意用户名的主目录（占位符 <you>/<user> 因 < > 不在字符类内而自动放行；
    # 纯点省略号如 /home/... 视为占位放行）
    (re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+([A-Za-z0-9._-]+)"), "Windows 用户目录"),
    (re.compile(r"/(?:Users|home)/([A-Za-z0-9._-]+)"), "Unix/Mac 用户目录"),
]
# CANONICAL §4 规定的必清零串（大小写不敏感比对）
FORBIDDEN_PII = ["33887", "ai_work", "腾讯云", "CSIG", "cloud.tencent.com",
                 "nowcoder", "WorkBuddy", "200.56", "5959"]

deny = []
cfg_file = os.path.join(ROOT, "config.json")
if os.path.exists(cfg_file):
    try:
        deny = json.load(open(cfg_file, encoding="utf-8")).get("piiDenylist") or []
    except Exception:
        deny = []

pii_hits = []
for p in TEXT_TARGETS:
    base = os.path.basename(p)
    if base == SELF:
        continue
    body = read(p)
    low = body.lower()
    for pat, label in GEN_PAT:
        for mm in pat.finditer(body):
            name = mm.group(1) if mm.groups() else None
            if name is not None and set(name) <= {"."}:
                continue  # /home/... 之类省略号占位
            pii_hits.append(f"{base}:{label}({mm.group(0)[:40]})")
            break
    for k in FORBIDDEN_PII:
        if k.lower() in low:
            pii_hits.append(f"{base}:禁止串[{k}]")
    for k in deny:
        if k and k in body:
            pii_hits.append(f"{base}:真名[{k}]")
            break
    for line in body.splitlines():
        if "小米" in line and not any(w in line for w in ("硬核联盟", "OPPO", "vivo")):
            pii_hits.append(f"{base}:小米(非行业常识行)")
            break

scope = f"通用规则 + 私有黑名单({len(deny)} 项)" if deny else "通用规则（无 config.json 黑名单）"
if pii_hits:
    add("FAIL", f"技能内含真实身份/雇主/目标公司（范围：md+profiles+scripts+配置模板；{scope}）",
        "; ".join(sorted(set(pii_hits))[:10]))
else:
    add("PASS", f"无真实身份与公司名（{scope}）")

# ---------- 13. 绝对路径红线（不写死本机路径） ----------
# 通用盘符绝对路径；含 < > 占位或「某」示例者放行。检测器自身豁免。
# (?<![A-Za-z0-9]) 防止把 http://、file:// 里的 "p:"/"e:" 误判为盘符。
ABS_PAT = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s`\"'|,;{}]+")
abs_hits = []
for p in TEXT_TARGETS:
    base = os.path.basename(p)
    if base == SELF:
        continue
    for mm in ABS_PAT.finditer(read(p)):
        seg = mm.group(0)
        if any(ch in seg for ch in "<>") or "某" in seg or "..." in seg or "xxxx" in seg.lower():
            continue
        if seg in ("C:/", "C:\\", "D:/", "D:\\"):
            continue
        abs_hits.append(f"{base}:{seg[:60]}")
if abs_hits:
    add("FAIL", "技能内写死了本机绝对路径（含 scripts）", "; ".join(sorted(set(abs_hits))[:10]))
else:
    add("PASS", "无本机绝对路径（md+profiles+scripts+配置模板），路径经 config.json 解析")

# ---------- 14. 一致性：字号只允许 24/12/10.5/9pt ----------
FONT_ALLOWED = {24.0, 12.0, 10.5, 9.0}
FONT_FORBIDDEN = {25.0, 13.0, 11.0, 10.0}
font_bad, font_unknown = [], []
for p in MD_TARGETS:
    base = os.path.basename(p)
    for mm in re.finditer(r"(\d+(?:\.\d+)?)\s*pt", read(p)):
        v = float(mm.group(1))
        if v > 40:
            continue  # 841.9pt 等是 A4 版面尺寸，不是字号
        if v in FONT_FORBIDDEN:
            font_bad.append(f"{base}:{mm.group(0)}")
        elif v not in FONT_ALLOWED:
            font_unknown.append(f"{base}:{mm.group(0)}")
if font_bad:
    add("FAIL", "残留旧字号（只允许 24/12/10.5/9pt，禁 25/13/11/10pt）", "; ".join(sorted(set(font_bad))))
elif font_unknown:
    add("WARN", "出现不在白名单的字号", "; ".join(sorted(set(font_unknown))))
else:
    add("PASS", "字号仅 24/12/10.5/9pt，无旧字号残留")

# ---------- 15. 一致性：页数「1-2 页」只在 campus-tech ----------
page_bad = []
for p in MD_TARGETS:
    base = os.path.basename(p)
    if base == "campus-tech.md":
        continue  # 技术档本身就是 1-2 页
    for ln in read(p).splitlines():
        if not re.search(r"1\s*[-–—]\s*2\s*页", ln):
            continue
        # 允许「campus-tech/技术岗 1-2 页」这类正确归属；禁止把默认档写成 1-2 页
        if "campus-tech" in ln or "技术岗" in ln:
            continue
        page_bad.append(base)
if page_bad:
    add("FAIL", "「1-2 页」只允许出现在 campus-tech；其余应为 1 页",
        "; ".join(sorted(set(page_bad))))
else:
    add("PASS", "「1-2 页」仅在 campus-tech 出现，其余档均 1 页")

# ---------- 16. 一致性：复审轮数（standard 2 / strict 3，禁「1 轮」「strict 2 轮」） ----------
round_bad = []
for p in MD_TARGETS:
    base = os.path.basename(p)
    for ln in read(p).splitlines():
        if re.search(r"strict\s*2\s*轮", ln, re.I):
            round_bad.append(f"{base}:strict 2轮")
        for mm in re.finditer(r"(?<!\d)1\s*轮", ln):
            pre = ln[max(0, mm.start() - 2):mm.start()]
            if "第" in pre:
                continue
            round_bad.append(f"{base}:1轮")
            break
review_file = os.path.join(REF_DIR, "46-质检与复审.md")
if os.path.exists(review_file):
    body46 = read(review_file)
    has23 = bool(re.search(r"轮数[^\n]*2[^\n]*3", body46)) or (
        re.search(r"2\s*轮", body46) and re.search(r"3\s*轮", body46))
    if not has23:
        round_bad.append("46-质检与复审.md:缺 2 轮/3 轮 口径")
if round_bad:
    add("FAIL", "复审轮数口径错误（应 standard 2 轮 / strict 3 轮）", "; ".join(sorted(set(round_bad))[:8]))
else:
    add("PASS", "复审轮数口径正确（standard 2 轮 / strict 3 轮，无「1 轮」「strict 2 轮」）")

# ---------- 17. 一致性：PDF 投递命名 ----------
naming_bad = []
for p in TEXT_TARGETS:
    base = os.path.basename(p)
    if base == SELF:
        continue
    if "姓名_学校_专业_岗位.pdf" in read(p):
        naming_bad.append(f"{base}:旧PDF命名")
for f in ("43-输出与台账.md", "44-自检清单.md"):
    fp = os.path.join(REF_DIR, f)
    if not os.path.exists(fp):
        naming_bad.append(f"{f}缺失")
    elif "姓名-岗位-届别.pdf" not in read(fp):
        naming_bad.append(f"{f}:缺正确PDF命名")
if naming_bad:
    add("FAIL", "PDF 命名口径错误（应 姓名-岗位-届别.pdf，禁 姓名_学校_专业_岗位.pdf）",
        "; ".join(sorted(set(naming_bad))[:8]))
else:
    add("PASS", "PDF 命名口径正确（43/44 均含 姓名-岗位-届别.pdf，无旧命名）")

# ---------- 18. 配置模板与工作流档 ----------
if not os.path.exists(CFG_EXAMPLE):
    add("FAIL", "缺 config.example.json（首次使用无法引导）")
else:
    try:
        c = json.load(open(CFG_EXAMPLE, encoding="utf-8"))
        need = ["schemaVersion", "dataRoot", "profile"]
        miss = [k for k in need if k not in c]
        if miss:
            add("FAIL", "config.example.json 缺必填字段: " + ", ".join(miss))
        else:
            gate = c.get("qualityGate", "standard")
            q = (c.get("overrides") or {}).get("quality") or {}
            exp = GATE_DEF.get(gate)
            if exp and (q.get("reviewRounds") != exp["reviewRounds"]
                        or q.get("passScore") != exp["passScore"]):
                add("FAIL",
                    "config.example.json 质量门与 GATES 不一致（旧「1 轮」残留）",
                    f"gate={gate} 实际={q} 期望={exp}")
            else:
                add("PASS", "config.example.json 结构完整且质量门与 GATES 一致")
    except Exception as e:
        add("FAIL", f"config.example.json 不是合法 JSON: {e}")

expect = ["campus-cn.md", "campus-tech.md", "intern-cn.md"]
if not os.path.isdir(PROF_DIR):
    add("FAIL", "缺 profiles/ 目录（无法切换工作流）")
else:
    got = [os.path.basename(p) for p in PROF_FILES]
    miss = [f for f in expect if f not in got]
    if miss:
        add("FAIL", "工作流档缺失", ", ".join(miss))
    else:
        no_ptr = [f for f in expect
                  if "16-自我评价" not in read(os.path.join(PROF_DIR, f))]
        if no_ptr:
            add("WARN", "工作流档未指向自我评价权威文件", ", ".join(no_ptr))
        else:
            add("PASS", f"工作流档齐全（{len(got)} 档），且均正确指向字数权威")

# ---------- 19. SKILL.md 必须引导首次使用与质检 ----------
must_index = ["references/00-首次使用与配置.md", "references/46-质检与复审.md"]
miss_idx = [m for m in must_index if m not in txt]
if miss_idx:
    add("FAIL", "SKILL.md 未索引关键文件", ", ".join(miss_idx))
else:
    add("PASS", "SKILL.md 已索引初始化与质检文件")

# ---------- 输出 ----------
LABEL = {"PASS": "OK", "WARN": "WARN", "FAIL": "FAIL"}
order = {"FAIL": 0, "WARN": 1, "PASS": 2}
print("=" * 66)
print("campus-recruit-assistant  自检")
print("=" * 66)
for level, title, detail in sorted(results, key=lambda r: order[r[0]]):
    print(f"[{LABEL[level]}] {title}")
    if detail:
        print(f"        -> {detail}")
fails = sum(1 for r in results if r[0] == "FAIL")
warns = sum(1 for r in results if r[0] == "WARN")
passes = len(results) - fails - warns
print("-" * 66)
print(f"结果: {passes} PASS / {warns} WARN / {fails} FAIL")
print("=" * 66)
sys.exit(1 if fails else 0)
