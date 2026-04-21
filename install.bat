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
:: Use the embeddable zip distribution (not the WiX .exe bundle).
:: The WiX bundle installer refuses to write TargetDir when the same version
:: is already registered on the machine (WixBundleInstalled=1) and exits 0
:: without producing python.exe, leaving tools\python\ empty. The embeddable
:: zip has no registry check and always extracts — matching the pattern
:: already used by src/core/version_manager.download_python().
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"

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

echo       Downloading Python %PYTHON_VERSION% (embeddable)...
set "PY_ZIP=%TEMP_DIR%\python-%PYTHON_VERSION%-embed.zip"
if exist "%PY_ZIP%" del /q "%PY_ZIP%" >nul 2>&1
curl -L --progress-bar -o "%PY_ZIP%" "%PYTHON_URL%"
if errorlevel 1 (
    echo       curl failed, trying PowerShell...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PY_ZIP%'"
)
if not exist "%PY_ZIP%" (
    echo.
    echo       [ERROR] Python download failed.
    echo       Download manually: %PYTHON_URL%
    echo       Save as: %PY_ZIP%
    echo       Then re-run install.bat
    pause
    exit /b 1
)

echo       Extracting Python %PYTHON_VERSION% to %PYTHON_DIR%...
if not exist "%PYTHON_DIR%" mkdir "%PYTHON_DIR%"
powershell -NoProfile -Command "Expand-Archive -LiteralPath '%PY_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
if not exist "%PYTHON_DIR%\python.exe" (
    echo.
    echo       [ERROR] Python extraction failed.
    echo       Target dir: %PYTHON_DIR%
    echo       Zip file:   %PY_ZIP%
    echo       Try extracting manually and re-run install.bat.
    pause
    exit /b 1
)

echo       Enabling site-packages in python._pth...
:: Embeddable builds ship with `#import site` commented out in python3XX._pth,
:: which prevents pip-installed packages (e.g. PySide6) from being importable.
:: Uncomment it so Lib\site-packages\ is on sys.path.
:: Must write the file back WITHOUT a BOM. `Set-Content -Encoding UTF8` in
:: Windows PowerShell 5.1 prepends a BOM, which corrupts the first line of
:: python*._pth (e.g. `python312.zip`) and makes Python fail to locate the
:: stdlib zip with "ModuleNotFoundError: No module named 'encodings'".
:: The file is pure ASCII, so -Encoding ASCII is safe and BOM-free.
powershell -NoProfile -Command "Get-ChildItem -LiteralPath '%PYTHON_DIR%' -Filter 'python*._pth' | ForEach-Object { (Get-Content -LiteralPath $_.FullName) -replace '^#import site', 'import site' | Set-Content -LiteralPath $_.FullName -Encoding ASCII }"

echo       Bootstrapping pip via get-pip.py...
set "GET_PIP=%TEMP_DIR%\get-pip.py"
if exist "%GET_PIP%" del /q "%GET_PIP%" >nul 2>&1
curl -L --progress-bar -o "%GET_PIP%" "%GET_PIP_URL%"
if errorlevel 1 (
    echo       curl failed, trying PowerShell...
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%GET_PIP%'"
)
if not exist "%GET_PIP%" (
    echo.
    echo       [ERROR] get-pip.py download failed.
    echo       Download manually: %GET_PIP_URL%
    echo       Save as: %GET_PIP%
    echo       Then re-run install.bat
    pause
    exit /b 1
)
"%PYTHON_DIR%\python.exe" "%GET_PIP%"
if errorlevel 1 (
    echo.
    echo       [ERROR] pip bootstrap failed.
    echo       Try running manually:
    echo         "%PYTHON_DIR%\python.exe" "%GET_PIP%"
    pause
    exit /b 1
)
echo       Python %PYTHON_VERSION% installed.

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
if not exist "%PYTHON_DIR%\pythonw.exe" (
    echo [ERROR] pythonw.exe missing after install. Aborting launch.
    pause
    exit /b 1
)
echo Launching tool...
timeout /t 3 /nobreak >nul
call "%ROOT%start.bat"
if errorlevel 1 (
    echo.
    echo [ERROR] start.bat reported a problem. See launcher-startup.log.
    pause
)
