#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
print_pdf.py — 用 Edge/Chrome 无头模式把 index.html 打印成 A4 PDF

用法:
    python print_pdf.py --html course-review/index.html --out course-review/course-review.pdf
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CANDIDATES = [
    # Windows
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    # macOS
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def find_browser() -> str | None:
    env = os.environ.get("CER_BROWSER")
    if env and Path(env).exists():
        return env
    for c in CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        p = shutil.which(name)
        if p:
            return p
    return None


def file_url(html: Path) -> str:
    return html.resolve().as_uri() + "?print=1"


def main() -> int:
    ap = argparse.ArgumentParser(description="HTML -> A4 PDF")
    ap.add_argument("--html", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--budget", type=int, default=20000, help="virtual-time-budget(ms)")
    args = ap.parse_args()

    html = Path(args.html).resolve()
    out = Path(args.out).resolve()
    if not html.exists():
        print(f"[error] HTML 不存在: {html}")
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    browser = find_browser()
    if not browser:
        print("[error] 未找到 Edge/Chrome。可设置环境变量 CER_BROWSER 指向浏览器可执行文件。")
        return 3

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--virtual-time-budget={args.budget}",
        f"--print-to-pdf={out}",
        file_url(html),
    ]
    print(f"[pdf] {Path(browser).name} -> {out.name}")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print("[error] 浏览器打印超时")
        return 4

    # Edge/Chrome sometimes returns non-zero even when the PDF is written.
    if not out.exists() or out.stat().st_size < 1000:
        err = (proc.stderr or proc.stdout or "").strip()
        print(f"[error] PDF 未生成。退出码 {proc.returncode}")
        if err:
            print(err[-1500:])
        return 5

    try:
        import pymupdf
        doc = pymupdf.open(str(out))
        pages = doc.page_count
        text_len = sum(len(doc[i].get_text("text") or "") for i in range(min(pages, 10)))
        doc.close()
    except Exception:
        pages, text_len = -1, -1

    print(f"[pdf] 完成：{pages} 页，{out.stat().st_size / 1024:.0f} KB，前 10 页文本 {text_len} 字")
    if pages == 0:
        print("[error] PDF 页数为 0")
        return 6
    if 0 <= text_len < 200:
        print("[warn] PDF 文本层很薄，可能是纯图片或打印失败，请检查")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
