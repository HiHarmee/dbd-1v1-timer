# DBD 1v1 單挑計時器 (修正與優化版)

---

## 🛠️ 本次修正與重大優化

### 1. 解決「切換到 DBD 後無法偵測按鍵」
- **根本原因**：DBD 是由 Easy Anti-Cheat (EAC) 以**高權限 (Administrator/High Integrity)** 啟動。Windows 的 UIPI 權限隔離機制會強制阻擋「普通權限軟體」監聽「高權限遊戲」內的按鍵。
- **徹底解決**：啟動檔已加入自動提升管理員權限機制，讓計時器與遊戲處於同等權限，進遊戲後按 `T`、`F2`、`Del` **100% 精準響應**。

### 2. 解決「切換視窗會卡住」問題
- **根本原因**：切換穿透樣式時，Windows DWM 桌面合成器的命中測試緩存未即時刷新產生死鎖，且拖曳座標在跨元件時發生座標跳動。
- **徹底解決**：
  - 加入 Windows 原生 `SWP_FRAMECHANGED | SWP_NOACTIVATE` 標記，切換視窗絕不搶奪焦點、不卡死。
  - 重構為全螢幕絕對座標拖曳，並設有螢幕四週防脫軌保護，拖曳極度滑順。

### 3. 優化視窗鎖定（穿透切換更自然）
- 按下 **`F4`**（或點擊 `[🔓]`）進入 `[🔒]` 鎖定狀態時，完全穿透滑鼠，游標在遊戲內不會產生手勢變形。
- 解鎖 `[🔓]` 時點擊即可自由拖曳。

### 4. 預設按鍵配置更新
- **開始 / 倒地紀錄 / 下一局**：**`T` 鍵**
  - 未開始 → 開始新局
  - 計時中 → 紀錄倒地時間並結束本局
  - 本局已倒地後 → 開始下一局
- **首刀**：**`F2` 鍵**（只記首刀）
- **重設**：**`Del` 鍵** (Delete)
- **Shift**：可在設定中選為任一動作的按鍵（預設未指定）
- **穿透鎖定**：`F4`
- **設定面板**：點擊右側 `⚙`

---

## 🚀 啟動方式

### 方式一：雙擊 exe（免安裝 Python，推薦給使用者）
1. 先執行 `build.bat` 打包一次（見下方）
2. 之後雙擊 `dist\DBDTimer.exe` 即可（會自動要求管理員權限）
3. 除錯模式：建立捷徑，目標改為 `DBDTimer.exe --debug`

### 方式二：批次檔（開發者用，需 Python）
直接雙擊：
- `run_timer.bat`（或 `start_timer.bat`）：一鍵啟動，會自動
  - 請求管理員權限（否則遊戲內偵測不到按鍵）
  - 檢查 Python 與必要套件（numpy、Pillow），缺少時自動安裝
  - 以無視窗方式啟動，錯誤寫入 `timer.log`
- `run_debug.bat`：除錯模式，啟動後自動開啟除錯面板與判斷區域框

*(跳出 Windows 使用者帳戶控制提示時，請點選「是」以允許管理員權限，確保在 DBD 內正常偵測按鍵)*

---

## 📦 打包成單一 exe

在專案資料夾雙擊 **`build.bat`**（需 Python 3.10+，會自動安裝 PyInstaller），或手動執行：

```
python -m PyInstaller --onefile --windowed --uac-admin --name DBDTimer --add-data "downed_ref_roi.png;." dbd_timer.py
```

產出：`dist\DBDTimer.exe`（單一檔案，約 30 MB，免安裝 Python）

注意：
- `--onefile` 啟動約需 2~4 秒（解壓到臨時目錄）
- 首次執行若被 Windows Defender 警告，選擇「仍要執行」
- `config.json`、`history.json` 會自動產生在 exe 所在資料夾（`timer.log` 僅由批次檔啟動時產生）
- 只能在 Windows 上打包 Windows 版；Linux 需在 Linux 上另行打包
