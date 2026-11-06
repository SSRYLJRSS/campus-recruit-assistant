# 校招助手

> 把校招求职拆成一条能反复复用的流水线：建简历库 → 按 JD 定制 → 投递台账 → 面试备战 → 模拟面试 → 复盘回写。

[![license](https://img.shields.io/badge/license-MIT-3da639.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-3776ab.svg)]()
[![format](https://img.shields.io/badge/agent%20skill-SKILL.md-6b4fbb.svg)](SKILL.md)

一个面向校招 / 春招 / 实习投递的 Agent Skill。你在对话框里说人话，它在背后按固定流程办事。真正值钱的不是"生成"，而是把你的真实经历整理成一份能反复复用的母版。

## 它解决的问题

用 AI 改简历，最常见的三个坑：

- **编经历**。模型顺手补两段你没做过的事，面试一问就露馅。
- **每次从零开始**。换个 JD 就重写一遍，之前的版本和投递记录全散在聊天记录里。
- **自己给自己打分**。写出那句话的思路，和审它挑错的思路是同一条，挑不出问题。

这个 Skill 换了做法：先把真实经历沉淀成母版库，之后每投一个岗位只做"挑选 + 重构 + 强调"；新增事实先回写母版再动简历；写完必须换一个干净上下文的人来挑刺。流程比灵感重要。

## 一套母版，六个阶段

| 阶段 | 干什么 | 产出 |
|---|---|---|
| S0 建库 | 盘点经历，模板化录入母版，每条标来源与置信度 | `00_档案/` |
| S1 JD 匹配 | 把 JD 拆成必须/加分项，按权重打分，给区间和投递决策 | `01_JD库/` |
| S2 定制简历 | 六步定制；改完过 G1 自检 + G2 换视角复审 | `02_定制简历/` |
| S3 投递台账 | 每投一家记一行，状态跟简历后缀对齐 | `03_投递台账/` |
| S4 面试备战 | 扒公司/岗位情报（带 URL、日期、置信度），按 8 模块出题 | `04_面试/情报`、`题库` |
| S5 模拟复盘 | 四档人设扮演，逐轮实录，5 维复盘 + 薄弱点归因 | `04_面试/记录` |
| S6 回写档案 | 复盘出的新事实，经你确认后写回母版并留痕 | `变更记录.md` |

每个阶段都有可审计的"完成判据"，不满足就不进下一阶段；从哪开始靠产物存在性判断，不靠你用什么措辞。

## 三套工作流档

同一套流程，三种默认口径，切换只改一个 `profile`：

- `campus-cn`（默认）：校招中文通用岗。单页、无求职意向、无独立技能段。
- `campus-tech`：技术岗。允许 1–2 页、独立技能段，项目排在实习前。
- `intern-cn`：实习。把课程/校园项目当迷你实习来写，单页。

规则优先级固定为：**用户当场指令 > 个人 overrides > profile > references 默认值**。两份说法打架时查 `references/01-口径总表.md`——它指定每类知识只有一个权威文件，查不到就来问你，不自行拍板。

## 安装

这是一个标准的 Agent Skill（一个带 `SKILL.md` 的目录），不用编译、不用构建：

```bash
git clone https://github.com/SSRYLJRSS/campus-recruit-assistant.git
```

把它放到 Agent 读取技能的位置之一，例如：

```text
~/.agents/skills/campus-recruit-assistant
~/.claude/skills/campus-recruit-assistant
```

第一次打开时会引导你配三件事（数据存哪、走哪条档、质量门多严）；配完直接进入你要办的事，不会停在"配置好了"。

## 快速开始

直接用日常说法提要求，不用记命令：

```text
帮我建简历库，我先把经历都倒给你
这段 JD 帮我分析一下，和我简历匹配打几分：<粘贴 JD>
按这个 JD 定制一页简历
模拟面试，用压力面人设
我投了 XX 公司，岗位是后端开发
```

## 目录结构

```text
.
├── SKILL.md                # 中央路由：铁律、状态机、红线、路由表
├── config.example.json     # 配置模板（首次使用会问你要不要改）
├── profiles/               # 三套工作流档：campus-cn / campus-tech / intern-cn
├── references/             # 28 篇按主题拆开的参考，按需加载
│   ├── 00-首次使用与配置.md
│   ├── 01-口径总表.md       # 每类知识的唯一权威表
│   ├── 10~19-*.md          # S0/S1/S2：建库、匹配、定制、改写、写作、自评……
│   ├── 20~25-*.md          # S4/S5：面试准备、出题、人设、复盘、群面
│   ├── 30~32-*.md          # 岗位方向案例：游戏发行 / 云销售 / 零售终端
│   ├── 40~46-*.md          # 格式红线、去 AI 味、ATS、输出台账、自检、质检
│   └── 90-踩坑档案.md       # 真实踩过的坑
└── scripts/                # 初始化 / 自检 / 导出 / docx-pdf 工具链
```

## 配置

`config.json` 放在技能目录下，首次使用自动生成；字段说明见 `config.example.json`：

- `dataRoot`：你的求职数据放哪（母版、JD、定制简历、面试记录都在这里）。
- `profile`：`campus-cn` / `campus-tech` / `intern-cn`。
- `qualityGate`：`standard`（默认，复审最多 2 轮、门槛 8）/ `strict`（3 轮、门槛 9）/ `off`。
- `overrides`：只写和 profile 不一样的地方，例如页数、证件照、自我评价字数。

技能目录内不写死任何绝对路径，所有路径都从 `dataRoot` 推导。

## 脚本

| 脚本 | 用途 |
|---|---|
| `init-skill.py` | 首次初始化：建目录骨架、写 `config.json` |
| `check-skill.py` | 改完规则跑一遍自检（一致性 / 悬空引用 / PII 扫描） |
| `export-skill.py` | 导出脱敏副本到公共目录，自带校验 |
| `docxtpl-build-template.py` / `docxtpl-render-and-pdf.py` | 占位符渲染成 docx，再转 PDF |
| `docx-template-fill.py` | 按模板填充内容 |
| `docx-style-extract.py` / `docx-run-replace.py` / `docx-drawing-extract.py` / `docx-fidelity-check.py` | 提样式、run 级替换、提图片、保真度校验 |
| `pdf-convert.sh` | 跨平台 PDF 转换 |

建库 / 打分 / 定制 / 自检 / 导出这些核心流程只依赖 Python 标准库；只有生成 docx、PDF 时才需要 `python-docx`、`docxtpl`、`PyMuPDF`（见 `requirements.txt`），转 PDF 推荐装 LibreOffice。

## 质检怎么跑

简历写完不是直接给你。三关：

1. **G1 自查**：`references/44-自检清单.md` 逐项打勾（结构、格式、内容、机器可读）。
2. **G2 换视角复审**：换一个干净上下文，只把成品、JD、岗位类型交给复审者，用 HR 六秒 / ATS 解析 / 压力面面试官 / 首次读者四个视角打分；发现的问题逐条反驳，拿不准判不成立，只修确认项。
3. **G3 用户终审**：给你一张"视角 / 分数 / 必改清单"，你拍板。

到轮数上限还没过门，就如实说哪些没解决，不假装通过。

## 使用须知

- 案例里的公司名是**化名**、数字是**示例值**，只用来理解"怎么写"，别抄进自己的简历。
- 母版没有的经历一律不写，缺料就标缺口。
- 本 Skill 不覆盖社招、薪资谈判、背调、offer 比较。
- 要分发给别人，跑 `python scripts/export-skill.py <目标目录>` 生成脱敏副本，别手工拷贝，否则真名黑名单会一起带出去。

## License

MIT，见 [LICENSE](LICENSE)。
