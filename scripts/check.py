#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check.py — 复习包质检

用法:
    python check.py --work .review --out course-review

检查:
    - 覆盖：非 skip 内容页 100% 归节；待核对项有清单
    - 讲义：来源、公式、占位符、图注、范围外标记
    - 自测：Q/A 编号、英文题干、中文解析、英文答案、题目/答案分离
    - 计划：假设、每日时长、20% 自测/错题、范围外、保底方案
    - PDF：中文、公式、图片、A4、空白页；自测 PDF 分离
    - 源文件包：content/figures/meta/scripts/templates/assets/README
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, str]] = []
        self.fail = 0
        self.warn = 0

    def ok(self, title, detail=""):
        self.rows.append(("PASS", title, detail))

    def wa(self, title, detail=""):
        self.warn += 1
        self.rows.append(("WARN", title, detail))

    def bad(self, title, detail=""):
        self.fail += 1
        self.rows.append(("FAIL", title, detail))

    def render(self) -> str:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}
        out = ["# 质检报告", "", f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
        out.append(f"**结论：{'不通过' if self.fail else '通过'}** — "
                   f"{self.fail} 项失败，{self.warn} 项警告。")
        out.append("")
        for level, title, detail in self.rows:
            out.append(f"- {icon[level]} **{title}**" + (f"：{detail}" if detail else ""))
        return "\n".join(out) + "\n"


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def content_files(work: Path, meta: dict) -> list[Path]:
    cdir = work / "content"
    if not cdir.exists():
        return []
    names = meta.get("sections") or []
    files = [cdir / n for n in names if (cdir / n).exists()]
    if not files:
        files = sorted(p for p in cdir.glob("*.md") if not p.name.startswith("."))
    return files


def title_of(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return path.stem
    m = re.search(r"^---\s*\n(.*?)\n---", text, flags=re.S)
    if m:
        t = re.search(r"^title:\s*(.+)$", m.group(1), flags=re.M)
        if t:
            return t.group(1).strip().strip("\"'")
    return path.stem


def find_content(work: Path, preferred: str, keywords: list[str]) -> Path | None:
    cdir = work / "content"
    p = cdir / preferred
    if p.exists():
        return p
    for f in sorted(cdir.glob("*.md")):
        name = f.name.lower()
        title = title_of(f).lower()
        if any(k.lower() in name or k.lower() in title for k in keywords):
            return f
    return None


def strip_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def check_math(text: str) -> tuple[bool, str]:
    t = strip_code(text).replace(r"\$", "")
    if t.count("$$") % 2:
        return False, "`$$` 数量为奇数"
    t2 = re.sub(r"\$\$.*?\$\$", "", t, flags=re.S)
    if t2.count("$") % 2:
        return False, "`$` 数量为奇数"
    return True, ""


def pdf_text(path: Path) -> str:
    try:
        import pymupdf
        d = pymupdf.open(str(path))
        text = "\n".join(d[i].get_text("text") or "" for i in range(d.page_count))
        d.close()
        return text
    except Exception:
        return ""


def pdf_pages(path: Path) -> int:
    try:
        import pymupdf
        d = pymupdf.open(str(path))
        n = d.page_count
        d.close()
        return n
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="复习包质检")
    ap.add_argument("--work", default=".review")
    ap.add_argument("--out", default="course-review")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    out = Path(args.out).resolve()
    r = Report()

    meta = read_json(work / "meta.json")
    profile = read_json(work / "exam_profile.json")
    files = content_files(work, meta)

    if not files:
        r.bad("内容文件", f"{work / 'content'} 下没有 Markdown")
    else:
        r.ok("内容文件", f"{len(files)} 个")

    # ---------------------------------------------------------------- required sections
    required = {
        "导读": ("00-guide.md", ["导读", "使用说明"]),
        "知识地图": ("01-knowledge-map.md", ["知识地图", "地图"]),
        "速查": ("90-quick-reference.md", ["速查", "quick reference"]),
        "英文自测题": ("91-self-test.md", ["自测题", "self-test"]),
        "自测答案": ("92-self-test-answers.md", ["答案", "answers"]),
        "复习计划": ("93-review-plan.md", ["复习计划", "复习安排"]),
        "覆盖报告": ("94-coverage.md", ["材料覆盖", "覆盖与待核对", "coverage"]),
    }
    found: dict[str, Path | None] = {}
    for label, (preferred, keys) in required.items():
        p = find_content(work, preferred, keys)
        found[label] = p
        if p:
            r.ok(f"章节：{label}", p.name)
        else:
            r.bad(f"章节：{label}", "缺失")

    # ---------------------------------------------------------------- coverage
    rows = None
    cov_p = work / "coverage.csv"
    if cov_p.exists():
        with cov_p.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        r.bad("coverage.csv", "文件不存在")

    if rows is not None:
        covered, missing, skipped, verify = [], [], [], []
        for row in rows:
            sec = (row.get("section") or "").strip()
            status = (row.get("status") or "").strip()
            low = status.lower()
            if sec.lower() in {"skip", "略过", "不覆盖"} or low.startswith("skip"):
                skipped.append(row)
            elif "to-verify" in low or "to_verify" in low or "待核" in low or sec.lower() in {"to-verify", "to_verify", "待核"}:
                verify.append(row)
            elif not sec:
                missing.append(row)
            else:
                covered.append(row)
        denom = len(covered) + len(missing) + len(verify)
        ratio = (len(covered) / denom * 100) if denom else 100.0
        detail = f"{len(covered)}/{denom} 已确认归节（{ratio:.1f}%），跳过 {len(skipped)}，待核对 {len(verify)}"
        if missing:
            r.bad("内容页覆盖", detail)
        else:
            r.ok("内容页覆盖", detail)
        if missing:
            ids = ", ".join(f"{m.get('source','?')} p.{m.get('index','?')}" for m in missing[:20])
            r.bad("未归节页面", ids + (" …" if len(missing) > 20 else ""))
        for s in skipped:
            if not (s.get("status") or "").strip():
                r.bad("跳过页缺少理由", f"{s.get('source')} p.{s.get('index')}")
        if verify:
            tv = work / "TO_VERIFY.md"
            if not tv.exists() or not tv.read_text(encoding="utf-8").strip():
                r.bad("待核对页无清单", f"{len(verify)} 页标 to-verify，但 TO_VERIFY.md 缺失/为空")
            else:
                r.ok("待核对页", f"{len(verify)} 页，已登记 TO_VERIFY.md")

    cov_md = found.get("覆盖报告")
    if cov_md:
        ct = cov_md.read_text(encoding="utf-8")
        if "确认覆盖率" in ct and "未覆盖页" in ct:
            r.ok("覆盖报告内容", "含总览/未覆盖/待核对")
        else:
            r.bad("覆盖报告内容", "缺少总览/未覆盖/待核对")

    # ---------------------------------------------------------------- content
    total_math_bad = 0
    no_source = []
    placeholder_hits = 0
    pending = 0
    image_no_caption = 0
    outscope_marker = False
    for f in files:
        text = f.read_text(encoding="utf-8")
        ok, msg = check_math(text)
        if not ok:
            total_math_bad += 1
            r.bad(f"公式定界符：{f.name}", msg)
        # 主章节要求来源；导语/地图/速查/自测/计划/覆盖不强制
        aux = re.match(r"^(00|01|90|91|92|93|94)", f.name)
        if not aux and not re.search(r"^#{2,4}\s*(?:[\d.]+\s*)?来源|^\*\*来源\*\*|^来源[:：]", text, flags=re.M):
            no_source.append(f.name)
        for pat in (r"\bTODO\b", r"\bTBD\b", r"\bFIXME\b", r"\bXXX\b", r"lorem ipsum", r"待补"):
            n = len(re.findall(pat, text, flags=re.I))
            if n:
                placeholder_hits += n
                r.wa(f"占位符：{f.name}", f"`{pat}` × {n}")
        pending += text.count("【待核】")
        if "out-of-scope" in text or "outscope" in text:
            outscope_marker = True
        # 图注：图片后 3 行内应有 * 或 图
        lines = text.splitlines()
        for i, ln in enumerate(lines):
            if re.search(r"!\[[^\]]*\]\([^)]+\)", ln):
                window = "\n".join(lines[i + 1:i + 4])
                if not re.search(r"^\s*\*|图注|图\s*\d", window, flags=re.M):
                    image_no_caption += 1

    if total_math_bad == 0:
        r.ok("公式定界符", "全部成对")
    if no_source:
        r.bad("来源引用缺失", "、".join(no_source))
    else:
        r.ok("来源引用", "主章节都有")
    if pending:
        r.wa("待核内容", f"{pending} 处 `【待核】`，交付时需说明")
    if image_no_caption:
        r.wa("图注", f"{image_no_caption} 张图缺少中文图注")
    else:
        r.ok("图注", "图片均有说明")

    all_content = "\n".join(f.read_text(encoding="utf-8") for f in files)
    if "必考" in all_content and not (profile.get("emphasized") or profile.get("scope")):
        r.wa("必考表述", "未提供明确范围/强调，但正文出现“必考”；请确认依据或改为“重点/高频”")

    kp_p = work / "knowledge_points.csv"
    kp_rows = []
    if kp_p.exists():
        with kp_p.open("r", encoding="utf-8-sig", newline="") as f:
            kp_rows = list(csv.DictReader(f))
    if not kp_rows:
        r.bad("knowledge_points.csv", "缺失或为空")
    else:
        r.ok("知识点表", f"{len(kp_rows)} 条")
        out_of_scope = [x for x in kp_rows if str(x.get("in_scope", "")).lower() in {"false", "0", "no", "否", "out"}]
        if out_of_scope and not outscope_marker:
            r.bad("范围外标记", "knowledge_points 有 out-of-scope，但讲义没有 out-of-scope 标记")

    # ---------------------------------------------------------------- self-test
    qf = found.get("英文自测题")
    af = found.get("自测答案")
    bank_p = out / "self-test" / "bank.json"
    if qf and af:
        selftest = Path(__file__).resolve().parent / "selftest.py"
        try:
            proc = subprocess.run(
                [sys.executable, str(selftest), "--questions", str(qf), "--answers", str(af),
                 "--out", str(bank_p), "--check"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            if proc.returncode != 0:
                tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-8:]
                r.bad("自测题校验", "；".join(tail))
            else:
                r.ok("自测题校验", "编号、语言、来源通过")
        except Exception as e:
            r.bad("自测题校验", f"运行 selftest.py 失败: {e}")

        qt = qf.read_text(encoding="utf-8")
        if "English answer" in qt or "中文思路" in qt:
            r.bad("题目/答案分离", "题目文件含答案/解析")
        else:
            r.ok("题目/答案分离", "题目文件不含答案")

    if bank_p.exists():
        try:
            bank = json.loads(bank_p.read_text(encoding="utf-8"))
            if not isinstance(bank, list) or not bank:
                r.bad("bank.json", "为空或格式错误")
            else:
                missing_fields = [
                    x.get("id", "?") for x in bank
                    if not all(x.get(k) for k in ("id", "question_en", "answer_en", "analysis_zh", "source"))
                ]
                if missing_fields:
                    r.bad("bank.json 字段", "缺字段: " + ", ".join(missing_fields[:10]))
                else:
                    r.ok("bank.json", f"{len(bank)} 题，字段完整")
                if len(bank) < 10:
                    r.wa("自测题数量", f"{len(bank)} 题；2–3 讲建议 15–30 题")
        except Exception as e:
            r.bad("bank.json", f"解析失败: {e}")
    else:
        r.bad("bank.json", "不存在")

    # ---------------------------------------------------------------- plan
    plan_p = found.get("复习计划")
    if plan_p:
        pt = plan_p.read_text(encoding="utf-8")
        checks = {
            "假设": "假设" in pt,
            "计划表": "计划表" in pt,
            "自测/错题": "自测" in pt and ("错题" in pt or "回顾" in pt),
            "范围外": "范围外" in pt,
            "保底方案": "保底" in pt,
        }
        missing_checks = [k for k, v in checks.items() if not v]
        if missing_checks:
            r.bad("复习计划结构", "缺少: " + "、".join(missing_checks))
        else:
            r.ok("复习计划结构", "假设/计划表/自测/范围外/保底齐全")

        if not profile.get("exam_date"):
            if "默认按今天起 7 天" not in pt:
                r.wa("计划假设", "未提供考试日期，但计划未写“默认按今天起 7 天”")
        if not profile.get("daily_hours"):
            if "未提供每日可用时长" not in pt:
                r.wa("计划假设", "未提供每日时长，但计划未说明")
        if not profile.get("scope"):
            if "未提供考试范围" not in pt:
                r.wa("计划假设", "未提供范围，但计划未说明")

    # ---------------------------------------------------------------- HTML
    index = out / "index.html"
    if not index.exists():
        r.bad("index.html", "不存在")
    else:
        doc = index.read_text(encoding="utf-8")
        leftovers = re.findall(r"<!--(?:TITLE|COURSE|SUBTITLE|TOC|SIDE_META|COVER|EXAM_MAP|CONTENT)-->", doc)
        if leftovers:
            r.bad("模板占位符未替换", "、".join(sorted(set(leftovers))))
        else:
            r.ok("模板占位符", "全部替换")
        chapters = len(re.findall(r'<section class="chapter"', doc))
        if chapters == len(files):
            r.ok("章节渲染", f"{chapters} 节")
        else:
            r.bad("章节渲染", f"HTML {chapters} 节，内容文件 {len(files)} 个")
        hrefs = re.findall(r'href="#([^"]+)"', doc)
        ids = set(re.findall(r'id="([^"]+)"', doc))
        broken = sorted({h for h in hrefs if h not in ids})
        if broken:
            r.wa("目录锚点", "、".join(broken[:10]) + (" …" if len(broken) > 10 else ""))
        else:
            r.ok("目录锚点", f"{len(set(hrefs))} 个全部可达")
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', doc)
        missing_imgs = [s for s in imgs if not s.startswith(("http", "data:")) and not (out / s).exists()]
        if missing_imgs:
            r.bad("图片引用", "、".join(missing_imgs[:10]))
        else:
            r.ok("图片引用", f"{len(imgs)} 张全部存在")
        if re.search(r"https?://cdn\.", doc):
            r.wa("外部依赖", "HTML 仍引用 CDN，离线可能失效")
        if 'class="exam-map"' in doc:
            r.ok("考试地图", "存在")
        else:
            r.wa("考试地图", "未生成")

    # ---------------------------------------------------------------- PDF
    pdf = out / "course-review.pdf"
    if not pdf.exists():
        r.bad("主 PDF", "不存在")
    else:
        try:
            import pymupdf
            d = pymupdf.open(str(pdf))
            pages = d.page_count
            texts = [d[i].get_text("text") or "" for i in range(pages)]
            blank = sum(1 for t in texts if len(t.strip()) < 10)
            size = d[0].rect
            all_text = "\n".join(texts)
            imgs = sum(len(d[i].get_images(full=True)) for i in range(pages))
            d.close()
            if pages <= 0:
                r.bad("主 PDF", "页数为 0")
            elif blank > max(2, pages * 0.2):
                r.wa("PDF 空白页", f"{blank}/{pages} 页几乎无文本")
            else:
                r.ok("主 PDF", f"{pages} 页，{size.width:.0f}×{size.height:.0f} pt")
            if abs(size.width - 595) > 25 or abs(size.height - 842) > 25:
                r.wa("PDF 纸张", "不是标准 A4")
            if len(re.findall(r"[一-鿿]", all_text)) < 500:
                r.wa("PDF 中文", "中文字符偏少，检查字体/编码")
            else:
                r.ok("PDF 中文", "可提取")
            if all_text.count("$") > 0 or re.search(r"\\[a-zA-Z]+", all_text):
                r.bad("PDF 公式", "文本层仍有原始 LaTeX")
            else:
                r.ok("PDF 公式", "无原始 LaTeX")
            if imgs <= 0:
                r.wa("PDF 图片", "未检测到嵌入图片")
            else:
                r.ok("PDF 图片", f"{imgs} 张嵌入图")
            required_titles = ["考试地图", "知识地图", "核心概念", "英文自测题", "自测答案", "复习计划", "材料覆盖"]
            missing_titles = [t for t in required_titles if t not in all_text]
            if missing_titles:
                r.wa("PDF 章节", "未检测到：" + "、".join(missing_titles))
            else:
                r.ok("PDF 章节", "考试地图/地图/速查/自测/答案/计划/覆盖齐全")
        except Exception as e:
            r.wa("PDF 检查失败", str(e))

    for name, label in (("questions.pdf", "自测题目 PDF"), ("answers.pdf", "自测答案 PDF")):
        p = out / "self-test" / name
        if not p.exists():
            r.bad(label, "不存在")
            continue
        t = pdf_text(p)
        if name == "questions.pdf":
            if "English answer" in t or "中文思路" in t:
                r.bad(label, "疑似包含答案/解析")
            else:
                r.ok(label, f"{pdf_pages(p)} 页，题目与答案分离")
        else:
            if "中文思路" not in t and "English answer" not in t:
                r.wa(label, "未检测到解析/答案标签")
            else:
                r.ok(label, f"{pdf_pages(p)} 页，含解析/答案")

    # ---------------------------------------------------------------- markdown / source
    md = out / "course-review.md"
    if md.exists():
        mt = md.read_text(encoding="utf-8")
        bad_imgs = re.findall(r"!\[[^\]]*\]\((slides/[^)]+)\)", mt)
        if bad_imgs:
            r.bad("course-review.md 图片路径", "仍指向 slides/：" + "、".join(bad_imgs[:5]))
        else:
            r.ok("course-review.md 图片路径", "无 slides/ 残留")

    src = out / "source"
    src_checks = {
        "source/content": (src / "content").is_dir() and any((src / "content").glob("*.md")),
        "source/figures": (src / "figures").is_dir(),
        "source/meta.json": (src / "meta.json").exists(),
        "source/scripts/build.py": (src / "scripts" / "build.py").exists(),
        "source/templates/report.html": (src / "templates" / "report.html").exists(),
        "source/assets/katex/katex.min.css": (
            (src / "assets" / "katex" / "katex.min.css").exists()
            or (src / "assets" / "katex" / "dist" / "katex.min.css").exists()
        ),
        "source/README.md": (src / "README.md").exists(),
    }
    missing_src = [k for k, v in src_checks.items() if not v]
    if missing_src:
        r.bad("源文件包", "缺少: " + "、".join(missing_src))
    else:
        r.ok("源文件包", "content/figures/meta/scripts/templates/assets/README 齐全")
    src_md = list((src / "content").glob("*.md")) if (src / "content").is_dir() else []
    if len(src_md) != len(files):
        r.bad("源文件包 content 数量", f"source {len(src_md)} 个，正文 {len(files)} 个")
    else:
        r.ok("源文件包 content 数量", f"{len(src_md)} 个")

    # ---------------------------------------------------------------- write
    report = r.render()
    (work / "QA_REPORT.md").write_text(report, encoding="utf-8")
    print(f"[check] {'FAIL' if r.fail else 'PASS'} — {r.fail} fail, {r.warn} warn")
    for level, title, detail in r.rows:
        if level != "PASS":
            print(f"  [{level}] {title}: {detail}")
    print(f"[check] 报告：{work / 'QA_REPORT.md'}")
    return 1 if r.fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
