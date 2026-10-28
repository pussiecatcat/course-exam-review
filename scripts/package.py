#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
package.py — 打包可重新编译的源文件

用法:
    python package.py --work .review --out course-review [--verify]

生成:
    course-review/source/
      content/ figures/ meta.json exam_profile.json knowledge_points.csv
      outline.md coverage.csv TO_VERIFY.md
      scripts/ templates/ assets/
      README.md
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return True


def unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        used.add(name)
        return name
    p = Path(name)
    stem, suffix = p.stem, p.suffix
    i = 2
    while f"{stem}-{i}{suffix}" in used:
        i += 1
    out = f"{stem}-{i}{suffix}"
    used.add(out)
    return out


IMG_RE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\s+\"[^\"]*\")?(\))")


def rewrite_images(md_text: str, work: Path, out: Path, src_figures: Path,
                   used: set[str], mapping: dict[str, str], warnings: list[str]) -> str:
    def repl(m):
        prefix, src, title, suffix = m.group(1), m.group(2), m.group(3) or "", m.group(4)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        candidates = [work / src, out / src, work.parent / src]
        found = next((p for p in candidates if p.exists()), None)
        if not found:
            warnings.append(f"图片不存在: {src}")
            return m.group(0)
        key = str(found.resolve())
        if key not in mapping:
            name = unique_name(found.name, used)
            dest = src_figures / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(found, dest)
            mapping[key] = name
        name = mapping[key]
        return f"{prefix}figures/{name}{title}{suffix}"

    return IMG_RE.sub(repl, md_text)


def write_readme(source: Path, course: str) -> None:
    text = f"""# {course} · 复习讲义源文件

## 目录

- `content/`：分章 Markdown（可编辑）
- `figures/`：讲义引用的图片
- `meta.json`：课程名、副标题、章节顺序、深度
- `exam_profile.json`：考试日期、每日时长、范围、题型、强调内容
- `knowledge_points.csv`：知识点、优先级、依赖、预计学时
- `outline.md`：知识地图
- `coverage.csv`：每一页 → 讲义哪一节
- `TO_VERIFY.md`：待核对清单
- `scripts/`：build / print_pdf / check / plan / coverage / selftest
- `templates/report.html`：HTML 模板
- `assets/`：样式、脚本、KaTeX（离线可用）

## 重新编译

在本目录下：

```bash
python scripts/build.py --work . --out ../rebuilt
python scripts/print_pdf.py --html ../rebuilt/index.html --out ../rebuilt/course-review.pdf
python scripts/check.py --work . --out ../rebuilt
```

单独编译自测题/答案（题目与答案分开）：

```bash
python scripts/build.py --work . --out ./build-questions --sections 91-self-test.md --title "英文自测题（只有题目）" --minimal
python scripts/print_pdf.py --html ./build-questions/index.html --out ../rebuilt/self-test/questions.pdf
python scripts/build.py --work . --out ./build-answers --sections 92-self-test-answers.md --title "自测答案与解析" --minimal
python scripts/print_pdf.py --html ./build-answers/index.html --out ../rebuilt/self-test/answers.pdf
```

单独编译速查（可选）：

```bash
python scripts/build.py --work . --out ./build-quick --sections 90-quick-reference.md --title "核心概念与公式速查" --minimal
python scripts/print_pdf.py --html ./build-quick/index.html --out ../rebuilt/quick-reference.pdf
```

要求：Python 3.10+，`pymupdf`、`python-pptx`、`python-docx`、`Pillow`；导出 PDF 需要 Edge 或 Chrome。

## 修改内容

1. 改讲义：编辑 `content/*.md`，图片路径用 `figures/...`。
2. 换图：把新图放进 `figures/`，在 Markdown 里引用。
3. 改章节顺序：编辑 `meta.json` 的 `sections`。
4. 改复习计划：编辑 `exam_profile.json` / `knowledge_points.csv`，然后：
   ```bash
   python scripts/plan.py --work . --out content/93-review-plan.md
   ```
5. 改覆盖：编辑 `coverage.csv`，然后：
   ```bash
   python scripts/coverage.py --work . --out content/94-coverage.md --strict
   ```
6. 改自测：编辑 `content/91-self-test.md` / `92-self-test-answers.md`，然后：
   ```bash
   python scripts/selftest.py --questions content/91-self-test.md --answers content/92-self-test-answers.md --out self-test/bank.json --check
   ```

## 注意

- `build.py` 会把 `content/` 里的图片复制到输出目录；不要删 `figures/`。
- `meta.json` 的 `sections` 顺序决定讲义章节顺序。
- 重新编译后请重跑 `check.py`，确认公式、图片、目录、交叉引用。
"""
    (source / "README.md").write_text(text, encoding="utf-8")


def verify(source: Path) -> bool:
    build = source / "scripts" / "build.py"
    if not build.exists():
        log("[verify] 缺少 scripts/build.py")
        return False
    tmp = source / ".build-test"
    if tmp.exists():
        shutil.rmtree(tmp)
    try:
        proc = subprocess.run(
            [sys.executable, str(build), "--work", str(source), "--out", str(tmp)],
            capture_output=True, text=True, timeout=120,
        )
        ok = proc.returncode == 0 and (tmp / "index.html").exists()
        if not ok:
            log("[verify] 构建失败")
            if proc.stdout:
                log(proc.stdout[-1000:])
            if proc.stderr:
                log(proc.stderr[-1000:])
        return ok
    except Exception as e:
        log(f"[verify] 构建异常: {e}")
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="打包可重新编译的源文件")
    ap.add_argument("--work", default=".review")
    ap.add_argument("--out", default="course-review")
    ap.add_argument("--skill", default=None, help="skill 目录；默认用本脚本的上级目录")
    ap.add_argument("--verify", action="store_true", help="打包后试编译一次")
    args = ap.parse_args()

    work = Path(args.work).resolve()
    out = Path(args.out).resolve()
    skill = Path(args.skill).resolve() if args.skill else Path(__file__).resolve().parent.parent

    source = out / "source"
    if source.exists():
        shutil.rmtree(source)
    (source / "content").mkdir(parents=True)
    (source / "figures").mkdir(parents=True)

    warnings: list[str] = []
    used_names: set[str] = set()
    img_map: dict[str, str] = {}

    # 1) copy content, rewrite image paths
    content_src = work / "content"
    if content_src.exists():
        for md in sorted(content_src.glob("*.md")):
            text = md.read_text(encoding="utf-8")
            text = rewrite_images(text, work, out, source / "figures", used_names, img_map, warnings)
            (source / "content" / md.name).write_text(text, encoding="utf-8")
    else:
        warnings.append(f"缺少 {content_src}")

    # 2) 只保留 content 里实际引用的图片；out/figures 已通过 rewrite_images 复制
    #    （不再整目录复制，避免源包里出现重复图片）

    # 3) copy metadata
    for name in ("meta.json", "exam_profile.json", "knowledge_points.csv",
                 "outline.md", "coverage.csv", "TO_VERIFY.md"):
        if not copy_if_exists(work / name, source / name):
            if name in {"meta.json"}:
                warnings.append(f"缺少 {name}，源文件无法直接编译")
            else:
                warnings.append(f"缺少 {name}（可选）")

    # 4) copy scripts / templates / assets
    scripts_src = skill / "scripts"
    if scripts_src.exists():
        (source / "scripts").mkdir(exist_ok=True)
        for py in scripts_src.glob("*.py"):
            shutil.copy2(py, source / "scripts" / py.name)
    else:
        warnings.append("缺少 skill scripts 目录")

    copy_if_exists(skill / "templates", source / "templates")
    copy_if_exists(skill / "assets", source / "assets")

    # 5) README
    course = "课程复习"
    meta_p = work / "meta.json"
    if meta_p.exists():
        try:
            import json
            course = json.loads(meta_p.read_text(encoding="utf-8")).get("course", course)
        except Exception:
            pass
    write_readme(source, course)

    # 6) summary
    files = sum(1 for p in source.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in source.rglob("*") if p.is_file()) / 1024 / 1024
    log(f"[package] {source} — {files} 个文件，{size:.1f} MB")
    for w in warnings:
        log(f"[warn] {w}")

    if args.verify:
        ok = verify(source)
        log(f"[verify] {'PASS' if ok else 'FAIL'}")
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
