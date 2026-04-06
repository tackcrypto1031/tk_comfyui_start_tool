# Homepage Banner & Action Cards Design

**Date:** 2026-04-06
**Status:** Approved

## Overview

在首頁右半邊內容區新增兩個區塊：Banner 歡迎圖片區域 + 功能按鈕卡片網格。

## 1. Banner 歡迎區域

- **高度**: 280px
- **背景**: 靜態預設圖片（打包在工具內），`object-fit: cover`
- **遮罩**: 從下到上的深色漸層（確保底部過渡自然），從左到右的輕微漸層
- **右上角**: 環境選擇下拉選單
  - 半透明深色背景 `#000000`，`border-outline-variant/20` 邊框
  - 呼叫 `BridgeAPI.listEnvironments()` 載入環境列表
  - 未選擇時顯示 placeholder 文字「選擇環境」
- **無其他文字或標題**，圖片為視覺主體
- **Sharp edges**（0px border-radius），符合 Obsidian Edge 設計系統

## 2. 功能按鈕區域

Banner 下方間距 `32px`，6 張卡片以 3 列 x 2 排網格排列，gap `16px`。

### 卡片樣式

- 橫向矩形，高度約 140px
- 背景圖片（靜態預設，每張不同）+ 底部深色漸層遮罩
- 底部顯示功能名稱（Space Grotesk, uppercase, 白色文字）
- Sharp edges（0px border-radius）
- Hover: 邊框變為 `#cc97ff`，圖片 `scale(1.1)` 放大，`overflow: hidden` 裁切

### 卡片內容

| # | 名稱 | 行為 | API |
|---|------|------|-----|
| 1 | 圖片輸出 | 打開選定環境的 output 資料夾 | `BridgeAPI.openFolder(env, 'output')` |
| 2 | 模型 | 打開選定環境的 models 資料夾 | `BridgeAPI.openFolder(env, 'models')` |
| 3 | 根目錄 | 打開選定環境的根目錄 | `BridgeAPI.openFolder(env, '')` |
| 4 | 節點插件 | 打開選定環境的 custom_nodes 資料夾 | `BridgeAPI.openFolder(env, 'custom_nodes')` |
| 5 | 工具倉庫 | 開啟外部網站 | `BridgeAPI.openUrl('https://www.google.com')` |
| 6 | 推薦工具 | 開啟外部網站 | `BridgeAPI.openUrl('https://www.google.com')` |

### 狀態邏輯

- **卡片 1-4**: 需要已選擇環境才能使用。未選環境時 disabled（降低透明度 `opacity: 0.4`，禁止點擊，cursor: not-allowed）
- **卡片 5-6**: 不依賴環境選擇，始終可用

## 3. 技術實作

- 頁面檔案: `src/gui/web/js/pages/home.js`
- 遵循現有 page 模式: IIFE + `App.registerPage('home', { render })`
- 使用 Tailwind CSS utility classes + custom.css 既有元件樣式
- Banner 圖片與卡片圖片放置於 `src/gui/web/images/` 目錄（暫用 placeholder）
- 環境選擇狀態存於模組局部變數

## 4. 靜態資源

需要準備 7 張圖片：
- 1 張 banner 背景圖（建議寬度 >= 1200px）
- 6 張卡片背景圖（建議寬度 >= 400px）

暫時可使用純色漸層 placeholder 替代，待設計師提供實際圖片後替換。
