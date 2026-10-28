#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
coverage.py — 生成“材料覆盖与待核对”章节

用法:
    python coverage.py --work .review --out .review/content/94-coverage.md [--strict]

输入:
    .review/manifest.json
    .review/coverage.csv
    .review/TO_VERIFY.md      (可选)

输出:
    Markdown 章节；--strict 在存在未覆盖内容页时返回 1。
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


def load_manifest(work: Path) -> dict:
    p = work / "manifest.json"
    if not p.exists():
        return {"sources": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"[warn] manifest.json 解析失败: {e}")
        return {"sources": []}


def load_coverage(work: Path) -> list[dict]:
    p = work / "coverage.csv"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def classify(row: dict) -> str:
    sec = (row.get("section") or "").strip()
    status = (row.get("status") or "").strip().lower()
    if sec.lower() in {"skip", "略过", "不覆盖"} or status.startswith("skip"):
        return "skip"
    if "to-verify" in status or "to_verify" in status or "待核" in status or sec.lower() in {"to-verify", "to_verify", "待核"}:
        return "verify"
    if sec:
        return "covered"
    return "missing"


def strip_frontmatter(text: str) -> str:
    text = text.replace("\r\n", "\n")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].lstrip("\n")
    return text


def build_report(work: Path) -> tuple[str, int, int, int]:
    manifest = load_manifest(work)
    rows = load_coverage(work)

    # 按 manifest 顺序组织来源
    source_order = [s.get("source") for s in manifest.get("sources", [])]
    for r in rows:
        if r.get("source") not in source_order:
            source_order.append(r.get("source"))

    by_source: dict[str, dict] = {}
    for src in source_order:
        by_source[src] = {"total": 0, "covered": 0, "skip": 0, "verify": 0, "missing": 0, "rows": []}

    total = covered = skipped = verify = missing = 0
    missing_rows = []
    verify_rows = []
    skip_rows = []

    for r in rows:
        src = r.get("source") or "未知来源"
        by_source.setdefault(src, {"total": 0, "covered": 0, "skip": 0, "verify": 0, "missing": 0, "rows": []})
        kind = classify(r)
        by_source[src]["total"] += 1
        by_source[src][kind] += 1
        by_source[src]["rows"].append(r)
        total += 1
        if kind == "covered":
            covered += 1
        elif kind == "skip":
            skipped += 1
            skip_rows.append(r)
        elif kind == "verify":
            verify += 1
            verify_rows.append(r)
        else:
            missing += 1
            missing_rows.append(r)

    denom = covered + verify + missing
    ratio = (covered / denom * 100) if denom else 100.0

    out: list[str] = []
    out.append("---")
    out.append("title: 材料覆盖与待核对")
    out.append("short: 覆盖")
    out.append("slides:")
    out.append("weight: —")
    out.append("priority: —")
    out.append("scope: in")
    out.append("map: false")
    out.append("keypoints: 覆盖率 · 跳过页 · 待核对 · 未覆盖")
    out.append("---")
    out.append("")
    out.append("# 材料覆盖与待核对")
    out.append("")
    out.append("::: lead")
    out.append(
        f"共 **{total}** 页/条目，已确认覆盖 **{covered}**，跳过 **{skipped}**，"
        f"待核对 **{verify}**，未覆盖 **{missing}**；确认覆盖率 **{ratio:.1f}%**。"
    )
    out.append(":::")
    out.append("")
    out.append("## 1. 总览")
    out.append("")
    out.append(f"- 来源文件：{len([s for s in source_order if s])}")
    out.append(f"- 内容页（不含跳过）：{denom}")
    out.append(f"- 已确认覆盖：{covered}")
    out.append(f"- 待核对：{verify}")
    out.append(f"- 未覆盖：{missing}")
    out.append(f"- 跳过：{skipped}")
    out.append(f"- 确认覆盖率：**{ratio:.1f}%**")
    out.append("")
    if missing == 0 and verify == 0:
        out.append("**结论：所有非跳过页面均已归节，且无待核对项。**")
    elif missing == 0:
        out.append("**结论：所有非跳过页面均已归节；仍有待核对项，见第 4、6 节。**")
    else:
        out.append("**结论：存在未覆盖内容页，见第 5 节；不能宣称已完整覆盖。**")
    out.append("")

    out.append("## 2. 逐来源")
    out.append("")
    out.append("| 来源 | 总页 | 已覆盖 | 跳过 | 待核对 | 未覆盖 |")
    out.append("|---|---|---|---|---|---|")
    for src, s in by_source.items():
        if not s["total"]:
            continue
        out.append(f"| {src} | {s['total']} | {s['covered']} | {s['skip']} | {s['verify']} | {s['missing']} |")
    out.append("")

    out.append("## 3. 跳过页")
    out.append("")
    if skip_rows:
        out.append("| 来源 | 页/条目 | 标题 | 理由 |")
        out.append("|---|---|---|---|")
        for r in skip_rows:
            out.append(
                f"| {r.get('source','')} | {r.get('index','')} | {r.get('title','')} | "
                f"{r.get('status','') or '未写理由（需补）'} |"
            )
    else:
        out.append("- 无。")
    out.append("")

    out.append("## 4. 待核对页")
    out.append("")
    if verify_rows:
        out.append("| 来源 | 页/条目 | 标题 | 归节 | 说明 |")
        out.append("|---|---|---|---|---|")
        for r in verify_rows:
            out.append(
                f"| {r.get('source','')} | {r.get('index','')} | {r.get('title','')} | "
                f"{r.get('section','')} | {r.get('status','')} |"
            )
    else:
        out.append("- 无。")
    out.append("")

    out.append("## 5. 未覆盖页")
    out.append("")
    if missing_rows:
        out.append("| 来源 | 页/条目 | 标题 | 说明 |")
        out.append("|---|---|---|---|")
        for r in missing_rows:
            out.append(
                f"| {r.get('source','')} | {r.get('index','')} | {r.get('title','')} | "
                f"未归节；请补 section 或标 to-verify |"
            )
    else:
        out.append("- 无。")
    out.append("")

    out.append("## 6. 待核对清单")
    out.append("")
    tv = work / "TO_VERIFY.md"
    if tv.exists():
        content = strip_frontmatter(tv.read_text(encoding="utf-8")).strip()
        out.append(content if content else "- 文件为空。")
    else:
        out.append("- 未提供 `TO_VERIFY.md`。遇到无法可靠识别的公式/图/文字时，请在该文件中登记。")
    out.append("")

    out.append("## 7. 说明")
    out.append("")
    out.append("- “已确认覆盖”指页面已归入讲义某一节，且内容已核对。")
    out.append("- “待核对”指页面已归节但存在无法确认的公式/图/文字，不影响归节，但不能算完全确认。")
    out.append("- “跳过”只允许封面、目录、致谢、纯章节分隔页；内容页不允许跳过。")
    out.append("- 本报告由 `coverage.csv` 和 `manifest.json` 生成；修改后请重跑。")
    out.append("")
    out.append(f"*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    out.append("")

    return "\n".join(out), missing, verify, total


def main() -> int:
    ap = argparse.ArgumentParser(description="生成覆盖与待核对章节")
    ap.add_argument("--work", default=".review")
    ap.add_argument("--out", default=".review/content/94-coverage.md")
    ap.add_argument("--strict", action="store_true", help="存在未覆盖页时返回非零")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    text, missing, verify, total = build_report(work)

    out = Path(args.out)
    if not out.is_absolute():
        if str(out).startswith(".review"):
            out = (work.parent / out).resolve()
        else:
            out = (Path.cwd() / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    log(f"[coverage] {total} 页；未覆盖 {missing}；待核对 {verify} -> {out}")
    if args.strict and missing > 0:
        log("[coverage] 失败：存在未覆盖内容页")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
