/* ===== TTS 音频库 前端逻辑 ===== */
"use strict";

const AUDIO_EXT = ["mp3", "wav", "ogg", "m4a", "aac", "flac", "wma", "opus", "webm", "mid", "midi"];
const IMG_EXT = ["png", "jpg", "jpeg", "jfif", "jpe", "gif", "webp", "bmp", "svg", "ico"];
const ENUM_KINDS = ["sources", "genders", "ages", "occupations"];

const state = {
  items: [],
  enums: { sources: [], genders: [], ages: [], occupations: [], tags: [] },
  filters: { source: null, gender: null, age: null, occupation: null, tags: new Set(), search: "" },
  currentId: null,
};

const $ = (sel) => document.querySelector(sel);
const audio = $("#player");

/* ---------- 基础请求 ---------- */
async function api(url, options) {
  const res = await fetch(url, options);
  let data = null;
  try { data = await res.json(); } catch (e) { /* 非 JSON */ }
  if (!res.ok) throw new Error((data && data.error) || `请求失败(${res.status})`);
  return data;
}

/* ---------- 数据加载（完整模式用后端 API；静态/Git Pages 模式读 data.json 只读） ---------- */
let IS_STATIC = false;   // true = 静态只读（Git Pages 等纯静态托管）

async function loadAll() {
  let items, enums;
  try {
    const itemsRes = await api("/api/items");
    const enumsRes = await api("/api/enums");
    items = itemsRes.items;
    enums = enumsRes;
    IS_STATIC = false;
  } catch (e) {
    // 无后端：尝试 Git Pages 静态数据
    IS_STATIC = true;
    const res = await fetch("./data.json");
    if (!res.ok) throw new Error("无法连接本地服务，也未找到 data.json（静态模式需要它）");
    const data = await res.json();
    items = data.items || [];
    enums = data.enums || { sources: [], genders: [], ages: [], occupations: [], tags: [] };
  }
  state.items = items;
  state.enums = enums;
  applyStaticUI();
  renderFilters();
  renderCards();
}

/* 静态只读模式：隐藏 添加/批量添加/设置 与卡片上的 编辑/删除/打开文件夹 */
function applyStaticUI() {
  const hide = (id) => { const b = $("#" + id); if (b) b.classList.toggle("hidden", IS_STATIC); };
  ["btnAdd", "btnBatch", "btnSettings"].forEach(hide);
}

/* ---------- 筛选区 ---------- */
const FILTER_DIMS = [
  { kind: "source", label: "来源" },
  { kind: "gender", label: "性别" },
  { kind: "age", label: "年龄" },
  { kind: "occupation", label: "职业" },
];

function renderFilters() {
  // 单选维度：来源/性别/年龄/职业
  FILTER_DIMS.forEach(({ kind }) => {
    const row = document.querySelector(`.filter-row[data-kind="${kind}"]`);
    const box = row.querySelector(".chips");
    box.innerHTML = "";
    const values = state.enums[kind + "s"] || [];
    values.forEach((v) => {
      const chip = document.createElement("button");
      chip.className = "chip" + (state.filters[kind] === v ? " active" : "");
      chip.textContent = v;
      chip.onclick = () => {
        state.filters[kind] = state.filters[kind] === v ? null : v;
        renderFilters();
        renderCards();
      };
      box.appendChild(chip);
    });
  });
  // 多选维度：其他标签
  const tagRow = document.querySelector('.filter-row[data-kind="tag"]');
  const tagBox = tagRow.querySelector(".chips");
  tagBox.innerHTML = "";
  state.enums.tags.forEach((v) => {
    const chip = document.createElement("button");
    chip.className = "chip" + (state.filters.tags.has(v) ? " active" : "");
    chip.textContent = v;
    chip.onclick = () => {
      state.filters.tags.has(v) ? state.filters.tags.delete(v) : state.filters.tags.add(v);
      renderFilters();
      renderCards();
    };
    tagBox.appendChild(chip);
  });
}

function matchesFilter(item) {
  const f = state.filters;
  if (f.source && item.source !== f.source) return false;
  if (f.gender && item.gender !== f.gender) return false;
  if (f.age && item.age !== f.age) return false;
  if (f.occupation && item.occupation !== f.occupation) return false;
  if (f.tags.size > 0 && !item.tags.some((t) => f.tags.has(t))) return false;
  // 关键词搜索：仅匹配名称
  if (f.search && !String(item.name || "").toLowerCase().includes(f.search)) return false;
  return true;
}

/* ---------- 名称搜索栏（实时过滤，仅匹配名称） ---------- */
$("#searchInput").addEventListener("input", (e) => {
  state.filters.search = e.target.value.trim().toLowerCase();
  renderCards();
});

/* ---------- 筛选标签左右滑动（单行超出部分） ---------- */
document.querySelectorAll(".chip-scroll").forEach((btn) => {
  btn.addEventListener("click", () => {
    const chips = btn.closest(".filter-row").querySelector(".chips");
    const dir = parseInt(btn.dataset.scroll, 10) || 0;
    chips.scrollBy({ left: dir * 220, behavior: "smooth" });
  });
});

/* ---------- 卡片渲染 ---------- */
function fmtTime(sec) {
  if (!isFinite(sec) || sec < 0) return "0:00";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

function tagHtml(item) {
  let html = "";
  if (item.gender) html += `<span class="tag tag-gender">${esc(item.gender)}</span>`;
  if (item.age) html += `<span class="tag tag-age">${esc(item.age)}</span>`;
  if (item.occupation) html += `<span class="tag tag-occ">${esc(item.occupation)}</span>`;
  item.tags.forEach((t) => { html += `<span class="tag tag-other">${esc(t)}</span>`; });
  return html;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

/* 默认头像（内嵌 SVG，与后端一致）：静态模式下无头像文件时使用 */
const DEFAULT_AVATAR_URI = "data:image/svg+xml," + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">' +
  '<circle cx="50" cy="50" r="50" fill="#7c9cff"/>' +
  '<circle cx="50" cy="38" r="16" fill="#ffffff"/>' +
  '<path d="M20 82 Q20 56 50 56 Q80 56 80 82 Z" fill="#ffffff"/></svg>'
);

function cardHtml(item) {
  const playing = state.currentId === item.id;
  const avatarSrc = item.avatar_url || DEFAULT_AVATAR_URI;
  const avatar = `<img src="${avatarSrc}" alt="头像">`;
  const playIcon = playing && !audio.paused ? "⏸" : "▶";
  const tools = IS_STATIC ? "" : `
        <div class="card-tools">
          <button class="icon-btn" data-act="folder" title="打开所在文件夹">📂</button>
          <button class="icon-btn" data-act="edit" title="编辑">✎</button>
          <button class="icon-btn danger" data-act="del" title="删除">🗑</button>
        </div>`;
  return `
  <div class="card" data-id="${item.id}">
    <div class="card-avatar">${avatar}</div>
    <div class="card-body">
      <div class="card-top">
        <div class="card-name" title="${esc(item.name)}">${esc(item.name)}<span class="card-index">#${item.index}</span></div>
        ${tools}
      </div>
      <div class="card-player">
        <button class="btn-play ${playing ? "playing" : ""}" data-act="play">${playIcon}</button>
        <div class="progress" data-act="seek">
          <div class="progress-fill" style="width:${playing ? progressPct(item.id) : 0}%"></div>
        </div>
        <span class="card-time" data-time>${playing ? fmtTime(audio.currentTime) : "0:00"} / ${playing ? fmtTime(audio.duration) : "0:00"}</span>
      </div>
      <div class="card-bottom">
        <div class="card-tags">${tagHtml(item)}</div>
        <div class="card-source">${item.source ? esc(item.source) : "未分类"}</div>
      </div>
    </div>
  </div>`;
}

function progressPct(id) {
  if (state.currentId !== id || !audio.duration) return 0;
  return (audio.currentTime / audio.duration) * 100;
}

function renderCards() {
  const grid = $("#cardGrid");
  const filtered = state.items.filter(matchesFilter);
  grid.innerHTML = filtered.map(cardHtml).join("");
  $("#emptyState").classList.toggle("hidden", state.items.length > 0);
  if (state.items.length === 0) return;
  grid.querySelector(".empty-note")?.remove();
  if (filtered.length === 0) {
    const note = document.createElement("div");
    note.className = "empty-note empty";
    note.innerHTML = `<p class="big">🔍</p><p>没有符合筛选条件的条目</p>`;
    grid.appendChild(note);
  }
}

/* ---------- 播放器 ---------- */
function playItem(id) {
  const item = state.items.find((i) => i.id === id);
  if (!item) return;
  if (state.currentId === id && !audio.paused) {
    audio.pause();
    return;
  }
  state.currentId = id;
  audio.src = item.audio_url;
  audio.play().catch(() => {});
  renderCards();
}

audio.addEventListener("timeupdate", () => {
  if (!state.currentId) return;
  const card = document.querySelector(`.card[data-id="${state.currentId}"]`);
  if (!card) return;
  card.querySelector(".progress-fill").style.width = progressPct(state.currentId) + "%";
  card.querySelector("[data-time]").textContent =
    `${fmtTime(audio.currentTime)} / ${fmtTime(audio.duration)}`;
});
audio.addEventListener("ended", () => {
  const id = state.currentId;
  state.currentId = null;
  renderCards();
  if (id) {
    // 可选的连播：找下一张卡片
    // 简单起见停在结束状态
  }
});

/* ---------- 弹窗工具 ---------- */
function openModal(id) { $("#" + id).classList.remove("hidden"); }
function closeModal(id) {
  $("#" + id).classList.add("hidden");
  // 关闭添加/编辑弹窗时停止音频试听
  if (id === "modal") {
    const ap = $("#fAudioPreview");
    ap.pause();
    ap.removeAttribute("src");
    ap.classList.add("hidden");
  }
}

document.querySelectorAll("[data-close]").forEach((btn) => {
  btn.addEventListener("click", () => closeModal(btn.dataset.close));
});
document.querySelectorAll(".modal").forEach((m) => {
  m.addEventListener("click", (e) => { if (e.target === m) m.classList.add("hidden"); });
});

/* ---------- 枚举 select 填充 ---------- */
function fillSelect(sel, values, selected) {
  sel.innerHTML = `<option value="">— 无 —</option>` +
    values.map((v) => `<option value="${esc(v)}" ${v === selected ? "selected" : ""}>${esc(v)}</option>`).join("");
}

/* ---------- 添加 / 编辑 ---------- */
let editingId = null;
let avatarFileProcessed = null; // 选择头像后裁切压缩为 128x128 的文件

/* 把图片先按最小边缩放到 128（长边等比），再居中裁切为 128x128；处理失败（非图片）时回调原文件 */
function processAvatar(file, done) {
  const url = URL.createObjectURL(file);
  const img = new Image();
  img.onload = () => {
    URL.revokeObjectURL(url);
    // 1. 最小边缩放到 128，长边等比例缩放
    const scale = 128 / Math.min(img.width, img.height);
    const scaledW = Math.max(1, Math.round(img.width * scale));
    const scaledH = Math.max(1, Math.round(img.height * scale));
    const tmp = document.createElement("canvas");
    tmp.width = scaledW;
    tmp.height = scaledH;
    tmp.getContext("2d").drawImage(img, 0, 0, scaledW, scaledH);
    // 2. 从缩放后的图中居中裁切 128x128（长边超出部分裁掉）
    const canvas = document.createElement("canvas");
    canvas.width = 128;
    canvas.height = 128;
    canvas.getContext("2d").drawImage(tmp, (scaledW - 128) / 2, (scaledH - 128) / 2, 128, 128, 0, 0, 128, 128);
    // 3. 统一输出 WebP（保留 alpha 透明层）；浏览器不支持 webp 编码时回退 PNG
    canvas.toBlob((blob) => {
      if (blob) {
        const webpName = file.name.replace(/\.[^.]+$/, "") + ".webp";
        done(new File([blob], webpName, { type: "image/webp" }));
      } else {
        canvas.toBlob((blob2) => {
          if (blob2) done(new File([blob2], file.name, { type: "image/png" }));
          else done(file);
        }, "image/png");
      }
    }, "image/webp");
  };
  img.onerror = () => {
    URL.revokeObjectURL(url);
    done(file);
  };
  img.src = url;
}

function openItemModal(item) {
  editingId = item ? item.id : null;
  $("#modalTitle").textContent = item ? "编辑音频" : "添加音频";
  $("#fId").value = item ? item.id : "";
  $("#fName").value = item ? item.name : "";
  $("#fTags").value = item ? item.tags.join(",") : "";
  fillSelect($("#fSource"), state.enums.sources, item ? item.source : "");
  fillSelect($("#fGender"), state.enums.genders, item ? item.gender : "");
  fillSelect($("#fAge"), state.enums.ages, item ? item.age : "");
  fillSelect($("#fOccupation"), state.enums.occupations, item ? item.occupation : "");
  $("#fAvatar").value = "";
  $("#fAvatarName").classList.add("hidden");
  $("#fAvatarNameText").textContent = "";
  avatarFileProcessed = null;
  $("#fAudio").value = "";
  /* 音频试听：编辑时可试听当前音频，添加时等待选择新文件 */
  const ap = $("#fAudioPreview");
  ap.pause();
  ap.removeAttribute("src");
  if (item) {
    ap.src = item.audio_url;
    ap.classList.remove("hidden");
  } else {
    ap.classList.add("hidden");
  }
  const preview = $("#avatarPreview");
  preview.innerHTML = item && item.has_avatar ? `<img src="${item.avatar_url}">` : "";
  $("#fSubmit").textContent = item ? "保存" : "添加";
  openModal("modal");
}

/* 头像：选文件则裁切压缩为 128x128 后使用；不选则默认；文件名后可 ❌ 删除已选 */
$("#fAvatarBtn").addEventListener("click", () => $("#fAvatar").click());
$("#fAvatar").addEventListener("change", () => {
  const f = $("#fAvatar").files[0];
  const nameEl = $("#fAvatarName");
  if (!f) {
    nameEl.classList.add("hidden");
    avatarFileProcessed = null;
    resetAvatarPreview();
    return;
  }
  $("#fAvatarNameText").textContent = f.name;
  nameEl.classList.remove("hidden");
  processAvatar(f, (processed) => {
    avatarFileProcessed = processed || f;
    const url = URL.createObjectURL(avatarFileProcessed);
    $("#avatarPreview").innerHTML = `<img src="${url}">`;
  });
});
$("#fAvatarClear").addEventListener("click", () => {
  $("#fAvatar").value = "";
  $("#fAvatarName").classList.add("hidden");
  avatarFileProcessed = null;
  resetAvatarPreview();
});
function resetAvatarPreview() {
  const preview = $("#avatarPreview");
  if (editingId) {
    const item = state.items.find((i) => i.id === editingId);
    preview.innerHTML = item && item.has_avatar ? `<img src="${item.avatar_url}">` : "";
  } else {
    preview.innerHTML = "";
  }
}

$("#btnAdd").addEventListener("click", () => openItemModal(null));

/* 音频试听：选择新文件后可播放预览 */
$("#fAudio").addEventListener("change", () => {
  const ap = $("#fAudioPreview");
  const f = $("#fAudio").files[0];
  if (f) {
    ap.src = URL.createObjectURL(f);
    ap.classList.remove("hidden");
  } else {
    ap.pause();
    ap.removeAttribute("src");
    ap.classList.add("hidden");
  }
});

/* 拖放：音频文件自动进音频栏，图片文件自动进头像栏（头像走 128x128 webp 处理流程） */
(function () {
  const modalEl = $("#modal");
  const hint = $(".drop-hint");
  let dragDepth = 0;
  function setDrag(on) {
    modalEl.classList.toggle("drag-over", on);
    hint.classList.toggle("hidden", !on);
  }
  function extOf(name) { return (name.split(".").pop() || "").toLowerCase(); }
  function setFileToInput(input, file) {
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event("change"));
  }
  modalEl.addEventListener("dragenter", (e) => {
    if (!e.dataTransfer) return;
    e.preventDefault();
    dragDepth++;
    setDrag(true);
  });
  modalEl.addEventListener("dragleave", (e) => {
    e.preventDefault();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) setDrag(false);
  });
  modalEl.addEventListener("dragover", (e) => {
    if (!e.dataTransfer) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  });
  modalEl.addEventListener("drop", (e) => {
    e.preventDefault();
    dragDepth = 0;
    setDrag(false);
    const files = Array.from(e.dataTransfer.files || []);
    const audioFile = files.find((f) => AUDIO_EXT.includes(extOf(f.name)));
    const imageFile = files.find((f) => IMG_EXT.includes(extOf(f.name)));
    if (audioFile) setFileToInput($("#fAudio"), audioFile);
    if (imageFile) setFileToInput($("#fAvatar"), imageFile);
  });
})();

$("#itemForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData();
  fd.set("name", $("#fName").value.trim());
  fd.set("source", $("#fSource").value);
  fd.set("gender", $("#fGender").value);
  fd.set("age", $("#fAge").value);
  fd.set("occupation", $("#fOccupation").value);
  fd.set("tags", $("#fTags").value);
  const avatarFile = avatarFileProcessed || $("#fAvatar").files[0] || null;
  const audioFile = $("#fAudio").files[0];
  if (avatarFile) fd.set("avatar", avatarFile, avatarFile.name);
  if (audioFile) fd.set("audio", audioFile, audioFile.name);
  try {
    if (editingId) {
      await api(`/api/items/${editingId}`, { method: "PUT", body: fd });
    } else {
      await api("/api/items", { method: "POST", body: fd });
    }
    closeModal("modal");
    await loadAll();
  } catch (err) {
    alert(err.message);
  }
});

/* ---------- 删除 ---------- */
$("#cardGrid").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-act]");
  if (!btn) return;
  const card = btn.closest(".card");
  const id = card.dataset.id;
  const item = state.items.find((i) => i.id === id);
  if (btn.dataset.act === "edit") {
    openItemModal(item);
  } else if (btn.dataset.act === "folder") {
    try {
      await api(`/api/items/${id}/open-folder`, { method: "POST" });
    } catch (err) { alert(err.message); }
  } else if (btn.dataset.act === "del") {
    if (!confirm(`确定删除「${item.name}」吗？`)) return;
    try {
      await api(`/api/items/${id}`, { method: "DELETE" });
      if (state.currentId === id) { audio.pause(); state.currentId = null; }
      await loadAll();
    } catch (err) { alert(err.message); }
  } else if (btn.dataset.act === "play") {
    playItem(id);
  } else if (btn.dataset.act === "seek") {
    seekTo(btn, id, e);
  }
});

function seekTo(progressEl, id, ev) {
  if (state.currentId !== id || !audio.duration) return;
  const rect = progressEl.getBoundingClientRect();
  const ratio = (ev.clientX - rect.left) / rect.width;
  audio.currentTime = ratio * audio.duration;
}

/* ---------- 枚举管理：新建 / 重命名（设置弹窗、表单小 +、筛选区新建共用） ---------- */
let enumCtx = { kind: null, mode: "create", old: null };
const ENUM_LABELS = { sources: "来源", genders: "性别", ages: "年龄", occupations: "职业" };
function openEnumModal(mode, kind, oldValue) {
  enumCtx = { kind, mode, old: oldValue };
  $("#enumTitle").textContent = (mode === "rename" ? "重命名" : "新建") + ENUM_LABELS[kind] + "枚举";
  $("#enumValue").value = oldValue || "";
  openModal("enumModal");
  $("#enumValue").focus();
}
document.querySelectorAll(".mini-add").forEach((btn) => {
  btn.addEventListener("click", () => openEnumModal("create", btn.dataset.kind, null));
});
$("#enumOk").addEventListener("click", async () => {
  const value = $("#enumValue").value.trim();
  if (!value) return;
  try {
    const isTag = enumCtx.kind === "tags";
    const body = isTag
      ? (enumCtx.mode === "rename" ? { old: enumCtx.old, new: value } : { value })
      : (enumCtx.mode === "rename"
          ? { kind: enumCtx.kind, old: enumCtx.old, new: value }
          : { kind: enumCtx.kind, value });
    const res = await api(isTag ? "/api/tags" : "/api/enums", {
      method: enumCtx.mode === "rename" ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    state.enums = { ...state.enums, ...res.enums };  // 合并，避免覆盖丢 tags
    // 刷新弹窗里的 select：新建自动选中新值；重命名时若原值被选中则切到新值
    if (!isTag) {
      const sel = ["fSource", "fGender", "fAge", "fOccupation", "bSource", "bGender", "bAge", "bOccupation"];
      const map = { fSource: "sources", fGender: "genders", fAge: "ages", fOccupation: "occupations",
                    bSource: "sources", bGender: "genders", bAge: "ages", bOccupation: "occupations" };
      sel.forEach((id) => {
        const el = $("#" + id);
        if (el) {
          const kind = map[id];
          let selected = el.value;
          if (kind === enumCtx.kind) {
            if (enumCtx.mode === "rename" && selected === enumCtx.old) selected = value;
            else if (enumCtx.mode !== "rename") selected = value;
          }
          fillSelect(el, state.enums[kind], selected);
        }
      });
    }
    refreshEnumsUI();
    await loadAll();   // 重拉条目与枚举，卡片立即显示最新分类/标签
    renderSettings();
    closeModal("enumModal");
  } catch (err) { alert(err.message); }
});
$("#enumValue").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#enumOk").click(); });

/* ---------- 筛选区的新建按钮 ---------- */
document.querySelectorAll(".chip-add").forEach((btn) => {
  btn.addEventListener("click", () => {
    const kind = { source: "sources", gender: "genders", age: "ages", occupation: "occupations" }[btn.closest(".filter-row").dataset.kind];
    openEnumModal("create", kind, null);
  });
});

/* ---------- 设置弹窗：枚举列表（重命名 / 删除） ---------- */
function renderSettings() {
  document.querySelectorAll(".settings-group").forEach((group) => {
    const kind = group.dataset.kind;
    const box = group.querySelector(".settings-items");
    box.innerHTML = "";
    (state.enums[kind] || []).forEach((v) => {
      const row = document.createElement("div");
      row.className = "settings-item";
      row.innerHTML = `<span class="settings-value" title="${esc(v)}">${esc(v)}</span>
        <div class="settings-ops">
          <button class="icon-btn" data-act="ren" title="重命名">✎</button>
          <button class="icon-btn danger" data-act="del" title="删除">🗑</button>
        </div>`;
      row.querySelector('[data-act="ren"]').addEventListener("click", () => openEnumModal("rename", kind, v));
      row.querySelector('[data-act="del"]').addEventListener("click", async () => {
        const what = kind === "tags" ? "标签" : "枚举";
        if (!confirm(`确定删除${what}「${v}」吗？`)) return;
        try {
          const isTag = kind === "tags";
          const res = await api(isTag ? "/api/tags" : "/api/enums", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(isTag ? { value: v } : { kind, value: v }),
          });
          state.enums = { ...state.enums, ...res.enums };
          refreshEnumsUI();
          await loadAll();
          renderSettings();
        } catch (err) { alert(err.message); }
      });
      box.appendChild(row);
    });
  });
}

function refreshEnumsUI() {
  // 清理筛选区中已失效的枚举值
  ["source", "gender", "age", "occupation"].forEach((k) => {
    if (state.filters[k] && !state.enums[k + "s"].includes(state.filters[k])) state.filters[k] = null;
  });
}

$("#btnSettings").addEventListener("click", () => {
  renderSettings();
  openModal("settingsModal");
});

/* ---------- 批量添加 ---------- */
let batchGroups = [];

$("#btnBatch").addEventListener("click", () => {
  batchGroups = [];
  $("#bDir").value = "";
  $("#batchList").innerHTML = "";
  $("#batchStatus").textContent = "";
  fillSelect($("#bSource"), state.enums.sources, "");
  fillSelect($("#bGender"), state.enums.genders, "");
  fillSelect($("#bAge"), state.enums.ages, "");
  fillSelect($("#bOccupation"), state.enums.occupations, "");
  openModal("batchModal");
});

$("#bDir").addEventListener("change", (e) => {
  const files = Array.from(e.target.files);
  batchGroups = files
    .filter((f) => AUDIO_EXT.includes((f.name.split(".").pop() || "").toLowerCase()))
    .map((f) => ({
      name: f.name.replace(/\.[^.]+$/, ""),  // 默认名称 = 文件名去扩展名
      audio: f,
    }));
  renderBatchList();
});

function renderBatchList() {
  const box = $("#batchList");
  box.innerHTML = "";
  batchGroups.forEach((g, i) => {
    const row = document.createElement("div");
    row.className = "batch-item";
    row.innerHTML = `
      <div class="b-line1">
        <input type="text" value="${esc(g.name)}" data-b-name="${i}" title="条目名称">
        <span class="b-audio-name" title="${esc(g.audio.name)}">${esc(g.audio.name)}</span>
      </div>
      <div class="b-line2">
        <select data-b-gender="${i}" title="性别"></select>
        <select data-b-age="${i}" title="年龄"></select>
        <select data-b-occupation="${i}" title="职业"></select>
        <input type="text" placeholder="其他标签（逗号分隔）" data-b-tags="${i}" title="其他标签">
      </div>`;
    // 行内下拉预选顶部统一值，可逐行修改
    fillSelect(row.querySelector(`[data-b-gender="${i}"]`), state.enums.genders, $("#bGender").value);
    fillSelect(row.querySelector(`[data-b-age="${i}"]`), state.enums.ages, $("#bAge").value);
    fillSelect(row.querySelector(`[data-b-occupation="${i}"]`), state.enums.occupations, $("#bOccupation").value);
    box.appendChild(row);
  });
  $("#batchStatus").textContent = batchGroups.length ? `已选择 ${batchGroups.length} 个音频` : "未选择音频文件";
}

$("#bSubmit").addEventListener("click", async () => {
  if (!batchGroups.length) { alert("请先选择音频文件"); return; }
  const fd = new FormData();
  fd.set("source", $("#bSource").value);
  fd.set("gender", $("#bGender").value);
  fd.set("age", $("#bAge").value);
  fd.set("occupation", $("#bOccupation").value);
  batchGroups.forEach((g, i) => {
    const nameInput = document.querySelector(`[data-b-name="${i}"]`);
    const tagsInput = document.querySelector(`[data-b-tags="${i}"]`);
    const genderSel = document.querySelector(`[data-b-gender="${i}"]`);
    const ageSel = document.querySelector(`[data-b-age="${i}"]`);
    const occSel = document.querySelector(`[data-b-occupation="${i}"]`);
    fd.set(`name_${i}`, (nameInput ? nameInput.value : g.name).trim());
    fd.set(`tags_${i}`, tagsInput ? tagsInput.value : "");
    fd.set(`gender_${i}`, genderSel ? genderSel.value : "");
    fd.set(`age_${i}`, ageSel ? ageSel.value : "");
    fd.set(`occupation_${i}`, occSel ? occSel.value : "");
    fd.set(`audio_${i}`, g.audio, g.audio.name);
    if (g.avatar) fd.set(`avatar_${i}`, g.avatar, g.avatar.name);
  });
  const btn = $("#bSubmit");
  btn.disabled = true;
  btn.textContent = "导入中…";
  try {
    const res = await api("/api/batch/import", { method: "POST", body: fd });
    const msg = `成功导入 ${res.imported.length} 条` + (res.errors.length ? `，失败 ${res.errors.length} 条：${res.errors.join("；")}` : "");
    alert(msg);
    closeModal("batchModal");
    await loadAll();
  } catch (err) {
    alert(err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "批量导入";
  }
});

/* ---------- 键盘：Esc 关闭弹窗 ---------- */
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal:not(.hidden)").forEach((m) => m.classList.add("hidden"));
  }
});

/* ---------- 暗/亮主题 ---------- */
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("tts-theme", theme); } catch (e) { /* 忽略 */ }
  const btn = $("#btnTheme");
  if (btn) {
    btn.textContent = theme === "dark" ? "☀️" : "🌙";
    btn.title = theme === "dark" ? "切换到亮色" : "切换到暗色";
  }
}

$("#btnTheme").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  applyTheme(cur === "dark" ? "light" : "dark");
});

/* 启动时同步按钮状态（head 内联脚本已提前设置 data-theme 防闪烁） */
applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light");

/* ---------- 卡片大小滑块（整体缩放，localStorage 持久化，重启保持） ---------- */
const CARD_SIZE_KEY = "tts-card-size";
function applyCardSize(v) {
  document.documentElement.style.setProperty("--card-min", v);  // 数字，CSS 内 calc(... * 1px)
  try { localStorage.setItem(CARD_SIZE_KEY, v); } catch (e) { /* 忽略 */ }
}
(function () {
  const slider = $("#cardSize");
  let saved = 0;
  try { saved = parseInt(localStorage.getItem(CARD_SIZE_KEY)) || 0; } catch (e) { /* 忽略 */ }
  if (!saved) {
    // 默认按当前视口宽度排 5 列（容器左右 padding 24*2 + 4 个 14px 间隙）
    const avail = window.innerWidth - 48 - 4 * 14;
    saved = Math.max(180, Math.round(avail / 5));
  }
  slider.value = saved;
  applyCardSize(saved);
  slider.addEventListener("input", () => applyCardSize(parseInt(slider.value)));
})();

/* ---------- 启动 ---------- */
loadAll().catch((err) => alert("加载失败：" + err.message));
