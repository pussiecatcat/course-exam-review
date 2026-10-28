#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plan.py — 根据考试画像和知识点表生成复习计划

用法:
    python plan.py --work .review --out .review/content/93-review-plan.md
    python plan.py --work .review --dry-run

输入:
    .review/exam_profile.json
    .review/knowledge_points.csv

输出:
    Markdown 计划（默认写入 .review/content/93-review-plan.md）

规则:
    - 有考试日期按天排；没有日期默认 7 天并写明假设。
    - 有每日时长按小时排；没有时长只给任务顺序 + 预计耗时，不虚构日期。
    - 预留约 20% 给自测/错题回顾。
    - A 级优先，前置知识先排；范围外内容单列，不占主计划。
    - 时间不足时优先保留 A 级，未被排入的任务单独列出。
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

PRIORITY_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def as_bool(value, default=True) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "in", "scope", "in-scope"}


def as_float(value, default=1.0) -> float:
    try:
        v = float(str(value).strip())
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def load_profile(work: Path) -> dict:
    p = work / "exam_profile.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"[warn] exam_profile.json 解析失败: {e}")
    return {}


def load_kps(work: Path) -> list[dict]:
    p = work / "knowledge_points.csv"
    if not p.exists():
        return []
    rows = []
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        for i, row in enumerate(csv.DictReader(f)):
            if not row.get("id"):
                continue
            deps = [x.strip() for x in str(row.get("depends_on") or "").replace("，", ";").replace(",", ";").split(";") if x.strip()]
            pri = (row.get("priority") or "B").strip().upper()
            if pri not in PRIORITY_ORDER:
                pri = "B"
            rows.append({
                "id": row["id"].strip(),
                "title": (row.get("title") or row["id"]).strip(),
                "section": (row.get("section") or "").strip(),
                "priority": pri,
                "in_scope": as_bool(row.get("in_scope"), True),
                "deps": deps,
                "est_hours": as_float(row.get("est_hours"), 1.0),
                "source": (row.get("source") or "").strip(),
                "order": i,
            })
    return rows


def topo_sort(kps: list[dict]) -> list[dict]:
    by_id = {k["id"]: k for k in kps}
    indeg = {k["id"]: 0 for k in kps}
    children = {k["id"]: [] for k in kps}
    for k in kps:
        for d in k["deps"]:
            if d in by_id and d != k["id"]:
                indeg[k["id"]] += 1
                children[d].append(k["id"])

    def key(k):
        return (PRIORITY_ORDER.get(k["priority"], 9), k["order"])

    ready = sorted([k for k in kps if indeg[k["id"]] == 0], key=key)
    out: list[dict] = []
    while ready:
        k = ready.pop(0)
        out.append(k)
        for c in children[k["id"]]:
            indeg[c] -= 1
            if indeg[c] == 0:
                ready.append(by_id[c])
        ready.sort(key=key)
    if len(out) < len(kps):
        done = {k["id"] for k in out}
        out += sorted([k for k in kps if k["id"] not in done], key=key)
    return out


def fmt_day(d: date) -> str:
    return f"{d.isoformat()}（{WEEKDAYS[d.weekday()]}）"


def schedule_daily(tasks: list[dict], days: int, daily_hours: float, budget: float):
    """Greedy day-aware scheduler. Returns (rows, unscheduled, spent, day_cursor, day_used)."""
    rows: list[dict] = []
    unscheduled: list[dict] = []
    spent = 0.0
    day = 1
    day_used = {d: 0.0 for d in range(1, days + 1)}

    for k in tasks:
        remain_budget = budget - spent
        if remain_budget <= 0.01:
            unscheduled.append({**k, "reason": "预算不足，未排入"})
            continue
        est = k["est_hours"]
        alloc = min(est, remain_budget)
        if alloc < est - 1e-9:
            unscheduled.append({**k, "partial": True, "reason": "预算不足，已压缩"})

        remaining = alloc
        parts = max(1, int((alloc + daily_hours - 1e-9) // daily_hours))
        part = 0
        placed = 0.0
        while remaining > 0.01 and day <= days:
            cap = daily_hours - day_used[day]
            if cap <= 0.01:
                day += 1
                continue
            # 小任务不拆天：放不下就顺延到第二天
            if remaining <= daily_hours and cap < remaining - 1e-9:
                day += 1
                continue
            take = min(remaining, cap)
            part += 1
            day_used[day] += take
            remaining -= take
            placed += take
            spent += take
            note = ""
            if parts > 1:
                note = f"第 {part}/{parts} 部分；"
            if k["deps"]:
                note += "前置：" + "、".join(k.get("dep_titles", k["deps"]))
            rows.append({
                "day": day,
                "task": k["title"],
                "section": k["section"],
                "priority": k["priority"],
                "hours": round(take, 2),
                "note": note,
                "order": k["order"],
            })
            if remaining > 0.01:
                day += 1

        if placed <= 0.01:
            unscheduled.append({**k, "reason": "天数不足，未排入"})
        elif remaining > 0.01:
            unscheduled.append({**k, "partial": True, "reason": "天数不足，只排了一部分"})
    return rows, unscheduled, spent, day, day_used


def place_reserve(days: int, daily_hours: float, reserve: float, day: int, day_used: dict):
    rows = []
    remaining = reserve
    while remaining > 0.01 and day <= days:
        cap = daily_hours - day_used.get(day, 0.0)
        if cap <= 0.01:
            day += 1
            continue
        take = min(remaining, cap)
        rows.append({"day": day, "hours": round(take, 2), "overflow": False})
        day_used[day] = day_used.get(day, 0.0) + take
        remaining -= take
        if remaining > 0.01:
            day += 1
    if remaining > 0.01:
        if rows and rows[-1]["day"] == days:
            rows[-1]["hours"] = round(rows[-1]["hours"] + remaining, 2)
            rows[-1]["overflow"] = True
        else:
            rows.append({"day": days, "hours": round(remaining, 2), "overflow": True})
    return rows



def build_plan(profile: dict, kps: list[dict], today_override: date | None = None) -> str:
    today = today_override or parse_date(profile.get("today")) or date.today()
    exam = parse_date(profile.get("exam_date"))
    daily_hours_raw = profile.get("daily_hours")
    daily_hours = None
    try:
        v = float(daily_hours_raw)
        if v > 0:
            daily_hours = v
    except (TypeError, ValueError):
        pass

    assumptions: list[str] = []
    if exam:
        days = (exam - today).days
        if days < 0:
            days = 1
            assumptions.append("考试日期早于今天，按 1 天冲刺安排。")
        elif days == 0:
            days = 1
            assumptions.append("考试就在今天，按 1 天冲刺安排。")
        else:
            days = max(1, days)
    else:
        days = 7
        exam = today + timedelta(days=7)
        assumptions.append("未提供考试日期，默认按今天起 7 天安排。")

    if daily_hours is None:
        assumptions.append("未提供每日可用时长，只给任务顺序与预计耗时，不排具体日期。")
    if not profile.get("exam_type"):
        assumptions.append("未提供开闭卷信息，内容不据此删减。")
    if not profile.get("scope"):
        assumptions.append("未提供考试范围，全部提供的课件按 in-scope 处理。")
    if not kps:
        assumptions.append("knowledge_points.csv 为空，计划只给总体顺序，无法按知识点细分。")

    ordered = topo_sort(kps)
    in_scope = [k for k in ordered if k["in_scope"]]
    out_scope = [k for k in ordered if not k["in_scope"]]

    if not in_scope:
        in_scope = [{
            "id": "ALL", "title": "按讲义章节顺序复习", "section": "全部",
            "priority": "A", "in_scope": True, "deps": [], "est_hours": 1.0,
            "source": "knowledge_points.csv 为空", "order": 0,
        }]

    id_title = {k["id"]: k["title"] for k in kps}
    for k in in_scope:
        k["dep_titles"] = [id_title.get(d, d) for d in k["deps"]]

    rows: list[dict] = []
    unscheduled: list[dict] = []
    total_est = sum(k["est_hours"] for k in in_scope)

    if daily_hours is None:
        cum = 0.0
        for k in in_scope:
            cum += k["est_hours"]
            rows.append({
                "order": len(rows) + 1, "task": k["title"], "section": k["section"],
                "priority": k["priority"], "hours": k["est_hours"], "cum": cum,
                "note": "前置：" + "、".join(k.get("dep_titles", k["deps"])) if k["deps"] else "",
            })
        reserve = max(0.5, round(total_est * 0.2, 1))
    else:
        total_available = days * daily_hours
        reserve = round(total_available * 0.2, 2)
        study_budget = max(0.0, total_available - reserve)
        rows, unscheduled, spent, day_cursor, day_used = schedule_daily(
            in_scope, days, daily_hours, study_budget
        )
        reserve_rows = place_reserve(days, daily_hours, reserve, day_cursor, day_used)
        if spent < total_est - 1e-6:
            assumptions.append(
                f"任务总时长约 {total_est:.1f} h，可用复习时间约 {study_budget:.1f} h，"
                "已优先保留高优先级任务；未排入部分见“时间不足”。"
            )

    # 把任务行按天汇总成 Markdown 表
    lines: list[str] = []
    if daily_hours is None:
        lines.append("| # | 任务 | 知识点 | 优先级 | 预计 | 累计 | 说明 |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in rows:
            lines.append(
                f"| {r['order']} | {r['task']} | {r['section']} | {r['priority']} | "
                f"{r['hours']:.1f} h | {r['cum']:.1f} h | {r['note']} |"
            )
        lines.append(
            f"| — | **自测 + 错题回顾** | 全部 A 级 | — | 约 {reserve:.1f} h | — | 预留约 20% |"
        )
    else:
        by_day: dict[int, list[dict]] = {d: [] for d in range(1, days + 1)}
        for r in rows:
            by_day.setdefault(r["day"], []).append(r)
        for rr in reserve_rows:
            by_day.setdefault(rr["day"], []).append({
                "task": "自测 + 错题回顾", "section": "全部 A 级", "priority": "—",
                "hours": rr["hours"], "note": "预留约 20%；做题库 + 重做错题"
                + ("；超出每日时长，需压缩" if rr.get("overflow") else ""),
                "reserve": True,
            })
        used_days = {d for d, items in by_day.items() if items}
        for d in range(1, days + 1):
            if d not in used_days:
                by_day[d].append({
                    "task": "机动（补弱/重做错题）", "section": "—", "priority": "—",
                    "hours": daily_hours, "note": "可提前，也可留给弱项", "reserve": True,
                })
        lines.append("| 日期 | Day | 任务 | 知识点 | 优先级 | 预计 | 说明 |")
        lines.append("|---|---|---|---|---|---|---|")
        for d in range(1, days + 1):
            ddate = today + timedelta(days=d - 1)
            items = by_day.get(d, [])
            if not items:
                lines.append(f"| {fmt_day(ddate)} | D{d} | 机动 | — | — | — | — |")
                continue
            for i, r in enumerate(items):
                date_cell = fmt_day(ddate) if i == 0 else ""
                day_cell = f"D{d}" if i == 0 else ""
                lines.append(
                    f"| {date_cell} | {day_cell} | {r['task']} | {r['section']} | "
                    f"{r['priority']} | {r['hours']:.1f} h | {r.get('note', '')} |"
                )

    # 文档
    out: list[str] = []
    out.append("---")
    out.append("title: 复习计划")
    out.append("short: 计划")
    out.append("slides:")
    out.append("weight: —")
    out.append("priority: —")
    out.append("scope: in")
    out.append("map: false")
    out.append("keypoints: 剩余天数 · 每日时长 · 优先级 · 自测回顾")
    out.append("---")
    out.append("")
    out.append("# 复习计划")
    out.append("")
    out.append("::: lead")
    out.append(
        f"考试日期 **{exam.isoformat()}**，今天 **{today.isoformat()}**，"
        f"剩余 **{days} 天**"
        + (f"，每天约 **{daily_hours:g} 小时**。" if daily_hours else "，未提供每日时长。")
    )
    out.append(":::")
    out.append("")
    out.append("## 1. 假设")
    out.append("")
    if assumptions:
        for a in assumptions:
            out.append(f"- {a}")
    else:
        out.append("- 考试日期与每日可用时长由用户提供。")
    out.append(f"- 计划按知识点优先级和前置依赖排序；范围外内容不占主计划。")
    out.append("")
    out.append("## 2. 计划表")
    out.append("")
    out.extend(lines)
    out.append("")
    out.append("## 3. 范围外内容")
    out.append("")
    if out_scope:
        out.append("| 知识点 | 章节 | 优先级 | 处理 |")
        out.append("|---|---|---|---|")
        for k in out_scope:
            out.append(f"| {k['title']} | {k['section']} | {k['priority']} | 已写入讲义，标 out-of-scope；不占主计划 |")
    else:
        out.append("- 未发现明确的范围外内容；如考试范围有排除项，请补充到 `exam_profile.json`。")
    out.append("")
    out.append("## 4. 时间不足时的保底方案")
    out.append("")
    out.append("- 只做 A 级知识点 + 速查表 + 自测错题；B/C 级只看结论。")
    out.append("- 计算题优先练 A 级例题的变式，不做新题。")
    out.append("- 考前最后一天不再开新知识点，只回顾错题和公式条件。")
    out.append("")
    if unscheduled:
        out.append("### 未排入/被压缩的任务")
        out.append("")
        out.append("| 知识点 | 章节 | 优先级 | 预计 | 原因 |")
        out.append("|---|---|---|---|---|")
        for k in unscheduled:
            reason = "时间不足，已部分压缩" if k.get("partial") else "时间不足，未排入"
            out.append(f"| {k['title']} | {k['section']} | {k['priority']} | {k['est_hours']:.1f} h | {reason} |")
        out.append("")
    out.append("## 5. 每日检查")
    out.append("")
    out.append("- [ ] 今天的目标知识点能用自己的话讲一遍")
    out.append("- [ ] 例题遮住答案能独立做出来")
    out.append("- [ ] 自测错题已记录，并知道错在哪个概念/步骤")
    out.append("- [ ] 明天要用的公式/条件已能在速查表定位")
    out.append("")
    out.append("## 6. 来源")
    out.append("")
    out.append("考试信息来自 `.review/exam_profile.json`；知识点与优先级来自 `.review/knowledge_points.csv` 和 `outline.md`。")
    out.append("未提供的日期/时长按本文件“假设”处理，不虚构用户时间安排。")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="生成复习计划")
    ap.add_argument("--work", default=".review")
    ap.add_argument("--out", default=".review/content/93-review-plan.md")
    ap.add_argument("--today", default=None, help="覆盖今天日期 YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    profile = load_profile(work)
    kps = load_kps(work)
    today = parse_date(args.today) if args.today else None
    text = build_plan(profile, kps, today)

    if args.dry_run:
        print(text)
        return 0

    out = Path(args.out)
    if not out.is_absolute():
        out = (work.parent / out).resolve() if str(out).startswith(".review") else (Path.cwd() / out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    log(f"[plan] {len(kps)} 个知识点 -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
