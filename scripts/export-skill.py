# -*- coding: utf-8 -*-
"""把本技能导出为「可分发副本」到公共目录。

设计原则
--------
1. 技能源目录（本技能的安装处）是唯一正本，规则改动只在源里做。
2. 公共目录里的副本是**只读发布物**：不带真实身份、不带真名黑名单、不带私有 config。
3. 每次导出自动跑两检：结构自检（副本内 check-skill.py）+ 真名扫描（用源 config 的黑名单）。
   任何一项不过就整体失败，不留半成品。

用法
----
    python scripts/export-skill.py                       # 默认导出到 ~/.agents/skills/
    python scripts/export-skill.py "D:/某处/skills"       # 指定目标父目录
    python scripts/export-skill.py --dry-run             # 只看会做什么
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_NAME = os.path.basename(ROOT)
DEFAULT_DEST_PARENT = os.path.expanduser("~/.agents/skills")

# 不随副本分发的私有文件
PRIVATE = {"config.json", ".DS_Store"}
# _work 是内部工作区（CANONICAL/研究摘要，含真名与绝对路径），绝不可随副本分发
EXCLUDE_DIR = {"__pycache__", ".git", ".pytest_cache", "_work"}
# 源 config 里只透传到副本的非敏感字段（dataRoot 刻意不透传，见 build_public_config）
PUBLIC_CFG_KEYS = ("schemaVersion", "profile", "qualityGate", "overrides")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def collect(src):
    """收集要复制的文件（相对路径），跳过私有与缓存"""
    out = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIR]
        for f in files:
            if f in PRIVATE or f.endswith((".pyc", ".bak", ".tmp")):
                continue
            out.append(os.path.relpath(os.path.join(root, f), src))
    return sorted(out)


def build_public_config(src_cfg_path):
    """生成副本用的 config：去掉 identity（真名）与 piiDenylist（真名清单）"""
    if not os.path.exists(src_cfg_path):
        return None
    src = json.load(open(src_cfg_path, encoding="utf-8"))
    out = {k: src[k] for k in PUBLIC_CFG_KEYS if k in src}
    # dataRoot 绝不随副本泄露真实本机路径：置空占位，首次使用由 init-skill.py 重新填
    out["dataRoot"] = ""
    out["setupDate"] = "YYYY-MM-DD"
    out["identity"] = {"name": "", "school": "", "major": "", "gradYear": ""}
    out["_note"] = ("本文件由 export-skill.py 生成；dataRoot 已置空、identity 已清空，"
                    "真名黑名单不随副本分发")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dest_parent", nargs="?", default=DEFAULT_DEST_PARENT,
                    help=f"目标父目录，默认 {DEFAULT_DEST_PARENT}")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    dest = os.path.normpath(os.path.join(args.dest_parent, SKILL_NAME))
    files = collect(ROOT)

    print(f"源     : {os.path.normpath(ROOT)}")
    print(f"目标   : {dest}")
    print(f"文件数 : {len(files)}（已排除 config.json / 缓存）")
    if args.dry_run:
        for f in files:
            print("   " + f)
        print("\n[dry-run] 未写入任何文件")
        return 0

    # 目标已存在 → 先备份再覆盖，避免误删用户改动
    if os.path.exists(dest):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{dest}.bak-{stamp}"
        shutil.move(dest, bak)
        print(f"旧副本已备份: {bak}")

    os.makedirs(dest, exist_ok=True)
    for rel in files:
        s = os.path.join(ROOT, rel)
        d = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True) if os.path.dirname(d) else None
        shutil.copy2(s, d)

    # 写入干净的 config（让副本开箱可用，又不含任何真名）
    cfg = build_public_config(os.path.join(ROOT, "config.json"))
    if cfg:
        with open(os.path.join(dest, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print("已生成脱敏 config.json（identity 清空、无真名黑名单）")

    # 加一份只读声明，防止在副本里改规则导致漂移
    readme = f"""# 这是发布副本，不要在里直接改规则

- **正本**：技能源目录（本副本的发布来源；不要在副本里改规则）。
- **导出时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}
- 规则改动请在正本改，改完重新运行 `scripts/export-skill.py` 覆盖本副本。
- 本副本不含真实身份、不含真名黑名单、不含真实数据根目录；`check-skill.py` 的隐私项在此只会跑通用规则（手机号/邮箱/用户名），不会比对真名。
"""
    with open(os.path.join(dest, "EXPORT-README.md"), "w", encoding="utf-8") as f:
        f.write(readme)

    # ---------- 校验 1：副本内自检 ----------
    # 用 subprocess.call 让子进程自检报告直接流到控制台（不捕获管道：某些沙箱/
    # 受限环境禁止创建管道会报 WinError 5）。是否通过只看子进程 returncode：
    # 0=PASS，任何非 0（自检 FAIL / 崩溃 / 语法错）都判本次导出失败。
    print("\n[1/2] 副本结构自检")
    try:
        rc = subprocess.call([sys.executable, "scripts/check-skill.py"], cwd=dest)
    except Exception as e:
        print(f"   [FAIL] 无法运行 check-skill.py: {e}")
        rc = -1
    check_ok = (rc == 0)
    if not check_ok:
        print(f"   [FAIL] check-skill.py 退出码 {rc}（副本结构自检未通过）")

    # ---------- 校验 2：真名扫描（用源黑名单，源无黑名单则跳过）----------
    print("[2/2] 真名扫描")
    deny, hits = [], []
    src_cfg = os.path.join(ROOT, "config.json")
    if os.path.exists(src_cfg):
        deny = json.load(open(src_cfg, encoding="utf-8")).get("piiDenylist") or []
    if deny:
        for root2, _, fs in os.walk(dest):
            for f in fs:
                p = os.path.join(root2, f)
                try:
                    body = read(p)
                except Exception:
                    continue
                for k in deny:
                    if k and k in body:
                        hits.append(f"{os.path.relpath(p, dest)}:{k}")
    if hits:
        print("   [FAIL] 副本含真实信息：" + "; ".join(sorted(set(hits))[:8]))
    elif deny:
        print(f"   [OK] {len(deny)} 项黑名单全扫零命中")
    else:
        print("   [WARN] 源 config 无黑名单，跳过（无法验证）")

    ok = check_ok and (not hits)
    print("\n" + ("导出成功 [OK]" if ok else "导出有问题 [FAIL] 请查看上面输出"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
