# -*- coding: utf-8 -*-
"""后端 API 冒烟测试：覆盖条目 CRUD、批量导入、枚举。运行后自动清理测试数据。"""
import base64
import io
import os
import shutil
import sys
import wave

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import app  # noqa: E402

PNG_1x1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def make_wav(path: str) -> None:
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000)


def up(path: str, name: str):
    return (io.BytesIO(open(path, "rb").read()), name)


def main() -> None:
    os.makedirs("tmp", exist_ok=True)
    make_wav("tmp/t.wav")
    open("tmp/icon.png", "wb").write(PNG_1x1)
    c = app.app.test_client()

    # --- 单个创建（带头像）---
    r = c.post("/api/items", data={
        "name": "角色A", "source": "游戏", "gender": "男", "age": "少年",
        "occupation": "配音员", "tags": "御姐,日常",
        "audio": up("tmp/t.wav", "t.wav"), "avatar": up("tmp/icon.png", "icon.png"),
    }, content_type="multipart/form-data")
    assert r.status_code == 201, r.get_data(as_text=True)
    iid = r.get_json()["item"]["id"]

    # --- 列表与流 ---
    assert any(x["id"] == iid for x in c.get("/api/items").get_json()["items"])
    assert c.get(f"/api/items/{iid}/audio").status_code == 200
    assert c.get(f"/api/items/{iid}/avatar").status_code == 200

    # --- 无头像 -> 默认 SVG ---
    r = c.post("/api/items", data={
        "name": "角色B", "source": "游戏", "gender": "男", "age": "少年",
        "occupation": "配音员", "audio": up("tmp/t.wav", "t.wav"),
    }, content_type="multipart/form-data")
    iid2 = r.get_json()["item"]["id"]
    assert c.get(f"/api/items/{iid2}/avatar").headers.get("Content-Type", "").startswith("image/svg")

    # --- 编辑搬移 ---
    old_dir = app.find_item_dir(iid)
    r = c.put(f"/api/items/{iid}", data={"source": "番剧", "gender": "女", "age": "青年", "tags": "温柔"},
              content_type="multipart/form-data")
    assert r.status_code == 200, r.get_data(as_text=True)
    new_dir = app.find_item_dir(iid)
    assert new_dir == app.classify_path("番剧", "女", "青年", "配音员") / "角色A", new_dir
    assert not old_dir.exists()

    # --- 替换音频 ---
    assert c.post(f"/api/items/{iid}/audio", data={"audio": up("tmp/t.wav", "r.wav")},
                  content_type="multipart/form-data").status_code == 200

    # --- 批量导入 ---
    os.makedirs("tmp/夹A", exist_ok=True)
    os.makedirs("tmp/夹B", exist_ok=True)
    make_wav("tmp/夹A/voice.wav")
    make_wav("tmp/夹B/voice.wav")
    open("tmp/夹A/角色icon.png", "wb").write(PNG_1x1)
    r = c.post("/api/batch/import", data={
        "source": "游戏", "gender": "女", "age": "青年", "occupation": "歌手",
        "name_0": "夹A", "tags_0": "日常,御姐",
        "audio_0": up("tmp/夹A/voice.wav", "voice.wav"),
        "avatar_0": up("tmp/夹A/角色icon.png", "角色icon.png"),
        "name_1": "夹B", "audio_1": up("tmp/夹B/voice.wav", "voice.wav"),
    }, content_type="multipart/form-data")
    js = r.get_json()
    assert r.status_code == 200 and js["ok"] and len(js["imported"]) == 2 and js["errors"] == [], js
    assert js["imported"][0]["has_avatar"] and not js["imported"][1]["has_avatar"]

    # --- 枚举 ---
    e = c.get("/api/enums").get_json()
    assert "日常" in e["tags"] and "御姐" in e["tags"]
    assert "歌手" in e["occupations"]
    assert c.post("/api/enums", json={"kind": "ages", "value": "幼儿"}).get_json()["ok"] is True
    assert "幼儿" in c.get("/api/enums").get_json()["ages"]

    # --- 删除 ---
    assert c.delete(f"/api/items/{iid}").status_code == 200
    assert c.delete(f"/api/items/{iid2}").status_code == 200
    assert app.find_item_dir(iid) is None and app.find_item_dir(iid2) is None

    # --- 清理 ---
    shutil.rmtree("tmp", ignore_errors=True)
    for sub in list(app.LIBRARY_ROOT.iterdir()):
        if sub.is_dir():
            shutil.rmtree(sub)
    if app.ENUMS_FILE.exists():
        app.ENUMS_FILE.unlink()
    print("=== 冒烟测试通过：CRUD / 批量导入 / 枚举 / 清理 ===")


if __name__ == "__main__":
    main()
