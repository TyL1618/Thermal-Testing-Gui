# Thermal-Testing-GUI — 技術文件 / Technical Documentation

> **版本 Version：** v1.4  
> **日期 Date：** 2026-05-08  
> **語言 Language：** 中英對照 / Chinese–English Bilingual  
> **作者 Author：** _(TyL / Fill in your name)_

---

## 目錄 / Table of Contents

1. [專案概述 / Project Overview](#1-專案概述--project-overview)
2. [開發環境建置 / Development Environment Setup](#2-開發環境建置--development-environment-setup)
3. [專案架構 / Project Architecture](#3-專案架構--project-architecture)
4. [模組說明 / Module Reference](#4-模組說明--module-reference)
5. [功能操作說明 / User Manual](#5-功能操作說明--user-manual)
6. [API / 函式文件 / API & Function Reference](#6-api--函式文件--api--function-reference)
7. [通訊協議 / Communication Protocol](#7-通訊協議--communication-protocol)
8. [已知問題與注意事項 / Known Issues & Notes](#8-已知問題與注意事項--known-issues--notes)
9. [長時間測試資料壓縮演算法 / Long-Run Data Compression Algorithm](#9-長時間測試資料壓縮演算法--long-run-data-compression-algorithm)
10. [版本更新記錄 / Changelog](#10-版本更新記錄--changelog)

---

## 1. 專案概述 / Project Overview

### 中文

Thermal-Testing-GUI 是一套針對 **Thermal Testing Machine** 熱變形 / 維卡軟化點試驗機（HDT / VICAT）所開發的桌面監控與報告軟體，以 Python + PyQt6 實作，具備即時數據監控、多通道折線圖、測試方法管理、自動報告匯出等功能。

**主要功能：**
- 六通道即時變形量（LVDT）與溫度監控
- 多種測試方法管理（HDT-ISO、HDT-CNS、VICAT-ASTM 等）
- 測試結果記錄、預覽與匯出（Excel + 折線圖）
- 使用者登入 / 登出管理（未登入僅可監控）
- 模擬模式（離線開發 / 測試用）

### English

Thermal-Testing-GUI is a desktop monitoring and reporting application for the **Thermal Testing Machine** Heat Deflection Temperature (HDT) / Vicat Softening Point tester. Built with Python and PyQt6, it provides real-time data monitoring, multi-channel waveform display, test method management, and automated Excel report export.

**Key Features:**
- 6-channel real-time LVDT deflection and temperature monitoring
- Configurable test methods (HDT-ISO, HDT-CNS, VICAT-ASTM, etc.)
- Test result recording, preview, and export (Excel with embedded line chart)
- User login/logout (unauthenticated users can only monitor, not export)
- Simulation mode for offline development and testing

---

## 2. 開發環境建置 / Development Environment Setup

### 系統需求 / System Requirements

| 項目 Item | 需求 Requirement |
|---|---|
| 作業系統 OS | Windows 10 / 11（推薦 Recommended） |
| Python | 3.10 以上 / 3.10 or above |
| 網路 Network | 與機台同一 LAN，機台 IP `192.168.1.100`，Port `1500` |

### 安裝步驟 / Installation Steps

**步驟一：建立虛擬環境（建議）**  
**Step 1: Create a virtual environment (recommended)**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**步驟二：安裝套件**  
**Step 2: Install dependencies**

```bash
pip install PyQt6 pyqtgraph openpyxl
```

| 套件 Package | 用途 Purpose |
|---|---|
| `PyQt6` | GUI 框架 / GUI framework |
| `pyqtgraph` | 即時折線圖 / Real-time waveform plotting |
| `openpyxl` | Excel 報告匯出（含圖表）/ Excel export with chart |

**步驟三：確認目錄結構**  
**Step 3: Verify directory structure**

確認 `core/` 和 `gui/` 目錄存在，並有對應的 `__init__.py`（可為空白檔案）。  
Ensure `core/` and `gui/` directories exist with corresponding `__init__.py` files (can be empty).

```bash
# 若無 __init__.py，手動建立 / Create if missing
touch core/__init__.py
touch gui/__init__.py
```

**步驟四：啟動程式**  
**Step 4: Run the application**

```bash
python main.py
```

若無法連上機台，請在 `main.py` 中將 `simulation=False` 改為 `simulation=True` 進行離線測試。  
If the machine is unreachable, set `simulation=True` in `main.py` for offline testing.

---

## 3. 專案架構 / Project Architecture

### 目錄結構 / Directory Structure

```
Thermal-Testing-GUI/
│
├── main.py                  # 程式進入點 / Entry point
│
├── core/
│   ├── __init__.py
│   └── machine.py           # 機台通訊層 / Machine communication layer
│
├── gui/
│   ├── __init__.py
│   ├── main_window.py       # 主視窗、分頁管理、登入狀態 / Main window & auth state
│   ├── login_panel.py       # 登入頁面 / Login panel
│   ├── monitor_panel.py     # 監控頁面（主功能）/ Monitor panel (main function)
│   ├── setup_panel.py       # 測試方法設定 / Test method setup
│   └── report_panel.py      # 報告產生與匯出 / Report generation & export
│
└── test_data/               # 測試記錄暫存（程式啟動時自動清空）
                             # Temp storage for test records (cleared on startup)
```

### 模組關係圖 / Module Relationship Diagram

```
main.py
  └── TestingMachine (core/machine.py)
        │  signals: data_updated, status_updated, connected
        │
  └── MainWindow (gui/main_window.py)
        ├── LoginPanel      ──→ login_success signal ──→ MainWindow._on_login_success()
        ├── MonitorPanel    ──→ test_finished signal  ──→ ReportPanel.add_test_record()
        ├── SetupPanel      ──→ methods_changed signal──→ MonitorPanel.on_methods_updated()
        └── ReportPanel
```

### 資料流 / Data Flow

```
機台 TCP (528 bytes)
  └── TestingMachine._receive_loop()
        └── _process_packet()
              ├── 解析 LVDT (deflection mm)
              ├── 解析溫度 (°C)
              └── emit data_updated(channels)
                    └── MonitorPanel.update_data()
                          ├── 更新 ChannelCard 顯示
                          ├── 記錄折線圖歷史（測試進行中）
                          └── 移動平均平滑化 (SMOOTH_N=8)
```

---

## 4. 模組說明 / Module Reference

### 4.1 `core/machine.py` — 機台通訊層

**中文：** 負責與 Thermal Testing Machine 建立 TCP 連線、發送/接收 528-byte 封包、解析 LVDT 與溫度資料，並透過 Qt 信號向 GUI 推送更新。

**English:** Handles TCP connection to the Thermal Testing Machine, sends/receives 528-byte packets, parses LVDT and temperature data, and pushes updates to the GUI via Qt signals.

---

### 4.2 `gui/main_window.py` — 主視窗

**中文：** 管理所有分頁的生命週期，包括登入狀態控制（未登入時停用 Setup / Report 分頁）、右上角使用者資訊顯示、登出確認。

**English:** Manages the lifecycle of all tabs, including authentication state control (Setup/Report tabs disabled when not logged in), top-right user info display, and logout confirmation.

---

### 4.3 `gui/login_panel.py` — 登入頁面

**中文：** 簡易登入介面。帳號密碼以 SHA-256 比對，不明文儲存。目前為硬編碼開發者帳號；未來可替換 `_verify()` 函式接資料庫。

**English:** Simple login interface. Passwords are compared using SHA-256 hashing (never stored in plaintext). Currently uses a hardcoded developer account; replace the `_verify()` function to integrate a database in the future.

---

### 4.4 `gui/monitor_panel.py` — 監控頁面

**中文：** 核心功能頁面。即時顯示六通道數值卡片、折線圖、測試控制按鈕（TEST/STOP/ZERO/UP/DOWN）。測試結束後自動彈出儲存對話框，並發送 `test_finished` 信號給 ReportPanel。

**English:** Core feature panel. Displays real-time 6-channel data cards, waveform chart, and test control buttons (TEST/STOP/ZERO/UP/DOWN). On test stop, auto-shows a save dialog and emits `test_finished` signal to ReportPanel.

---

### 4.5 `gui/setup_panel.py` — 設定頁面

**中文：** 測試方法管理。可新增、修改、刪除測試方法，設定撓曲值、加熱速率、負載單位、壓力清單、跨距清單及報告欄位。修改後透過 `methods_changed` 信號通知 MonitorPanel 更新下拉選單。

**English:** Test method management. Allows creating, editing, and deleting test methods, configuring deflection limit, heating rate, load unit, pressure list, span list, and report fields. Changes are broadcast via the `methods_changed` signal to update MonitorPanel's dropdown.

---

### 4.6 `gui/report_panel.py` — 報告頁面

**中文：** 測試記錄管理與報告產生。左側為記錄列表，右側為報告欄位填寫與折線圖預覽。可匯出 `.xlsx`（含兩個工作表：報告頁 + 折線圖、原始數據頁）。

**English:** Test record management and report generation. Left panel shows the record list; right panel has report field inputs and a waveform preview. Exports `.xlsx` containing two sheets: a formatted report with embedded chart, and a raw data sheet.

---

## 5. 功能操作說明 / User Manual

### 5.1 登入 / Login

1. 程式啟動後自動停留在 **LOGIN** 分頁。  
   The app starts on the **LOGIN** tab automatically.

2. 輸入帳號與密碼，按 **LOGIN** 或按 Enter 確認。  
   Enter your username and password, then press **LOGIN** or hit Enter.

3. 登入成功後，畫面右上角顯示 `顯示名稱 (帳號)`，並出現 **LOGOUT** 按鈕。  
   After successful login, the top-right corner shows `Display Name (username)` with a **LOGOUT** button.

4. 未登入狀態下，**SETUP** 和 **REPORT** 分頁呈灰色無法點選；**MONITOR** 分頁可正常使用。  
   Without login, the **SETUP** and **REPORT** tabs are grayed out; **MONITOR** remains accessible.

> **開發者帳號 / Developer Account**  
> 帳號 Username：`admin`　密碼 Password：`123abc`

---

### 5.2 監控頁面操作 / Monitor Panel Operations

| 按鈕 Button | 功能 Function |
|---|---|
| **▶ TEST** | 開始測試，重置折線圖與計時器 / Start test, reset chart and timer |
| **■ STOP**（測試中）| 停止測試，彈出儲存對話框 / Stop test, open save dialog |
| **▲ UP** | 馬達上升 / Motor move up |
| **▼ DOWN** | 馬達下降 / Motor move down |
| **■ STOP**（控制區）| 立即停止馬達 / Immediately stop motor |
| **◎ ZERO** | 所有通道 LVDT 軟體歸零 / Software zero all LVDT channels |

**測試流程 / Test Flow:**

1. 確認通道啟用狀態（右上角 checkbox）。  
   Check channel enable state (checkbox on each card).

2. 在 **TEST SETUP** 區選擇測試方法、加熱速率，並填入任務名稱。  
   In the **TEST SETUP** section, select test method, heating rate, and enter a task name.

3. 按 **▶ TEST** 開始，計時器啟動，折線圖開始記錄。  
   Press **▶ TEST** to start; the timer begins and the chart starts recording.

4. 按 **■ STOP** 結束測試，彈出儲存對話框。可截圖（PNG）或匯出 CSV，兩個動作可獨立執行，對話框不會在單次操作後自動關閉。點「不儲存，直接關閉」才會關閉視窗。  
   Press **■ STOP** to end the test; a save dialog appears. Screenshot (PNG) and CSV export can be performed independently — the dialog stays open after each action. Click "Close without saving" to dismiss.

5. 測試資料自動傳送至 **REPORT** 頁面的記錄列表。  
   Test data is automatically sent to the **REPORT** tab's record list.

---

### 5.3 設定頁面操作 / Setup Panel Operations

1. 從左側清單選擇一個測試方法，右側欄位自動填入。  
   Select a test method from the left list; the right fields auto-populate.

2. 修改所需欄位（撓曲值、速率、壓力清單等）。  
   Modify the desired fields (deflection, rate, pressure list, etc.).

3. 按 **儲存** 保存，或輸入新名稱後按 **儲存** 建立新方法。  
   Press **儲存 (Save)** to update, or type a new name and press **儲存** to create a new method.

4. 刪除方法：選中後按 **刪除**（至少保留一個方法）。  
   Delete a method: select it and press **刪除 (Delete)** (at least one method must remain).

---

### 5.4 報告頁面操作 / Report Panel Operations

1. 左側列表顯示本次開機後的所有測試記錄。  
   The left list shows all test records from the current session.

2. 點選記錄 → 按 **匯入至報告產生器** → 右側欄位與折線圖更新。  
   Select a record → click **匯入至報告產生器 (Import to Report Generator)** → right panel updates.

3. 填寫基本資訊欄位（客戶名稱、材料名稱等）。  
   Fill in the basic info fields (customer name, material, etc.).

4. 按 **匯出報告** 選擇儲存路徑，產生 `.xlsx` 檔案。  
   Click **匯出報告 (Export Report)** to choose a save path and generate the `.xlsx` file.

**匯出的 Excel 結構 / Exported Excel Structure:**

| 工作表 Sheet | 內容 Contents |
|---|---|
| `Report` | 報告頁首資訊 + 通道資料表格 + 內嵌折線圖 |
| `ChartData` | 時間序列原始數據（時間、各通道變形量） |

---

## 6. API / 函式文件 / API & Function Reference

### 6.1 `TestingMachine` 類別

```python
class TestingMachine(QObject)
```

**Qt 信號 / Qt Signals**

| 信號 Signal | 參數 Parameters | 說明 Description |
|---|---|---|
| `data_updated` | `list[ChannelData]` | 每收到一包資料後發射 / Emitted on each data packet |
| `status_updated` | `str` | 狀態訊息更新 / Status message update |
| `connected` | `bool` | 連線成功/失敗 / Connection success or failure |
| `raw_data_received` | `bytes` | 原始 528-byte 封包 / Raw 528-byte packet |

**主要方法 / Main Methods**

```python
def connect(self) -> bool
```
建立 TCP 連線或啟動模擬模式。  
Establishes TCP connection or starts simulation mode.

```python
def disconnect(self)
```
關閉 TCP 連線。  
Closes the TCP connection.

```python
def zero(self)
```
以目前 AD 原始值為基準進行軟體歸零，所有通道變形量歸零。  
Software zero using current raw AD values as reference; all channels reset to 0.0 mm.

```python
def start_test(self)
```
標記測試開始（`test_running = True`），不發送任何 WRITE 封包。  
Marks test as started (`test_running = True`); no WRITE packet is sent.

```python
def stop_test(self)
```
標記測試停止（`test_running = False`）。  
Marks test as stopped.

```python
def move_up(self)
def move_down(self)
def stop(self)
```
控制馬達上升 / 下降 / 停止，透過 IO Output bit 操作。  
Control motor up/down/stop via IO Output bit manipulation.

```python
def calibrate(self, ch_index: int, known_mm: float)
```
單點校正 LVDT 換算係數。把棒子移到已知位置後呼叫。  
Single-point LVDT calibration. Move the probe to a known position, then call this method.

```python
# 使用範例 / Example
machine.calibrate(5, 1.0)   # CH6，棒子位在 1.0mm 位置
```

---

### 6.2 `ChannelData` 類別

```python
class ChannelData
```

| 屬性 Attribute | 型別 Type | 說明 Description |
|---|---|---|
| `ch_id` | `int` | 通道編號（1-based）/ Channel ID (1-based) |
| `temperature` | `float` | 溫度（°C）/ Temperature in °C |
| `deflection` | `float` | 換算後變形量（mm）/ Converted deflection in mm |
| `raw_ad` | `int` | 原始 AD 值 / Raw AD value |
| `zero_ref_ad` | `int \| None` | 歸零基準 AD 值 / Zero reference AD value |
| `enabled` | `bool` | 是否啟用 / Channel enabled state |
| `deflection_limit` | `float` | 終點變形量閾值（mm）/ End-point deflection threshold |

---

### 6.3 `TestRecord` 類別（`report_panel.py`）

```python
class TestRecord
```

| 屬性 Attribute | 型別 Type | 說明 Description |
|---|---|---|
| `record_id` | `str` | 唯一識別碼（時間戳）/ Unique ID (timestamp) |
| `name` | `str` | 完整記錄名稱 / Full record name |
| `test_name` | `str` | 任務名稱 / Task name |
| `test_date` | `str` | 測試日期 (`YYYY/MM/DD`) |
| `test_method` | `str` | 測試方法名稱 / Test method name |
| `time_data` | `list[float]` | 時間序列（秒）/ Time series in seconds |
| `deflection_data` | `dict[int, list[float]]` | 各通道變形量歷史 / Per-channel deflection history |
| `temp_data` | `dict[int, list[float]]` | 各通道溫度歷史 / Per-channel temperature history |
| `channels` | `list[dict]` | 通道終值資訊 / Channel final-value info |

**主要方法 / Main Methods**

```python
@classmethod
def from_dict(cls, d: dict) -> TestRecord
```
從 JSON dict 重建 TestRecord 物件（目前啟動時不載入，保留供未來使用）。  
Reconstruct a TestRecord from a JSON dict (currently not loaded on startup; reserved for future use).

```python
def to_dict(self) -> dict
```
序列化為 JSON-serializable dict，供存入磁碟。  
Serialize to a JSON-serializable dict for disk storage.

---

### 6.4 `LoginPanel` 重要方法

```python
def reset(self)
```
清除帳號/密碼欄位，隱藏錯誤訊息，焦點回到帳號欄。登出後由 `MainWindow` 呼叫。  
Clears username/password fields, hides error label, and refocuses the username field. Called by `MainWindow` after logout.

---

### 6.5 `MonitorPanel` 信號

```python
test_finished = pyqtSignal(TestRecord)
```
測試停止後發射，攜帶完整的 `TestRecord`，由 `MainWindow` 串接至 `ReportPanel.add_test_record()`。  
Emitted after test stops, carrying the complete `TestRecord`. Wired by `MainWindow` to `ReportPanel.add_test_record()`.

---

### 6.6 `SetupPanel` 信號

```python
methods_changed = pyqtSignal(dict)
```
儲存或刪除測試方法後發射，攜帶最新 `methods` dict，由 `MonitorPanel.on_methods_updated()` 接收更新下拉選單。  
Emitted after saving or deleting a test method, carrying the updated `methods` dict. Received by `MonitorPanel.on_methods_updated()` to refresh the method dropdown.

---

## 7. 通訊協議 / Communication Protocol

### 封包格式 / Packet Format（528 bytes）

```
Offset  Size  描述 Description
──────  ────  ─────────────────────────────────────────
0x00    4     CRC / Fixed header (Little-Endian uint32)
0x04    1     命令字元 1 / Command byte 1 (0x52='R' / 0x57='W')
0x05    1     命令字元 2 / Command byte 2 (0x44='D' / 0x52='R')
0x06    2     讀寫長度 / R/W length (Little-Endian, READ=0x00FB)
0x08    4     起始位址 / Start address (Little-Endian)
0x0C+   516   資料區 / Data region（RAM address 0x00 從此開始 / RAM dump starts here）
```

> **★ buf index 換算規則 / Index Conversion Rule**  
> 封包前 12 bytes（`buf[0x00~0x0B]`）為 header，RAM 資料從 `buf[0x0C]` 開始。  
> 因此：**`buf index = RAM address + 0x0C`**  
> The first 12 bytes are header. RAM data starts at `buf[0x0C]`.  
> Therefore: **`buf_index = RAM_address + 0x0C`**

### 關鍵 buf Index / Key buf Indices

> 下表所有數值為**封包 buf 索引**（= RAM address + 0x0C），直接對應 `struct.unpack_from` 的 offset 參數。  
> All values below are **buf indices** (= RAM address + 0x0C), used directly as the offset in `struct.unpack_from`.

| buf Index | RAM Address | 型別 Type | 通道 Channel | 說明 Description |
|---|---|---|---|---|
| `0x0C` | `0x00` | `int32` | — | RunSetting 控制位元 / Control bits |
| `0x14` | `0x08` | `int32` | — | IO Output（馬達控制）/ Motor control |
| `0x18` | `0x0C` | `int32` | — | IO Input（狀態讀取）/ Status read |
| `0x7C~0x90` | `0x70~0x84` | `float32` x6 | CH1–6 | 溫度（°C）/ Temperature |
| `0xAC~0xC0` | `0xA0~0xB4` | `int32` x6 | CH1–6 | LVDT AD 原始值 / Raw LVDT AD value |

### LVDT 換算公式 / LVDT Conversion Formula

```
deflection (mm) = (raw_AD − zero_ref_AD) × LVDT_AD_TO_MM
LVDT_AD_TO_MM   = −0.0001455  (實測值 / empirically calibrated)
```

負號代表 AD 值增大時棒子向內縮（變形量為負）。  
Negative sign: increasing AD value means probe retracting inward (negative deflection).

### 讀取封包 / Read Packet

```
52 44 FB 00   ← 固定 header / Fixed header
52 44         ← CMD_READ
FB 00         ← 讀取長度 0x00FB / Read length
00 00 00 00   ← 起始位址 0 / Start address 0
(512 bytes padding, all 0x00)
```

---

## 8. 已知問題與注意事項 / Known Issues & Notes

### 8.1 帳號系統 / Authentication

- 目前帳號為硬編碼，僅供開發階段使用。正式部署前請將 `login_panel.py` 中的 `_verify()` 函式替換為資料庫查詢。  
  The account is currently hardcoded for development only. Before production deployment, replace `_verify()` in `login_panel.py` with a database query.

- 密碼以 SHA-256 比對，但帳號小寫化後比對（大小寫不敏感）。  
  Passwords are compared via SHA-256; usernames are lowercased before lookup (case-insensitive).

### 8.2 測試資料儲存 / Test Data Storage

- 程式啟動時 `test_data/` 目錄下的 `.json` 檔案會被**全部刪除**，這是設計行為（避免舊記錄污染新會話）。  
  All `.json` files in `test_data/` are **deleted on startup** by design (prevents stale records from previous sessions).

- 如需保留歷史資料，請在 `report_panel.py` 的 `_load_records_from_disk()` 中修改邏輯。  
  To retain historical data, modify `_load_records_from_disk()` in `report_panel.py`.

### 8.3 LVDT buf Index 換算說明 / LVDT buf Index Explanation

- 原廠 DOC 記載 LVDT CH1 的 **RAM address 為 `0xA0`**，這是正確的。  
  The OEM datasheet lists LVDT CH1 at **RAM address `0xA0`**, which is correct.

- 封包 header 佔 `buf[0x00~0x0B]` 共 12 bytes，RAM dump 從 `buf[0x0C]` 開始。  
  讀取時須換算：**`buf index = RAM address + 0x0C`**  
  因此 LVDT CH1 讀 `buf[0xAC]`，CH2 讀 `buf[0xB0]`，以此類推——這是正常設計，非偏移 bug。  
  The packet header occupies `buf[0x00~0x0B]` (12 bytes); RAM dump begins at `buf[0x0C]`.  
  Conversion: **`buf_index = RAM_address + 0x0C`**  
  So LVDT CH1 reads `buf[0xAC]`, CH2 reads `buf[0xB0]`, etc. — this is by design, not an offset bug.

- 換算係數 `LVDT_AD_TO_MM = -0.0001455` 為初期單點校正值，尚待精確校正。  
  實測 1mm 行程約感測到 -0.168mm，顯示現有係數偏差較大，正式使用前請執行 `machine.calibrate()` 重新校正。  
  The conversion constant `LVDT_AD_TO_MM = -0.0001455` is an early single-point estimate and requires recalibration.  
  Empirical testing shows ~1mm travel reads as -0.168mm, indicating significant deviation. Run `machine.calibrate()` before production use.

### 8.4 機台不接受 WRITE 封包 / Machine Rejects WRITE Packets

- Wireshark 抓包確認：原廠軟體全程只送讀取封包。送出 WRITE 後機台不回 ACK，導致 timeout 與連線失敗。  
  Wireshark capture confirmed: the OEM software only sends read packets. Sending WRITE causes no ACK → timeout → connection failure.

- 目前 `start_test()` / `stop_test()` 均為純軟體標記，不發送任何 WRITE 指令。  
  Currently `start_test()` / `stop_test()` are software-only flags; no WRITE packet is sent.

### 8.5 openpyxl 套件 / openpyxl Dependency

- 匯出 Excel 報告需要 `openpyxl`。若未安裝，匯出時程式會自動顯示安裝提示訊息。  
  Excel report export requires `openpyxl`. If not installed, the app will show a prompt with installation instructions.

```bash
pip install openpyxl
```

---

*文件結束 / End of Documentation*

---

## 9. 長時間測試資料壓縮演算法 / Long-Run Data Compression Algorithm

> **狀態 Status：** ✅ 已實作 / Implemented（`gui/monitor_panel.py`，`CompressedBuffer` 類別）

### 9.1 背景與需求 / Background & Requirements

#### 中文

當測試時間拉長至數小時甚至數天，若持續以固定採樣率（例如 100ms/點）累積資料，記憶體與折線圖效能會崩潰。需要一套**原地壓縮**機制，在固定大小的環形陣列內儲存所有歷史資料，不論測試跑多久都不超過上限。

壓縮門檻（陣列大小）由開發者自訂，目前規劃為 **10,000 點**。

#### English

For long-running tests (hours to days), continuously accumulating data at a fixed sample rate (e.g. 100ms/point) will exhaust memory and crash the chart. A **in-place compression** scheme is needed: store all history in a fixed-size circular array that never grows beyond a set limit, regardless of test duration.

The compression threshold (array size) is developer-configurable; currently planned at **10,000 points**.

---

### 9.2 演算法原理 / Algorithm Explanation

#### 固定陣列 + 等間距抽稀 / Fixed Array + Stride Decimation

使用一個長度為 `N`（偶數）的陣列。填滿後不擴張，而是**把偶數索引的資料往前壓，奇數索引捨棄**，後半段空出來繼續存新資料。

```
初始 Y=0，K=1（每格代表1個採樣間距）：
索引：[0][1][2][3][4][5][6][7][8][9]
資料：  a  b  c  d  e  f  g  h  i  j

→ 填滿，觸發壓縮 Y→1，K=2：
保留偶數：a c e g i → 移到前5格
索引：[0][1][2][3][4][5][6][7][8][9]
資料：  a  c  e  g  i  ← 空 →  繼續存新資料

→ 再次填滿，觸發壓縮 Y→2，K=4：
保留偶數：a e i ... → 移到前5格
```

每次壓縮後，歷史資料的**時間解析度降為一半**，但整段歷史都保留在陣列內。最近的資料（後半段）始終維持最高密度。

---

### 9.3 關鍵參數與公式 / Key Parameters & Formulas

| 符號 Symbol | 說明 Description |
|---|---|
| `N` | 陣列大小（必須為偶數）/ Array size (must be even) |
| `Y` | 壓縮次數 / Compression count (starts at 0) |
| `K` | 當前增量間距 = `2^Y` / Current stride = `2^Y` |
| `i` | 寫入指標 / Write pointer |

**時間還原公式 / Time Reconstruction:**
```
T[NO] = 採樣間隔(ST) × K × NO
```
例：ST=0.1s，K=2，NO=3 → T[3] = 0.1 × 2 × 3 = 0.6s

**壓縮後寫入指標重置 / Write Pointer Reset After Compression:**
```python
i = (N) // 2   # 前半已存壓縮後歷史，從中間開始繼續寫
```
> ⚠️ 注意：若寫入邏輯是「先加 1 再寫入」，則 `i = N // 2 - 1`，避免壓縮後第一點無法更新。

**解碼位置（環形定址）/ Decode Position (Modular Addressing):**
```python
addr = NO * K
if addr >= N:
    addr = addr % (N - 1)   # 環形回繞
```

---

### 9.4 峰值保留機制 / Peak Value Preservation

#### 問題 / Problem

壓縮捨棄奇數索引時，如果**應力峰值或最大變形量剛好落在被捨棄的位置**，該筆關鍵數據會永久消失。

#### 解法 / Solution

每次壓縮前，記錄峰值所在的陣列索引，壓縮後用以下公式計算峰值的新位址，**強制將峰值寫入存活的格子**：

```python
# 每次壓縮時執行
peak_index = (peak_index + 1) // 2
```

壓縮多次後峰值依然被追蹤，不會丟失。

**範例 / Example（N=10，峰值原在索引 7）：**

```
Y=0 → 峰值在索引 7（實際時間位置 = 7 × 1 = 7）
Y=1 → 新索引 = (7+1)//2 = 4（實際時間位置 = 4 × 2 = 8）
Y=2 → 新索引 = (4+1)//2 = 2（實際時間位置 = 2 × 4 = 8）
Y=3 → 新索引 = (2+1)//2 = 1（實際時間位置 = 1 × 8 = 8）
```

峰值的**時間座標**在壓縮後仍大致保持不變。

---

### 9.5 採樣時間補償 / Sampling Time Compensation

壓縮發生在陣列填滿的瞬間，若不處理，壓縮交接點的時間間距會少一個採樣週期，造成時間誤差。

**解法：** 程式在每次寫入前**預判下一點是否會觸發壓縮**，若是，提前將採樣間隔 ×2，讓交接點時間連續。

```python
# 偽代碼 / Pseudocode
if i + 1 >= N:   # 下一點會觸發壓縮
    current_sample_interval = ST * K * 2   # 提前加倍
else:
    current_sample_interval = ST * K
```

---

### 9.6 實作說明 / Implementation Notes

**已實作於：** `gui/monitor_panel.py` → `CompressedBuffer` 類別（第 105 行起）

**實際介接點（已完成）：**
- `_start_test()`：呼叫各通道 `buf.reset()` 重置所有緩衝區
- `update_data()`：呼叫 `buf.push(elapsed, smoothed, ch.temperature)` 寫入平滑後資料
- `_refresh_plot()`：從 `buf.get_series()` 取得 `(times, deflections, temperatures)` 繪圖
- `_emit_test_record()`：從 buffer 取出完整序列傳給 `ReportPanel`

**關鍵常數（`monitor_panel.py` 頂部）：**

| 常數 Constant | 預設值 Default | 說明 Description |
|---|---|---|
| `COMPRESS_N` | `10_000` | 每通道緩衝區大小（必須為偶數）/ Buffer size per channel |
| `SMOOTH_N` | `8` | 移動平均視窗大小 / Moving average window |
| `SCROLL_WINDOW_SEC` | `300` | 捲動模式顯示視窗（秒）/ Scroll window width (seconds) |

**時間軸設計：** 直接儲存 `time.time() - t0` 的真實秒數（而非由採樣間隔推算），壓縮後時間軸仍完全準確。

---

## 10. 版本更新記錄 / Changelog

### v1.4 — 2026-05-08

**文件修正 / Documentation Fixes**

- 第 7 節封包格式：新增「★ buf index 換算規則」說明（`buf_index = RAM_address + 0x0C`），釐清封包 header 12 bytes 與 RAM address 的換算關係。  
  Section 7 packet format: added "★ buf index conversion rule" (`buf_index = RAM_address + 0x0C`) to clarify the 12-byte header offset.

- 第 7 節關鍵 Offset 表格：將欄位從「RAM address」更正為「buf index」，並補充對應的 RAM address 欄，RunSetting / IO Output / IO Input / 溫度 / LVDT 全部更正。  
  Section 7 key offsets table: corrected all values from RAM addresses to buf indices, added corresponding RAM address column.

- 第 8.3 節：原「LVDT Offset 偏移（已知問題）」重新定性——此為封包結構的正常換算，並非 bug。同時補充 LVDT 校正係數偏差警告（實測 1mm ≈ 0.168mm）。  
  Section 8.3: reclassified "LVDT offset discrepancy" — this is normal packet structure conversion, not a bug. Added calibration coefficient deviation warning (empirical: 1mm ≈ 0.168mm).

---

### v1.3 — 2026-05-07

**修正 / Bug Fixes**

- `monitor_panel.py` — `SaveResultDialog`：截圖（PNG）和匯出 CSV 完成後不再自動關閉對話框，使用者可在同一次停止操作中同時執行截圖與匯出。  
  `SaveResultDialog`: Screenshot and CSV export no longer close the dialog automatically. Users can now perform both actions in a single stop event.

**樣式 / Visual**

- 全面提升深色模式對比度：`text_mid` 從 `#8892a4` → `#b0bcd4`，`text_lo` 從 `#4a5568` → `#6a7a96`，`border` / `border_hi` 同步提亮。  
  Improved dark mode contrast across all panels: text and border colors brightened for better readability without altering the overall aesthetic.
- Tab bar 字體從 11px → 12px；GroupBox 標題從 10px → 11px；ChannelCard 溫度字體從 14px → 16px；單位標籤 mm 從 10px → 11px。  
  Incremental font size increases in key UI areas for improved legibility.
- 各 panel（`monitor_panel`、`setup_panel`、`report_panel`、`login_panel`、`main_window`）的色彩常數統一對齊新色板。  
  Color constants synchronized across all panels.

**文件 / Documentation**

- 第 9 節壓縮演算法狀態從「待實作」更新為「已實作」，補充實際常數與介接點說明。  
  Section 9 compression algorithm status updated from pending to implemented.
- 新增本版本更新記錄（第 10 節）。  
  Added this changelog section.

---

### v1.0 — 2026-05-07（初始版本 / Initial Release）

- 完成六通道即時監控、折線圖記錄（含壓縮緩衝）、測試方法管理、Excel 報告匯出、登入/登出管理。  
  Initial release: 6-channel real-time monitoring, waveform recording with compression buffer, test method management, Excel report export, and login/logout management.

---

*文件結束 / End of Documentation*