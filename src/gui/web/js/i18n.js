/**
 * i18n.js — Translation system for The Obsidian Edge UI
 * Loaded before all other scripts. Provides global `t()` function.
 */
const I18N = (function() {

    const TRANSLATIONS = {
        "en": {
            // Main window
            "app_title": "Tack ComfyUI Launcher",
            "ready": "Ready",
            "sidebar_brand": "TACK COMFYUI LAUNCHER",
            "sidebar_status": "All-in-One Manager",

            // Sidebar
            "sidebar_environments": "Environments",
            "sidebar_launch": "Launch",
            "sidebar_plugins": "Plugins",
            "sidebar_versions": "Versions",
            "sidebar_snapshots": "Snapshots",

            // Home page
            "sidebar_home": "Home",
            "home_hero_title": "TACK COMFYUI LAUNCHER",
            "home_hero_subtitle": "All-in-One Manager",
            "home_select_env": "Select Environment",
            "home_section_title": "Quick Access",
            "home_btn_output": "Image Output",
            "home_btn_models": "Models",
            "home_btn_nodes": "Custom Nodes",
            "home_btn_root": "Root Directory",
            "home_btn_registry": "Tool Registry",
            "home_btn_recommended": "Recommended Tools",
            "home_no_env_selected": "Please select an environment first.",
            "home_folder_not_found": "Folder not found. Make sure the environment has been initialized.",
            "home_no_envs": "No environments found. Create one in the Environments page.",

            // Language
            "language": "Language",

            // Env panel
            "env_create": "Create",
            "env_clone": "Clone",
            "env_delete": "Delete",
            "env_refresh": "Refresh",
            "env_col_name": "Name",
            "env_col_branch": "Branch",
            "env_col_commit": "Commit",
            "env_col_sandbox": "Sandbox",
            "env_col_created": "Created",
            "env_create_title": "Create Environment",
            "env_clone_title": "Clone Environment",
            "env_name": "Name:",
            "env_branch": "Branch:",
            "env_commit": "Commit:",
            "env_commit_placeholder": "Leave empty for latest",
            "env_source": "Source:",
            "env_new_name": "New Name:",
            "env_creating": "Creating '{}'...",
            "env_cloning": "Cloning '{}' to '{}'...",
            "env_deleting": "Deleting '{}'...",
            "env_count": "{} environment(s)",
            "env_confirm_delete": "Delete environment '{}'?",
            "env_edit": "Edit",
            "env_select_to_clone": "Select an environment to clone.",
            "env_select_to_delete": "Select an environment to delete.",
            "env_version_type": "Version:",
            "env_fetch_versions": "Fetch Versions",
            "env_select_version": "Select a version...",
            "env_fetching_versions": "Fetching available versions...",

            // Python/CUDA version switching
            "env_advanced_options": "Advanced Options",
            "env_python_version": "Python Version:",
            "env_cuda_version": "CUDA / PyTorch:",
            "env_recommended": "Recommended",
            "env_refresh_versions": "Refresh Version List",
            "env_version_hint_cached": "List updated on {}. Click to refresh.",
            "env_version_hint_offline": "Currently using offline list. Click to refresh for latest versions.",
            "env_refresh_success": "Version list updated.",
            "env_refresh_failed": "Refresh failed, using offline list.",
            "env_downloading_python": "Downloading Python {}...",
            "env_reinstall_pytorch": "Reinstall PyTorch",
            "env_reinstall_confirm": "Will reinstall torch, torchvision, torchaudio for {}. Other packages unchanged.",
            "env_reinstall_success": "PyTorch reinstall complete.",
            "env_reinstall_failed": "PyTorch reinstall failed: {}",

            "loading": "Loading...",
            "info": "Info",
            "error": "Error",
            "confirm": "Confirm",
            "yes": "Yes",
            "cancel": "Cancel",

            // Launcher panel
            "launch_environment": "Environment:",
            "launch_port": "Port:",
            "launch_start": "Start",
            "launch_stop": "Stop",
            "launch_refresh": "Refresh",
            "launch_log": "Log Output",
            "launch_status": "Status:",
            "launch_status_stopped": "Stopped",
            "launch_status_running": "Running (PID: {}, Port: {})",
            "launch_starting": "Starting ComfyUI...",
            "launch_stopping": "Stopping ComfyUI...",
            "launch_started": "ComfyUI started (PID: {}, Port: {})",
            "launch_stopped": "ComfyUI stopped.",
            "launch_select_env": "Select an environment first.",
            "launch_export_log": "Export Log",
            "launch_export_success": "Log exported successfully.",
            "launch_export_no_log": "No log file found for this environment.",
            "launch_export_cancelled": "Export cancelled.",

            // Launcher tabs
            "launch_tab_launcher": "Launcher",
            "launch_tab_running": "Running List",
            "launch_running_env": "Environment",
            "launch_running_port": "Port",
            "launch_running_pid": "PID",
            "launch_running_version": "Version",
            "launch_running_actions": "Actions",
            "launch_running_empty": "No running environments.",
            "launch_running_open": "Open Browser",
            "launch_running_stop": "Stop",
            "launch_running_stopping": "Stopping...",
            "launch_running_stopped_ok": "Environment stopped.",
            "launch_running_count": "{} running",
            "launch_port_conflict": "Port {} is in use, auto-changed to {}",

            // Plugin panel
            "plugin_environment": "Environment:",
            "plugin_url_placeholder": "Plugin Git URL or local path...",
            "plugin_analyze": "Analyze",
            "plugin_conflict_report": "Conflict Report",
            "plugin_risk_level": "Risk Level:",
            "plugin_col_package": "Package",
            "plugin_col_current": "Current",
            "plugin_col_new": "New",
            "plugin_col_type": "Type",
            "plugin_col_risk": "Risk",
            "plugin_analyzing": "Analyzing...",
            "plugin_analysis_complete": "Analysis complete.",
            "plugin_select_env_and_path": "Select an environment and enter a plugin path.",

            // Version panel
            "version_environment": "Environment:",
            "version_target": "Target:",
            "version_load": "Load Commits",
            "version_switch": "Switch to Selected",
            "version_update": "Update to Latest",
            "version_col_hash": "Hash",
            "version_col_message": "Message",
            "version_col_author": "Author",
            "version_col_date": "Date",
            "version_loading": "Loading commits...",
            "version_switching": "Switching version...",
            "version_updating": "Updating...",
            "version_switched": "Version switched.",
            "version_updated": "Updated to latest.",
            "version_select_commit": "Select a commit to switch to.",
            "version_confirm_switch": "Switch to commit {}?",
            "version_confirm_update": "Update to latest version?",
            "version_type": "Version Type:",
            "version_type_branch": "Branch",
            "version_type_tag": "Tag",
            "version_available_tags": "Available Tags",
            "version_available_branches": "Available Branches",
            "version_fetching": "Fetching versions...",
            "version_fetch_failed": "Failed to fetch versions: {}",
            "version_refresh_versions": "Refresh Versions",
            "version_tag": "Tag:",
            "version_no_tags": "No tags found",
            "version_selected": "Selected",
            "version_tag_count": "{} tag(s) available",
            "version_branch_count": "{} branch(es) available",

            // Snapshot panel
            "snapshot_environment": "Environment:",
            "snapshot_create": "Create",
            "snapshot_restore": "Restore",
            "snapshot_delete": "Delete",
            "snapshot_refresh": "Refresh",
            "snapshot_col_id": "ID",
            "snapshot_col_trigger": "Trigger",
            "snapshot_col_commit": "Commit",
            "snapshot_col_created": "Created",
            "snapshot_creating": "Creating snapshot...",
            "snapshot_restoring": "Restoring...",
            "snapshot_created": "Snapshot created: {}",
            "snapshot_restored": "Restored from {}",
            "snapshot_deleted": "Snapshot deleted.",
            "snapshot_select_to_restore": "Select a snapshot to restore.",
            "snapshot_select_to_delete": "Select a snapshot to delete.",
            "snapshot_confirm_restore": "Restore from '{}'?",
            "snapshot_confirm_delete": "Delete snapshot '{}'?",
            "snapshot_count": "{} snapshot(s)",
        },
        "zh-TW": {
            // Main window
            "app_title": "塔克ComfyUI啟動器",
            "ready": "就緒",
            "sidebar_brand": "塔克COMFYUI啟動器",
            "sidebar_status": "多功能環境管理工具",

            // Sidebar
            "sidebar_environments": "環境管理",
            "sidebar_launch": "啟動器",
            "sidebar_plugins": "插件管理",
            "sidebar_versions": "版本控制",
            "sidebar_snapshots": "快照管理",

            // Home page
            "sidebar_home": "首頁",
            "home_hero_title": "塔克COMFYUI啟動器",
            "home_hero_subtitle": "多功能環境管理工具",
            "home_select_env": "選擇環境",
            "home_section_title": "快速存取",
            "home_btn_output": "圖片輸出",
            "home_btn_models": "模型",
            "home_btn_nodes": "節點插件",
            "home_btn_root": "根目錄",
            "home_btn_registry": "工具倉庫",
            "home_btn_recommended": "推薦工具",
            "home_no_env_selected": "請先選擇環境",
            "home_folder_not_found": "資料夾不存在，請確認環境已初始化。",
            "home_no_envs": "尚無環境，請至環境管理頁面建立。",

            // Language
            "language": "語言",

            // Env panel
            "env_create": "建立",
            "env_clone": "複製",
            "env_delete": "刪除",
            "env_refresh": "重新整理",
            "env_col_name": "名稱",
            "env_col_branch": "分支",
            "env_col_commit": "提交",
            "env_col_sandbox": "沙箱",
            "env_col_created": "建立時間",
            "env_create_title": "建立環境",
            "env_clone_title": "複製環境",
            "env_name": "名稱：",
            "env_branch": "分支：",
            "env_commit": "提交：",
            "env_commit_placeholder": "留空使用最新版",
            "env_source": "來源：",
            "env_new_name": "新名稱：",
            "env_creating": "正在建立 '{}'...",
            "env_cloning": "正在複製 '{}' 到 '{}'...",
            "env_deleting": "正在刪除 '{}'...",
            "env_count": "{} 個環境",
            "env_confirm_delete": "確定刪除環境 '{}'？",
            "env_edit": "編輯",
            "env_select_to_clone": "請先選擇要複製的環境",
            "env_select_to_delete": "請先選擇要刪除的環境",
            "env_version_type": "版本：",
            "env_fetch_versions": "取得版本列表",
            "env_select_version": "選擇版本...",
            "env_fetching_versions": "正在取得可用版本...",

            // Python/CUDA version switching
            "env_advanced_options": "進階選項",
            "env_python_version": "Python 版本：",
            "env_cuda_version": "CUDA / PyTorch：",
            "env_recommended": "推薦",
            "env_refresh_versions": "刷新版本清單",
            "env_version_hint_cached": "清單更新於 {}，點此刷新",
            "env_version_hint_offline": "目前為離線清單，點此刷新取得最新版本",
            "env_refresh_success": "版本清單已更新",
            "env_refresh_failed": "刷新失敗，使用離線清單",
            "env_downloading_python": "正在下載 Python {}...",
            "env_reinstall_pytorch": "重裝 PyTorch",
            "env_reinstall_confirm": "將重裝 torch, torchvision, torchaudio 為 {} 版本，其他套件不變",
            "env_reinstall_success": "PyTorch 重裝完成",
            "env_reinstall_failed": "PyTorch 重裝失敗：{}",

            "loading": "載入中...",
            "info": "提示",
            "error": "錯誤",
            "confirm": "確認",
            "yes": "是",
            "cancel": "取消",

            // Launcher panel
            "launch_environment": "環境：",
            "launch_port": "埠號：",
            "launch_start": "啟動",
            "launch_stop": "停止",
            "launch_refresh": "重新整理",
            "launch_log": "日誌輸出",
            "launch_status": "狀態：",
            "launch_status_stopped": "已停止",
            "launch_status_running": "運行中（PID: {}，埠號: {}）",
            "launch_starting": "正在啟動 ComfyUI...",
            "launch_stopping": "正在停止 ComfyUI...",
            "launch_started": "ComfyUI 已啟動（PID: {}，埠號: {}）",
            "launch_stopped": "ComfyUI 已停止",
            "launch_select_env": "請先選擇環境",
            "launch_export_log": "匯出日誌",
            "launch_export_success": "日誌匯出成功",
            "launch_export_no_log": "此環境尚無日誌檔案",
            "launch_export_cancelled": "已取消匯出",

            // Launcher tabs
            "launch_tab_launcher": "啟動器",
            "launch_tab_running": "運行列表",
            "launch_running_env": "環境名稱",
            "launch_running_port": "埠號",
            "launch_running_pid": "PID",
            "launch_running_version": "版本",
            "launch_running_actions": "操作",
            "launch_running_empty": "目前沒有運行中的環境",
            "launch_running_open": "開啟瀏覽器",
            "launch_running_stop": "停止",
            "launch_running_stopping": "正在停止...",
            "launch_running_stopped_ok": "環境已停止",
            "launch_running_count": "{} 個運行中",
            "launch_port_conflict": "埠號 {} 已被佔用，自動改為 {}",

            // Plugin panel
            "plugin_environment": "環境：",
            "plugin_url_placeholder": "插件 Git URL 或本地路徑...",
            "plugin_analyze": "分析",
            "plugin_conflict_report": "衝突報告",
            "plugin_risk_level": "風險等級：",
            "plugin_col_package": "套件",
            "plugin_col_current": "目前版本",
            "plugin_col_new": "新版本",
            "plugin_col_type": "類型",
            "plugin_col_risk": "風險",
            "plugin_analyzing": "分析中...",
            "plugin_analysis_complete": "分析完成",
            "plugin_select_env_and_path": "請選擇環境並輸入插件路徑",

            // Version panel
            "version_environment": "環境：",
            "version_target": "目標：",
            "version_load": "載入提交紀錄",
            "version_switch": "切換至選取版本",
            "version_update": "更新至最新版",
            "version_col_hash": "雜湊值",
            "version_col_message": "訊息",
            "version_col_author": "作者",
            "version_col_date": "日期",
            "version_loading": "正在載入提交紀錄...",
            "version_switching": "正在切換版本...",
            "version_updating": "正在更新...",
            "version_switched": "版本已切換",
            "version_updated": "已更新至最新版",
            "version_select_commit": "請先選擇要切換的提交",
            "version_confirm_switch": "確定切換至提交 {}？",
            "version_confirm_update": "確定更新至最新版本？",
            "version_type": "版本類型：",
            "version_type_branch": "分支",
            "version_type_tag": "標籤",
            "version_available_tags": "可用標籤",
            "version_available_branches": "可用分支",
            "version_fetching": "正在取得版本...",
            "version_fetch_failed": "取得版本失敗：{}",
            "version_refresh_versions": "重新整理版本",
            "version_tag": "標籤：",
            "version_no_tags": "未找到標籤",
            "version_selected": "已選擇",
            "version_tag_count": "{} 個標籤可用",
            "version_branch_count": "{} 個分支可用",

            // Snapshot panel
            "snapshot_environment": "環境：",
            "snapshot_create": "建立",
            "snapshot_restore": "還原",
            "snapshot_delete": "刪除",
            "snapshot_refresh": "重新整理",
            "snapshot_col_id": "快照 ID",
            "snapshot_col_trigger": "觸發原因",
            "snapshot_col_commit": "提交",
            "snapshot_col_created": "建立時間",
            "snapshot_creating": "正在建立快照...",
            "snapshot_restoring": "正在還原...",
            "snapshot_created": "快照已建立：{}",
            "snapshot_restored": "已從 {} 還原",
            "snapshot_deleted": "快照已刪除",
            "snapshot_select_to_restore": "請先選擇要還原的快照",
            "snapshot_select_to_delete": "請先選擇要刪除的快照",
            "snapshot_confirm_restore": "確定從 '{}' 還原？",
            "snapshot_confirm_delete": "確定刪除快照 '{}'？",
            "snapshot_count": "{} 個快照",
        },
    };

    let currentLang = "zh-TW";

    function t(key) {
        const args = Array.prototype.slice.call(arguments, 1);
        const dict = TRANSLATIONS[currentLang] || TRANSLATIONS["en"];
        let text = dict[key] || TRANSLATIONS["en"][key] || key;
        // Replace {} placeholders with args
        args.forEach(function(arg) {
            text = text.replace('{}', arg);
        });
        return text;
    }

    function setLanguage(lang) {
        if (TRANSLATIONS[lang]) {
            currentLang = lang;
            document.documentElement.lang = lang === 'zh-TW' ? 'zh-Hant' : 'en';
            retranslateAll();
        }
    }

    function getLanguage() {
        return currentLang;
    }

    function retranslateAll() {
        document.querySelectorAll('[data-i18n]').forEach(function(el) {
            el.textContent = t(el.dataset.i18n);
        });
        // Update page title in header
        var pageTitle = document.getElementById('page-title');
        if (pageTitle && pageTitle.dataset.i18n) {
            pageTitle.textContent = t(pageTitle.dataset.i18n);
        }
    }

    return { t: t, setLanguage: setLanguage, getLanguage: getLanguage, retranslateAll: retranslateAll };
})();

// Global shorthand
var t = I18N.t.bind(I18N);
