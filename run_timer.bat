@echo off
chcp 65001 >nul
cd /d "%~dp0"
title DBD 單挑計時器 - 一鍵啟動

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [提示] 正在請求管理員權限...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\" %*' -Verb RunAs"
    exit /b
)

where python >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo [錯誤] 找不到 Python 3 (python.exe)
    echo 請先安裝 Python 3.10 以上：https://www.python.org/downloads/
    echo 安裝時記得勾選 "Add python.exe to PATH"。
    echo.
    pause
    exit /b 1
)

echo 檢查必要套件 (numpy、Pillow)...
python -c "import numpy, PIL" >nul 2>&1
if %errorLevel% neq 0 (
    echo 首次執行，正在安裝套件，請稍候...
    python -m pip install --disable-pip-version-check -q numpy Pillow
    if %errorLevel% neq 0 (
        echo.
        echo [錯誤] 套件安裝失敗，請手動執行：python -m pip install numpy Pillow
        echo.
        pause
        exit /b 1
    )
) else (
    echo 套件已就緒。
)

echo 啟動計時器...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Hidden -FilePath 'pythonw' -ArgumentList 'dbd_timer.py' -WorkingDirectory '%~dp0' -RedirectStandardError '%~dp0timer.log'"

echo.
echo 已啟動！HUD 會顯示在螢幕上方。
echo ------------------------------------------------
echo  T    開始 / 倒地紀錄 / 下一局
echo  F2   首刀
echo  Del  重設        F4   滑鼠穿透鎖定
echo  F8   音效開關    S    開啟設定視窗
echo ------------------------------------------------
echo 若程式未出現，請查看 timer.log
echo.
timeout /t 4 >nul
exit /b 0
