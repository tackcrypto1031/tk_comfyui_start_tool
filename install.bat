@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ================================================
echo   TK ComfyUI Start Tool - 環境安裝程式
echo ================================================
echo.

:: ===== Configuration =====
set "ROOT=%~dp0"
set "TOOLS_DIR=%ROOT%tools"
set "PYTHON_DIR=%TOOLS_DIR%\python"
set "GIT_DIR=%TOOLS_DIR%\git"
set "TEMP_DIR=%TOOLS_DIR%\_temp"

set "PYTHON_VERSION=3.12.8"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-amd64.exe"

set "GIT_VERSION=2.47.1"
set "GIT_URL=https://github.com/git-for-windows/git/releases/download/v%GIT_VERSION%.windows.1/PortableGit-%GIT_VERSION%-64-bit.7z.exe"

:: Create directories
if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

:: ===== Step 1: Python =====
echo [1/4] 檢測 Python...
if exist "%PYTHON_DIR%\python.exe" (
    echo       Python 已安裝，跳過。
    goto :check_git
)

echo       下載 Python %PYTHON_VERSION%...
curl -L --progress-bar -o "%TEMP_DIR%\python-installer.exe" "%PYTHON_URL%"
if errorlevel 1 (
    echo       curl 失敗，嘗試 PowerShell...
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%TEMP_DIR%\python-installer.exe'"
)
if not exist "%TEMP_DIR%\python-installer.exe" (
    echo.
    echo       [錯誤] Python 下載失敗！
    echo       請手動下載: %PYTHON_URL%
    echo       下載後放到 %TEMP_DIR%\python-installer.exe 並重新執行本程式
    pause
    exit /b 1
)

echo       安裝 Python %PYTHON_VERSION%（靜默模式）...
"%TEMP_DIR%\python-installer.exe" /quiet TargetDir="%PYTHON_DIR%" ^
    InstallAllUsers=0 Include_launcher=0 Include_test=0 ^
    AssociateFiles=0 Shortcuts=0 Include_doc=0 ^
    Include_tcltk=0 PrependPath=0 CompileAll=0

if not exist "%PYTHON_DIR%\python.exe" (
    echo.
    echo       [錯誤] Python 安裝失敗！
    echo       請嘗試手動安裝 Python %PYTHON_VERSION% 到 %PYTHON_DIR%
    pause
    exit /b 1
)
echo       Python %PYTHON_VERSION% 安裝完成。

:: ===== Step 2: Git =====
:check_git
echo.
echo [2/4] 檢測 Git...
if exist "%GIT_DIR%\cmd\git.exe" (
    echo       Git 已安裝，跳過。
    goto :install_packages
)

echo       下載 Git %GIT_VERSION% Portable...
curl -L --progress-bar -o "%TEMP_DIR%\git-portable.exe" "%GIT_URL%"
if errorlevel 1 (
    echo       curl 失敗，嘗試 PowerShell...
    powershell -Command "Invoke-WebRequest -Uri '%GIT_URL%' -OutFile '%TEMP_DIR%\git-portable.exe'"
)
if not exist "%TEMP_DIR%\git-portable.exe" (
    echo.
    echo       [錯誤] Git 下載失敗！
    echo       請手動下載: %GIT_URL%
    echo       下載後放到 %TEMP_DIR%\git-portable.exe 並重新執行本程式
    pause
    exit /b 1
)

echo       解壓 Git（可能需要一些時間）...
"%TEMP_DIR%\git-portable.exe" -o"%GIT_DIR%" -y >nul 2>&1
if not exist "%GIT_DIR%\cmd\git.exe" (
    echo.
    echo       [錯誤] Git 解壓失敗！
    pause
    exit /b 1
)
echo       Git %GIT_VERSION% 安裝完成。

:: ===== Step 3: Python packages =====
:install_packages
echo.
echo [3/4] 安裝 Python 套件...
"%PYTHON_DIR%\python.exe" -m pip install --upgrade pip --quiet 2>nul
if errorlevel 1 (
    echo       [錯誤] pip 升級失敗！
    pause
    exit /b 1
)

"%PYTHON_DIR%\python.exe" -m pip install -r "%ROOT%requirements.txt" --quiet 2>nul
if errorlevel 1 (
    echo.
    echo       [錯誤] Python 套件安裝失敗！
    echo       請檢查網路連線後重新執行本程式
    pause
    exit /b 1
)
echo       Python 套件安裝完成。

:: ===== Step 4: GPU Detection =====
:gpu_check
echo.
echo [4/4] 檢測 GPU...
set "GPU_DETECTED=0"
nvidia-smi >nul 2>&1
if not errorlevel 1 (
    set "GPU_DETECTED=1"
)

:: ===== Clean up temp =====
if exist "%TEMP_DIR%" rd /s /q "%TEMP_DIR%" >nul 2>&1

:: ===== Summary =====
echo.
echo ================================================
echo   安裝完成！
echo ================================================
echo   Python:  %PYTHON_VERSION%
echo   Git:     %GIT_VERSION%
echo   位置:    %TOOLS_DIR%
echo.

if "%GPU_DETECTED%"=="1" (
    echo   GPU 狀態:
    for /f "tokens=*" %%i in ('nvidia-smi --query-gpu=name --format^=csv^,noheader 2^>nul') do (
        echo     GPU:      %%i
    )
    for /f "tokens=*" %%i in ('nvidia-smi --query-gpu=driver_version --format^=csv^,noheader 2^>nul') do (
        echo     驅動版本: %%i
    )
    echo     GPU 加速已就緒。
) else (
    echo   GPU 狀態:
    echo     未偵測到 NVIDIA GPU 或驅動未安裝。
    echo     ComfyUI 將以 CPU 模式運行（較慢）。
    echo     如需 GPU 加速，請安裝 NVIDIA 驅動:
    echo     https://www.nvidia.com/download/index.aspx
)

echo.
echo ================================================
echo.
echo 正在啟動工具...
timeout /t 3 /nobreak >nul
call "%ROOT%start.bat"
