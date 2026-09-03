# -*- coding: utf-8 -*-
"""
静态数据导出器 —— 为 Git Pages 静态版生成 data.json
================================================================
用法（在仓库根目录执行）：
    python export_static.py                # 扫描 ./library，生成 ./data.json
    python export_static.py --out out/data.json
    python export_static.py --library D:/x/library

之后把 data.json 与整个 library 目录一起提交到仓库，
Git Pages 即可用纯静态方式浏览/试听/筛选/搜索（只读）。
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".wma", ".opus", ".webm", ".mid", ".midi"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".jfif", ".jpe", ".gif", ".webp", ".bmp", ".svg", ".ico"}


def find_audio(entry_dir: Path):
    for f in sorted(entry_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
            return f
    return None


def find_avatar(entry_dir: Path):
    for f in sorted(entry_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS and "icon" in f.stem.lower():
            return f
    return None


def rel_posix(root: Path, p: Path) -> str:
    """相对仓库根的 POSIX 路径（正斜杠），供前端直接作为 URL 使用。"""
    return p.relative_to(root).as_posix()


def main() -> None:
    ap = argparse.ArgumentParser(description="导出静态数据 data.json")
    ap.add_argument("--library", default=None, help="library 目录（默认脚本旁 ./library）")
    ap.add_argument("--out", default=None, help="输出 data.json（默认仓库根 ./data.json）")
    args = ap.parse_args()

    root = Path(__file__).resolve().parent
    library = Path(args.library) if args.library else (root / "library")
    out = Path(args.out) if args.out else (root / "data.json")

    if not library.exists():
        print(f"[错误] library 目录不存在: {library}")
        sys.exit(1)

    items, used_enum = [], {}
    for meta_file in sorted(library.rglob("meta.json")):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not meta.get("id"):
            continue
        entry_dir = meta_file.parent
        audio = find_audio(entry_dir)
        avatar = find_avatar(entry_dir)
        item = {
            "id": meta["id"],
            "index": meta.get("index", 0),
            "name": meta.get("name", entry_dir.name),
            "source": meta.get("source", ""),
            "gender": meta.get("gender", ""),
            "age": meta.get("age", ""),
            "occupation": meta.get("occupation", ""),
            "tags": meta.get("tags", []),
            "audio_url": rel_posix(root, audio) if audio else "",
            "avatar_url": rel_posix(root, avatar) if avatar else "",
        }
        items.append(item)
        for kind, field in (("sources", "source"), ("genders", "gender"),
                            ("ages", "age"), ("occupations", "occupation")):
            if meta.get(field):
                used_enum.setdefault(kind, [])
                if meta[field] not in used_enum[kind]:
                    used_enum[kind].append(meta[field])
        used_enum.setdefault("tags", [])
        for t in meta.get("tags", []):
            if t not in used_enum["tags"]:
                used_enum["tags"].append(t)

    for k in list(used_enum):
        used_enum[k].sort()

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "version": 1,
        "item_count": len(items),
        "items": sorted(items, key=lambda x: (x.get("index") or 0)),
        "enums": used_enum,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[完成] 已导出 {len(items)} 个条目 -> {out}")
    print("提示：将 data.json 与 library 目录一起提交到 Git 仓库即可被 Pages 静态访问（只读）。")


if __name__ == "__main__":
    main()
