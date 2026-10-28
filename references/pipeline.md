# 执行流程与降级

## 目录约定

在课程目录下执行。`SKILL_DIR` 指本 skill 目录：

- Windows: `C:\Users\<用户名>\.claude\skills\course-exam-review`
- macOS/Linux: `~/.claude/skills/course-exam-review`

中间产物 `.review/`，交付 `course-review/`。不要污染用户原有课件目录。

## 0. 盘点

```bash
python "$SKILL_DIR/scripts/ingest.py" --input <路径...> --out .review --dry-run
```

先确认：

- 哪些是课件，哪些是笔记/作业/往年题/教材；
- 有没有扫描版 PDF（文本层为空）；
- 有没有视频（PPT 内嵌）；
- 文件是否被 PowerPoint 占用（存在 `~$` 锁文件）；
- 是否混入其他课程。

把判断写进 `.review/meta.json` 和 `.review/exam_profile.json`。

## 1. 提取

```bash
python "$SKILL_DIR/scripts/ingest.py" --input <路径...> --out .review --dpi 130
```

产物：

```
.review/manifest.json
.review/outline_seed.md
.review/coverage.csv
.review/slides/*.png
.review/media/*
```

### 读图策略

1. 先读 `outline_seed.md`，按标题和文本建骨架。
2. 按讲分块看 `slides/*.png`，每块 8–12 页。先看标题与版式，判断内容类型（概念/公式/例题/图）。
3. `image_only: true` 的页必须看；文本页也扫一眼，防止公式在图里。
4. 表格、数据、代码、流程图记录页码与关键内容。
5. 视频页看 `media/` 关键帧；没有关键帧就记录“需回看视频”，不要臆测画面。

### 提取失败时

| 现象 | 原因 | 处理 |
|---|---|---|
| PPT 导出全黑/空白 | COM 渲染失败 | 改用 LibreOffice；再不行抽内嵌图片，并在 QA 标明“版式可能不完整” |
| 中文乱码 | 编码 | 统一 UTF-8；Windows 设 `PYTHONIOENCODING=utf-8` |
| 文件名带空格/中文 | 路径 | 脚本用 `Path` 处理；命令中加引号 |
| PDF 文本层为空 | 扫描版 | 只看渲染图，不引用不存在的文本 |
| 视频无关键帧 | 缺 opencv/ffmpeg | 记录页码与视频名，讲义标“需回看” |
| `.doc` 无法读取 | 旧格式 | 需要 Microsoft Word 转 `.docx`；否则跳过并记录 |
| 公式是图片 | 课件截图 | 用 LaTeX 重写关键公式，标“原页为公式截图” |

## 2. 考试画像与知识地图

写 `.review/exam_profile.json`（模板 `templates/exam_profile.example.json`）和 `.review/outline.md`。

知识点表 `.review/knowledge_points.csv`：

```csv
id,title,section,priority,in_scope,depends_on,est_hours,source
KP01,路径损耗模型,2.2-2.3,A,true,,1.5,PPT p.2-5
KP02,阴影衰落,2.4,A,true,KP01,1.0,PPT p.6; 笔记 §3
```

同时填 `coverage.csv`：

```csv
id,source,index,title,image_only,section,status
pl-002,2-Path Loss(2).pptx,2,mmWave Measurement,true,2.10,covered
pl-001,2-Path Loss(2).pptx,1,Path Loss,false,skip,封面
```

规则：

- 每个内容页必须有一个 `section`；封面/目录/致谢可 `skip`，`status` 写理由。
- 读不懂的页写 `to-verify`，不写 `skip`。
- 一页跨多节时写主节，`status` 注明“另见”。
- 覆盖率按“非 skip 页”计算，目标 100%。

## 3. 写内容

按 `references/content-template.md`。建议顺序：

1. `00-guide.md`：范围、假设、使用方法、符号约定、优先级图例。
2. `01-knowledge-map.md`：章节关系、前置、学习顺序、优先级依据。
3. 各章：先写“三句话结论”和公式表，再补推导、例题、易错点、图注。
4. `90-quick-reference.md`：四张表 + 考前 10 分钟清单。
5. `91-self-test.md` / `92-self-test-answers.md`。
6. `93-review-plan.md` / `94-coverage.md`（脚本生成后微调）。

### 篇幅参考（standard）

| 输入 | 建议篇幅 |
|---|---|
| 1 讲（8–12 页 PPT） | 8–15 页 A4 |
| 2–3 讲 | 20–35 页 A4 |
| 整门课（10+ 讲） | 60–120 页 A4，按讲分文件 |

`quick` 约为 standard 的 40%，`deep` 约为 1.6–2 倍。

### 批量处理

材料多时（> 40 页或 > 3 讲）：

1. 先建全局 `outline.md` 和术语/符号表；
2. 每批 1–2 讲，写完立即更新 coverage；
3. 每批结束核对：术语、符号、章节编号、引用格式；
4. 最后统一做跨讲联系、速查、自测、计划、覆盖检查。

不要一批写完再回头改符号；先定符号表，再写各章。

## 4. 自测题库

```bash
python "$SKILL_DIR/scripts/selftest.py" \
  --questions .review/content/91-self-test.md \
  --answers .review/content/92-self-test-answers.md \
  --out course-review/self-test/bank.json --check --split
```

`--check` 检查：

- Q/A 编号一一对应；
- 题干有英文；
- 答案有中文解析和英文答案；
- 来源标记存在；自编题有 `【自测·生成】`；
- 题目文件不包含答案。

`--split` 写出 `course-review/self-test/questions.md` 和 `answers.md`。

## 5. 复习计划

```bash
python "$SKILL_DIR/scripts/plan.py" --work .review --out .review/content/93-review-plan.md
```

规则见 `references/exam-profile.md` 和脚本头部注释。重点：

- 有日期按天排；无日期默认 7 天并说明；
- 无每日时长只给顺序 + 耗时；
- 预留 20% 自测/错题；
- 范围外单列；
- 时间不足给保底方案。

## 6. 覆盖检查

```bash
python "$SKILL_DIR/scripts/coverage.py" --work .review --out .review/content/94-coverage.md --strict
```

`--strict` 在缺失页 > 0 时返回非零。生成总览、逐来源表、跳过页、缺失页、待核对。

## 7. 组装与 PDF

```bash
python "$SKILL_DIR/scripts/build.py" --work .review --out course-review
python "$SKILL_DIR/scripts/print_pdf.py" --html course-review/index.html --out course-review/course-review.pdf
```

自测 PDF（题目/答案分开）：

```bash
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-questions --sections 91-self-test.md --title "英文自测题（只有题目）" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-questions/index.html --out course-review/self-test/questions.pdf
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-answers --sections 92-self-test-answers.md --title "自测答案与解析（中文解析 + 英文答案）" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-answers/index.html --out course-review/self-test/answers.pdf
python "$SKILL_DIR/scripts/build.py" --work .review --out .review/build-quick --sections 90-quick-reference.md --title "核心概念与公式速查" --minimal
python "$SKILL_DIR/scripts/print_pdf.py" --html .review/build-quick/index.html --out course-review/quick-reference.pdf
```

检查：

- `index.html` 离线打开，公式正常；
- 侧栏目录层级正确；
- 图片无 404；
- 答案折叠块可展开；
- 打印预览分页合理（标题不孤行、表格不截断）。

PDF 失败时：

1. 确认 `index.html` 用绝对路径传入；
2. 加大 `--virtual-time-budget`（默认 20000 ms）；
3. 仍失败则只交付 HTML，并告诉用户可用浏览器“打印 → 另存为 PDF”。

## 8. 质检

```bash
python "$SKILL_DIR/scripts/check.py" --work .review --out course-review
```

按 `references/quality-gates.md` 修到通过。质检报告写给用户看，不是内部日志。

## 9. 打包源文件

```bash
python "$SKILL_DIR/scripts/package.py" --work .review --out course-review
```

生成 `course-review/source/`。重新编译：

```bash
cd course-review/source
python scripts/build.py --work . --out ../rebuilt
python scripts/print_pdf.py --html ../rebuilt/index.html --out ../rebuilt/course-review.pdf
```

`package.py` 会把内容里的 `slides/...` 图片复制到 `source/figures/` 并改写路径，保证源文件脱离 `.review/` 也能编译。

## 10. 交付

交付消息模板：

```
已生成：
- course-review/course-review.pdf（完整讲义，N 页）
- course-review/index.html（离线网页）
- course-review/self-test/questions.pdf / answers.pdf（题目与答案分开）
- course-review/source/（可重新编译的 Markdown + 图片 + 脚本）

覆盖：X 个文件，Y 个内容页，覆盖率 100%；跳过封面 2 页。
检查：公式、中文、图片、目录、交叉引用、Q/A 编号均通过。
待核对：V01 ...；V02 ...
计划假设：考试日期由你提供；每日 3 小时；预留 20% 自测/错题。
互动自测：说“开始自测”即可，从 Q1 开始。
```

不要罗列中间步骤，不要贴工具日志。

## 11. 互动自测

用户主动说“开始自测”后，按 `references/interactive-selftest.md` 执行：

- 读 `course-review/self-test/bank.json`；
- 一次一题，英文题干；
- 用户回答前不显示答案；
- 记录 `.review/self_test_log.json`；
- 每 5–10 题总结薄弱点并回链讲义。
