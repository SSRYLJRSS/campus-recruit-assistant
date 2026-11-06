#!/usr/bin/env python3
"""campus-recruit-assistant 初始化 / 配置检查

用途：
  1) 检查配置状态      python scripts/init-skill.py --check
  2) 初始化（建目录+写配置）
     python scripts/init-skill.py --data-root "<数据目录>" --profile campus-cn --gate standard
  可选：--name --school --major --grad-year / --force 覆盖已有配置 / --json 机器可读输出

设计说明：
  - 缺配置是正常的首次状态，--check 在缺配置时退出码 0（不当作错误）。
  - 路径一律用正斜杠存储，Windows 与 macOS/Linux 通用。
  - 只写稳定信息；在投岗位、简历版本等易变状态属于数据层，不进 config。
"""
import argparse
import json
import os
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")

PROFILES = ("campus-cn", "campus-tech", "intern-cn")
GATES = {"standard": {"reviewRounds": 2, "passScore": 8},
         "strict": {"reviewRounds": 3, "passScore": 9},
         "off": {"reviewRounds": 0, "passScore": 0}}

SUBDIRS = [
    "00_档案/模板", "00_档案/原始材料", "00_档案/挖掘记录", "00_档案/snapshots", "00_档案/归档",
    "01_JD库", "02_定制简历", "03_投递台账",
    "04_面试/情报", "04_面试/题库", "04_面试/讲稿", "04_面试/记录",
]


def norm(p):
    return p.replace("\\", "/").rstrip("/")


def check():
    if not os.path.exists(CONFIG_PATH):
        return {"ready": False, "reason": "config.json 不存在（首次使用，属正常状态）",
                "next": "按 references/00-首次使用与配置.md 询问四个问题后重新运行本脚本"}
    try:
        cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"ready": False, "reason": f"config.json 解析失败: {e}", "next": "修正 JSON 或重跑初始化"}
    problems = []
    root = cfg.get("dataRoot")
    if not root:
        problems.append("缺 dataRoot")
    elif not os.path.isdir(root):
        problems.append(f"dataRoot 不存在或不可访问: {root}")
    else:
        missing = [d for d in SUBDIRS if not os.path.isdir(os.path.join(root, d.replace("/", os.sep)))]
        if missing:
            problems.append(f"目录骨架缺失 {len(missing)} 项: " + ", ".join(missing[:4]))
        else:
            try:
                probe = os.path.join(root, ".write_probe")
                with open(probe, "w", encoding="utf-8") as _f:
                    _f.write("x")
                os.remove(probe)
            except OSError as e:
                problems.append(f"dataRoot 不可写: {root} ({e})")
    if cfg.get("profile") not in PROFILES:
        problems.append(f"profile 非法: {cfg.get('profile')}")
    if problems:
        return {"ready": False, "reason": "；".join(problems), "next": "重跑初始化补齐", "config": cfg}
    return {"ready": True, "config": cfg}


def init(args):
    if os.path.exists(CONFIG_PATH) and not args.force:
        print(f"配置已存在：{CONFIG_PATH}\n如需重建请加 --force", file=sys.stderr)
        return 2

    root = norm(args.data_root)
    if not os.path.isabs(root):
        print(f"错误：--data-root 必须是绝对路径，收到：{args.data_root}\n"
              f"例：python scripts/init-skill.py --data-root \"<数据目录绝对路径>\" "
              f"--profile campus-cn --gate standard", file=sys.stderr)
        return 2
    created, existing = [], []
    for d in SUBDIRS:
        full = os.path.join(root, d.replace("/", os.sep))
        if os.path.isdir(full):
            existing.append(d)
        else:
            try:
                os.makedirs(full, exist_ok=True)
            except OSError as e:
                print(f"错误：无法创建目录 {full}：{e}\n请换一个可写的绝对路径。", file=sys.stderr)
                return 2
            created.append(d)

    gate = GATES[args.gate]
    # 自我评价字数按 CANONICAL §2-4：默认/校招 140-180，intern 120-160
    self_eval = [120, 160] if args.profile == "intern-cn" else [140, 180]
    cfg = {
        "schemaVersion": 1,
        "setupDate": date.today().isoformat(),
        "dataRoot": root,
        "profile": args.profile,
        "qualityGate": args.gate,
        "identity": {
            "name": args.name or "",
            "school": args.school or "",
            "major": args.major or "",
            "gradYear": args.grad_year or "",
        },
        "overrides": {
            "resume": {
                "selfEvalRange": self_eval,
                "maxPages": 2 if args.profile == "campus-tech" else 1,
                "noObjective": args.profile == "campus-cn",
                "noSkillSection": args.profile != "campus-tech",
                "noPhoto": True,
            },
            "quality": gate,
        },
    }
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as e:
        print(f"错误：无法写入配置文件 {CONFIG_PATH}：{e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"ok": True, "config": cfg, "created": created,
                          "existing": existing}, ensure_ascii=False, indent=2))
    else:
        print("初始化完成")
        print(f"  数据目录 : {root}")
        print(f"  工作流档 : {args.profile}")
        print(f"  质量门   : {args.gate}  复审 {gate['reviewRounds']} 轮 / 门槛 {gate['passScore']}/10")
        print(f"  新建目录 : {len(created)} 项" + (f"，已存在 {len(existing)} 项" if existing else ""))
        if existing:
            print("  提示：检测到已有目录骨架，按“接续现有库”处理，未覆盖任何已有文件")
        print(f"  配置文件 : {CONFIG_PATH}")
        print("\n下一步：把 config 摘要回显给用户确认，然后继续他原本要办的事。")
    return 0


def main():
    ap = argparse.ArgumentParser(description="campus-recruit-assistant 初始化 / 配置检查")
    ap.add_argument("--check", action="store_true", help="检查配置状态")
    ap.add_argument("--data-root", help="数据根目录（绝对路径）")
    ap.add_argument("--profile", default="campus-cn", choices=PROFILES)
    ap.add_argument("--gate", default="standard", choices=tuple(GATES))
    ap.add_argument("--name"), ap.add_argument("--school")
    ap.add_argument("--major"), ap.add_argument("--grad-year")
    ap.add_argument("--force", action="store_true", help="覆盖已有 config.json")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    if args.check:
        res = check()
        print(json.dumps(res, ensure_ascii=False, indent=2) if args.json
              else ("已就绪" if res["ready"] else f"未就绪：{res['reason']}\n→ {res['next']}"))
        return 0

    if not args.data_root:
        print("缺少 --data-root。请先问用户数据放哪，再带上参数重跑。", file=sys.stderr)
        return 2
    return init(args)


if __name__ == "__main__":
    sys.exit(main())
