# 交付物与验收

## 一、目录

```
course-review/
├── course-review.pdf
├── index.html
├── course-review.md
├── quick-reference.pdf        # 可选：速查单独成册
├── self-test/
│   ├── questions.pdf
│   ├── answers.pdf
│   ├── questions.md
│   ├── answers.md
│   └── bank.json
├── figures/
├── assets/
└── source/
    ├── content/
    ├── figures/
    ├── meta.json
    ├── exam_profile.json
    ├── knowledge_points.csv
    ├── outline.md
    ├── coverage.csv
    ├── TO_VERIFY.md
    ├── scripts/
    ├── templates/report.html
    ├── assets/
    └── README.md
```

## 二、每个文件负责什么

| 文件 | 内容 | 谁生成 |
|---|---|---|
| `course-review.pdf` | 完整讲义：导读、知识地图、各章、速查、自测题、答案、计划、覆盖 | `build.py` + `print_pdf.py` |
| `index.html` | 离线网页，侧栏目录、搜索、答案折叠、打印 | `build.py` |
| `course-review.md` | 合并后的可编辑 Markdown，图片路径已改写为 `figures/...` | `build.py` |
| `quick-reference.pdf` | 可选：核心概念/公式/易混/易错单独成册 | `build.py --sections 90-quick-reference.md` |
| `self-test/questions.pdf` | 只有英文题，不含答案 | `build.py --sections 91-self-test.md` |
| `self-test/answers.pdf` | 中文解析 + 英文答案 | `build.py --sections 92-self-test-answers.md` |
| `self-test/questions.md` | 可编辑题目 | 模型 / `selftest.py --split` |
| `self-test/answers.md` | 可编辑答案 | 模型 / `selftest.py --split` |
| `self-test/bank.json` | 互动自测题库，字段见下 | `selftest.py` |
| `source/` | 重新编译所需的一切 | `package.py` |
| `source/README.md` | 重新编译命令、依赖、目录说明 | `package.py` |

## 三、`bank.json` 字段

```json
[
  {
    "id": "Q1",
    "topic": "Path loss exponent",
    "section": "2.3",
    "source": "【往年题｜2024 秋 Q2】",
    "question_en": "...",
    "answer_en": "...",
    "analysis_zh": "...",
    "pitfall": "...",
    "type": "calculation"
  }
]
```

- `id` 与答案 ID 对应（Q1 ↔ A1）。
- `question_en` 必须是英文题干。
- `answer_en` 英文参考答案；`analysis_zh` 中文思路。
- `source` 标出来源；自编题写 `【自测·生成】`。
- `type`：`concept` / `calculation` / `derivation` / `comparison` / `application`。

## 四、验收标准

### 讲义

- 100% 非 skip 内容页有归节；
- 每章有前置知识、前后章联系、优先级依据；
- 每个 A 级知识点有定义、公式、例题、自测；
- 重要图有中文图注（坐标轴/曲线/参数）；
- 课件省略的关键推导有补全，标 `【补充】`；
- 范围外内容标 `out-of-scope`；
- 每节有来源；冲突有对照；不确定有 `【待核】`。

### 自测

- 题目与答案分开；
- Q/A 编号一一对应；
- 英文题干、中文解析、英文答案齐全；
- 来源标注正确，自编题不冒充往年题；
- 答案含步骤/条件/检查，不只给最终数字。

### 计划

- 有考试日期时按天排；没有日期默认 7 天并说明；
- 没有每日时长时只给任务顺序 + 耗时，不虚构日期；
- 预留约 20% 自测/错题时间；
- 范围外内容单列；
- 时间不足有保底方案。

### 覆盖

- `94-coverage.md` 有总览、逐来源表、跳过页、缺失页、待核对；
- `--strict` 时缺失页为 0；
- `TO_VERIFY.md` 每条有位置、问题、处理建议。

### PDF / 网页

- 中文无乱码；公式渲染正常；图片清晰；分页合理；
- 目录锚点全部可达；交叉引用（§、p.、Q/A）指向存在；
- HTML 离线打开正常（KaTeX 本地）；
- 源文件能重新编译出同页数 PDF。

## 五、交付消息

只写：

- 生成的文件（PDF / HTML / Markdown / 自测 / 源文件）；
- 覆盖范围与覆盖率；
- 通过/未通过的检查；
- 待核对项；
- 计划假设；
- 互动自测如何开启。

不要罗列过程日志、工具输出、逐章写作细节。
