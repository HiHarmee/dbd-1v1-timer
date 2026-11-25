@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DBD 計時器 - 打包單一 exe

where python >nul 2>&1
if %errorLevel% neq 0 (
    echo [錯誤] 找不到 Python 3，請先安裝。
    pause
    exit /b 1
)

echo [1/3] 檢查 PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorLevel% neq 0 (
    echo 安裝 PyInstaller，請稍候...
    python -m pip install --disable-pip-version-check -q pyinstaller
    if %errorLevel% neq 0 (
        echo [錯誤] PyInstaller 安裝失敗。
        pause
        exit /b 1
    )
)

echo [2/3] 開始打包（約 1~3 分鐘）...
python -m PyInstaller --noconfirm --clean --windowed --onefile --name DBDTimer --uac-admin --add-data "downed_ref_roi.png;." dbd_timer.py
if %errorLevel% neq 0 (
    echo.
    echo [錯誤] 打包失敗，請看上方訊息。
    pause
    exit /b 1
)

echo [3/3] 完成！產出 dist\DBDTimer.exe
echo 雙擊即可使用（會自動要求管理員權限）
echo 除錯模式：建立捷徑，目標改為 DBDTimer.exe --debug
echo.
pause
