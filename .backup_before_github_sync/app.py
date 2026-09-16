# -*- coding: utf-8 -*-
"""TTS 音频库 WebUI —— 本地 Flask 应用

数据目录结构：
    library/enums.json                 枚举列表（来源/性别/年龄/职业，均可新增）
    library/<来源>/<性别>/<年龄>/<职业>/<条目名>/
        meta.json                      条目元数据
        <音频文件>                     音频（任意格式，取第一个音频文件）
        <头像文件>                     文件名含 icon 的图片，缺失用默认头像
"""
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
LIBRARY_ROOT = BASE_DIR / "library"
STATIC_DIR = BASE_DIR / "static"
ENUMS_FILE = LIBRARY_ROOT / "enums.json"

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".wma", ".opus", ".webm", ".mid", ".midi"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".jfif", ".jpe", ".gif", ".webp", ".bmp", ".svg", ".ico"}

# 默认头像（内嵌 SVG，蓝色圆形 + 白色人形剪影）
DEFAULT_AVATAR = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <circle cx="50" cy="50" r="50" fill="#7c9cff"/>
  <circle cx="50" cy="38" r="16" fill="#ffffff"/>
  <path d="M20 82 Q20 56 50 56 Q80 56 80 82 Z" fill="#ffffff"/>
</svg>"""


def _safe_name(name: str) -> str:
    """过滤文件系统非法字符，返回安全目录名。"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip()
    name = re.sub(r"\.+$", "", name)
    return name or "未命名"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/style.css")
def root_style():
    return send_from_directory(BASE_DIR, "style.css")


@app.route("/app.js")
def root_script():
    return send_from_directory(BASE_DIR, "app.js")


@app.route("/data.json")
def root_data():
    return send_from_directory(BASE_DIR, "data.json")


# ---------------------------------------------------------------------------
# 数据层工具
# ---------------------------------------------------------------------------

def get_enums() -> dict:
    """读取枚举列表（来源/性别/年龄/职业），缺失项自动补默认值。"""
    enums = _read_json(ENUMS_FILE, {}) or {}
    defaults = {
        "sources": [],
        "genders": ["男", "女"],
        "ages": ["少年", "青年", "中年", "老年"],
        "occupations": [],
    }
    for k, v in defaults.items():
        enums.setdefault(k, list(v))
    return enums


def save_enums(enums: dict) -> None:
    _write_json(ENUMS_FILE, enums)


def add_enum(kind: str, value: str) -> bool:
    """新增一个枚举项，返回是否真的新增（已存在则 False）。"""
    value = (value or "").strip()
    if not value:
        return False
    enums = get_enums()
    lst = enums.setdefault(kind, [])
    if value in lst:
        return False
    lst.append(value)
    save_enums(enums)
    return True


def classify_path(source: str, gender: str, age: str, occupation: str) -> Path:
    """由分类键构造条目目录的父路径：library/<来源>/<性别>/<年龄>/<职业>/"""
    return (LIBRARY_ROOT
            / _safe_name(source)
            / _safe_name(gender)
            / _safe_name(age)
            / _safe_name(occupation))


def iter_item_dirs():
    """深度遍历分类树（来源/性别/年龄/职业/条目 共 5 层），产出条目目录。"""
    if not LIBRARY_ROOT.exists():
        return
    for src in sorted(p for p in LIBRARY_ROOT.iterdir() if p.is_dir()):
        for gen in sorted(p for p in src.iterdir() if p.is_dir()):
            for age in sorted(p for p in gen.iterdir() if p.is_dir()):
                for occ in sorted(p for p in age.iterdir() if p.is_dir()):
                    for entry in sorted(p for p in occ.iterdir() if p.is_dir()):
                        yield entry


def find_audio(entry_dir: Path):
    """条目目录中的音频文件（第一个），没有则 None。"""
    for f in sorted(entry_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
            return f
    return None


def find_avatar(entry_dir: Path):
    """条目目录中的头像文件：文件名含 icon 的图片，没有则 None。"""
    for f in sorted(entry_dir.iterdir()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS and "icon" in f.stem.lower():
            return f
    return None


def find_item_dir(item_id: str):
    """按 id 在分类树中查找条目目录。"""
    for entry_dir in iter_item_dirs():
        meta = _read_json(entry_dir / "meta.json", {})
        if meta.get("id") == item_id:
            return entry_dir
    return None


def unique_entry_name(parent: Path, name: str, exclude: Path = None) -> str:
    """在父目录下取不冲突的条目名，冲突自动加 _2/_3 编号；exclude 为当前自身目录时跳过。"""
    name = _safe_name(name)
    candidate, i = name, 2
    while (parent / candidate).exists() and (parent / candidate) != exclude:
        candidate = f"{name}_{i}"
        i += 1
    return candidate


def load_items() -> list:
    """扫描分类树，返回全部条目（含音频/头像 URL 与分类键）。"""
    items = []
    for entry_dir in iter_item_dirs():
        meta = _read_json(entry_dir / "meta.json", {})
        if not meta.get("id"):
            continue
        items.append({
            "id": meta["id"],
            "index": meta.get("index", 0),
            "name": meta.get("name", entry_dir.name),
            "source": meta.get("source", ""),
            "gender": meta.get("gender", ""),
            "age": meta.get("age", ""),
            "occupation": meta.get("occupation", ""),
            "tags": meta.get("tags", []),
            "has_avatar": find_avatar(entry_dir) is not None,
            "audio_url": f"/api/items/{meta['id']}/audio",
            "avatar_url": f"/api/items/{meta['id']}/avatar",
        })
    return items


def next_index() -> int:
    """下一个可用索引号（已用索引的最大值 + 1，删除后不复用）。"""
    used = {it["index"] for it in load_items() if it.get("index")}
    return (max(used) + 1) if used else 1


def ensure_indexes() -> int:
    """为缺失索引的条目补齐索引号（迁移用），返回补齐数量。"""
    used = {it["index"] for it in load_items() if it.get("index")}
    nxt = (max(used) + 1) if used else 1
    added = 0
    for entry_dir in sorted(iter_item_dirs()):
        meta = _read_json(entry_dir / "meta.json", {})
        if not meta.get("id") or meta.get("index"):
            continue
        while nxt in used:
            nxt += 1
        meta["index"] = nxt
        used.add(nxt)
        nxt += 1
        _write_json(entry_dir / "meta.json", meta)
        added += 1
    return added


# ---------------------------------------------------------------------------
# 条目 CRUD API
# ---------------------------------------------------------------------------

def item_dict(entry_dir: Path, meta: dict) -> dict:
    """条目目录 + meta -> 前端展示用的 dict。"""
    return {
        "id": meta["id"],
        "index": meta.get("index", 0),
        "name": meta.get("name", entry_dir.name),
        "source": meta.get("source", ""),
        "gender": meta.get("gender", ""),
        "age": meta.get("age", ""),
        "occupation": meta.get("occupation", ""),
        "tags": meta.get("tags", []),
        "has_avatar": find_avatar(entry_dir) is not None,
        "audio_url": f"/api/items/{meta['id']}/audio",
        "avatar_url": f"/api/items/{meta['id']}/avatar",
    }


def _parse_meta_form(form) -> dict:
    """从表单解析条目元数据（tags 用逗号分隔）。"""
    return {
        "name": (form.get("name") or "").strip(),
        "source": (form.get("source") or "").strip(),
        "gender": (form.get("gender") or "").strip(),
        "age": (form.get("age") or "").strip(),
        "occupation": (form.get("occupation") or "").strip(),
        "tags": [t.strip() for t in (form.get("tags") or "").split(",") if t.strip()],
    }


def _save_audio(entry_dir: Path, file) -> None:
    """保存/替换音频：统一命名为 audio<原扩展名>，删旧文件。"""
    old = find_audio(entry_dir)
    if old:
        old.unlink()
    ext = Path(file.filename).suffix.lower() or ".mp3"
    file.save(str(entry_dir / ("audio" + ext)))


def _save_avatar(entry_dir: Path, file) -> None:
    """保存/替换头像：统一命名为 icon<原扩展名>（含 icon 便于识别），删旧文件。"""
    old = find_avatar(entry_dir)
    if old:
        old.unlink()
    ext = Path(file.filename).suffix.lower() or ".png"
    file.save(str(entry_dir / ("icon" + ext)))


def _sync_enums_from_meta(meta: dict) -> None:
    """把条目用到的来源/性别/年龄/职业自动补进枚举（去重）。"""
    for kind, value in (("sources", meta.get("source")),
                        ("genders", meta.get("gender")),
                        ("ages", meta.get("age")),
                        ("occupations", meta.get("occupation"))):
        if value:
            add_enum(kind, value)


@app.route("/api/items")
def list_items():
    return jsonify({"items": load_items()})


@app.route("/api/items", methods=["POST"])
def create_item():
    meta = _parse_meta_form(request.form)
    if not meta["name"]:
        return jsonify({"error": "名称不能为空"}), 400
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"error": "音频文件不能为空"}), 400

    parent = classify_path(meta["source"], meta["gender"], meta["age"], meta["occupation"])
    parent.mkdir(parents=True, exist_ok=True)
    entry_dir = parent / unique_entry_name(parent, meta["name"])
    entry_dir.mkdir()

    meta["id"] = uuid.uuid4().hex[:12]
    meta["index"] = next_index()
    _save_audio(entry_dir, audio)
    avatar = request.files.get("avatar")
    if avatar and avatar.filename:
        _save_avatar(entry_dir, avatar)
    _write_json(entry_dir / "meta.json", meta)
    _sync_enums_from_meta(meta)
    return jsonify({"ok": True, "item": item_dict(entry_dir, meta)}), 201


@app.route("/api/items/<item_id>", methods=["PUT"])
def update_item(item_id):
    entry_dir = find_item_dir(item_id)
    if not entry_dir:
        return jsonify({"error": "条目不存在"}), 404
    old_meta = _read_json(entry_dir / "meta.json", {})

    new_meta = _parse_meta_form(request.form)
    # 未提供的字段保持原值；tags 特殊：表单里没传则保持原值（传了空串即清空）
    for k in ("name", "source", "gender", "age", "occupation"):
        if not new_meta[k]:
            new_meta[k] = old_meta.get(k, "")
    if "tags" not in request.form:
        new_meta["tags"] = old_meta.get("tags", [])
    if not new_meta["name"]:
        return jsonify({"error": "名称不能为空"}), 400

    # 分类键或名称变化 -> 整体搬移条目文件夹
    new_parent = classify_path(new_meta["source"], new_meta["gender"], new_meta["age"], new_meta["occupation"])
    new_parent.mkdir(parents=True, exist_ok=True)
    new_dir = new_parent / unique_entry_name(new_parent, new_meta["name"], exclude=entry_dir)
    if new_dir != entry_dir:
        entry_dir.rename(new_dir)
        entry_dir = new_dir

    audio = request.files.get("audio")
    if audio and audio.filename:
        _save_audio(entry_dir, audio)
    avatar = request.files.get("avatar")
    if avatar and avatar.filename:
        _save_avatar(entry_dir, avatar)
    if request.form.get("remove_avatar") == "1":
        old_avatar = find_avatar(entry_dir)
        if old_avatar:
            old_avatar.unlink()

    new_meta["id"] = item_id
    _write_json(entry_dir / "meta.json", new_meta)
    _sync_enums_from_meta(new_meta)
    return jsonify({"ok": True, "item": item_dict(entry_dir, new_meta)})


@app.route("/api/items/<item_id>/audio", methods=["POST"])
def replace_audio(item_id):
    """替换音频专用接口（为以后批量替换预留）。"""
    entry_dir = find_item_dir(item_id)
    if not entry_dir:
        return jsonify({"error": "条目不存在"}), 404
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        return jsonify({"error": "音频文件不能为空"}), 400
    _save_audio(entry_dir, audio)
    return jsonify({"ok": True})


@app.route("/api/items/<item_id>", methods=["DELETE"])
def delete_item(item_id):
    entry_dir = find_item_dir(item_id)
    if not entry_dir:
        return jsonify({"error": "条目不存在"}), 404
    shutil.rmtree(entry_dir)
    return jsonify({"ok": True})


def open_folder(path: Path) -> None:
    """用系统文件管理器打开文件夹（Windows/macOS/Linux）。"""
    if sys.platform.startswith("win"):
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


@app.route("/api/items/<item_id>/open-folder", methods=["POST"])
def open_item_folder(item_id):
    entry_dir = find_item_dir(item_id)
    if not entry_dir:
        return jsonify({"error": "条目不存在"}), 404
    try:
        open_folder(entry_dir)
        return jsonify({"ok": True, "path": str(entry_dir)})
    except Exception as e:
        return jsonify({"error": f"打开文件夹失败: {e}"}), 500


@app.route("/api/items/<item_id>/audio")
def item_audio(item_id):
    entry_dir = find_item_dir(item_id)
    if not entry_dir:
        return jsonify({"error": "条目不存在"}), 404
    audio = find_audio(entry_dir)
    if not audio:
        return jsonify({"error": "没有音频文件"}), 404
    return send_file(audio)


@app.route("/api/items/<item_id>/avatar")
def item_avatar(item_id):
    entry_dir = find_item_dir(item_id)
    if not entry_dir:
        return jsonify({"error": "条目不存在"}), 404
    avatar = find_avatar(entry_dir)
    if not avatar:
        return Response(DEFAULT_AVATAR, mimetype="image/svg+xml")
    return send_file(avatar)


def find_by_index(n: int):
    """按索引号查找条目（返回 (entry_dir, meta) 或 None）。"""
    for entry_dir in iter_item_dirs():
        meta = _read_json(entry_dir / "meta.json", {})
        if meta.get("index") == n:
            return entry_dir, meta
    return None


@app.route("/api/index/<int:n>")
def item_by_index(n):
    """按索引号获取条目信息（供 TTS 引用检索）。"""
    found = find_by_index(n)
    if not found:
        return jsonify({"error": f"索引 {n} 不存在"}), 404
    entry_dir, meta = found
    return jsonify(item_dict(entry_dir, meta))


@app.route("/api/index/<int:n>/audio")
def item_audio_by_index(n):
    """按索引号直接返回音频文件（供 TTS 引用播放）。"""
    found = find_by_index(n)
    if not found:
        return jsonify({"error": f"索引 {n} 不存在"}), 404
    entry_dir, _ = found
    audio = find_audio(entry_dir)
    if not audio:
        return jsonify({"error": "该条目没有音频文件"}), 404
    return send_file(audio)


# ---------------------------------------------------------------------------
# 批量导入 & 枚举 API
# ---------------------------------------------------------------------------

@app.route("/api/batch/import", methods=["POST"])
def batch_import():
    """批量导入：条目按 audio_<i>/avatar_<i>/name_<i>/tags_<i> 分组。
    每行可用 source_<i>/gender_<i>/age_<i>/occupation_<i> 覆盖统一分类（缺省用顶部统一值）。"""
    source = (request.form.get("source") or "").strip()
    gender = (request.form.get("gender") or "").strip()
    age = (request.form.get("age") or "").strip()
    occupation = (request.form.get("occupation") or "").strip()

    idxs = set()
    for key in request.files:
        m = re.match(r"^(audio|avatar)_(\d+)$", key)
        if m:
            idxs.add(int(m.group(2)))

    imported, errors = [], []
    for i in sorted(idxs):
        audio = request.files.get(f"audio_{i}")
        if not audio or not audio.filename:
            errors.append(f"第 {i + 1} 组缺少音频文件")
            continue
        name = (request.form.get(f"name_{i}") or "").strip() or Path(audio.filename).stem
        tags = [t.strip() for t in (request.form.get(f"tags_{i}") or "").split(",") if t.strip()]

        # 每行独立分类（缺省回退到顶部统一值）
        i_source = (request.form.get(f"source_{i}") or "").strip() or source
        i_gender = (request.form.get(f"gender_{i}") or "").strip() or gender
        i_age = (request.form.get(f"age_{i}") or "").strip() or age
        i_occupation = (request.form.get(f"occupation_{i}") or "").strip() or occupation

        parent_i = classify_path(i_source, i_gender, i_age, i_occupation)
        parent_i.mkdir(parents=True, exist_ok=True)
        entry_dir = parent_i / unique_entry_name(parent_i, name)
        entry_dir.mkdir()
        meta = {
            "id": uuid.uuid4().hex[:12],
            "index": next_index(),
            "name": name,
            "source": i_source, "gender": i_gender, "age": i_age, "occupation": i_occupation,
            "tags": tags,
        }
        _save_audio(entry_dir, audio)
        avatar = request.files.get(f"avatar_{i}")
        if avatar and avatar.filename:
            _save_avatar(entry_dir, avatar)
        _write_json(entry_dir / "meta.json", meta)
        _sync_enums_from_meta(meta)
        imported.append(item_dict(entry_dir, meta))

    return jsonify({"ok": True, "imported": imported, "errors": errors})


@app.route("/api/enums")
def enums_api():
    return jsonify(full_enums())


def full_enums() -> dict:
    """完整枚举（含从所有条目动态聚合的其他标签）。"""
    enums = get_enums()
    enums["tags"] = sorted({t for it in load_items() for t in it["tags"]})
    return enums


@app.route("/api/enums", methods=["POST"])
def add_enum_api():
    data = request.get_json(silent=True) or {}
    kind, value = data.get("kind", ""), (data.get("value") or "").strip()
    if kind not in ("sources", "genders", "ages", "occupations"):
        return jsonify({"error": "未知枚举类型"}), 400
    added = add_enum(kind, value)
    return jsonify({"ok": added, "enums": full_enums()})


ENUM_FIELDS = {"sources": "source", "genders": "gender", "ages": "age", "occupations": "occupation"}


@app.route("/api/enums", methods=["PUT"])
def rename_enum_api():
    """重命名枚举：同步更新所有使用该值的条目（字段 + meta.json + 目录搬移）。"""
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "")
    old = (data.get("old") or "").strip()
    new = (data.get("new") or "").strip()
    if kind not in ENUM_FIELDS:
        return jsonify({"error": "未知枚举类型"}), 400
    if not old or not new:
        return jsonify({"error": "旧值与新值不能为空"}), 400
    if old == new:
        return jsonify({"ok": True, "enums": full_enums()})
    enums = get_enums()
    lst = enums.setdefault(kind, [])
    if old not in lst:
        return jsonify({"error": f"枚举「{old}」不存在"}), 404
    if new in lst:
        return jsonify({"error": f"枚举「{new}」已存在"}), 400
    lst[lst.index(old)] = new
    save_enums(enums)

    field = ENUM_FIELDS[kind]
    for entry_dir in list(iter_item_dirs()):
        meta = _read_json(entry_dir / "meta.json", {})
        if meta.get(field) == old:
            meta[field] = new
            _write_json(entry_dir / "meta.json", meta)
            new_parent = classify_path(meta.get("source", ""), meta.get("gender", ""),
                                       meta.get("age", ""), meta.get("occupation", ""))
            new_parent.mkdir(parents=True, exist_ok=True)
            new_dir = new_parent / unique_entry_name(new_parent, meta.get("name", entry_dir.name), exclude=entry_dir)
            if new_dir != entry_dir:
                entry_dir.rename(new_dir)
    return jsonify({"ok": True, "enums": full_enums()})


@app.route("/api/enums", methods=["DELETE"])
def delete_enum_api():
    """删除枚举：仍被条目使用的值拒绝删除。"""
    data = request.get_json(silent=True) or {}
    kind = data.get("kind", "")
    value = (data.get("value") or "").strip()
    if kind not in ENUM_FIELDS:
        return jsonify({"error": "未知枚举类型"}), 400
    if not value:
        return jsonify({"error": "枚举值不能为空"}), 400
    used = sum(1 for it in load_items() if it.get(ENUM_FIELDS[kind]) == value)
    if used > 0:
        return jsonify({"error": f"「{value}」正被 {used} 个条目使用，请先修改这些条目"}), 400
    enums = get_enums()
    lst = enums.get(kind, [])
    if value in lst:
        lst.remove(value)
        save_enums(enums)
    return jsonify({"ok": True, "enums": full_enums()})


@app.route("/api/tags", methods=["PUT"])
def rename_tag_api():
    """重命名其他标签：同步更新所有包含该标签的条目。"""
    data = request.get_json(silent=True) or {}
    old = (data.get("old") or "").strip()
    new = (data.get("new") or "").strip()
    if not old or not new:
        return jsonify({"error": "旧值与新值不能为空"}), 400
    if old == new:
        return jsonify({"ok": True, "enums": full_enums()})
    for entry_dir in list(iter_item_dirs()):
        meta = _read_json(entry_dir / "meta.json", {})
        tags = meta.get("tags", [])
        if old in tags:
            meta["tags"] = [new if t == old else t for t in tags]
            _write_json(entry_dir / "meta.json", meta)
    return jsonify({"ok": True, "enums": full_enums()})


@app.route("/api/tags", methods=["DELETE"])
def delete_tag_api():
    """删除其他标签：从所有条目中移除该标签。"""
    data = request.get_json(silent=True) or {}
    value = (data.get("value") or "").strip()
    if not value:
        return jsonify({"error": "标签不能为空"}), 400
    for entry_dir in list(iter_item_dirs()):
        meta = _read_json(entry_dir / "meta.json", {})
        tags = meta.get("tags", [])
        if value in tags:
            meta["tags"] = [t for t in tags if t != value]
            _write_json(entry_dir / "meta.json", meta)
    return jsonify({"ok": True, "enums": full_enums()})


if __name__ == "__main__":
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    if not ENUMS_FILE.exists():
        _write_json(ENUMS_FILE, {
            "sources": [],
            "genders": ["男", "女"],
            "ages": ["少年", "青年", "中年", "老年"],
            "occupations": [],
        })
    added = ensure_indexes()
    if added:
        print(f"已为 {added} 个条目补齐索引号")
    print("TTS 音频库已启动: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
