#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py — 把 .review/content/*.md 组装成离线 HTML 与合并 Markdown

用法:
    python build.py --work .review --out course-review
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS = SKILL_DIR / "assets"
TEMPLATES = SKILL_DIR / "templates"


# ================================================================ markdown
class MD:
    """A small, predictable Markdown subset.

    Supports: headings, paragraphs, lists, tables, blockquotes, hr, fenced code,
    images, links, bold/italic/code, math ($...$ / $$...$$), callouts (::: name).
    """

    CALLOUTS = {
        "exam": ("div", "callout callout-exam"),
        "warn": ("div", "callout callout-warn"),
        "tip": ("div", "callout callout-tip"),
        "note": ("div", "callout callout-note"),
        "prereq": ("div", "callout callout-prereq"),
        "connect": ("div", "callout callout-connect"),
        "outscope": ("div", "callout callout-outscope"),
        "verify": ("div", "callout callout-verify"),
        "lead": ("div", "lead"),
        "answer": ("details", "answer"),
        "summary": ("div", "callout callout-note"),
    }

    def __init__(self, work: Path, out: Path):
        self.work = work
        self.out = out
        self.headings: list[dict] = []
        self.figures: dict[str, str] = {}
        self.figure_count = 0
        self.warnings: list[str] = []
        self._hid = 0
        self._store: dict[str, str] = {}
        self._store_n = 0

    # ---------------------------------------------------------- public
    def render(self, text: str, in_callout: bool = False) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = self._protect(text)
        lines = text.split("\n")
        out: list[str] = []
        i = 0
        n = len(lines)
        while i < n:
            line = lines[i]
            s = line.strip()

            if not s:
                i += 1
                continue

            # block placeholder (fenced code / display math / standalone image html)
            m = re.fullmatch(r"@@BLK(\d+)@@", s)
            if m:
                out.append(self._store.get(s, s))
                i += 1
                continue

            # callout
            m = re.match(r"^:::\s*([a-zA-Z]+)\s*$", s)
            if m:
                name = m.group(1).lower()
                body_lines = []
                i += 1
                depth = 1
                while i < n:
                    if re.match(r"^:::\s*$", lines[i].strip()):
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    elif re.match(r"^:::\s*[a-zA-Z]+\s*$", lines[i].strip()):
                        depth += 1
                    body_lines.append(lines[i])
                    i += 1
                inner = self.render("\n".join(body_lines), in_callout=True)
                tag, cls = self.CALLOUTS.get(name, ("div", "callout callout-note"))
                if tag == "details":
                    out.append(f'<details class="{cls}"><summary>查看答案</summary><div class="answer-body">{inner}</div></details>')
                elif name == "lead":
                    out.append(f'<div class="{cls}">{inner}</div>')
                else:
                    label = {
                        "exam": "考点", "warn": "易错", "tip": "提示", "note": "说明",
                        "prereq": "前置", "connect": "联系", "outscope": "范围外", "verify": "待核",
                    }.get(name, "")
                    if label and re.match(r"<p>\s*<strong>", inner):
                        label = ""
                    head = f'<div class="callout-title">{html_lib.escape(label)}</div>' if label else ""
                    out.append(f'<div class="{cls}">{head}{inner}</div>')
                continue

            # heading
            m = re.match(r"^(#{1,6})\s+(.*)$", s)
            if m:
                level = len(m.group(1))
                raw = m.group(2).strip()
                body = self.inline(raw)
                self._hid += 1
                hid = f"h-{self._hid}"
                if level <= 3:
                    self.headings.append({"level": level, "text": self.plain(raw), "id": hid})
                out.append(f'<h{level} id="{hid}">{body}</h{level}>')
                i += 1
                continue

            # hr
            if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
                out.append("<hr>")
                i += 1
                continue

            # table
            if s.startswith("|") and i + 1 < n and re.match(r"^\|?\s*:?-{2,}", lines[i + 1].strip()):
                table_lines = [line]
                i += 1
                while i < n and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i])
                    i += 1
                out.append(self.table(table_lines))
                continue

            # blockquote
            if s.startswith(">"):
                q = []
                while i < n and lines[i].strip().startswith(">"):
                    q.append(re.sub(r"^\s*>\s?", "", lines[i]))
                    i += 1
                out.append(f"<blockquote>{self.render(chr(10).join(q), in_callout=True)}</blockquote>")
                continue

            # list
            if re.match(r"^(\s*)([-*+]|\d+\.)\s+", line):
                html_list, i = self.list_block(lines, i)
                out.append(html_list)
                continue

            # paragraph
            para = [line]
            i += 1
            while i < n:
                nxt = lines[i]
                ns = nxt.strip()
                if not ns:
                    break
                if re.match(r"^(#{1,6})\s+", ns) or ns.startswith("|") or ns.startswith(">") \
                   or re.match(r"^:::\s*", ns) or re.fullmatch(r"@@BLK\d+@@", ns) \
                   or re.match(r"^(\s*)([-*+]|\d+\.)\s+", nxt) \
                   or re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", ns):
                    break
                para.append(nxt)
                i += 1
            out.append(f"<p>{self.inline(self.smart_join(para))}</p>")

        return "\n".join(out)

    # ---------------------------------------------------------- protect
    def _stash(self, html: str) -> str:
        key = f"@@BLK{self._store_n}@@"
        self._store_n += 1
        self._store[key] = html
        return key

    def _protect(self, text: str) -> str:
        def stash(html: str) -> str:
            return self._stash(html)

        # fenced code
        def code_repl(m):
            lang = (m.group(1) or "").strip()
            code = html_lib.escape(m.group(2))
            cls = f' class="language-{html_lib.escape(lang)}"' if lang else ""
            return stash(f"<pre><code{cls}>{code}</code></pre>")

        text = re.sub(r"```([^\n`]*)\n(.*?)```", code_repl, text, flags=re.S)

        # display math
        def dm_repl(m):
            body = html_lib.escape(m.group(1), quote=False)
            return stash(f'<div class="math-block">$${body}$$</div>')

        text = re.sub(r"\$\$(.+?)\$\$", dm_repl, text, flags=re.S)

        # inline math (avoid escaped \$ and empty)
        def im_repl(m):
            body = m.group(1)
            if not body.strip() or "\n" in body:
                return m.group(0)
            return stash(f"${html_lib.escape(body, quote=False)}$")

        text = re.sub(r"(?<!\\)\$([^$\n]+?)(?<!\\)\$", im_repl, text)
        return text

    # ---------------------------------------------------------- inline
    def inline(self, text: str) -> str:
        # inline code
        text = re.sub(r"`([^`\n]+)`", lambda m: self._stash(f"<code>{html_lib.escape(m.group(1))}</code>"), text)

        # images
        def img_repl(m):
            alt = m.group(1) or ""
            src = m.group(2).strip()
            src2 = self.copy_figure(src)
            return self._stash(
                f'<img src="{html_lib.escape(src2, quote=True)}" alt="{html_lib.escape(alt, quote=True)}" loading="lazy">'
            )

        text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", img_repl, text)

        # links
        def link_repl(m):
            label, href = m.group(1), m.group(2).strip()
            extra = ' target="_blank" rel="noopener"' if href.startswith(("http://", "https://")) else ""
            return self._stash(f'<a href="{html_lib.escape(href, quote=True)}"{extra}>{label}</a>')

        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)

        # escape remaining html
        text = html_lib.escape(text, quote=False)

        # emphasis
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
        text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)

        # restore all protected blocks (math / code / html)
        text = re.sub(r"@@BLK\d+@@", lambda m: self._store.get(m.group(0), m.group(0)), text)
        return text

    # ---------------------------------------------------------- table
    def table(self, lines: list[str]) -> str:
        rows = []
        for ln in lines:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows.append(cells)
        if len(rows) < 2:
            return ""
        header = rows[0]
        body = rows[2:] if re.match(r"^:?-{2,}", rows[1][0].strip() if rows[1] else "") else rows[1:]
        thead = "".join(f"<th>{self.inline(c)}</th>" for c in header)
        trs = []
        for r in body:
            # pad/truncate
            if len(r) < len(header):
                r = r + [""] * (len(header) - len(r))
            tds = "".join(f"<td>{self.inline(c)}</td>" for c in r[:len(header)])
            trs.append(f"<tr>{tds}</tr>")
        return f'<div class="table-wrap"><table><thead><tr>{thead}</tr></thead><tbody>{"".join(trs)}</tbody></table></div>'

    # ---------------------------------------------------------- list
    def list_block(self, lines: list[str], i: int) -> tuple[str, int]:
        first = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
        indent = len(first.group(1))
        ordered = first.group(2).endswith(".")
        start = int(first.group(2)[:-1]) if ordered else 1
        items: list[list[str]] = []
        n = len(lines)
        while i < n:
            m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", lines[i])
            if not m or len(m.group(1)) < indent or (m.group(2).endswith(".") != ordered):
                break
            if len(m.group(1)) > indent + 1:
                # nested line: append to previous item
                if items:
                    items[-1].append(lines[i].strip())
                i += 1
                continue
            items.append([m.group(3)])
            i += 1
            # continuation lines
            while i < n and lines[i].strip() and not re.match(r"^(\s*)([-*+]|\d+\.)\s+", lines[i]) \
                    and not lines[i].strip().startswith(("#", "|", ">", ":::")) \
                    and not re.fullmatch(r"@@BLK\d+@@", lines[i].strip()):
                items[-1].append(lines[i].strip())
                i += 1
        tag = "ol" if ordered else "ul"
        start_attr = f' start="{start}"' if ordered and start != 1 else ""
        lis = []
        has_task = False
        for it in items:
            content = it[0]
            extra = it[1:]
            task = (not ordered) and re.match(r"^\[([ xX])\]\s+(.*)$", content)
            if task:
                has_task = True
                done = task.group(1).lower() == "x"
                body = self.inline(task.group(2))
                if extra:
                    body += "".join(f"<br>{self.inline(x)}" for x in extra)
                lis.append(
                    f'<li class="task{" done" if done else ""}">'
                    f'<span class="cb">{"✓" if done else ""}</span><span>{body}</span></li>'
                )
            else:
                body = self.inline(content)
                if extra:
                    body += "".join(f"<br>{self.inline(x)}" for x in extra)
                lis.append(f"<li>{body}</li>")
        cls = ' class="task-list"' if has_task else ""
        return f"<{tag}{start_attr}{cls}>" + "".join(lis) + f"</{tag}>", i

    # ---------------------------------------------------------- helpers
    def copy_figure(self, src: str) -> str:
        if src.startswith(("http://", "https://", "data:")):
            return src
        if src in self.figures:
            return self.figures[src]
        candidates = [self.work / src, self.work.parent / src, Path(src)]
        found = next((p for p in candidates if p.exists()), None)
        if not found:
            self.warnings.append(f"图片不存在: {src}")
            return src
        self.figure_count += 1
        suffix = found.suffix.lower() or ".png"
        name = f"fig-{self.figure_count:03d}{suffix}"
        dest = self.out / "figures" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(found, dest)
        rel = f"figures/{name}"
        self.figures[src] = rel
        return rel

    @staticmethod
    def smart_join(lines: list[str]) -> str:
        out = ""
        for ln in lines:
            ln = ln.strip()
            if not out:
                out = ln
            elif re.search(r"[一-鿿]$", out) and re.match(r"^[一-鿿]", ln):
                out += ln
            else:
                out += " " + ln
        return out

    def plain(self, s: str) -> str:
        def tok(m):
            raw = self._store.get(m.group(0), "")
            raw = re.sub(r"<[^>]+>", " ", raw).replace("$$", "").replace("$", "")
            return " " + math_to_text(raw) + " "

        s = re.sub(r"@@BLK\d+@@", tok, s)
        s = re.sub(r"\$([^$]*)\$", lambda m: math_to_text(m.group(1)), s)
        s = s.replace("**", "").replace("~~", "").replace("*", "").replace("`", "")
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def _callout_title(inner: str) -> str:
        return ""

    @staticmethod
    def _strip_first_strong(inner: str) -> str:
        return inner


# ================================================================ frontmatter
def math_to_text(s: str) -> str:
    """Turn simple LaTeX into readable text for headings / TOC."""
    s = html_lib.unescape(s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    s = re.sub(r"\\(?:mathrm|text|operatorname|overline|boxed|mathcal|mathbb)\{([^{}]*)\}", r"\1", s)
    s = s.replace("\\left", "").replace("\\right", "")
    s = re.sub(r"\\[,;:! ]", "", s)
    greek = {
        "alpha": "α", "beta": "β", "gamma": "γ", "Gamma": "Γ", "delta": "δ",
        "Delta": "Δ", "theta": "θ", "lambda": "λ", "mu": "μ", "pi": "π",
        "rho": "ρ", "sigma": "σ", "tau": "τ", "phi": "φ", "psi": "ψ",
        "omega": "ω", "infty": "∞",
        "approx": "≈", "sim": "~", "propto": "∝", "Rightarrow": "⇒",
        "le": "≤", "ge": "≥", "ne": "≠", "times": "×", "cdot": "·", "pm": "±",
        "log": "log", "cos": "cos", "sin": "sin", "erf": "erf", "exp": "exp",
    }

    def cmd(m):
        name = m.group(1)
        return greek.get(name, name)

    s = re.sub(r"\\([A-Za-z]+)", cmd, s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("~", " ")
    return re.sub(r"\s+", " ", s).strip()


def plain_text(s: str) -> str:
    s = re.sub(r"\$[^$]*\$", "", s)
    s = re.sub(r"[*_`~]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def split_frontmatter(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, flags=re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, m.group(2)


# ================================================================ build
def load_meta(work: Path) -> dict:
    p = work / "meta.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"course": "课程复习", "subtitle": "考前复习讲义", "depth": "standard", "language": "zh"}


def collect_sections(work: Path, meta: dict) -> list[dict]:
    cdir = work / "content"
    if not cdir.exists():
        return []
    names = meta.get("sections") or []
    files = []
    if names:
        for n in names:
            p = cdir / n
            if p.exists():
                files.append(p)
    if not files:
        files = sorted(p for p in cdir.glob("*.md") if not p.name.startswith("."))
    sections = []
    for p in files:
        raw = p.read_text(encoding="utf-8")
        fm, body = split_frontmatter(raw)
        # strip first h1 if it duplicates title
        title = fm.get("title") or p.stem
        body = body.lstrip("\n")
        m = re.match(r"^#\s+(.*)\n+", body)
        if m and plain_text(m.group(1)).strip() == title.strip():
            body = body[m.end():]
        sections.append({
            "file": p.name,
            "title": title,
            "short": fm.get("short") or title[:8],
            "slides": fm.get("slides", ""),
            "weight": fm.get("weight", "★★"),
            "priority": fm.get("priority", "—"),
            "scope": fm.get("scope", "in"),
            "map": str(fm.get("map", "true")).strip().lower() not in {"false", "0", "no", "off", "否"},
            "keypoints": fm.get("keypoints", ""),
            "body": body,
        })
    return sections


def build_toc(sections: list[dict], rendered: list[dict]) -> str:
    parts = []
    for idx, (sec, r) in enumerate(zip(sections, rendered), 1):
        num = f"{idx:02d}"
        subs = [h for h in r["headings"] if h["level"] == 2][:20]
        sub_html = "".join(
            f'<a class="toc-sub-link" href="#{h["id"]}">{html_lib.escape(h["text"])}</a>'
            for h in subs
        )
        sub_wrap = f'<div class="toc-sub">{sub_html}</div>' if sub_html else ""
        parts.append(
            f'<div class="toc-group">'
            f'<a class="toc-chapter" href="#ch-{idx}" data-short="{html_lib.escape(sec["short"])}">'
            f'<span class="toc-num">{num}</span><span class="toc-label">{html_lib.escape(sec["short"])}</span></a>'
            f'{sub_wrap}</div>'
        )
    return "".join(parts)


def build_exam_map(sections: list[dict], rendered: list[dict]) -> str:
    rows = []
    for idx, (sec, r) in enumerate(zip(sections, rendered), 1):
        if not sec.get("map", True):
            continue
        h2 = [h["text"] for h in r["headings"] if h["level"] == 2][:3]
        kp = sec["keypoints"] or " · ".join(h2) or "—"
        rows.append(
            f'<tr><td><a href="#ch-{idx}">{html_lib.escape(sec["short"])}</a></td>'
            f'<td class="p">{html_lib.escape(sec["priority"])}</td>'
            f'<td class="w">{html_lib.escape(sec["weight"])}</td>'
            f'<td>{html_lib.escape(sec["slides"] or "—")}</td>'
            f'<td>{html_lib.escape(kp)}</td></tr>'
        )
    return (
        '<section class="exam-map" id="exam-map">'
        '<div class="section-kicker">EXAM MAP</div>'
        '<h2 class="map-title">考试地图</h2>'
        '<p class="map-lead">先看这张表决定时间怎么分配：优先级 A、页数多、核心考点密集的章节优先。权重来自课件信号，依据见各章开头。</p>'
        '<div class="table-wrap"><table class="map-table"><thead><tr>'
        '<th>章节</th><th>优先级</th><th>权重</th><th>覆盖页</th><th>核心考点</th>'
        '</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
        '</section>'
    ) if rows else ""


def count_slides(spec: str) -> int:
    total = 0
    for part in re.split(r"[,，;；\s]+", spec or ""):
        m = re.fullmatch(r"(\d+)\s*[-–—~]\s*(\d+)", part)
        if m:
            total += max(0, int(m.group(2)) - int(m.group(1)) + 1)
        elif part.isdigit():
            total += 1
    return total


def build_cover(meta: dict, sections: list[dict], figure_count: int, minimal: bool = False) -> str:
    course = meta.get("course", "课程复习")
    subtitle = meta.get("subtitle", "考前复习讲义")
    term = meta.get("term", "")
    instructor = meta.get("instructor", "")
    depth = {"quick": "速成", "standard": "标准", "deep": "全面"}.get(meta.get("depth", "standard"), "标准")
    gen = meta.get("generated") or datetime.now().strftime("%Y-%m-%d")
    meta_bits = [x for x in [term, instructor, f"深度：{depth}", f"生成：{gen}"] if x]
    if minimal:
        return f'''
<header class="cover cover-minimal">
  <div class="cover-kicker">COURSE REVIEW · 自测材料</div>
  <h1 class="cover-title">{html_lib.escape(course)}</h1>
  <div class="cover-sub">{html_lib.escape(subtitle)}</div>
  <div class="cover-meta">{" · ".join(html_lib.escape(x) for x in meta_bits)}</div>
</header>
'''
    stats = [
        ("章节", str(len(sections))),
        ("覆盖页", str(sum(count_slides(s["slides"]) for s in sections))),
        ("图表", str(figure_count)),
        ("模式", depth),
    ]
    stat_html = "".join(f'<div class="stat"><div class="stat-n">{v}</div><div class="stat-l">{k}</div></div>' for k, v in stats)
    return f'''
<header class="cover">
  <div class="cover-kicker">COURSE REVIEW · 考前复习讲义</div>
  <h1 class="cover-title">{html_lib.escape(course)}</h1>
  <div class="cover-sub">{html_lib.escape(subtitle)}</div>
  <div class="cover-meta">{" · ".join(html_lib.escape(x) for x in meta_bits)}</div>
  <div class="cover-stats">{stat_html}</div>
  <div class="cover-note">
    <strong>怎么用：</strong>先看「考试地图」分配时间；每节先读三句话结论，再补公式与例题；
    自测题答案默认折叠，先自己写再展开。
  </div>
</header>
'''


def build_section(idx: int, sec: dict, rendered: dict) -> str:
    meta_bits = []
    if sec["slides"]:
        meta_bits.append(f'<span class="pill">PPT p.{html_lib.escape(sec["slides"])}</span>')
    if sec["weight"] and sec["weight"] not in {"—", "-", "–"}:
        meta_bits.append(f'<span class="pill pill-weight">{html_lib.escape(sec["weight"])}</span>')
    if sec.get("priority") and sec["priority"] not in {"—", "-", "–"}:
        meta_bits.append(f'<span class="pill pill-priority">优先级 {html_lib.escape(sec["priority"])}</span>')
    if str(sec.get("scope", "in")).lower() in {"out", "false", "no", "0"}:
        meta_bits.append('<span class="pill pill-out">out-of-scope</span>')
    return (
        f'<section class="chapter" id="ch-{idx}" data-short="{html_lib.escape(sec["short"])}">'
        f'<div class="chapter-head">'
        f'<div class="chapter-num">SECTION {idx:02d}</div>'
        f'<h1 class="chapter-title">{html_lib.escape(sec["title"])}</h1>'
        f'<div class="chapter-meta">{"".join(meta_bits)}</div>'
        f'</div>'
        f'{rendered["html"]}'
        f'</section>'
    )


def copy_assets(out: Path) -> None:
    (out / "assets").mkdir(parents=True, exist_ok=True)
    src_katex = ASSETS / "katex" / "dist"
    if not src_katex.exists():
        src_katex = ASSETS / "katex"
    dst_katex = out / "assets" / "katex"
    if src_katex.exists():
        if dst_katex.exists():
            shutil.rmtree(dst_katex)
        shutil.copytree(src_katex, dst_katex)
    for name in ("style.css", "app.js"):
        src = ASSETS / name
        if src.exists():
            shutil.copy2(src, out / "assets" / name)


def main() -> int:
    ap = argparse.ArgumentParser(description="组装复习讲义")
    ap.add_argument("--work", default=".review")
    ap.add_argument("--out", default="course-review")
    ap.add_argument("--sections", nargs="+", default=None, help="只构建这些内容文件（如 91-self-test.md）")
    ap.add_argument("--title", default=None, help="覆盖封面副标题（用于自测 PDF）")
    ap.add_argument("--minimal", action="store_true", help="精简封面，不生成考试地图（用于自测 PDF）")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)

    meta = load_meta(work)
    if args.sections:
        meta["sections"] = args.sections
    if args.title:
        meta["subtitle"] = args.title
    sections = collect_sections(work, meta)
    if not sections:
        print(f"[error] 没有找到内容文件：{work / 'content'}/*.md")
        return 2

    md = MD(work, out)
    rendered: list[dict] = []
    for sec in sections:
        html = md.render(sec["body"])
        rendered.append({"html": html, "headings": list(md.headings)})
        md.headings.clear()

    cover = build_cover(meta, sections, md.figure_count, minimal=args.minimal)
    exam_map = "" if args.minimal else build_exam_map(sections, rendered)
    toc = build_toc(sections, rendered)
    body = "".join(build_section(i, s, r) for i, (s, r) in enumerate(zip(sections, rendered), 1))

    template = (TEMPLATES / "report.html").read_text(encoding="utf-8")
    title = f'{meta.get("course", "课程复习")} · {meta.get("subtitle", "考前复习讲义")}'
    side_meta = f'{len(sections)} 节 · {md.figure_count} 图 · {meta.get("depth", "standard")}'
    html_doc = (template
                .replace("<!--TITLE-->", html_lib.escape(title))
                .replace("<!--COURSE-->", html_lib.escape(meta.get("course", "课程复习")))
                .replace("<!--SUBTITLE-->", html_lib.escape(meta.get("subtitle", "考前复习讲义")))
                .replace("<!--TOC-->", toc)
                .replace("<!--SIDE_META-->", html_lib.escape(side_meta))
                .replace("<!--COVER-->", cover)
                .replace("<!--EXAM_MAP-->", exam_map)
                .replace("<!--CONTENT-->", body))
    (out / "index.html").write_text(html_doc, encoding="utf-8")

    # merged markdown
    parts = [f'# {meta.get("course", "课程复习")} · {meta.get("subtitle", "考前复习讲义")}', ""]
    if meta.get("notes"):
        parts += [f'> {meta["notes"]}', ""]
    for sec in sections:
        body = sec["body"].strip()
        for src, dst in md.figures.items():
            body = body.replace(f"]({src})", f"]({dst})")
        parts += [f'## {sec["title"]}', "", body, ""]
    (out / "course-review.md").write_text("\n".join(parts), encoding="utf-8")

    copy_assets(out)

    report = {
        "sections": len(sections),
        "figures": md.figure_count,
        "warnings": md.warnings,
        "html": str(out / "index.html"),
    }
    (work / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build] {len(sections)} 节，{md.figure_count} 张图 -> {out / 'index.html'}")
    for w in md.warnings:
        print(f"[warn] {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
