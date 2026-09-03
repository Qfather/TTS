# 🎧 TTS 音频库

本地 TTS 音频库 WebUI：管理、分类、筛选、播放 TTS 音频片段。
同一套文件既支持本地 Flask 完整版（增删改），也支持 **Git Pages 静态只读版**。

## 快速开始（本地完整版）

```bat
:: 方式一：双击
start.bat

:: 方式二：命令行
pip install flask
python app.py
```

启动后浏览器自动打开 `http://127.0.0.1:5000`。

## 功能

- **单个添加**：名称、来源、性别、年龄、职业、其他标签（逗号分隔多值）、头像（可选，不传用默认头像；选择后自动裁切压缩为 128×128 WebP）、音频文件（可拖放 / 试听）
- **批量添加**：多选音频文件 → 生成列表 → 每行独立设置 性别/年龄/职业 + 名称 + 其他标签 → 批量导入
- **编辑 / 删除 / 打开文件夹**：卡片右上角操作；编辑可改分类与标签、替换头像/音频；改分类自动搬移文件夹
- **索引号**：每个条目有稳定索引号（卡片名称后半透明显示 `#n`），可用
  - `GET /api/index/<n>` 查条目、`GET /api/index/<n>/audio` 直接取音频（供 TTS 引用）
- **筛选**：来源 / 性别 / 年龄 / 职业（单行 + 左右滑动）/ 其他标签 组合筛选；底部透明搜索框仅按名称实时搜索
- **枚举管理**（⚙ 设置）：来源、性别、年龄、职业可新增/重命名/删除；其他标签可重命名/删除
- **播放**：卡片内播放/暂停、进度条拖动、时间显示；卡片大小滑块整体缩放；暗/亮主题

## Git Pages 静态只读版

> 纯静态托管**没有后端**：浏览 / 试听 / 筛选 / 搜索可用；**添加/修改需在本地 Flask 版完成**后再重新推送。

部署到 GitHub Pages 用户站点（`username.github.io`，页面从仓库根目录提供）：

```bash
# 1.（本地改完音频后）重新生成静态数据快照
python export_static.py            # 扫描 ./library 生成 ./data.json

# 2. 提交并推送（务必包含 index.html/style.css/app.js/data.json/library/）
git add -A
git commit -m "更新音色库"
git push origin main               # Pages 会自动更新

# 3. 打开 https://username.github.io 即可（页面自动识别静态模式）
```

- 页面无后端时自动读取 `./data.json` 并隐藏所有写操作（添加/批量/编辑/删除/设置）
- 音频与头像按 `library/...` 相对路径直接访问（中文路径由浏览器自动编码）
- `data.json` 由 `export_static.py` 生成，**每次本地改动后记得重新导出**；换机器/仓库同样适用

## 数据目录结构

```
library/
├── enums.json                  # 枚举：sources / genders / ages / occupations
└── <来源>/<性别>/<年龄>/<职业>/<条目名>/
    ├── meta.json               # 条目元数据（id、index、名称、分类、tags）
    ├── audio.wav               # 音频文件（任意格式）
    └── icon.webp               # 头像（文件名含 icon 的图片，可选，默认头像兜底）
```

> 直接往 `library/` 按上述结构放文件夹也能被自动扫描识别（`meta.json` 缺失会被跳过）。

## 技术栈

- 后端（完整版）：Python + Flask（单文件 `app.py`，无数据库，数据即目录结构）
- 前端：原生 HTML/CSS/JS 单页（`index.html` / `style.css` / `app.js` 位于仓库根，本地完整版与 Git Pages 静态版共用）

## 测试

```bat
python tests_smoke.py
```

> ⚠️ 注意：`tests_smoke.py` 会**清空 `library/` 下所有条目**（仅适合空库/测试环境），不要在真实数据上运行。
