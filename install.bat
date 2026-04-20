@echo off
chcp 65001 >nul 2>&1
setlocal

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
set "PY_INSTALL_LOG=%TEMP_DIR%\python-install.log"
if exist "%PY_INSTALL_LOG%" del /q "%PY_INSTALL_LOG%" >nul 2>&1
"%TEMP_DIR%\python-installer.exe" /quiet /log "%PY_INSTALL_LOG%" ^
    TargetDir="%PYTHON_DIR%" ^
    InstallAllUsers=0 Include_launcher=0 Include_test=0 ^
    AssociateFiles=0 Shortcuts=0 Include_doc=0 ^
    Include_tcltk=0 PrependPath=0 CompileAll=0
set "PY_EXIT=%errorlevel%"

if not exist "%PYTHON_DIR%\python.exe" (
    echo       [WARN] Silent install did not create python.exe ^(exit=%PY_EXIT%^)
    echo       Retrying with visible progress window (may prompt for permission)...
    "%TEMP_DIR%\python-installer.exe" /passive /log "%PY_INSTALL_LOG%" ^
        TargetDir="%PYTHON_DIR%" ^
        InstallAllUsers=0 Include_launcher=0 Include_test=0 ^
        AssociateFiles=0 Shortcuts=0 Include_doc=0 ^
        Include_tcltk=0 PrependPath=0 CompileAll=0
    set "PY_EXIT=%errorlevel%"
)

if not exist "%PYTHON_DIR%\python.exe" (
    echo.
    echo       [ERROR] Python install failed ^(final exit=%PY_EXIT%^)
    echo       Target dir: %PYTHON_DIR%
    echo       Common causes:
    echo         - antivirus blocked the installer
    echo         - missing Visual C++ Redistributable
    echo         - UAC prompt cancelled
    echo       Manual fallback: download and extract to the target dir above:
    echo         %PYTHON_URL%
    if exist "%PY_INSTALL_LOG%" (
        echo.
        echo       ---- Last 30 lines of installer log ----
        powershell -NoProfile -Command "Get-Content -LiteralPath '%PY_INSTALL_LOG%' -Tail 30"
        echo       ----------------------------------------
    )
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
set "PIP_UPGRADE_LOG=%TEMP_DIR%\pip-upgrade.log"
set "PIP_INSTALL_LOG=%TEMP_DIR%\pip-install.log"
if exist "%PIP_UPGRADE_LOG%" del /q "%PIP_UPGRADE_LOG%" >nul 2>&1
if exist "%PIP_INSTALL_LOG%" del /q "%PIP_INSTALL_LOG%" >nul 2>&1
echo       首次安裝可能需數分鐘，下載進度將顯示在下方。

"%PYTHON_DIR%\python.exe" -m pip install --upgrade pip --progress-bar on --log "%PIP_UPGRADE_LOG%"
if errorlevel 1 (
    echo       [WARN] pip upgrade failed, continue with current pip.
    echo       Log: %PIP_UPGRADE_LOG%
)

"%PYTHON_DIR%\python.exe" -m pip install -r "%ROOT%requirements.txt" --progress-bar on --log "%PIP_INSTALL_LOG%"
if errorlevel 1 (
    echo       Standard install failed, retrying with trusted-host...
    "%PYTHON_DIR%\python.exe" -m pip install -r "%ROOT%requirements.txt" --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org --progress-bar on --log "%PIP_INSTALL_LOG%"
    if errorlevel 1 (
        goto :pip_requirements_failed
    )
)
echo       Python 套件安裝完成。
goto :gpu_check

:pip_requirements_failed
echo.
echo       [ERROR] Python package installation failed.
echo       Please verify access to pypi.org and files.pythonhosted.org, then retry.
echo       Log file: %PIP_INSTALL_LOG%
echo.
echo       ---- Last 40 lines from pip log ----
powershell -NoProfile -Command "if (Test-Path '%PIP_INSTALL_LOG%') { Get-Content -Path '%PIP_INSTALL_LOG%' -Tail 40 } else { Write-Output 'pip log not found' }"
echo       ------------------------------------
pause
exit /b 1

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
