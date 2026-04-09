# 塔克 ComfyUI 啟動器

**一款用於管理多個獨立 ComfyUI 安裝的桌面工具。**

建立、複製、快照和版本控制獨立的 ComfyUI 環境 — 每個環境擁有獨立的插件、Python 版本和 CUDA 配置。

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)]()

[English](README.md) | **繁體中文**

---

## 功能特色

### 多環境管理

- **建立**完全隔離的 ComfyUI 環境，擁有獨立的 Python 虛擬環境
- **複製**現有環境，安心進行實驗
- 自由**重新命名**及**刪除**環境
- **合併**環境之間的套件與插件（新增或取代策略）
- 每個環境都有自己的 venv、ComfyUI 安裝和插件集

### 插件管理

- 從 Git 網址**安裝**自訂節點，自動解析依賴
- **啟用 / 停用**插件，透過切換目錄實現（不會遺失資料）
- **更新**單一插件或批量更新全部插件
- 安裝前進行 **6 步驟衝突分析**：
  1. 依賴提取（requirements.txt + install.py AST 解析）
  2. Pip 模擬安裝（dry-run）
  3. 與當前環境的版本比對
  4. 關鍵套件偵測（torch、numpy、transformers 等）
  5. 風險分級（綠色 / 黃色 / 高風險 / 嚴重）
  6. 使用者建議

### 快照與還原

- **時間點快照**，記錄 pip freeze、ComfyUI commit、Python/CUDA 版本、自訂節點狀態及設定備份
- **一鍵還原**到任何歷史快照
- 在複製、合併、版本切換前**自動建立快照**
- 可配置最大快照數量，自動清理舊快照

### 版本控制

- 瀏覽並切換 ComfyUI 的**標籤**和**分支**
- 檢視最近的提交紀錄
- 一鍵更新 ComfyUI 至最新版本

### 啟動與運行

- 按環境**啟動 / 停止** ComfyUI 實例
- 可配置的啟動設定（每個環境獨立）：
  - Cross-attention 模式（pytorch、split、quad、sage、flash 等）
  - VRAM 管理（gpu_only、high、normal、low、cpu）
  - 網路設定（監聽 IP、埠號、CORS、TLS）
  - 自訂命令列參數
- **PyTorch 引擎切換** — 即時更改 CUDA 版本
- **啟動前診斷** — 依賴檢查、衝突偵測、重複節點掃描
- **日誌檢視器**，支援匯出
- 多個環境可同時在不同埠號運行

### GPU 與版本偵測

- 透過 `nvidia-smi` 自動偵測 GPU
- 根據驅動版本推薦最佳 CUDA 標籤
- Python 版本管理（3.10 – 3.13），支援嵌入式版本
- 從官方 wheel 索引擷取 PyTorch 版本

### 自動更新

- 從 GitHub 檢查新版本
- 一鍵更新，附帶進度追蹤
- 更新後自動重啟

### 國際化

- 完整支援**英文**和**繁體中文**（zh-TW）介面

---

## 截圖

> GUI 是一個現代 HTML5 SPA，運行在 PySide6 桌面視窗中。

應用程式包含以下頁面：
- **首頁** — 快速操作和資料夾捷徑
- **環境管理** — 建立、複製、編輯、刪除環境
- **啟動器** — 啟動/停止 ComfyUI，進階設定與診斷
- **插件管理** — 安裝、管理和分析自訂節點
- **版本管理** — 瀏覽和切換 ComfyUI 版本
- **快照管理** — 建立、還原和管理快照

---

## 安裝

### 系統需求

- **Windows 10/11**
- **Python 3.10+**（或使用內建的嵌入式 Python）
- **Git**（或使用內建的嵌入式 Git）
- 建議使用 **NVIDIA GPU**（支援 CPU 模式）

### 快速開始

1. **下載**最新版本，從 [GitHub Releases](https://github.com/tackcrypto1031/tk_comfyui_start_tool/releases) 或複製倉庫：

   ```bash
   git clone https://github.com/tackcrypto1031/tk_comfyui_start_tool.git
   cd tk_comfyui_start_tool
   ```

2. **安裝依賴**（使用內建 Python 可跳過）：

   ```bash
   pip install -r requirements.txt
   ```

3. **啟動應用程式**：

   雙擊 `start.bat`，或手動執行：

   ```bash
   pythonw launcher.py
   ```

4. **建立第一個環境** — 在環境管理頁面點擊「建立」，選擇 ComfyUI 版本，工具會自動處理虛擬環境建立、ComfyUI 下載、PyTorch 安裝和依賴設定。

### 內建工具

本工具可包含嵌入式執行檔，實現零依賴安裝：

```
tools/
├── git/cmd/git.exe        # 嵌入式 Git
└── python/pythonw.exe     # 嵌入式 Python
```

如果這些檔案存在，啟動器會自動使用它們。否則會使用系統安裝的 Git 和 Python。

---

## 使用方式

### GUI 模式（預設）

雙擊 `start.bat` 或執行：

```bash
pythonw launcher.py
```

### CLI 模式

本工具同時提供完整的命令列介面：

```bash
# 環境管理
python launcher.py env list
python launcher.py env create my_env --branch master
python launcher.py env create my_env --tag v0.3.0
python launcher.py env clone main my_experiment
python launcher.py env delete old_env
python launcher.py env merge source_env target_env --strategy add
python launcher.py env info my_env
python launcher.py env analyze my_env path/to/custom_node

# 快照管理
python launcher.py snapshot create my_env --reason "重大變更前"
python launcher.py snapshot list my_env
python launcher.py snapshot restore my_env snap-20250101-120000-000000
python launcher.py snapshot delete my_env snap-20250101-120000-000000

# 版本管理
python launcher.py version list my_env
python launcher.py version switch my_env v0.3.0
python launcher.py version update my_env

# 啟動 ComfyUI
python launcher.py launch start my_env --port 8188
python launcher.py launch stop my_env
python launcher.py launch status
```

---

## 設定

設定檔儲存在專案根目錄的 `config.json`：

| 設定項目 | 預設值 | 說明 |
|----------|--------|------|
| `default_env` | `"main"` | 預設環境名稱 |
| `environments_dir` | `"./environments"` | 環境儲存位置 |
| `models_dir` | `"./models"` | 共享模型目錄 |
| `snapshots_dir` | `"./snapshots"` | 快照儲存位置 |
| `max_snapshots` | `20` | 每個環境最大快照數量（自動清理最舊的） |
| `auto_snapshot` | `true` | 複製/合併前自動建立快照 |
| `auto_open_browser` | `true` | 啟動 ComfyUI 後自動開啟瀏覽器 |
| `default_port` | `8188` | ComfyUI 預設埠號 |
| `theme` | `"dark"` | 介面主題 |
| `language` | `"zh-TW"` | 介面語言（`en` 或 `zh-TW`） |

### 共享模型

所有環境共享單一 `models/` 目錄，包含以下子目錄：

```
models/
├── checkpoints/
├── loras/
├── vae/
├── controlnet/
├── clip/
├── embeddings/
└── upscale_models/
```

工具會自動為每個環境產生 `extra_model_paths.yaml`，指向此共享位置。

---

## 專案結構

```
tk_comfyui_start_tool/
├── launcher.py              # 進入點（GUI 或 CLI）
├── cli.py                   # CLI 指令（Click）
├── start.bat                # Windows GUI 啟動器
├── config.json              # 設定檔
├── VERSION.json             # 版本與更新資訊
├── requirements.txt         # Python 依賴
├── src/
│   ├── core/                # 核心邏輯
│   │   ├── env_manager.py       # 環境生命週期
│   │   ├── snapshot_manager.py  # 快照備份與還原
│   │   ├── version_manager.py   # GPU 偵測、Python/CUDA 管理
│   │   ├── version_controller.py# ComfyUI 版本切換
│   │   ├── conflict_analyzer.py # 6 步驟插件衝突分析
│   │   ├── comfyui_launcher.py  # 程序啟動/停止
│   │   ├── diagnostics.py       # 依賴與衝突檢查
│   │   └── updater.py           # 自動更新系統
│   ├── gui/
│   │   ├── bridge.py            # QWebChannel Python-JS 橋接
│   │   └── web/                 # HTML5 SPA 前端
│   ├── models/              # 資料模型
│   └── utils/               # 工具程式（pip、git、程序、檔案系統）
├── environments/            # 運行環境
├── models/                  # 共享模型檔案
├── snapshots/               # 環境快照
└── tools/                   # 內建 Git 與 Python
```

---

## 架構

應用程式是一個 **PySide6 + QWebEngineView** 的混合桌面應用。前端是 HTML5 SPA，透過 **QWebChannel** 與 Python 後端通訊。

```
┌─────────────────────────────────────────────┐
│                PySide6 視窗                  │
│  ┌───────────────────────────────────────┐  │
│  │       QWebEngineView（SPA）            │  │
│  │  ┌─────────┐  ┌───────────────────┐   │  │
│  │  │  側邊欄  │  │    頁面內容        │   │  │
│  │  │  導航    │  │                   │   │  │
│  │  └─────────┘  └───────────────────┘   │  │
│  └──────────────┬────────────────────────┘  │
│                 │ QWebChannel                │
│  ┌──────────────┴────────────────────────┐  │
│  │          Bridge（Python）              │  │
│  │  環境管理 | 啟動器 | 快照              │  │
│  │  版本控制 | 插件   | 更新器            │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

長時間運行的操作使用非同步工作模式：橋接器立即返回 `request_id`，前端輪詢進度和結果。

---

## 開發

### 執行測試

```bash
# 全部測試
pytest

# 含覆蓋率
pytest --cov

# 特定測試檔案
pytest tests/test_core/test_env_manager.py

# 模式匹配
pytest -k test_create
```

### 依賴套件

| 套件 | 用途 |
|------|------|
| PySide6 | 桌面視窗與 QWebChannel |
| click | CLI 框架 |
| rich | CLI 格式化輸出 |
| gitpython | Git 操作 |
| psutil | 程序管理 |
| pyyaml | YAML 設定檔 |
| packaging | 版本比對 |
| requests | HTTP 請求 |

---

## 授權

本專案採用 **Apache License 2.0** 授權 — 詳見 [LICENSE](LICENSE) 文件。

---

## 連結

- [GitHub 倉庫](https://github.com/tackcrypto1031/tk_comfyui_start_tool)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)
