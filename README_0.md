# FLIR Thermal Analyzer - 伺服器部署版本

這是一個將 FLIR Thermal Analyzer 打包用於伺服器部署的版本。
我們對程式碼進行了優化，並加上了處理併發請求 (Concurrent Requests) 的伺服器 (Gunicorn/Waitress)，讓多位使用者可以同時上傳、分析資料並存入資料庫。

## 目錄結構
- `app/` - 應用程式原始碼與靜態檔案
- `Dockerfile` - 用於建構 Docker 映像檔的設定
- `docker-compose.yml` - 用於輕鬆啟動 Docker 容器的設定檔
- `run_server.sh` - 在 Linux/Mac 上直接執行的腳本
- `run_server.bat` - 在 Windows 上直接執行的腳本

## 部署與安裝方式

您可以選擇使用 **Docker (推薦)** 或 **原生環境 (Python)** 兩種方式進行部署。

### 方式一：使用 Docker 部署 (最推薦)
Docker 部署可以確保環境一致，並且我們已經預先安裝好系統層級的依賴軟體 (例如 `exiftool`)，省去您手動安裝的麻煩。

**先決條件**：確認伺服器已安裝 Docker 與 Docker Compose。

1. 打開終端機 (Terminal)，進入本資料夾 (`FLIR_server`)。
2. 執行以下指令啟動服務：
   ```bash
   docker-compose up -d
   ```
3. 系統將會自動啟動，並在背景執行。
4. (說明) Docker 會自動於此資料夾下建立映射用的子目錄 (`data`, `uploads`, `processed`, `models`)，確保所有使用者上傳的圖片與儲存的資料庫 (`flir_data.db`) 在重啟後依然能永久保留。

### 方式二：使用原生 Python 環境執行
如果您不方便使用 Docker，也可以直接在系統上執行。

**先決條件**：
1. 需安裝 Python 3.8 以上版本。
2. **必須在系統中安裝 `exiftool`** (否則無法讀取高精度溫度資料)：
   - **Ubuntu/Debian**: `sudo apt-get install exiftool`
   - **Mac**: `brew install exiftool`
   - **Windows**: 從[官網](https://exiftool.org/)下載並加到系統環境變數 PATH 中。

**執行步驟 (Linux/Mac)**：
1. 開啟終端機，進入本資料夾。
2. 執行啟動腳本 (首次執行會自動建立虛擬環境並安裝所需套件)：
   ```bash
   ./run_server.sh
   ```

**執行步驟 (Windows)**：
1. 雙擊 `run_server.bat` 執行 (首次執行會自動建立虛擬環境並安裝 Waitress 等所需套件)。

## 如何連線使用

伺服器預設會運行在 `5050` port。
如果您將系統部署在伺服器上 (假設內部 IP 為 `10.20.32.XXX`)：

1. 請確認伺服器的防火牆 (Firewall) 已開放 **TCP 5050** port。
2. 讓內網的任何人透過瀏覽器輸入網址：
   ```
   http://10.20.32.XXX:5050
   ```
3. 即可進行資料上傳、ROI 分析。得益於 Gunicorn/Waitress 執行緒池 (Thread Pool) 與 SQLite WAL 模式，**所有使用者可以同時操作**，結果會統一寫入伺服器端的同一個資料庫 (`flir_data.db`)。
4. 使用者隨時可以從網頁介面上選擇「匯出 JSON」或「匯出 CSV」來取得所有整理好的分析結果。
