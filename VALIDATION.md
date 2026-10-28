# Validation report

Date: 2026-10-28  
验证方式：脚本编译 + 端到端合成样例（8 章、1 张图、2 道英文自测题）+ 源文件重编译。

## 1. 结构检查

```
course-exam-review/
├── SKILL.md
├── references/
│   ├── content-template.md
│   ├── deliverables.md
│   ├── exam-profile.md
│   ├── interactive-selftest.md
│   ├── pipeline.md
│   └── quality-gates.md
├── scripts/
│   ├── ingest.py
│   ├── build.py
│   ├── print_pdf.py
│   ├── check.py
│   ├── plan.py
│   ├── coverage.py
│   ├── selftest.py
│   └── package.py
├── assets/
│   ├── style.css
│   ├── app.js
│   └── katex/（离线公式渲染）
└── templates/
    ├── report.html
    ├── exam_profile.example.json
    └── knowledge_points.example.csv
```

## 2. 脚本编译

```bash
python -m py_compile ingest.py build.py print_pdf.py check.py plan.py coverage.py selftest.py package.py
```

结果：通过。

## 3. 端到端样例

输入：8 个内容文件（导读、知识地图、1 章正文、速查、自测题、答案、计划、覆盖）、1 张课件图、2 道英文自测题。

| 步骤 | 命令 | 结果 |
|---|---|---|
| 复习计划 | `plan.py` | 3 个知识点，8 天，每天 2 h，预留 20% 自测/错题；范围外单列 |
| 覆盖报告 | `coverage.py --strict` | 1/1 内容页归节，1 页跳过（封面），strict 退出 0 |
| 自测校验 | `selftest.py --check --split` | Q1/Q2 与 A1/A2 对应；英文题干、中文解析、英文答案通过 |
| 主讲义 | `build.py` + `print_pdf.py` | 13 页 A4；考试地图、优先级、前置、联系、图注、待核标记正常 |
| 自测题目 PDF | `build.py --sections 91-self-test.md --minimal` | 1 页，只有题目，无答案 |
| 自测答案 PDF | `build.py --sections 92-self-test-answers.md --minimal` | 1 页，中文解析 + 英文答案 |
| 速查 PDF | `build.py --sections 90-quick-reference.md --minimal` | 2 页，四张表 + 考前清单 |
| 源文件打包 | `package.py --verify` | 233 个文件，5.4 MB；试编译通过 |
| 源文件重编译 | `source/scripts/build.py` + `print_pdf.py` | 13 页，与交付版页数一致 |
| 质检 | `check.py` | PASS，0 失败；2 个警告（1 处待核；样例只有 2 题，低于建议的 15–30 题） |

## 4. 需求覆盖

| 要求 | 实现 |
|---|---|
| 完整讲义 PDF + 可编辑源文件 + 图片 | 主 PDF、`source/content`、`source/figures`、`source/assets` |
| 英文自测 + 中文解析 + 英文答案，题目/答案分开 | `91/92` 两个内容文件 + `self-test/questions.pdf` / `answers.pdf` + `bank.json` |
| 核心概念/公式/易混/易错速查 | `90-quick-reference.md` + 可选 `quick-reference.pdf` |
| 按剩余天数和每日时长的复习计划 | `plan.py`；缺日期默认 7 天，缺时长只给顺序与耗时 |
| 覆盖检查 + 待核对清单 | `coverage.py` + `TO_VERIFY.md` + `94-coverage.md` |
| 按知识体系组织、合并重复、讲联系/前置/顺序 | 知识地图 + 每章 `prereq` / `connect` |
| 中文讲解 + 英文术语 | 内容模板 + 自测格式 |
| 定义/条件/公式/单位/推导/联系/易混/例题 | 九段模板 |
| 课件省略推导补全、前置补讲 | `【补充】` + `prereq` |
| 原图保留 + 中文图注 | `ingest.py --dpi 130` + 图注规范 + `check.py` 检查 |
| 考试范围/强调/作业/往年题定优先级 | `exam_profile.json` + `knowledge_points.csv` + `exam` 块 |
| 区分明确要求与推断 | `[明确]` / `[推断]` 标签 |
| 范围外标 out-of-scope、计划不优先 | `outscope` 块 + `plan.py` |
| 符号差异/冲突保留 | `exam-profile.md` + 内容规范；人工核对 |
| 无法确认标待核 | `【待核】` + `TO_VERIFY.md` + coverage |
| 自动流程、不逐章审批 | `SKILL.md` 自动流程 + 默认值规则 |
| 批量处理、术语/符号一致 | `pipeline.md` 分批规则 |
| PDF 中英文/公式/图/分页/目录/交叉引用检查 | `check.py` + 浏览器打印 + 源文件重编译 |
| 互动自测/错题记录/回链 | `interactive-selftest.md` + `bank.json` + `self_test_log.json` |

## 5. 已知限制

- PPT 逐页渲染依赖 PowerPoint（Windows）或 LibreOffice；两者都没有时只能抽文本/内嵌图，版式可能不完整。
- PPT 内嵌视频抽帧依赖 `opencv-python`；没有时讲义会标“需回看原 PPT”，不臆测画面。
- 复习计划是启发式排程（优先级 + 前置 + 每日时长 + 20% 预留），不是最优解；生成后可按实际进度微调。
- 自测题数量门槛是建议值；样例只有 2 题，因此质检给出警告而不是失败。
- 源文件重编译需要与交付版相同的字体/浏览器环境；本机验证页数一致（13 页）。
