# install.bat 一鍵安裝設計

## 目標

讓全新 Windows 電腦的用戶執行一個 `install.bat`，自動安裝所有依賴並啟動工具。

## 設計決策

| 決策項目 | 選擇 | 理由 |
|----------|------|------|
| 安裝策略 | 全自動靜默安裝 | 降低使用門檻 |
| Python/Git 安裝方式 | 嵌入式/便攜版到 `tools/` | 不污染系統環境，綠色軟體體驗 |
| CUDA 處理 | 不處理，留給 `env create` | CUDA/PyTorch 是 ComfyUI 環境依賴，非工具本體依賴 |
| GPU 檢測 | 安裝完顯示報告 | 用戶一目了然 |
| 安裝後行為 | 自動啟動 `start.bat` | 一鍵到底 |
| Python 版本 | 3.12.x（靜默安裝器） | 包含完整標準庫（含 venv），相容性好 |
| bat 編碼 | UTF-8 + `chcp 65001` | 統一編碼管理 |

## 架構

### 目錄結構

```
<project>/
├─ tools/                  ← .gitignore 排除
│   ├─ python/             ← Python 靜默安裝到此（~100MB）
│   │   ├─ python.exe
│   │   ├─ pythonw.exe
│   │   ├─ Scripts/pip.exe
│   │   └─ Lib/
│   └─ git/                ← Git Portable 解壓到此（~300MB）
│       ├─ cmd/git.exe
│       └─ bin/git.exe
├─ install.bat             ← 一鍵安裝
├─ start.bat               ← 啟動（優先用 tools/ 下的 Python）
└─ launcher.py             ← 啟動時設定 Git 路徑
```

### 安裝流程

```
install.bat
  ├─ [1/4] Python: 檢測 → 下載安裝器 → 靜默安裝到 tools/python/
  ├─ [2/4] Git: 檢測 → 下載 Portable → 解壓到 tools/git/
  ├─ [3/4] pip: 升級 pip → 安裝 requirements.txt
  ├─ [4/4] GPU: 執行 nvidia-smi 檢測 → 顯示報告
  ├─ 清理暫存檔
  ├─ 顯示安裝摘要
  └─ 自動執行 start.bat
```

### 連動修改

- **start.bat**: 優先用 `tools/python/pythonw.exe`，不存在則 fallback 系統 Python
- **launcher.py**: 啟動時檢測 `tools/git/cmd/git.exe`，設定 `GIT_PYTHON_GIT_EXECUTABLE`
- **.gitignore**: 加入 `tools/`

## 錯誤處理

- 下載失敗：先嘗試 `curl`，失敗 fallback `powershell Invoke-WebRequest`，仍失敗顯示手動下載連結
- 可重複執行（冪等）：已安裝的元件自動跳過
- 最低要求：Windows 10

## 磁碟空間估算

- Python: ~100MB
- Git Portable: ~300MB
- pip 套件（PySide6 為主）: ~200MB
- 總計約 600MB
