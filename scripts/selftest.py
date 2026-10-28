#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
selftest.py — 校验英文自测题/答案，生成互动题库

用法:
    python selftest.py --questions .review/content/91-self-test.md \
        --answers .review/content/92-self-test-answers.md \
        --out course-review/self-test/bank.json --check --split

检查:
    - Q/A 编号一一对应
    - 题干英文、解析中文、参考答案英文
    - 来源标记存在；自编题标【自测·生成】
    - 题目文件不含答案
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


def strip_frontmatter(text: str) -> str:
    text = text.replace("\r\n", "\n")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return text


def parse_blocks(text: str, letter: str) -> dict[str, dict]:
    body = strip_frontmatter(text)
    pattern = re.compile(rf"^##\s+{letter}(\d+)\s*(?:[·:：]\s*)?(.*)$", re.M)
    matches = list(pattern.finditer(body))
    out: dict[str, dict] = {}
    for i, m in enumerate(matches):
        qid = f"{letter}{m.group(1)}"
        heading_topic = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end].strip()
        out[qid] = {"heading_topic": heading_topic, "block": block}
    return out


def field(block: str, label: str, next_labels: list[str]) -> str:
    labels = "|".join(re.escape(x) for x in next_labels)
    pat = rf"\*\*{re.escape(label)}[：:]\*\*\s*(.*?)(?=\n\*\*(?:{labels})[：:]\*\*|\Z)"
    m = re.search(pat, block, flags=re.S)
    return m.group(1).strip() if m else ""


def one_line_field(block: str, label: str) -> str:
    m = re.search(rf"\*\*{re.escape(label)}[：:]\*\*\s*([^\n]+?)(?=\s{{2,}}\*\*|\n|$)", block)
    return m.group(1).strip() if m else ""


def has_english(s: str, n: int = 10) -> bool:
    return len(re.findall(r"[A-Za-z]", s)) >= n


def cjk_count(s: str) -> int:
    return len(re.findall(r"[一-鿿]", s))


def source_marker_ok(source: str) -> tuple[bool, str]:
    s = source.strip()
    if not s:
        return False, "缺少来源"
    if ("生成" in s or "自编" in s or "generated" in s.lower()) and "【自测·生成】" not in s:
        return False, "自编题必须标【自测·生成】"
    if ("往年" in s or re.search(r"20\d{2}", s)) and "【往年题" not in s:
        return False, "往年题必须标【往年题｜年份 题X】"
    if ("作业" in s or re.search(r"\bHW\d*\b", s, re.I)) and "【作业" not in s:
        return False, "作业题必须标【作业｜文件名 题X】"
    if not re.search(r"【(?:往年题|作业|自测·生成|课件)", s):
        return False, "来源需带【往年题/作业/自测·生成/课件】标记"
    return True, ""


def build_bank(qblocks: dict[str, dict], ablocks: dict[str, dict]) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    q_by_num = {int(re.sub(r"\D", "", q) or 0): q for q in qblocks}
    a_by_num = {int(re.sub(r"\D", "", a) or 0): a for a in ablocks}
    if set(q_by_num) != set(a_by_num):
        only_q = sorted(set(q_by_num) - set(a_by_num))
        only_a = sorted(set(a_by_num) - set(q_by_num))
        if only_q:
            errors.append("缺少答案: " + ", ".join(f"Q{n}" for n in only_q))
        if only_a:
            errors.append("缺少题目: " + ", ".join(f"A{n}" for n in only_a))

    bank: list[dict] = []
    for num in sorted(q_by_num):
        qid = q_by_num[num]
        aid = a_by_num.get(num)
        qb = qblocks[qid]["block"]
        ab = ablocks[aid]["block"] if aid else ""

        topic = one_line_field(qb, "Topic") or qblocks[qid]["heading_topic"]
        section = one_line_field(qb, "Section")
        qtype = one_line_field(qb, "Type") or "unknown"
        source = one_line_field(qb, "Source")
        if not source:
            source = one_line_field(qb, "来源")

        question = field(qb, "Question (English)", ["Topic", "Section", "Source", "Type", "Question", "来源"])
        if not question:
            question = field(qb, "Question", ["Topic", "Section", "Source", "Type", "来源"])
        if not question:
            # 取第一个非元信息段落
            lines = [ln.strip() for ln in qb.splitlines() if ln.strip() and not ln.strip().startswith("**")]
            question = " ".join(lines).strip()

        analysis = field(ab, "中文思路", ["English answer", "易错点", "回到讲义"])
        answer = field(ab, "English answer", ["易错点", "回到讲义", "中文思路"])
        pitfall = field(ab, "易错点", ["回到讲义", "中文思路", "English answer"])
        back = field(ab, "回到讲义", ["中文思路", "English answer", "易错点"])

        if not question:
            errors.append(f"{qid}: 缺少题干")
        elif not has_english(question, 20):
            errors.append(f"{qid}: 题干英文不足（至少 20 个英文字母）")
        if not analysis:
            errors.append(f"{qid}: 缺少中文思路")
        elif cjk_count(analysis) < 10:
            errors.append(f"{qid}: 中文解析过少")
        if not answer:
            errors.append(f"{qid}: 缺少英文参考答案")
        elif not has_english(answer, 20):
            errors.append(f"{qid}: 英文答案过少")
        ok, msg = source_marker_ok(source)
        if not ok:
            errors.append(f"{qid}: {msg}（来源：{source or '空'}）")

        bank.append({
            "id": qid,
            "topic": topic,
            "section": section,
            "source": source,
            "question_en": question,
            "answer_en": answer,
            "analysis_zh": analysis,
            "pitfall": pitfall,
            "section_link": back,
            "type": qtype,
        })

    # 题目文件不得含答案
    qtext = "\n".join(v["block"] for v in qblocks.values())
    if "English answer" in qtext or "中文思路" in qtext:
        errors.append("题目文件疑似包含答案/解析，请拆到 92-self-test-answers.md")

    return bank, errors


def write_split(questions_path: Path, answers_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    qbody = strip_frontmatter(questions_path.read_text(encoding="utf-8")).strip()
    abody = strip_frontmatter(answers_path.read_text(encoding="utf-8")).strip()
    qfm = "---\ntitle: 英文自测题\nshort: 自测题\nslides:\nweight: —\npriority: —\nscope: in\nmap: false\nkeypoints: 英文题干 · 题型 · 来源\n---\n\n"
    afm = "---\ntitle: 自测答案与解析\nshort: 答案\nslides:\nweight: —\npriority: —\nscope: in\nmap: false\nkeypoints: 中文思路 · 英文答案 · 易错点\n---\n\n"
    (out_dir / "questions.md").write_text(qfm + qbody + "\n", encoding="utf-8")
    (out_dir / "answers.md").write_text(afm + abody + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="校验自测题并生成题库")
    ap.add_argument("--questions", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--out", default="self-test/bank.json")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--split", action="store_true", help="同时输出 questions.md / answers.md")
    args = ap.parse_args()

    qpath = Path(args.questions)
    apath = Path(args.answers)
    if not qpath.exists():
        log(f"[error] 题目文件不存在: {qpath}")
        return 2
    if not apath.exists():
        log(f"[error] 答案文件不存在: {apath}")
        return 2

    qblocks = parse_blocks(qpath.read_text(encoding="utf-8"), "Q")
    ablocks = parse_blocks(apath.read_text(encoding="utf-8"), "A")
    bank, errors = build_bank(qblocks, ablocks)

    if args.split:
        out_dir = Path(args.out).parent
        write_split(qpath, apath, out_dir)
        log(f"[selftest] 写出 {out_dir / 'questions.md'} / {out_dir / 'answers.md'}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bank, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[selftest] {len(bank)} 题 -> {out}")

    if errors:
        log(f"[selftest] FAIL — {len(errors)} 项")
        for e in errors:
            log(f"  - {e}")
        return 1
    log("[selftest] PASS — 编号、语言、来源检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
