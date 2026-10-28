#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest.py — 课程资料提取器

用法:
    python ingest.py --input <文件或目录...> --out .review [--dpi 120] [--dry-run]

产物:
    .review/manifest.json     每个输入页的文本、图片、备注、媒体
    .review/outline_seed.md   逐页索引，供建大纲
    .review/coverage.csv      每一页 -> 讲义章节（初始为空）
    .review/slides/*.png      每页渲染图
    .review/media/*           抽出的图片/视频/关键帧
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

SUPPORTED = {
    ".pptx", ".ppt", ".pdf", ".docx", ".doc", ".md", ".txt",
    ".png", ".jpg", ".jpeg", ".webp", ".bmp",
}
SKIP_DIRS = {".review", "course-review", "__pycache__", ".git", ".claude", "node_modules"}


# ---------------------------------------------------------------- utilities
def log(msg: str) -> None:
    print(msg, flush=True)


def slugify(name: str, maxlen: int = 40) -> str:
    name = Path(name).stem
    name = re.sub(r"[^\w一-鿿]+", "-", name, flags=re.UNICODE)
    name = name.strip("-").lower()
    return (name or "doc")[:maxlen]


def unique_prefix(base: str, used: set[str]) -> str:
    p = base
    n = 2
    while p in used:
        p = f"{base}-{n}"
        n += 1
    used.add(p)
    return p


def scan_inputs(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser().resolve()
        if not p.exists():
            log(f"[warn] 不存在，跳过: {p}")
            continue
        if p.is_file():
            found.append(p)
        else:
            for f in sorted(p.rglob("*")):
                if not f.is_file():
                    continue
                if f.name.startswith("~$"):
                    continue
                if f.name == "course-review.md":
                    continue
                if any(part in SKIP_DIRS for part in f.parts):
                    continue
                if f.suffix.lower() in SUPPORTED:
                    found.append(f)
    # de-duplicate, preserve order
    seen = set()
    out = []
    for f in found:
        key = str(f).lower()
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def ensure_dirs(out: Path) -> None:
    for d in ("slides", "media", "content", "figures"):
        (out / d).mkdir(parents=True, exist_ok=True)


def rel(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


# ---------------------------------------------------------------- pptx text
def _iter_shapes(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_shapes(sh.shapes)
        else:
            yield sh


def _slide_text(slide) -> tuple[str, str]:
    """Return (title, body_text)."""
    from pptx.enum.shapes import PP_PLACEHOLDER

    title = ""
    chunks: list[str] = []
    for sh in _iter_shapes(slide.shapes):
        if getattr(sh, "has_table", False) and sh.has_table:
            rows = []
            for row in sh.table.rows:
                cells = []
                for cell in row.cells:
                    cells.append((cell.text or "").replace("\n", " ").strip())
                rows.append(" | ".join(cells))
            if rows:
                chunks.append("\n".join(rows))
            continue
        if not getattr(sh, "has_text_frame", False) or not sh.has_text_frame:
            continue
        is_title = False
        try:
            if sh.is_placeholder and sh.placeholder_format.type in (
                PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE
            ):
                is_title = True
        except Exception:
            pass
        lines = []
        for para in sh.text_frame.paragraphs:
            t = "".join(run.text for run in para.runs).strip()
            if not t and para.text.strip():
                t = para.text.strip()
            if t:
                lines.append(t)
        text = "\n".join(lines).strip()
        if not text:
            continue
        if is_title and not title:
            title = text.replace("\n", " ")
        else:
            chunks.append(text)
    return title, "\n".join(chunks).strip()


def _notes(slide) -> str:
    try:
        if slide.has_notes_slide:
            return (slide.notes_slide.notes_text_frame.text or "").strip()
    except Exception:
        pass
    return ""


def _extract_pptx_media(path: Path, media_dir: Path, prefix: str) -> list[str]:
    """Extract embedded images and videos from the pptx zip."""
    import zipfile

    out: list[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if not name.startswith("ppt/media/"):
                    continue
                ext = Path(name).suffix.lower()
                if ext not in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".mp4", ".mov", ".avi", ".mkv", ".wmv"}:
                    continue
                base = f"{prefix}-{Path(name).stem}{ext}"
                dest = media_dir / base
                if not dest.exists():
                    dest.write_bytes(z.read(name))
                out.append(rel(dest, media_dir.parent))
    except Exception as e:
        log(f"[warn] 抽取内嵌媒体失败 {path.name}: {e}")
    return out


def _pptx_to_pdf_libreoffice(src: Path, tmpdir: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmpdir), str(src)],
            check=True, capture_output=True, timeout=180,
        )
        pdf = tmpdir / (src.stem + ".pdf")
        return pdf if pdf.exists() else None
    except Exception as e:
        log(f"[warn] LibreOffice 转换失败: {e}")
        return None


def _render_pdf_pages(pdf: Path, out_dir: Path, prefix: str, dpi: int) -> list[Path]:
    import pymupdf

    doc = pymupdf.open(str(pdf))
    paths = []
    for i, page in enumerate(doc, 1):
        dest = out_dir / f"{prefix}-{i:03d}.png"
        pix = page.get_pixmap(dpi=dpi)
        pix.save(str(dest))
        paths.append(dest)
    doc.close()
    return paths


def _render_pptx_com(src: Path, out_dir: Path, prefix: str, width_px: int, height_px: int) -> list[Path] | None:
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore
    except Exception:
        return None

    tmpdir = Path(tempfile.mkdtemp(prefix="cer-ppt-"))
    tmp_pptx = tmpdir / (src.stem + ".pptx")
    try:
        shutil.copy2(src, tmp_pptx)
    except Exception:
        tmp_pptx = src

    app = None
    pres = None
    try:
        app = win32com.client.Dispatch("PowerPoint.Application")
        pres = app.Presentations.Open(str(tmp_pptx), ReadOnly=True, Untitled=False, WithWindow=False)
        paths = []
        for i, slide in enumerate(pres.Slides, 1):
            dest = out_dir / f"{prefix}-{i:03d}.png"
            slide.Export(str(dest), "PNG", width_px, height_px)
            if dest.exists():
                paths.append(dest)
        return paths if paths else None
    except Exception as e:
        log(f"[warn] PowerPoint COM 渲染失败 {src.name}: {e}")
        return None
    finally:
        try:
            if pres is not None:
                pres.Close()
        except Exception:
            pass
        try:
            if app is not None:
                app.Quit()
        except Exception:
            pass
        shutil.rmtree(tmpdir, ignore_errors=True)


def _convert_ppt_to_pptx(src: Path, tmpdir: Path) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore

        app = win32com.client.Dispatch("PowerPoint.Application")
        pres = app.Presentations.Open(str(src), ReadOnly=True, Untitled=False, WithWindow=False)
        dest = tmpdir / (src.stem + ".pptx")
        pres.SaveAs(str(dest), 24)  # ppSaveAsOpenXMLPresentation
        pres.Close()
        app.Quit()
        return dest if dest.exists() else None
    except Exception as e:
        log(f"[warn] .ppt 转 .pptx 失败: {e}")
        return None


def extract_pptx(path: Path, out: Path, prefix: str, dpi: int) -> dict:
    from pptx import Presentation

    work = out
    media_dir = out / "media"
    slides_dir = out / "slides"

    src = path
    tmp_convert = None
    if path.suffix.lower() == ".ppt":
        tmp_convert = Path(tempfile.mkdtemp(prefix="cer-pptconv-"))
        converted = _convert_ppt_to_pptx(path, tmp_convert)
        if converted:
            src = converted
        else:
            return _pptx_without_text(path, out, prefix, dpi)

    prs = Presentation(str(src))
    w = prs.slide_width or 9144000
    h = prs.slide_height or 6858000
    width_px = 1600
    height_px = int(round(width_px * h / w))
    aspect = f"{w}:{h}"

    # 1) render
    rendered = _render_pptx_com(path, slides_dir, prefix, width_px, height_px)
    if not rendered:
        tmp_pdf_dir = Path(tempfile.mkdtemp(prefix="cer-pptx-pdf-"))
        pdf = _pptx_to_pdf_libreoffice(path, tmp_pdf_dir)
        if pdf:
            rendered = _render_pdf_pages(pdf, slides_dir, prefix, dpi)
        shutil.rmtree(tmp_pdf_dir, ignore_errors=True)
    if not rendered:
        log(f"[warn] {path.name}: 未能渲染任何页面（无 PowerPoint/LibreOffice），将只有文本层。")

    media = _extract_pptx_media(path, media_dir, prefix)

    items = []
    for i, slide in enumerate(prs.slides, 1):
        title, body = _slide_text(slide)
        notes = _notes(slide)
        image = f"slides/{prefix}-{i:03d}.png"
        has_img = (out / image).exists()
        body_clean = re.sub(r"[\s\d]+", "", body)
        items.append({
            "id": f"{prefix}-{i:03d}",
            "source": path.name,
            "source_path": str(path),
            "source_type": "pptx",
            "kind": "slide",
            "index": i,
            "title": (title or f"Slide {i}").strip()[:160],
            "text": body,
            "notes": notes,
            "image": image if has_img else "",
            "image_only": bool(has_img) and len(body_clean) < 8,
            "media": [m for m in media if re.search(rf"-{i:03d}-", m)],  # best effort
            "aspect": aspect,
        })

    if tmp_convert:
        shutil.rmtree(tmp_convert, ignore_errors=True)

    return {
        "source": path.name,
        "path": str(path),
        "type": "pptx",
        "pages": len(items),
        "rendered": sum(1 for x in items if x["image"]),
        "items": items,
    }


def _pptx_without_text(path: Path, out: Path, prefix: str, dpi: int) -> dict:
    """Fallback for .ppt when conversion fails: render only."""
    rendered = _render_pptx_com(path, out / "slides", prefix, 1600, 1200) or []
    items = []
    for i, p in enumerate(rendered, 1):
        items.append({
            "id": f"{prefix}-{i:03d}",
            "source": path.name, "source_path": str(path), "source_type": "pptx",
            "kind": "slide", "index": i, "title": f"Slide {i}", "text": "", "notes": "",
            "image": rel(p, out), "image_only": True, "media": [], "aspect": "4:3",
        })
    return {"source": path.name, "path": str(path), "type": "pptx", "pages": len(items),
            "rendered": len(items), "items": items}


# ---------------------------------------------------------------- pdf
def _pdf_title(page) -> str:
    try:
        d = page.get_text("dict")
        best = None
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                size = max(s.get("size", 0) for s in spans)
                if best is None or size > best[0]:
                    best = (size, text)
        if best:
            return best[1][:160]
    except Exception:
        pass
    return ""


def extract_pdf(path: Path, out: Path, prefix: str, dpi: int) -> dict:
    import pymupdf

    doc = pymupdf.open(str(path))
    items = []
    for i, page in enumerate(doc, 1):
        text = (page.get_text("text") or "").strip()
        title = _pdf_title(page) or (text.splitlines()[0][:160] if text else f"Page {i}")
        dest = out / "slides" / f"{prefix}-{i:03d}.png"
        page.get_pixmap(dpi=dpi).save(str(dest))
        rect = page.rect
        ratio = rect.width / rect.height if rect.height else 1
        kind = "slide" if 1.15 <= ratio <= 1.85 else "page"
        items.append({
            "id": f"{prefix}-{i:03d}",
            "source": path.name, "source_path": str(path), "source_type": "pdf",
            "kind": kind, "index": i, "title": title,
            "text": text, "notes": "",
            "image": rel(dest, out),
            "image_only": len(text) < 20,
            "media": [],
            "aspect": f"{rect.width:.0f}:{rect.height:.0f}",
        })
    doc.close()
    return {"source": path.name, "path": str(path), "type": "pdf",
            "pages": len(items), "rendered": len(items), "items": items}


# ---------------------------------------------------------------- docx
def _doc_to_docx(src: Path, tmpdir: Path) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import win32com.client  # type: ignore

        app = win32com.client.Dispatch("Word.Application")
        app.Visible = False
        doc = app.Documents.Open(str(src), ReadOnly=True)
        dest = tmpdir / (src.stem + ".docx")
        doc.SaveAs2(str(dest), 16)  # wdFormatXMLDocument
        doc.Close(False)
        app.Quit()
        return dest if dest.exists() else None
    except Exception as e:
        log(f"[warn] .doc 转 .docx 失败: {e}")
        return None


def extract_docx(path: Path, out: Path, prefix: str) -> dict:
    import docx

    src = path
    tmpdir = None
    if path.suffix.lower() == ".doc":
        tmpdir = Path(tempfile.mkdtemp(prefix="cer-doc-"))
        converted = _doc_to_docx(path, tmpdir)
        if not converted:
            raise RuntimeError("无法转换 .doc（需要 Microsoft Word）")
        src = converted

    doc = docx.Document(str(src))
    chunks: list[str] = []
    for para in doc.paragraphs:
        t = (para.text or "").strip()
        if not t:
            continue
        style = (para.style.name or "") if para.style else ""
        if style.lower().startswith("heading"):
            chunks.append(f"\n## {t}")
        else:
            chunks.append(t)
    for ti, table in enumerate(doc.tables, 1):
        rows = []
        for row in table.rows:
            rows.append(" | ".join((c.text or "").strip().replace("\n", " ") for c in row.cells))
        if rows:
            chunks.append(f"\n[表 {ti}]\n" + "\n".join(rows))

    media: list[str] = []
    media_dir = out / "media"
    try:
        for rel_id, relationship in doc.part.rels.items():
            if "image" not in relationship.reltype:
                continue
            part = relationship.target_part
            ext = Path(str(part.partname)).suffix or ".png"
            dest = media_dir / f"{prefix}-img-{len(media) + 1:02d}{ext}"
            dest.write_bytes(part.blob)
            media.append(rel(dest, out))
    except Exception as e:
        log(f"[warn] DOCX 图片抽取失败: {e}")

    text = "\n".join(chunks).strip()
    item = {
        "id": f"{prefix}-001",
        "source": path.name, "source_path": str(path), "source_type": "docx",
        "kind": "document", "index": 1,
        "title": path.stem, "text": text, "notes": "",
        "image": "", "image_only": False, "media": media, "aspect": "",
    }
    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return {"source": path.name, "path": str(path), "type": "docx",
            "pages": 1, "rendered": 0, "items": [item]}


# ---------------------------------------------------------------- text/image
def extract_text(path: Path, out: Path, prefix: str) -> dict:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            text = path.read_text(encoding=enc)
            break
        except Exception:
            continue
    else:
        text = ""
    item = {
        "id": f"{prefix}-001",
        "source": path.name, "source_path": str(path), "source_type": "text",
        "kind": "document", "index": 1,
        "title": path.stem, "text": text.strip(), "notes": "",
        "image": "", "image_only": False, "media": [], "aspect": "",
    }
    return {"source": path.name, "path": str(path), "type": "text",
            "pages": 1, "rendered": 0, "items": [item]}


def extract_image(path: Path, out: Path, prefix: str) -> dict:
    dest = out / "media" / f"{prefix}{path.suffix.lower()}"
    shutil.copy2(path, dest)
    item = {
        "id": f"{prefix}-001",
        "source": path.name, "source_path": str(path), "source_type": "image",
        "kind": "image", "index": 1,
        "title": path.stem, "text": "", "notes": "",
        "image": rel(dest, out), "image_only": True, "media": [], "aspect": "",
    }
    return {"source": path.name, "path": str(path), "type": "image",
            "pages": 1, "rendered": 1, "items": [item]}


# ---------------------------------------------------------------- video frames
def extract_video_frames(work: Path, max_frames: int = 6, every_sec: float = 2.0) -> list[str]:
    """Try to extract frames from videos in work/media. Optional dependency: cv2."""
    try:
        import cv2  # type: ignore
    except Exception:
        return []
    frames: list[str] = []
    for vid in sorted((work / "media").glob("*")):
        if vid.suffix.lower() not in {".mp4", ".mov", ".avi", ".mkv", ".wmv"}:
            continue
        cap = cv2.VideoCapture(str(vid))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        step = max(int(fps * every_sec), 1)
        idx = 0
        saved = 0
        while cap.isOpened() and saved < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                dest = work / "media" / f"{vid.stem}-frame{saved + 1:02d}.jpg"
                cv2.imwrite(str(dest), frame)
                frames.append(rel(dest, work))
                saved += 1
            idx += 1
            if total and idx >= total:
                break
        cap.release()
    return frames


# ---------------------------------------------------------------- outputs
def write_outline_seed(manifest: dict, out: Path) -> None:
    lines = ["# 逐页索引", "", "> 先用本文件搭骨架，再逐页看 `slides/` 补全。", ""]
    lines.append("## 材料清单")
    lines.append("")
    for s in manifest["sources"]:
        lines.append(f"- `{s['source']}` — {s['pages']} 页，已渲染 {s['rendered']} 页")
    lines.append("")
    for s in manifest["sources"]:
        lines.append(f"## {s['source']}")
        lines.append("")
        for it in s["items"]:
            flags = []
            if it["image_only"]:
                flags.append("图片型")
            if it["notes"]:
                flags.append("有备注")
            if it["media"]:
                flags.append(f"媒体×{len(it['media'])}")
            flag_s = f"（{'，'.join(flags)}）" if flags else ""
            lines.append(f"### {it['id']} · p.{it['index']} · {it['title']}{flag_s}")
            lines.append(f"- 图: `{it['image']}`" if it["image"] else "- 图: 无")
            if it["text"]:
                text = it["text"].replace("\n", " / ")
                lines.append(f"- 文本: {text[:600]}")
            if it["notes"]:
                lines.append(f"- 备注: {it['notes'][:400]}")
            lines.append("")
    (out / "outline_seed.md").write_text("\n".join(lines), encoding="utf-8")


def write_coverage(manifest: dict, out: Path) -> None:
    with (out / "coverage.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "index", "title", "image_only", "section", "status"])
        for s in manifest["sources"]:
            for it in s["items"]:
                w.writerow([it["id"], it["source"], it["index"], it["title"],
                            "true" if it["image_only"] else "false", "", ""])


def write_meta_if_absent(manifest: dict, out: Path) -> None:
    meta = out / "meta.json"
    if meta.exists():
        return
    course = Path(manifest["inputs"][0]).parent.name if manifest.get("inputs") else "课程复习"
    data = {
        "course": course,
        "subtitle": "考前复习讲义",
        "instructor": "",
        "term": "",
        "depth": "standard",
        "language": "zh",
        "sections": [],
        "notes": "",
        "generated": datetime.now().strftime("%Y-%m-%d"),
    }
    meta.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="课程资料提取器")
    ap.add_argument("--input", nargs="+", required=True, help="文件或目录")
    ap.add_argument("--out", default=".review", help="工作目录（默认 .review）")
    ap.add_argument("--dpi", type=int, default=120, help="PDF 渲染 DPI")
    ap.add_argument("--dry-run", action="store_true", help="只列出文件，不提取")
    args = ap.parse_args()

    files = scan_inputs(args.input)
    if not files:
        log("没有找到可处理的文件。支持: " + ", ".join(sorted(SUPPORTED)))
        return 2

    if args.dry_run:
        log(f"找到 {len(files)} 个文件：")
        for f in files:
            size = f.stat().st_size / 1024
            log(f"  [{f.suffix.lower():6s}] {f.name}  ({size:.0f} KB)")
        return 0

    out = Path(args.out).resolve()
    ensure_dirs(out)

    used: set[str] = set()
    sources = []
    for f in files:
        prefix = unique_prefix(slugify(f.name), used)
        log(f"[ingest] {f.name} -> {prefix}")
        try:
            if f.suffix.lower() in {".pptx", ".ppt"}:
                sources.append(extract_pptx(f, out, prefix, args.dpi))
            elif f.suffix.lower() == ".pdf":
                sources.append(extract_pdf(f, out, prefix, args.dpi))
            elif f.suffix.lower() in {".docx", ".doc"}:
                sources.append(extract_docx(f, out, prefix))
            elif f.suffix.lower() in {".md", ".txt"}:
                sources.append(extract_text(f, out, prefix))
            elif f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                sources.append(extract_image(f, out, prefix))
        except Exception as e:
            log(f"[error] 处理失败 {f.name}: {e}")
            sources.append({"source": f.name, "path": str(f), "type": "error",
                            "pages": 0, "rendered": 0, "items": [], "error": str(e)})

    manifest = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "inputs": [str(f) for f in files],
        "sources": sources,
        "stats": {
            "sources": len(sources),
            "items": sum(len(s["items"]) for s in sources),
            "image_only": sum(1 for s in sources for it in s["items"] if it.get("image_only")),
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    write_outline_seed(manifest, out)
    write_coverage(manifest, out)
    write_meta_if_absent(manifest, out)

    frames = extract_video_frames(out)
    if frames:
        manifest["video_frames"] = frames
        (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        with (out / "outline_seed.md").open("a", encoding="utf-8") as f:
            f.write("\n## 视频关键帧\n\n")
            f.write("> PPT 内嵌视频的画面，需结合对应页一起看。\n\n")
            for fr in frames:
                f.write(f"- `{fr}`\n")
        log(f"[ingest] 视频关键帧 {len(frames)} 张 -> media/（已写入 outline_seed.md）")

    st = manifest["stats"]
    log("")
    log(f"完成：{st['sources']} 个来源，{st['items']} 页/条目，其中图片型 {st['image_only']}。")
    log(f"工作目录：{out}")
    log("下一步：读 outline_seed.md + slides/*.png，写 outline.md，填 coverage.csv。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
