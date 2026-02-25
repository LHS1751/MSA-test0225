## 做成「長期背景服務」（Windows 內建：排程工作）
內網環境不方便安裝額外 Service Wrapper 時，最穩定的是用 Windows Task Scheduler 於「開機自動啟動」+「失敗自動重試」。本專案已附好腳本。

1) 建立設定檔
- 複製 [config/app.env.example](config/app.env.example) → `config/app.env`
- 填入你的 SQLite/MQTT/HTTP 參數（包含 `MQTT_USERNAME` / `MQTT_PASSWORD`）

cd C:\Users\alexa\Desktop\MSA3.0
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3) 註冊開機自啟任務（用 SYSTEM 執行，不需密碼）
以系統管理員 PowerShell 執行：
```powershell
cd C:\Users\alexa\Desktop\MSA3.0
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_task.ps1
```

4) 檢查日誌
- 日誌檔：`logs/msa3_flytime.log`

5) 解除安裝
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\uninstall_task.ps1
```
# MSA3 飛行時數彙整服務（MQTT + SQLite + 內網 UI）

此服務用於在內網環境下，透過 MQTT 取得每台 DJI 無人機的 `total_flight_time`（秒），每日自動落庫，並提供 Web UI 查詢「指定日期區間」每台無人機的飛行時數。

## 功能
- 訂閱 MQTT Topic：`thing/product/+/osd`
- 解析 Payload 中的 `total_flight_time`（單位秒），寫入 SQLite
- 每天 00:00 / 06:00 / 12:00 / 18:00 自動初始化當日資料（處理多天未上線情境）
- `paho-mqtt`（MQTT client）

若你的伺服器無法連外 `pip install`，請改用：
- 或在可連外機器先下載 wheel，拷貝到伺服器後離線安裝：`pip install *.whl`

## SQLite 建表
服務啟動時會自動執行 [msa3_flytime/migrations.sql](msa3_flytime/migrations.sql) 建表/建索引。

## 設定
用環境變數設定（建議以 Windows 服務或排程啟動時注入）。

必要：
- `SQLITE_PATH`（預設 `data/msa3_flytime.sqlite3`）
- `MQTT_HOST` / `MQTT_PORT`（如需帳密：`MQTT_USERNAME` / `MQTT_PASSWORD`）

- `HTTP_PORT`（預設 `8000`）

備註：服務使用系統本機時間（請用 `timedatectl` 設定 Jetson 的系統時區）。
# (建議) 建立 venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# 設定環境變數後啟動
python -m msa3_flytime.main

## NVIDIA Jetson（Ubuntu/Linux）執行方式

### 1) 安裝與依賴
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

cd /opt
sudo git clone <your-repo-url> msa3_flytime
sudo chown -R $USER:$USER /opt/msa3_flytime
cd /opt/msa3_flytime

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 建立設定檔
- 複製 [config/app.env.example](config/app.env.example) → `config/app.env`
- 依需求修改：`MQTT_HOST` / `MQTT_PORT` / `MQTT_USERNAME` / `MQTT_PASSWORD`

備註：如果你是從 Windows 複製 `app.env` 到 Jetson，請確保是 LF 換行（本專案的 `scripts/run_service.sh` 會自動處理常見 CRLF 情況）。

### 3) 前景執行（最簡單）
```bash
cd /opt/msa3_flytime
chmod +x scripts/run_service.sh
./scripts/run_service.sh
```

### 4) 開機自啟（systemd）
1) 以範本建立 service 檔（預設專案位置是 `/opt/msa3_flytime`，若不是請先改路徑）
```bash
cd /opt/msa3_flytime
chmod +x scripts/run_service.sh
sudo cp scripts/msa3_flytime.service.example /etc/systemd/system/msa3_flytime.service
sudo systemctl daemon-reload
sudo systemctl enable --now msa3_flytime
```

2) 查看狀態與日誌
```bash
systemctl status msa3_flytime --no-pager
journalctl -u msa3_flytime -f
```

3) 停止/重啟
```bash
sudo systemctl stop msa3_flytime
sudo systemctl restart msa3_flytime
```

啟動後：
- UI：`http://<server-ip>:8000/`
- API：`http://<server-ip>:8000/api/...`

- `GET /api/summary?start=YYYY-MM-DD&end=YYYY-MM-DD`
- `GET /api/drone/<drone_sn>/range?start=...&end=...`

python -m venv .venv

.\.venv\Scripts\Activate.ps1
