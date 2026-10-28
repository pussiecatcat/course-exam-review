---
name: course-exam-review
description: 为电子系课程（无线通信、微波工程、数字信号处理等）把中英混合的 PPT/PPTX/PDF 课件、考试范围、老师强调内容、作业与答案、往年题整理成完整复习包：中文精讲讲义 PDF/HTML、英文自测题（中文解析 + 英文答案）、核心概念/公式/易混点/常见错误速查、按剩余天数与每日时长制定的复习计划、材料覆盖检查与待核对清单。用于考前一周复习、PPT 总结、考试重点、cheat sheet、英文自测。以课程材料为主线，教材和外部资料仅在需要时补充并标注来源。
allowed-tools: Bash(*), Read, Write, Edit, Glob, Grep, WebSearch, WebFetch
---

# 课程材料 → 考试复习包

面向电子系本科课程（无线通信、微波工程、DSP 等）的考前复习。目标不是“把 PPT 压缩一遍”，而是把分散的课件、笔记、作业、往年题整合成一套能直接用于复习和自测的材料：**完整覆盖、按知识体系重排、重点有依据、英文题能上手、缺什么能看见**。

## 一、最终交付物

```
course-review/
├── course-review.pdf          # 完整讲义：导读 → 知识地图 → 各章 → 速查 → 自测 → 答案 → 计划 → 覆盖
├── index.html                 # 离线网页：侧栏目录、搜索、答案折叠、打印
├── course-review.md           # 合并后的可编辑 Markdown
├── quick-reference.pdf        # 可选：速查单独成册
├── self-test/
│   ├── questions.pdf          # 英文题，只有题目
│   ├── answers.pdf            # 中文解析 + 英文参考答案
│   ├── questions.md
│   ├── answers.md
│   └── bank.json              # 互动自测题库
├── figures/                   # 讲义引用的图片
├── assets/                    # 样式、脚本、KaTeX（离线可用）
└── source/                    # 可重新编译的源文件
    ├── content/*.md
    ├── figures/
    ├── meta.json
    ├── exam_profile.json
    ├── knowledge_points.csv
    ├── outline.md
    ├── coverage.csv
    ├── TO_VERIFY.md
    ├── scripts/               # build / print_pdf / check / plan / coverage / selftest
    ├── templates/report.html
    ├── assets/                # style.css / app.js / katex
    └── README.md              # 重新编译命令
```

如果用户只要其中一部分，按需交付；默认全部生成。

## 二、工作目录

中间产物放 `.review/`：

```
.review/
├── meta.json                 # 课程名、讲次、深度、语言、章节顺序
├── exam_profile.json         # 考试日期、每日时长、范围、题型、开闭卷、强调内容
├── knowledge_points.csv      # 知识点 → 优先级 → 依赖 → 预计学时
├── manifest.json             # 每页文本、图片、备注、媒体
├── outline.md                # 知识地图
├── coverage.csv              # 每一页 → 讲义哪一节
├── TO_VERIFY.md              # 无法确认/需要核对清单
├── slides/                   # 每页渲染图
├── media/                    # 抽出的图片/视频关键帧
├── figures/                  # 讲义用图
├── content/                  # 分章 Markdown
├── self_test_log.json        # 互动自测错题记录（可选）
└── QA_REPORT.md              # 质检结果
```

## 三、自动流程

材料上传后按顺序完成，**不需要用户审批目录、样稿或逐章确认**。只在“多门课混在一起、不知道处理哪一份”这类真正阻塞的问题上问一次。

### 0. 盘点材料

先看用户给了什么，按类型归档：

| 类型 | 用途 | 处理 |
|---|---|---|
| 课件 PPT/PPTX/PDF | 知识主线 | 逐页提取、渲染、看图 |
| 课堂笔记 | 补充推导、老师强调 | 与课件交叉核对 |
| 考试范围/大纲 | 划定 in-scope | 写入 exam_profile |
| 老师强调 | 提高优先级 | 标注 `[明确]` |
| 作业+答案 | 例题、自测素材 | 优先选用，标文件/题号 |
| 往年题 | 题型、重点、难度 | 优先选用，标年份/题号 |
| 教材/参考书 | 补前置、补推导 | 只在需要时用，标 `【外部】` |

如果目录里有几百页的教材，默认不作为主线；只把课件、笔记、作业、往年题放进 `--input`。教材内容只有在“课件省略了必要推导/前置知识”时才引用，并标来源。

### 1. 建立考试画像

写 `.review/exam_profile.json`。能从材料或用户话里提取的就提取，不要重复问。

```json
{
  "course": "无线通信",
  "exam_date": "2026-11-05",
  "today": "2026-10-28",
  "daily_hours": 3,
  "exam_type": "closed-book",
  "question_types": ["选择", "计算", "简答"],
  "scope": "第 2–4 讲；第 5 讲不考",
  "emphasized": ["路径损耗拟合", "中断概率", "多普勒"],
  "materials": {
    "homework": ["HW2", "HW3"],
    "past_exams": ["2024 秋期中", "2023 秋期末"]
  },
  "notes": "老师明确说 Example 2.3/2.4 会考；第 3 讲只考计算"
}
```

默认值（必须在讲义“导读”里说明假设）：

| 缺失项 | 默认 | 说明 |
|---|---|---|
| 考试日期 | 今天 + 7 天 | 计划按 7 天排 |
| 每日可用时长 | 不虚构；只给任务顺序与预计耗时 | 不排具体日期 |
| 考试范围 | 全部提供的课件 | 不擅自删除内容 |
| 题型 | 未说明；按课件信号推断 | 标注 `[推断]` |
| 开闭卷 | 未说明；不据此改变内容 | 在计划中注明假设 |
| 强调内容 | 无；按考点信号排序 | 标注 `[推断]` |

### 2. 提取与看图

```bash
python "$SKILL_DIR/scripts/ingest.py" --input <课件/笔记/作业/往年题...> --out .review
```

产物：`manifest.json`、`outline_seed.md`、`coverage.csv`、`slides/*.png`。

**必须看图。** 中英混合课件经常把公式、框图、波形、参数表放在图片里，只抽文字会漏。先读 `outline_seed.md` 建骨架，再按讲分块看 `slides/*.png`，每块 8–12 页。`image_only: true` 的页逐页看；文字页也要扫一眼，防止公式在图里。

### 3. 建知识地图

写 `.review/outline.md`，至少包括：

- 课程/讲次在整门课中的位置；
- 按**知识体系**组织的章节，不是照抄 PPT 顺序；
- 每章的前置知识、与前后章的联系、建议学习顺序；
- 每个知识点的来源页、优先级、预估考法；
- 合并重复内容（同一公式在多页出现，只讲一次，注明所有来源页）；
- 超出已知考试范围的内容，单独列出并标 `out-of-scope`。

写 `.review/knowledge_points.csv`（模板见 `templates/knowledge_points.example.csv`）：

```csv
id,title,section,priority,in_scope,depends_on,est_hours,source
KP01,路径损耗模型,2.2-2.3,A,true,,1.5,PPT p.2-5
KP02,阴影衰落,2.4,A,true,KP01,1.0,PPT p.6; 笔记 §3
```

- `priority`：`A` 明确在范围/老师强调/往年题命中/作业核心；`B` 课件重复/例题/核心公式，推断常考；`C` 背景/了解；`D` 超出已知范围。
- `in_scope`：`true/false`。范围外内容仍写进讲义，但标 `out-of-scope`，计划不优先安排。
- `depends_on`：前置知识点 ID，用分号分隔；`plan.py` 会尽量先排前置。
- `est_hours`：预计复习时长，按 standard 深度估。

同时填 `coverage.csv` 的 `section` 列：每个内容页都要归入某一节。封面、目录、致谢可标 `skip` 并写理由；**内容页不允许静默跳过**。看不懂的页标 `to-verify`，不标 `skip`。

### 4. 写讲义

按 `references/content-template.md` 写 `.review/content/`。推荐文件顺序：

```
00-guide.md              导读：范围、假设、使用方法、符号约定
01-knowledge-map.md      知识地图：章节关系、前置、学习顺序、优先级依据
02-*.md ...             各章精讲（按知识体系，不按 PPT 页码）
90-quick-reference.md    核心概念/公式/易混点/常见错误速查
91-self-test.md          英文自测题（只有题目）
92-self-test-answers.md  中文解析 + 英文答案
93-review-plan.md        复习计划（plan.py 生成后可微调）
94-coverage.md           覆盖检查 + 待核对清单（coverage.py 生成）
```

硬性要求：

- **中文讲解为主**，保留英文术语和关键定义的英文表述。首次出现用 `**path loss**（路径损耗）`，之后可只用英文。
- 每个知识点按实际需要包含：核心定义/物理意义、成立条件与适用范围、公式/变量/单位/符号约定、推导步骤与依据、与其他知识点的联系、易混点/易错点、典型例题。
- 课件省略的关键推导要补全；补讲前置知识时说明“它在当前知识点里起什么作用”。
- 重要原图保留，配中文图注，说明坐标轴、曲线、结构、参数各代表什么。图注不能只写“示意图”。
- 每节末尾写来源：`【课件｜文件名 p.X】`、`【作业｜文件名 题X】`、`【往年题｜年份 题X】`、`【补充】`、`【外部｜作者/文档 §X】`。
- 符号差异保留并解释换算；不同材料冲突时列出出处和差异，不静默选一个。
- 无法可靠识别的内容标 `【待核】`，并写入 `.review/TO_VERIFY.md`。

### 5. 例题与英文自测

**例题**优先用用户提供的作业和往年题，放在对应知识点之后，标明文件、题号或页码。解析按五段：

1. 题目在问什么、属于什么题型；
2. 为什么选这个方法、公式的适用条件；
3. 计算/推导步骤（关键中间量单独成行）；
4. 结果检查（量级、单位、极限情况、与课件是否一致）；
5. 这题的套路，换条件后怎么变。

没有可用作业/往年题时，可以用课件例题；仍不够时自行生成，标 `【自测·生成】`，不能冒充往年题。

**英文自测**：

- 默认英文题干；中文思路解析；英文参考答案。
- 题目与答案**分开**：`91-self-test.md` 只有题目，`92-self-test-answers.md` 只有答案；同时生成 `self-test/questions.pdf` 与 `self-test/answers.pdf`。
- 每个 A 级知识点至少 1 题；2–3 讲约 15–30 题，整门课约 40–80 题。题型覆盖概念、计算、推导、对比、应用。
- 题目 ID 用 `Q1, Q2, ...`，答案用 `A1, A2, ...`，一一对应。
- 来源标注：`【往年题｜2024 秋 Q2】`、`【作业｜HW3 题4】`、`【自测·生成】`。
- 解析要说明“怎么识别题型、为什么用这个方法、条件是否满足、步骤、怎么检查”，不能只给答案。

写完后校验并生成题库：

```bash
python "$SKILL_DIR/scripts/selftest.py" \
  --questions .review/content/91-self-test.md \
  --answers .review/content/92-self-test-answers.md \
  --out course-review/self-test/bank.json --check --split
```

### 6. 速查资料

`90-quick-reference.md` 至少四张表：

| 表 | 内容 |
|---|---|
| 核心概念 | 英文术语、中文、一句话定义、来源 |
| 公式速查 | 名称、公式、变量/单位、成立条件、来源 |
| 易混点 | A vs B、区别、怎么判断、典型题 |
| 常见错误 | 错误做法、为什么错、正确做法、来源 |

最后加一个“考前 10 分钟”清单，只放最容易失分的 8–12 条。

### 7. 复习计划

```bash
python "$SKILL_DIR/scripts/plan.py" --work .review --out .review/content/93-review-plan.md
```

脚本读取 `exam_profile.json` + `knowledge_points.csv`：

- 有考试日期：按剩余天数排；每天任务不超过 `daily_hours`。
- 没有日期：默认 7 天，并在计划开头写明假设。
- 没有每日时长：不排日期，只给任务顺序 + 预计耗时，写明假设。
- 预留约 20% 时间给自测与错题回顾，放在最后一天或分散到每天。
- A 级优先，前置知识先排；范围外内容单列，不占主计划。
- 时间不够时给出“保底方案”：只做 A 级 + 公式速查 + 自测错题。

计划生成后检查：是否包含自测/错题时间、是否说明假设、是否把范围外内容单列。

### 8. 覆盖检查

```bash
python "$SKILL_DIR/scripts/coverage.py" --work .review --out .review/content/94-coverage.md --strict
```

生成：

- 总览：来源数、内容页数、已归节、跳过、缺失、覆盖率；
- 逐来源表：每个文件多少页、覆盖到哪些节；
- 跳过页及理由；
- 未覆盖页（如果有，`--strict` 返回非零）；
- `TO_VERIFY.md` 中的待核对项。

覆盖率门槛：**非 skip 内容页 100% 归节**。封面/目录/致谢可 skip；内容页缺失就是失败。读不懂的页标 `to-verify`，仍要在 coverage 里出现。

### 9. 组装、编译、检查

```bash
python "$SKILL_DIR/scripts/build.py" --work .review --out course-review
python "$SKILL_DIR/scripts/print_pdf.py" --html course-review/index.html --out course-review/course-review.pdf
```

单独的英文自测 PDF：

```bash
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-questions --sections 91-self-test.md --title "英文自测题（只有题目）" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-questions/index.html --out course-review/self-test/questions.pdf
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-answers --sections 92-self-test-answers.md --title "自测答案与解析（中文解析 + 英文答案）" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-answers/index.html --out course-review/self-test/answers.pdf

# 速查 PDF（可选，主 PDF 已含速查章）
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-quick --sections 90-quick-reference.md --title "核心概念与公式速查" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-quick/index.html --out course-review/quick-reference.pdf
```

质检：

```bash
python "$SKILL_DIR/scripts/check.py" --work .review --out course-review
```

检查 PDF 的中文、公式、原图、分页、目录、交叉引用；检查自测题/答案 ID、语言、来源；检查计划假设、覆盖报告、待核对清单。

### 10. 打包源文件

```bash
python "$SKILL_DIR/scripts/package.py" --work .review --out course-review
```

生成 `course-review/source/`，包含可编辑 Markdown、图片、meta、exam_profile、knowledge_points、outline、coverage、TO_VERIFY，以及重新编译所需的 scripts/templates/assets。`source/README.md` 写明编译命令。

### 11. 交付与互动自测

交付消息只写：生成的文件、覆盖范围、通过/未通过的检查、待核对项、计划假设。

**互动自测由用户主动开启**（例如“开始自测”）。开启后：

- 读 `course-review/self-test/bank.json`，一次一题，英文题干；
- 用户回答前不显示答案；回答后给中文解析 + 英文参考答案；
- 计算题看步骤、单位、适用条件，不只看最后数字；
- 记录到 `.review/self_test_log.json`：题号、知识点、用户答案、是否正确、薄弱点；
- 每 5–10 题总结薄弱知识点，链接回讲义章节和原始材料页码；
- 错题优先安排到复习计划的“错题回顾”，不重写整份讲义。

详细流程见 `references/interactive-selftest.md`。

## 四、内容规范

### 语言

- 正文中文，英文术语保留；关键定义给英文原句或英文关键词。
- 公式、变量、单位用课程原记号；符号表覆盖正文出现的所有符号。
- 英文题目用英文写；解析用中文；参考答案用英文。不要中英混杂到影响阅读。

### 每个知识点的九件事

按实际需要取用，不必每个都写满：

1. **核心定义 / 物理意义 / 直觉**：一句话说清“是什么、为什么”。
2. **成立条件 / 适用范围 / 限制**：远场、窄带、单径、小角度、线性、独立遮挡等。
3. **公式 / 变量 / 单位 / 符号约定**：表格化；单位正体。
4. **推导 / 中间步骤 / 每一步依据**：课件省略的补全，标 `【补充】`。
5. **与其他知识点的联系**：前置、后续、对比、同一物理量的不同模型。
6. **易混点 / 易错点**：错误做法 → 为什么错 → 正确做法。
7. **典型例题**：优先作业/往年题，标文件/题号/页码。
8. **图**：保留原图，中文图注解释坐标轴/曲线/结构/参数。
9. **来源**：课件页、作业题、往年题、外部资料。

### 优先级与考试范围

- 每条重点标 `优先级 A/B/C/D`，并写 `依据`：`[明确]`（考试范围/老师强调/往年题）或 `[推断]`（课件信号/例题/重复）。
- 只有用户明确说“必考”或考试范围明确列出，才能写“必考”；否则写“重点”“高频”“建议掌握”。
- 范围外内容照常写进讲义，但标 `out-of-scope`，计划不优先安排。
- 作业和往年题优先于自编题；自编题标 `【自测·生成】`。

### 来源与准确性

- 重要知识点、例题、图表必须能追到文件 + 页/题号。
- 区分 `【课件】`、`【作业】`、`【往年题】`、`【补充】`、`【外部】`。
- 允许检索教材、官方文档、权威资料补足理解；必须标来源，不把外部结论写成课件结论。
- 不同材料符号/约定不同：保留原符号，给换算表；冲突时列出出处与差异，不静默选择。
- 无法可靠识别的公式/图/文字：标 `【待核】`，写入 `TO_VERIFY.md`，不凭空补写，不宣称“已完整覆盖”。

### 图

- 重要原图保留，尽量用高分辨率渲染（`--dpi 130` 或更高）。
- 图注写清：这张图在讲什么、横纵轴是什么、曲线/结构/参数分别代表什么、和正文哪个公式对应。
- 图里文字太小/被裁切：重新渲染或裁切；仍看不清就标 `【待核】`，不要猜。

## 五、默认值与询问

只问真正影响继续处理的信息（通常只有 1–2 个）：

1. 多门课/多份材料混在一起，不知道处理哪一份；
2. 用户明确要求“只做某几讲”，但材料里无法判断边界。

以下**不阻塞**，直接用默认值，并在讲义“导读”或计划里说明假设：

- 考试日期/每日时长缺失：默认 7 天 / 只给任务顺序与耗时；
- 输出格式未指定：默认 PDF + HTML + Markdown + 源文件包；
- 深度未指定：默认 `standard`；
- 语言未指定：默认中文讲解、保留英文术语；
- 开闭卷/题型未指定：不据此删内容，按常规准备并在计划中注明；
- 配色/目录名/样稿：不问，直接按模板生成。

不要问：目录名、样稿、逐章确认、配色、是否继续。普通偏好用默认值，交付时说明。

## 六、批量处理

材料多时（> 40 页或 > 3 讲）分批：

1. 先建全局 `outline.md` 和术语/符号表；
2. 每批 1–2 讲，写完立即更新 coverage；
3. 每批结束核对：术语、符号、章节编号、引用格式是否一致；
4. 最后统一做跨讲联系、速查、自测、计划、覆盖检查。

不要一批写完再回头改符号；先定符号表，再写各章。

## 七、质量红线

1. 不编造课件里没有的定义、公式、例题、数字。
2. 每个公式、每条结论能指回具体页/题；补充内容必须标记。
3. 数值例题独立重算；与原文不一致时写差异与原因。
4. 内容页不允许静默跳过；读不懂的页进 `TO_VERIFY`，不标 `skip`。
5. 自测题与答案 ID 一一对应；英文题干、中文解析、英文答案缺一不可。
6. 自编题必须标 `【自测·生成】`，不能冒充往年题。
7. 计划必须说明假设；没有每日时长就不排具体日期。
8. PDF 必须检查中文、公式、图片、分页、目录、交叉引用；源文件必须能重新编译。

## 八、命令速查

```bash
# 0) 提取
python "$SKILL_DIR/scripts/ingest.py" --input <材料...> --out .review --dpi 130

# 1) 自测题库校验
python "$SKILL_DIR/scripts/selftest.py" --questions .review/content/91-self-test.md \
  --answers .review/content/92-self-test-answers.md --out course-review/self-test/bank.json --check --split

# 2) 复习计划
python "$SKILL_DIR/scripts/plan.py" --work .review --out .review/content/93-review-plan.md

# 3) 覆盖检查
python "$SKILL_DIR/scripts/coverage.py" --work .review --out .review/content/94-coverage.md --strict

# 4) 主讲义
python "$SKILL_DIR/scripts/build.py" --work .review --out course-review
python "$SKILL_DIR/scripts/print_pdf.py" --html course-review/index.html --out course-review/course-review.pdf

# 5) 自测 PDF（题目/答案分开）
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-questions --sections 91-self-test.md --title "英文自测题（只有题目）" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-questions/index.html --out course-review/self-test/questions.pdf
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-answers --sections 92-self-test-answers.md --title "自测答案与解析（中文解析 + 英文答案）" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-answers/index.html --out course-review/self-test/answers.pdf
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-quick --sections 90-quick-reference.md --title "核心概念与公式速查" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-quick/index.html --out course-review/quick-reference.pdf

# 6) 质检 + 打包源文件
python "$SKILL_DIR/scripts/check.py" --work .review --out course-review
python "$SKILL_DIR/scripts/package.py" --work .review --out course-review
```

Windows 下 `$SKILL_DIR` 默认为：

```
C:\Users\<用户名>\.claude\skills\course-exam-review
```

## 九、参考文件

- `references/content-template.md`：讲义结构、知识点九段模板、图注、来源标记、非理工科适配。
- `references/exam-profile.md`：考试画像、优先级规则、明确要求 vs 推断、范围外标记。
- `references/pipeline.md`：完整流程、命令、批量处理、降级策略。
- `references/deliverables.md`：交付物清单与验收标准。
- `references/quality-gates.md`：机检 + 人工自检门槛。
- `references/interactive-selftest.md`：互动自测、错题记录、薄弱点回链。
- `templates/exam_profile.example.json`、`templates/knowledge_points.example.csv`：起手模板。
