"""
monitor_panel.py  ─  GOTECH HV3000 主監控面板
工業精密儀器風格：深碳纖維底色 + 螢光琥珀數字 + 即時波形

修正項目：
  1. 折線圖平滑化（移動平均，預設 N=8）
  2. Stop 後彈出儲存視窗（截圖 / CSV 匯出）
  3. 按鈕改名 TEST，Stop 後可重新 Start
  4. Stop 後可再次開始測試
  5. 打開即即時顯示行程/溫度，按 TEST 後才開始記錄折線圖和計時
"""
from __future__ import annotations
import time
import math
import csv
import os
from collections import deque
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QCheckBox,
    QSplitter, QFrame, QSizePolicy, QSpacerItem,
    QComboBox, QLineEdit, QScrollArea,
    QDialog, QDialogButtonBox, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import QTimer, Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, pyqtSignal
from PyQt6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontDatabase,
    QLinearGradient, QPainterPath, QRadialGradient,
)
import pyqtgraph as pg
import pyqtgraph.exporters

from core.machine import GotechMachine, ChannelData


# ══════════════════════════════════════════════════
#  色彩系統
# ══════════════════════════════════════════════════
C = {
    'bg_deep':    '#080a0d',
    'bg_panel':   '#0e1117',
    'bg_card':    '#141820',
    'bg_card2':   '#1a1f2a',
    'border':     '#2a3345',      # 提亮：原 #252b35
    'border_hi':  '#3d4f6a',      # 提亮：原 #2e3847
    'amber':      '#ffc233',      # 稍暖更亮
    'amber_dim':  '#7a5500',
    'green':      '#00f080',      # 更亮更飽和
    'green_dim':  '#004d26',
    'red':        '#ff6060',
    'red_dim':    '#7a0000',
    'blue':       '#5cd9ff',      # 更亮
    'blue_dim':   '#00405a',
    'text_hi':    '#f0f4ff',      # 幾乎純白，最高對比
    'text_mid':   '#b0bcd4',      # 原 #8892a4，大幅提亮
    'text_lo':    '#6a7a96',      # 原 #4a5568，提亮讓說明文字可讀
}

CH_COLORS = ['#ff6b6b','#ffa94d','#69db7c','#4fc3f7','#da77f2','#f783ac']

# 移動平均視窗大小（調大 → 更平滑，調小 → 更即時）
SMOOTH_N = 8

# 壓縮緩衝區大小（必須為偶數）。陣列填滿後自動壓縮，不論測試跑多久都不超過此上限。
COMPRESS_N = 10_000

# 捲動視窗預設寬度（秒）。顯示最近這段時間，舊資料往左滾出畫面。
SCROLL_WINDOW_SEC = 300   # 預設 5 分鐘，可自行調整


# ══════════════════════════════════════════════════
#  自定義時間 X 軸（顯示 HH:MM:SS 而非純秒數）
# ══════════════════════════════════════════════════
class TimeAxisItem(pg.AxisItem):
    """
    把 X 軸的秒數（真實 elapsed）轉成 HH:MM:SS 或 MM:SS 格式顯示。
    超過 1 小時自動切換成 HH:MM 格式，節省空間。
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._total_sec: float = 0.0

    def set_total_sec(self, sec: float):
        self._total_sec = sec

    def tickStrings(self, values, scale, spacing):
        result = []
        for v in values:
            s = max(0.0, float(v))
            h   = int(s) // 3600
            m   = (int(s) % 3600) // 60
            sec = int(s) % 60
            if self._total_sec >= 3600:
                result.append(f"{h:02d}:{m:02d}")
            else:
                result.append(f"{m:02d}:{sec:02d}")
        return result

# ══════════════════════════════════════════════════
#  CompressedBuffer：固定大小 + 等間距抽稀壓縮
# ══════════════════════════════════════════════════
class CompressedBuffer:
    """
    固定容量 N 的環形壓縮緩衝區，同時儲存：
      - deflection（變形量 mm）
      - temperature（溫度 °C）
      - 對應時間（秒，由外部傳入真實 elapsed，不在內部推算）

    演算法：陣列填滿時把偶數索引資料保留、奇數索引丟棄，
    後半段空出來繼續存新資料。每次壓縮時解析度減半，
    但整段歷史都保留在固定大小的陣列內。

    峰值保護：壓縮時同步追蹤「最大變形量」與「最大溫度」
    的陣列索引，強制讓峰值不被丟棄。

    時間軸：直接儲存 time.time() - t0 的真實秒數，
    不依賴採樣間隔估算，壓縮再多次時間軸都準確。
    """

    def __init__(self, n: int = COMPRESS_N):
        assert n % 2 == 0, "N 必須為偶數"
        self.N = n

        # 主資料陣列（預分配，避免 append 開銷）
        self._defl : List[Optional[float]] = [None] * n
        self._temp : List[Optional[float]] = [None] * n
        self._t    : List[float]           = [0.0]  * n

        self._i : int = 0   # 下一個要寫入的位置
        self._Y : int = 0   # 壓縮次數（僅用於 compression_count 回報）

        # 峰值追蹤（針對變形量絕對值、溫度最大值各一）
        self._peak_defl_idx : int   = 0
        self._peak_defl_val : float = 0.0
        self._peak_temp_idx : int   = 0
        self._peak_temp_val : float = -999.0

        self._count : int = 0   # 已寫入總點數（含壓縮前的原始點數）

    # ── 公開介面 ──────────────────────────────────
    def reset(self):
        """測試開始時重置所有狀態"""
        self._defl  = [None] * self.N
        self._temp  = [None] * self.N
        self._t     = [0.0]  * self.N
        self._i     = 0
        self._Y     = 0
        self._peak_defl_idx = 0
        self._peak_defl_val = 0.0
        self._peak_temp_idx = 0
        self._peak_temp_val = -999.0
        self._count = 0

    def push(self, elapsed: float, defl: Optional[float], temp: Optional[float]):
        """
        寫入一個新採樣點。
        elapsed：從測試開始到現在的真實秒數（time.time() - t0）。
        壓縮邏輯完全不影響時間軸準確性。
        """
        # ── 寫入
        self._defl[self._i] = defl
        self._temp[self._i] = temp
        self._t[self._i]    = elapsed
        self._count += 1

        # ── 更新峰值索引
        if defl is not None:
            if abs(defl) > abs(self._peak_defl_val):
                self._peak_defl_val = defl
                self._peak_defl_idx = self._i
        if temp is not None:
            if temp > self._peak_temp_val:
                self._peak_temp_val = temp
                self._peak_temp_idx = self._i

        self._i += 1

        # ── 陣列填滿 → 壓縮
        if self._i >= self.N:
            self._compress()

    def get_series(self) -> Tuple[List[float], List[Optional[float]], List[Optional[float]]]:
        """
        回傳 (times, deflections, temperatures)，只含已寫入的有效資料。
        """
        n = self._i   # 目前已填到的位置
        return (
            list(self._t[:n]),
            list(self._defl[:n]),
            list(self._temp[:n]),
        )

    def peak_deflection(self) -> Tuple[float, Optional[float]]:
        """回傳 (time, value) 的變形量峰值（絕對值最大）"""
        idx = self._peak_defl_idx
        if idx < self._i:
            return self._t[idx], self._defl[idx]
        return 0.0, None

    def peak_temperature(self) -> Tuple[float, Optional[float]]:
        """回傳 (time, value) 的溫度峰值"""
        idx = self._peak_temp_idx
        if idx < self._i:
            return self._t[idx], self._temp[idx]
        return 0.0, None

    @property
    def compression_count(self) -> int:
        return self._Y

    @property
    def total_points(self) -> int:
        return self._count

    # ── 內部壓縮 ───────────────────────────────────
    def _compress(self):
        """
        保留偶數索引（含其真實時間戳），奇數索引丟棄。
        時間軸因為存的是真實 elapsed，壓縮後仍然正確。
        峰值索引同步用 (idx + 1) // 2 重新定位。
        """
        half = self.N // 2
        for j in range(half):
            src = j * 2
            self._defl[j] = self._defl[src]
            self._temp[j] = self._temp[src]
            self._t[j]    = self._t[src]

        # 清空後半段
        for j in range(half, self.N):
            self._defl[j] = None
            self._temp[j] = None
            self._t[j]    = 0.0

        # 峰值索引重新對應
        self._peak_defl_idx = (self._peak_defl_idx + 1) // 2
        self._peak_temp_idx = (self._peak_temp_idx + 1) // 2

        # 確保峰值格子內容正確（防止峰值剛好落在被丟棄的奇數位）
        pd_idx = self._peak_defl_idx
        if pd_idx < half and self._defl[pd_idx] is None:
            self._defl[pd_idx] = self._peak_defl_val

        pt_idx = self._peak_temp_idx
        if pt_idx < half and self._temp[pt_idx] is None:
            self._temp[pt_idx] = self._peak_temp_val

        self._Y += 1
        self._i  = half   # 從中間繼續寫


# ══════════════════════════════════════════════════
#  工具：通用樣式片段
# ══════════════════════════════════════════════════
def _card_style(border_color=None) -> str:
    bc = border_color or C['border']
    return f"""
        background:{C['bg_card']};
        border:1px solid {bc};
        border-radius:6px;
    """

def _btn_style(color: str, hover: str) -> str:
    return f"""
        QPushButton {{
            background: transparent;
            color: {color};
            border: 1px solid {color};
            border-radius: 4px;
            padding: 8px 14px;
            font-family: 'Consolas','Courier New',monospace;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{
            background: {hover};
            color: #fff;
            border-color: {color};
        }}
        QPushButton:pressed {{
            background: {color};
            color: #000;
        }}
        QPushButton:disabled {{
            color: {C['text_lo']};
            border-color: {C['border']};
        }}
    """


# ══════════════════════════════════════════════════
#  ChannelCard：每個通道的數值卡片
# ══════════════════════════════════════════════════
class ChannelCard(QWidget):
    def __init__(self, ch_id: int, color: str, parent=None):
        super().__init__(parent)
        self.ch_id = ch_id
        self.color = color
        self.enabled = True
        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumHeight(100)
        self.setStyleSheet(f"""
            QWidget {{
                background: {C['bg_card']};
                border: 1px solid {C['border']};
                border-radius: 8px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(4)

        # ── 頂行：色塊 + 通道名 + 啟用 checkbox
        top = QHBoxLayout()
        self.dot = QLabel("●")
        self.dot.setStyleSheet(f"color:{self.color};font-size:14px;border:none;background:transparent;")
        top.addWidget(self.dot)

        lbl_ch = QLabel(f"CH {self.ch_id}")
        lbl_ch.setStyleSheet(f"""
            color:{C['text_hi']};font-size:12px;font-weight:700;
            letter-spacing:2px;border:none;background:transparent;
        """)
        top.addWidget(lbl_ch)
        top.addStretch()

        self.chk = QCheckBox()
        self.chk.setChecked(True)
        self.chk.setStyleSheet(f"""
            QCheckBox::indicator {{
                width:14px;height:14px;
                border-radius:3px;
                border:1px solid {C['border_hi']};
                background:{C['bg_card2']};
            }}
            QCheckBox::indicator:checked {{
                background:{self.color};
                border-color:{self.color};
            }}
        """)
        self.chk.stateChanged.connect(self._on_toggle)
        top.addWidget(self.chk)
        root.addLayout(top)

        # ── 變形量（大數字）
        self.lbl_deflection = QLabel("─ ─ ─")
        self.lbl_deflection.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_deflection.setStyleSheet(f"""
            color:{C['amber']};
            font-family:'Consolas','Courier New',monospace;
            font-size:26px;font-weight:700;
            letter-spacing:2px;
            border:none;background:transparent;
        """)
        root.addWidget(self.lbl_deflection)

        lbl_mm = QLabel("mm")
        lbl_mm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_mm.setStyleSheet(f"color:{C['text_lo']};font-size:11px;letter-spacing:2px;border:none;background:transparent;")
        root.addWidget(lbl_mm)

        # ── 溫度（小數字）
        self.lbl_temp = QLabel("─ ─ ─  °C")
        self.lbl_temp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_temp.setStyleSheet(f"""
            color:{C['blue']};
            font-family:'Consolas','Courier New',monospace;
            font-size:16px;
            border:none;background:transparent;
        """)
        root.addWidget(self.lbl_temp)

        # ── 測試方法標籤
        self.lbl_method = QLabel("HDT-ASTM")
        self.lbl_method.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_method.setStyleSheet(f"""
            color:{C['text_lo']};font-size:9px;letter-spacing:2px;
            border-top:1px solid {C['border']};
            padding-top:4px;background:transparent;
        """)
        root.addWidget(self.lbl_method)

    def _on_toggle(self, state):
        self.enabled = bool(state)
        alpha = "ff" if self.enabled else "59"
        self.dot.setStyleSheet(f"color:{self.color}{alpha};font-size:14px;border:none;background:transparent;")

    def update_data(self, ch: ChannelData):
        self.lbl_deflection.setText(f"{ch.deflection:+.3f}")
        self.lbl_temp.setText(f"{ch.temperature:.1f}  °C")

    def set_method(self, method: str):
        self.lbl_method.setText(method)


# ══════════════════════════════════════════════════
#  LED 狀態指示燈
# ══════════════════════════════════════════════════
class LEDWidget(QWidget):
    def __init__(self, color: str, label: str, parent=None):
        super().__init__(parent)
        self._on = False
        self._color = QColor(color)
        self._label = label
        self.setFixedSize(70, 32)

    def set_on(self, on: bool):
        self._on = on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 12, 16
        r = 6
        if self._on:
            glow = QRadialGradient(cx, cy, r * 2)
            glow.setColorAt(0, self._color)
            glow.setColorAt(1, QColor(self._color.red(), self._color.green(), self._color.blue(), 0))
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(cx - r*2, cy - r*2, r*4, r*4)
            p.setBrush(QBrush(self._color))
        else:
            dim = QColor(self._color.red()//4, self._color.green()//4, self._color.blue()//4)
            p.setBrush(QBrush(dim))

        p.setPen(QPen(QColor(255,255,255,30), 0.5))
        p.drawEllipse(cx - r, cy - r, r*2, r*2)

        p.setPen(QColor(C['text_mid']))
        p.setFont(QFont("Consolas", 8))
        p.drawText(24, 0, 46, 32, Qt.AlignmentFlag.AlignVCenter, self._label)


# ══════════════════════════════════════════════════
#  儲存結果對話框
# ══════════════════════════════════════════════════
class SaveResultDialog(QDialog):
    def __init__(self, parent, plot_widget: pg.PlotWidget,
                 time_series: List[float],
                 ch_series: Dict[int, List[Optional[float]]],
                 task_name: str):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self.time_series = time_series      # list[float]
        self.ch_series   = ch_series        # {ch_idx: list[float|None]}
        self.task_name   = task_name

        self.setWindowTitle("儲存測試結果")
        self.setFixedSize(360, 200)
        self.setStyleSheet(f"""
            QDialog {{background:{C['bg_panel']};color:{C['text_hi']};}}
            QLabel  {{background:transparent;font-family:'Consolas','Courier New',monospace;font-size:11px;}}
            QPushButton {{
                background:transparent;color:{C['amber']};
                border:1px solid {C['amber']};border-radius:4px;
                padding:8px 18px;font-family:'Consolas','Courier New',monospace;
                font-size:11px;font-weight:700;letter-spacing:1px;
            }}
            QPushButton:hover {{background:{C['amber_dim']};color:#fff;}}
            QPushButton#cancel {{color:{C['text_mid']};border-color:{C['border']};}}
            QPushButton#cancel:hover {{background:{C['border']};}}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl = QLabel("測試已停止。是否儲存結果？")
        lbl.setStyleSheet(f"color:{C['text_hi']};font-size:13px;")
        layout.addWidget(lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_screenshot = QPushButton("📷  截圖 (PNG)")
        btn_screenshot.clicked.connect(self._save_screenshot)
        btn_row.addWidget(btn_screenshot)

        btn_csv = QPushButton("📊  匯出 CSV")
        btn_csv.clicked.connect(self._save_csv)
        btn_row.addWidget(btn_csv)

        layout.addLayout(btn_row)

        btn_skip = QPushButton("不儲存，直接關閉")
        btn_skip.setObjectName("cancel")
        btn_skip.clicked.connect(self.accept)
        layout.addWidget(btn_skip)

    def _save_screenshot(self):
        default_name = f"{self.task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "儲存截圖", default_name, "PNG Files (*.png)"
        )
        if path:
            exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
            exporter.parameters()['width'] = 1200
            exporter.export(path)
            QMessageBox.information(self, "完成", f"截圖已儲存：\n{path}")
        # 不呼叫 self.accept()，讓視窗保持開啟，使用者可繼續選另一個操作

    def _save_csv(self):
        default_name = f"{self.task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "匯出 CSV", default_name, "CSV Files (*.csv)"
        )
        if path:
            xs   = self.time_series
            cols = [self.ch_series.get(i, []) for i in range(6)]
            # 各通道長度可能因壓縮略有差異，以最短對齊
            min_len = min(len(xs), *(len(c) for c in cols))
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["Time(s)", "CH1(mm)", "CH2(mm)", "CH3(mm)",
                                  "CH4(mm)", "CH5(mm)", "CH6(mm)"])
                for idx in range(min_len):
                    row = [f"{xs[idx]:.2f}"] + [
                        f"{cols[ch][idx]:.4f}" if cols[ch][idx] is not None else ""
                        for ch in range(6)
                    ]
                    writer.writerow(row)
            QMessageBox.information(self, "完成", f"CSV 已儲存：\n{path}")
        # 不呼叫 self.accept()，讓視窗保持開啟，使用者可繼續選另一個操作


# ══════════════════════════════════════════════════
#  主監控面板
# ══════════════════════════════════════════════════
class MonitorPanel(QWidget):
    test_finished = pyqtSignal(object)   # 傳出 TestRecord 給 ReportPanel

    def __init__(self, machine: GotechMachine):
        super().__init__()
        self.machine = machine
        self.ch_cards: List[ChannelCard] = []

        # ── 每通道各自一個壓縮緩衝區（固定容量，自動抽稀，永不爆炸）
        self._buffers: Dict[int, CompressedBuffer] = {
            i: CompressedBuffer(n=COMPRESS_N) for i in range(6)
        }

        # ── 平滑緩衝（每通道各自的短窗口，壓縮前先平滑）
        self._smooth_buf: Dict[int, deque] = {
            i: deque(maxlen=SMOOTH_N) for i in range(6)
        }

        self.curves: Dict[int, pg.PlotDataItem] = {}
        self.t0: float = 0.0           # 測試開始時間
        self._test_active: bool = False  # 是否正在測試（控制是否記錄資料）

        self._setup_style()
        self._setup_ui()

        self.machine.data_updated.connect(self.update_data)

        # 定期刷新曲線
        self._plot_timer = QTimer()
        self._plot_timer.timeout.connect(self._refresh_plot)
        self._plot_timer.start(100)

        # 計時器（每秒刷新 elapsed）
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._refresh_elapsed)
        self._clock_timer.start(1000)

    # ─────────────────────────────
    def _setup_style(self):
        self.setStyleSheet(f"""
            QWidget {{ background:{C['bg_deep']}; color:{C['text_hi']}; }}
            QGroupBox {{
                border:1px solid {C['border_hi']};
                border-radius:6px;
                margin-top:18px;
                padding:8px;
                font-family:'Consolas','Courier New',monospace;
                font-size:11px;
                color:{C['text_mid']};
                letter-spacing:2px;
            }}
            QGroupBox::title {{
                subcontrol-origin:margin;
                left:10px;
                padding:0 6px;
                color:{C['text_mid']};
            }}
            QLabel {{ background:transparent; }}
            QScrollBar:vertical {{
                background:{C['bg_panel']};
                width:6px;border-radius:3px;
            }}
            QScrollBar::handle:vertical {{
                background:{C['border_hi']};
                border-radius:3px;
            }}
        """)

    # ─────────────────────────────
    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(8)
        left.addWidget(self._make_plot_section(), stretch=1)
        left.addWidget(self._make_status_bar())

        left_widget = QWidget()
        left_widget.setLayout(left)
        root.addWidget(left_widget, stretch=68)
        root.addWidget(self._make_right_panel(), stretch=32)

    # ─────────────────────────────
    def _make_plot_section(self) -> QWidget:
        frame = QWidget()
        frame.setStyleSheet(f"background:{C['bg_panel']};border:1px solid {C['border']};border-radius:8px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # ── 標題列
        title_row = QHBoxLayout()
        lbl = QLabel("REALTIME  WAVEFORM")
        lbl.setStyleSheet(f"""
            color:{C['text_mid']};
            font-family:'Consolas','Courier New',monospace;
            font-size:11px;letter-spacing:4px;
        """)
        title_row.addWidget(lbl)
        title_row.addStretch()

        # 捲動 / 全程 切換按鈕
        self._scroll_mode = True   # True = 捲動視窗，False = 顯示全程
        self.btn_view_mode = QPushButton("⇔  全程")
        self.btn_view_mode.setFixedWidth(90)
        self.btn_view_mode.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C['text_mid']};
                border: 1px solid {C['border']};
                border-radius: 4px;
                padding: 3px 8px;
                font-family: 'Consolas','Courier New',monospace;
                font-size: 10px;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{ color:{C['amber']}; border-color:{C['amber']}; }}
            QPushButton:checked {{
                color:{C['amber']};
                border-color:{C['amber']};
                background:{C['amber_dim']};
            }}
        """)
        self.btn_view_mode.setCheckable(True)
        self.btn_view_mode.setChecked(False)
        self.btn_view_mode.clicked.connect(self._toggle_view_mode)
        title_row.addWidget(self.btn_view_mode)

        self.lbl_elapsed = QLabel("00:00:00")
        self.lbl_elapsed.setStyleSheet(f"""
            color:{C['amber']};
            font-family:'Consolas','Courier New',monospace;
            font-size:18px;font-weight:700;
        """)
        title_row.addWidget(self.lbl_elapsed)
        layout.addLayout(title_row)

        # ── pyqtgraph 繪圖（使用自定義時間 X 軸）
        pg.setConfigOption('background', C['bg_deep'])
        pg.setConfigOption('foreground', C['text_lo'])

        self._time_axis = TimeAxisItem(orientation='bottom')
        self._time_axis.setTextPen(C['text_lo'])

        self.plot_widget = pg.PlotWidget(axisItems={'bottom': self._time_axis})
        self.plot_widget.setBackground(C['bg_deep'])
        self.plot_widget.setLabel('left', 'DEFLECTION', units='mm',
                                  color=C['text_mid'], size='9pt')
        self.plot_widget.setLabel('bottom', 'TIME',
                                  color=C['text_mid'], size='9pt')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.15)
        self.plot_widget.getAxis('left').setTextPen(C['text_lo'])
        self.plot_widget.addLegend(
            offset=(10, 10),
            labelTextColor=C['text_mid'],
        )

        # 預設停用自動範圍（由 _refresh_plot 手動控制 X 範圍）
        self.plot_widget.enableAutoRange(axis='y', enable=True)
        self.plot_widget.enableAutoRange(axis='x', enable=False)

        for i in range(6):
            c = self.plot_widget.plot(
                pen=pg.mkPen(color=CH_COLORS[i], width=2.0),
                name=f' CH{i+1}',
            )
            self.curves[i] = c

        layout.addWidget(self.plot_widget)
        return frame

    def _toggle_view_mode(self, checked: bool):
        """切換「捲動視窗」和「顯示全程」模式"""
        self._scroll_mode = not checked
        if checked:
            self.btn_view_mode.setText("↺  捲動")
        else:
            self.btn_view_mode.setText("⇔  全程")

    # ─────────────────────────────
    def _make_status_bar(self) -> QWidget:
        frame = QWidget()
        frame.setFixedHeight(36)
        frame.setStyleSheet(f"background:{C['bg_panel']};border:1px solid {C['border']};border-radius:6px;")
        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(20)

        self.led_conn = LEDWidget(C['green'], "CONN")
        self.led_test = LEDWidget(C['amber'], "TEST")
        self.led_heat = LEDWidget(C['red'],   "HEAT")
        row.addWidget(self.led_conn)
        row.addWidget(self.led_test)
        row.addWidget(self.led_heat)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{C['border']};")
        row.addWidget(sep)

        self.lbl_status = QLabel("STANDBY")
        self.lbl_status.setStyleSheet(f"""
            color:{C['text_mid']};
            font-family:'Consolas','Courier New',monospace;
            font-size:10px;letter-spacing:2px;
        """)
        row.addWidget(self.lbl_status)
        row.addStretch()

        # 壓縮狀態顯示
        self.lbl_compress = QLabel("")
        self.lbl_compress.setStyleSheet(f"""
            color:{C['amber_dim']};
            font-family:'Consolas','Courier New',monospace;
            font-size:9px;letter-spacing:1px;
        """)
        row.addWidget(self.lbl_compress)

        lbl_ip = QLabel(f"IP  {self.machine.host}:{self.machine.port}")
        lbl_ip.setStyleSheet(f"""
            color:{C['text_lo']};
            font-family:'Consolas','Courier New',monospace;
            font-size:9px;letter-spacing:1px;
        """)
        row.addWidget(lbl_ip)

        self.machine.status_updated.connect(self._on_status)
        self.machine.connected.connect(lambda ok: self.led_conn.set_on(ok))
        return frame

    def _on_status(self, msg: str):
        self.lbl_status.setText(msg[:80])

    # ─────────────────────────────
    def _make_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background:{C['bg_panel']};border:1px solid {C['border']};border-radius:8px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        lbl_title = QLabel("Control Panel")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(f"""
            color:{C['amber']};
            font-family:'Consolas','Courier New',monospace;
            font-size:13px;font-weight:700;
            letter-spacing:4px;
            border-bottom:1px solid {C['amber_dim']};
            padding-bottom:8px;
        """)
        layout.addWidget(lbl_title)

        layout.addWidget(self._make_control_group())
        layout.addWidget(QLabel(""), stretch=0)

        ch_scroll = QScrollArea()
        ch_scroll.setWidgetResizable(True)
        ch_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ch_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")

        ch_widget = QWidget()
        ch_widget.setStyleSheet("background:transparent;")
        ch_grid = QGridLayout(ch_widget)
        ch_grid.setContentsMargins(0, 0, 0, 0)
        ch_grid.setSpacing(6)

        for i in range(6):
            card = ChannelCard(i + 1, CH_COLORS[i])
            self.ch_cards.append(card)
            r, col = divmod(i, 2)
            ch_grid.addWidget(card, r, col)

        ch_scroll.setWidget(ch_widget)
        layout.addWidget(ch_scroll, stretch=1)

        layout.addWidget(self._make_test_setup())
        return panel

    # ─────────────────────────────
    def _make_control_group(self) -> QGroupBox:
        grp = QGroupBox("MACHINE  CONTROL")
        grid = QGridLayout(grp)
        grid.setSpacing(6)

        def btn(label, color, slot):
            b = QPushButton(label)
            b.setStyleSheet(_btn_style(color, color + "44"))
            b.clicked.connect(slot)
            return b

        grid.addWidget(btn("▲  UP",    C['green'], self.machine.move_up),   0, 0)
        grid.addWidget(btn("▼  DOWN",  C['blue'],  self.machine.move_down), 0, 1)
        grid.addWidget(btn("■  STOP",  C['red'],   self.machine.stop),      1, 0)
        grid.addWidget(btn("◎  ZERO",  C['amber'], self.zero_all),          1, 1)

        # ── TEST 按鈕（Fix #3：改名 TEST，Fix #4：可重複開始）
        self.btn_test = QPushButton("▶  TEST")
        self.btn_test.setStyleSheet(_btn_style(C['green'], C['green'] + "33"))
        self.btn_test.clicked.connect(self._on_test_clicked)
        grid.addWidget(self.btn_test, 2, 0, 1, 2)

        return grp

    # ─────────────────────────────
    def _make_test_setup(self) -> QGroupBox:
        grp = QGroupBox("TEST  SETUP")
        vbox = QVBoxLayout(grp)
        vbox.setSpacing(6)

        def row_widget(label: str, widget: QWidget) -> QHBoxLayout:
            r = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{C['text_mid']};font-size:10px;letter-spacing:1px;min-width:60px;")
            r.addWidget(lbl)
            r.addWidget(widget)
            return r

        self.cbo_method = QComboBox()
        self.cbo_method.addItems(["HDT-ASTM", "HDT-CNS", "HDT-ISO", "VICAT-ASTM"])
        self.cbo_method.setStyleSheet(f"""
            QComboBox {{
                background:{C['bg_card2']};
                color:{C['text_hi']};
                border:1px solid {C['border_hi']};
                border-radius:4px;
                padding:4px 8px;
                font-family:'Consolas','Courier New',monospace;
                font-size:11px;
            }}
            QComboBox::drop-down {{border:none;}}
            QComboBox QAbstractItemView {{
                background:{C['bg_card2']};
                color:{C['text_hi']};
                selection-background-color:{C['border_hi']};
            }}
        """)
        vbox.addLayout(row_widget("METHOD", self.cbo_method))

        self.cbo_rate = QComboBox()
        self.cbo_rate.addItems(["50 °C/HR", "120 °C/HR"])
        self.cbo_rate.setStyleSheet(self.cbo_method.styleSheet())
        vbox.addLayout(row_widget("HEAT RATE", self.cbo_rate))

        self.le_task = QLineEdit("HV_Test")
        self.le_task.setStyleSheet(f"""
            QLineEdit {{
                background:{C['bg_card2']};
                color:{C['amber']};
                border:1px solid {C['border_hi']};
                border-radius:4px;
                padding:4px 8px;
                font-family:'Consolas','Courier New',monospace;
                font-size:11px;
            }}
        """)
        vbox.addLayout(row_widget("TASK NAME", self.le_task))
        return grp

    # ─────────────────────────────
    #  槽函式
    # ─────────────────────────────
    def zero_all(self):
        self.machine.zero()
        for card in self.ch_cards:
            card.update_data(self.machine.channels[card.ch_id - 1])

    def _on_test_clicked(self):
        """Fix #3 & #4：TEST 按鈕，按一次開始，再按停止，停止後可再次開始"""
        if not self._test_active:
            self._start_test()
        else:
            self._stop_test()

    def _start_test(self):
        """開始測試：重置計時與壓縮緩衝，啟用折線圖記錄"""
        self._test_active = True
        self.t0 = time.time()

        # 重置所有壓縮緩衝區與平滑緩衝
        for buf in self._buffers.values():
            buf.reset()
        for q in self._smooth_buf.values():
            q.clear()
        # 清除圖表
        for curve in self.curves.values():
            curve.setData([], [])

        self.machine.start_test()

        self.btn_test.setText("■  STOP")
        self.btn_test.setStyleSheet(_btn_style(C['red'], C['red'] + "33"))
        self.led_test.set_on(True)
        self.led_heat.set_on(True)
        self.lbl_elapsed.setText("00:00:00")

    def _stop_test(self):
        """停止測試，彈出儲存對話框，允許再次啟動"""
        self._test_active = False
        self.machine.stop_test()

        self.btn_test.setText("▶  TEST")
        self.btn_test.setStyleSheet(_btn_style(C['green'], C['green'] + "33"))
        self.led_test.set_on(False)
        self.led_heat.set_on(False)

        # 取出壓縮後的完整序列（用 CH0 的時間軸作為共用 X 軸）
        t_series, defl_series, temp_series = self._buffers[0].get_series()

        # 彈出儲存視窗
        dlg = SaveResultDialog(
            self,
            self.plot_widget,
            t_series,
            {i: self._buffers[i].get_series()[1] for i in range(6)},
            self.le_task.text() or "-TestName",
        )
        dlg.exec()

        # 傳送測試記錄給 ReportPanel
        self._emit_test_record()

    # ─────────────────────────────
    #  資料更新（Fix #5：即時顯示數值，僅測試中記錄折線圖）
    # ─────────────────────────────
    def update_data(self, channels: list):
        # 無論是否測試中，卡片數值都即時更新
        for i, ch in enumerate(channels):
            self.ch_cards[i].update_data(ch)

        # 只有測試進行中才記錄折線圖資料
        if not self._test_active:
            return

        # 真實經過秒數，直接傳給 buffer，不讓 buffer 自己推算
        elapsed = time.time() - self.t0

        for i, ch in enumerate(channels):
            if self.ch_cards[i].enabled:
                self._smooth_buf[i].append(ch.deflection)
                smoothed = sum(self._smooth_buf[i]) / len(self._smooth_buf[i])
                self._buffers[i].push(elapsed, smoothed, ch.temperature)
            else:
                self._buffers[i].push(elapsed, None, ch.temperature)

    # ─────────────────────────────
    #  計時顯示（只在測試中跑）
    # ─────────────────────────────
    def _refresh_elapsed(self):
        if not self._test_active:
            return
        elapsed = int(time.time() - self.t0)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.lbl_elapsed.setText(f"{h:02d}:{m:02d}:{s:02d}")

        # 顯示壓縮資訊（以 CH0 為代表）
        buf = self._buffers[0]
        if buf.compression_count > 0:
            self.lbl_compress.setText(
                f"COMPRESS ×{buf.compression_count}  "
                f"PTS {buf.total_points:,}"
            )
        else:
            self.lbl_compress.setText(f"PTS {buf.total_points:,}")

    # ─────────────────────────────
    #  刷新折線圖（Fix #1：已在 update_data 平滑，直接繪製）
    # ─────────────────────────────
    def _refresh_plot(self):
        # 用 CH0 取時間軸
        t_arr, _, _ = self._buffers[0].get_series()
        if not t_arr:
            return

        t_max = t_arr[-1] if t_arr else 0.0

        # 更新時間軸格式（決定是 MM:SS 還是 HH:MM）
        self._time_axis.set_total_sec(t_max)

        # ── X 軸範圍控制
        if self._scroll_mode:
            # 捲動模式：永遠顯示最近 SCROLL_WINDOW_SEC 秒
            x_min = max(0.0, t_max - SCROLL_WINDOW_SEC)
            x_max = max(t_max, SCROLL_WINDOW_SEC)
            self.plot_widget.setXRange(x_min, x_max, padding=0.02)
        else:
            # 全程模式：顯示 0 到目前最大時間
            self.plot_widget.setXRange(0, max(t_max, 1.0), padding=0.02)

        # ── 繪製各通道曲線
        for i, curve in self.curves.items():
            _, ys, _ = self._buffers[i].get_series()
            valid_x, valid_y = [], []
            for x, y in zip(t_arr, ys):
                if y is not None:
                    valid_x.append(x)
                    valid_y.append(y)
            if valid_x:
                curve.setData(valid_x, valid_y)
    # ─────────────────────────────
    #  產生 TestRecord 並發送給 ReportPanel
    # ─────────────────────────────
    def _emit_test_record(self):
        try:
            from gui.report_panel import TestRecord
        except ImportError:
            return

        rec = TestRecord()
        task = self.le_task.text() or "HV_Test"
        rec.name        = f"{task}_{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M')}"
        rec.record_id   = rec.name
        rec.test_name   = task
        rec.test_method = self.cbo_method.currentText()
        rec.test_date   = __import__('datetime').datetime.now().strftime("%Y/%m/%d")
        rec.test_time   = __import__('datetime').datetime.now().strftime("%H:%M:%S")

        # 從壓縮緩衝區取出完整序列（時間軸共用 CH0）
        xs, _, _ = self._buffers[0].get_series()
        rec.time_data = xs

        for i in range(6):
            _, ys, ts = self._buffers[i].get_series()
            rec.deflection_data[i] = [v for v in ys if v is not None]
            rec.temp_data[i]       = [v for v in ts if v is not None]

        for i, ch_data in enumerate(self.machine.channels):
            rec.channels.append({
                "group":      f"CH{i+1}",
                "width":      "--",
                "depth":      "--",
                "span":       "--",
                "deflection": f"{ch_data.deflection:.4f}",
                "load":       "--",
            })

        self.test_finished.emit(rec)

    # ─────────────────────────────
    #  Setup 方法更新時，同步 SETUP 下拉選單
    # ─────────────────────────────
    def on_methods_updated(self, methods: dict):
        current = self.cbo_method.currentText()
        self.cbo_method.clear()
        self.cbo_method.addItems(list(methods.keys()))
        idx = self.cbo_method.findText(current)
        if idx >= 0:
            self.cbo_method.setCurrentIndex(idx)