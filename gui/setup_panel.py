"""
setup_panel.py  
功能：
  1. 測試方法管理（HDT-ISO / HDT_CNS / Special / VICAT-ASTM / HDT-ISO2）
  2. 測試規範、撓曲值、反向應力、速率、負載單位設定
  3. Pressure 清單管理（新增 / 移除）
  4. Span 清單管理（新增 / 移除）
  5. 報告欄位勾選（左側：一般資訊；右側：測試資料欄位）
  6. 儲存 / 刪除 測試方法
"""
from __future__ import annotations
import json
import os
from typing import Dict, List, Optional
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QCheckBox,
    QComboBox, QLineEdit, QListWidget, QListWidgetItem,
    QFrame, QSizePolicy, QMessageBox, QDoubleSpinBox,
    QSpinBox, QScrollArea, QTreeWidget, QTreeWidgetItem,
    QAbstractItemView, QSplitter,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.machine import TestingMachine

# ── 色彩（與 monitor_panel 一致）
C = {
    'bg_deep':    '#080a0d',
    'bg_panel':   '#0e1117',
    'bg_card':    '#141820',
    'bg_card2':   '#1a1f2a',
    'border':     '#2a3345',
    'border_hi':  '#3d4f6a',
    'amber':      '#ffc233',
    'amber_dim':  '#7a5500',
    'green':      '#00f080',
    'green_dim':  '#004d26',
    'red':        '#ff6060',
    'red_dim':    '#7a0000',
    'blue':       '#5cd9ff',
    'blue_dim':   '#00405a',
    'text_hi':    '#f0f4ff',
    'text_mid':   '#b0bcd4',
    'text_lo':    '#6a7a96',
}

# ── 預設測試方法資料
DEFAULT_METHODS: Dict[str, dict] = {
    "HDT-ISO": {
        "standard": "HDT-ISO",
        "deflection": 1.0,
        "deflection_auto": True,
        "back_force": 0,
        "rate": 120,
        "load_unit": "MPa",
        "pressures": [0.455, 1.820, 8.000],
        "spans": [64.0, 100.0, 101.6],
        "default_pressure": 1.82,
        "default_span": 64.0,
        "two_temp": False,
        "report_fields_left": ["測試名稱", "客戶名稱", "使用介質", "測試方法", "客戶地址"],
        "report_fields_right": [
            "測試日期", "測試時間", "流水批號", "材料名稱", "測試方法",
            "組別", "寬度(mm)", "深度(mm)", "跨距(mm)", "變形(mm)", "負載",
            "速率(°C/h)", "測試結果(°C)"
        ],
    },
    "HDT_CNS": {
        "standard": "HDT-CNS",
        "deflection": 0.25,
        "deflection_auto": False,
        "back_force": 0,
        "rate": 120,
        "load_unit": "MPa",
        "pressures": [0.455, 1.820],
        "spans": [64.0, 100.0],
        "default_pressure": 0.455,
        "default_span": 64.0,
        "two_temp": False,
        "report_fields_left": ["測試名稱", "客戶名稱", "使用介質", "測試方法", "客戶地址"],
        "report_fields_right": [
            "測試日期", "測試時間", "流水批號", "材料名稱", "測試方法",
            "組別", "寬度(mm)", "深度(mm)", "跨距(mm)", "變形(mm)", "負載",
            "速率(°C/h)", "測試結果(°C)"
        ],
    },
    "Special": {
        "standard": "HDT-ISO",
        "deflection": 2.0,
        "deflection_auto": False,
        "back_force": 0,
        "rate": 50,
        "load_unit": "MPa",
        "pressures": [0.455, 1.820, 8.000],
        "spans": [64.0, 100.0, 101.6],
        "default_pressure": 0.455,
        "default_span": 64.0,
        "two_temp": False,
        "report_fields_left": ["測試名稱", "客戶名稱", "使用介質", "測試方法", "客戶地址"],
        "report_fields_right": [
            "測試日期", "測試時間", "流水批號", "材料名稱", "測試方法",
            "組別", "寬度(mm)", "深度(mm)", "跨距(mm)", "變形(mm)", "負載",
            "速率(°C/h)", "測試結果(°C)"
        ],
    },
    "VICAT-ASTM": {
        "standard": "VICAT-ASTM",
        "deflection": 1.0,
        "deflection_auto": True,
        "back_force": 0,
        "rate": 50,
        "load_unit": "N",
        "pressures": [10.0, 50.0],
        "spans": [64.0],
        "default_pressure": 10.0,
        "default_span": 64.0,
        "two_temp": False,
        "report_fields_left": ["測試名稱", "客戶名稱", "使用介質", "測試方法", "客戶地址"],
        "report_fields_right": [
            "測試日期", "測試時間", "流水批號", "材料名稱", "測試方法",
            "組別", "寬度(mm)", "深度(mm)", "跨距(mm)", "變形(mm)", "負載",
            "速率(°C/h)", "測試結果(°C)"
        ],
    },
    "HDT-ISO2": {
        "standard": "HDT-ISO",
        "deflection": 0.34,
        "deflection_auto": False,
        "back_force": 0,
        "rate": 120,
        "load_unit": "MPa",
        "pressures": [0.455, 1.820, 8.000],
        "spans": [64.0, 100.0, 101.6],
        "default_pressure": 1.82,
        "default_span": 64.0,
        "two_temp": True,
        "report_fields_left": ["測試名稱", "客戶名稱", "使用介質", "測試方法", "客戶地址"],
        "report_fields_right": [
            "測試日期", "測試時間", "流水批號", "材料名稱", "測試方法",
            "組別", "寬度(mm)", "深度(mm)", "跨距(mm)", "變形(mm)", "負載",
            "速率(°C/h)", "測試結果(°C)"
        ],
    },
}

STANDARDS = ["HDT-ASTM", "HDT-CNS", "HDT-ISO", "VICAT-ASTM"]
RATES     = [50, 120]
LOAD_UNITS = ["MPa", "psi", "N"]

LEFT_FIELDS = ["測試名稱", "客戶名稱", "使用介質", "測試方法", "客戶地址"]
RIGHT_FIELDS = [
    "測試日期", "測試時間", "流水批號", "材料名稱", "測試方法",
    "組別", "寬度(mm)", "深度(mm)", "跨距(mm)", "變形(mm)", "負載",
    "速率(°C/h)", "測試結果(°C)"
]


def _input_style() -> str:
    return f"""
        background:{C['bg_card2']};
        color:{C['text_hi']};
        border:1px solid {C['border_hi']};
        border-radius:4px;
        padding:4px 8px;
        font-family:'Consolas','Courier New',monospace;
        font-size:11px;
    """

def _combo_style() -> str:
    return f"""
        QComboBox {{
            {_input_style()}
        }}
        QComboBox::drop-down {{border:none;}}
        QComboBox QAbstractItemView {{
            background:{C['bg_card2']};
            color:{C['text_hi']};
            selection-background-color:{C['border_hi']};
        }}
    """

def _btn_style(color: str, small=False) -> str:
    pad = "4px 10px" if small else "7px 16px"
    return f"""
        QPushButton {{
            background: transparent;
            color: {color};
            border: 1px solid {color};
            border-radius: 4px;
            padding: {pad};
            font-family: 'Consolas','Courier New',monospace;
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{
            background: {color}33;
        }}
        QPushButton:pressed {{
            background: {color};
            color: #000;
        }}
    """

def _list_style() -> str:
    return f"""
        QListWidget {{
            background:{C['bg_card2']};
            border:1px solid {C['border_hi']};
            border-radius:4px;
            color:{C['text_hi']};
            font-family:'Consolas','Courier New',monospace;
            font-size:11px;
        }}
        QListWidget::item:selected {{
            background:{C['amber_dim']};
            color:{C['amber']};
        }}
        QListWidget::item:hover {{
            background:{C['border_hi']};
        }}
    """

def _label(text: str, color=None, size=10, bold=False, spacing=1) -> QLabel:
    c = color or C['text_lo']
    w = "700" if bold else "400"
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        color:{c};
        font-family:'Consolas','Courier New',monospace;
        font-size:{size}px;font-weight:{w};
        letter-spacing:{spacing}px;
        background:transparent;
    """)
    return lbl


class SetupPanel(QWidget):
    """測試設定主面板"""
    methods_changed = pyqtSignal(dict)  # 傳出最新 methods dict 給其他頁面使用

    def __init__(self, machine: TestingMachine):
        super().__init__()
        self.machine = machine
        # 深複製預設方法
        self.methods: Dict[str, dict] = {k: dict(v) for k, v in DEFAULT_METHODS.items()}
        self._current_method: str = "HDT-ISO"
        self._pressure_chks: Dict[str, QCheckBox] = {}
        self._span_chks: Dict[str, QCheckBox] = {}

        self._setup_style()
        self._setup_ui()
        self._load_method(self._current_method)

    # ─────────────────────────────────────────────
    def _setup_style(self):
        self.setStyleSheet(f"""
            QWidget {{ background:{C['bg_deep']}; color:{C['text_hi']}; }}
            QGroupBox {{
                border:1px solid {C['border']};
                border-radius:6px;
                margin-top:16px;
                padding:8px;
                font-family:'Consolas','Courier New',monospace;
                font-size:10px;
                color:{C['text_mid']};
                letter-spacing:2px;
            }}
            QGroupBox::title {{
                subcontrol-origin:margin;
                left:10px;
                padding:0 6px;
                color:{C['amber']};
            }}
            QLabel {{ background:transparent; }}
            QCheckBox {{ background:transparent; spacing:6px; }}
            QCheckBox::indicator {{
                width:13px;height:13px;
                border-radius:2px;
                border:1px solid {C['border_hi']};
                background:{C['bg_card2']};
            }}
            QCheckBox::indicator:checked {{
                background:{C['amber']};
                border-color:{C['amber']};
            }}
            QSpinBox, QDoubleSpinBox {{
                {_input_style()}
            }}
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {{
                background:{C['border_hi']};border:none;width:16px;
            }}
        """)

    # ─────────────────────────────────────────────
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # 頁標題
        title = _label("⚙   TEST  SETUP", C['amber'], size=13, bold=True, spacing=4)
        root.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']};")
        root.addWidget(sep)

        # 主體
        body = QHBoxLayout()
        body.setSpacing(12)

        # ── 左：方法樹 + 操作按鈕
        body.addWidget(self._make_method_tree(), stretch=18)
        # ── 中：參數設定
        body.addWidget(self._make_params_panel(), stretch=44)
        # ── 右：Pressure / Span
        body.addWidget(self._make_pressure_span_panel(), stretch=38)

        root.addLayout(body, stretch=1)

        # ── 底部：報告欄位
        root.addWidget(self._make_report_fields_panel())

    # ─────────────────────────────────────────────
    def _make_method_tree(self) -> QWidget:
        frame = QWidget()
        frame.setStyleSheet(f"background:{C['bg_panel']};border:1px solid {C['border']};border-radius:8px;")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        lay.addWidget(_label("編輯測試方法", C['text_mid'], size=10, spacing=2))

        self.tree = QListWidget()
        self.tree.setStyleSheet(_list_style())
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for name in self.methods:
            self.tree.addItem(name)
        self.tree.setCurrentRow(0)
        self.tree.currentTextChanged.connect(self._on_method_selected)
        lay.addWidget(self.tree, stretch=1)

        return frame

    # ─────────────────────────────────────────────
    def _make_params_panel(self) -> QGroupBox:
        grp = QGroupBox("測試方法設定")
        lay = QGridLayout(grp)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 20, 12, 12)

        def row_label(text):
            return _label(text + "：", C['text_mid'], size=10)

        # 測試方法名稱
        lay.addWidget(row_label("測試方法"), 0, 0)
        self.le_method_name = QLineEdit()
        self.le_method_name.setStyleSheet(_input_style())
        lay.addWidget(self.le_method_name, 0, 1)

        # 測試規範
        lay.addWidget(row_label("測試規範"), 1, 0)
        self.cbo_standard = QComboBox()
        self.cbo_standard.addItems(STANDARDS)
        self.cbo_standard.setStyleSheet(_combo_style())
        lay.addWidget(self.cbo_standard, 1, 1)

        # 撓曲值
        lay.addWidget(row_label("撓曲值"), 2, 0)
        defl_row = QHBoxLayout()
        self.spin_deflection = QDoubleSpinBox()
        self.spin_deflection.setRange(0.01, 99.99)
        self.spin_deflection.setSingleStep(0.01)
        self.spin_deflection.setDecimals(2)
        self.spin_deflection.setSuffix("  mm")
        defl_row.addWidget(self.spin_deflection)

        self.chk_auto = QCheckBox("Auto")
        self.chk_auto.setStyleSheet(f"color:{C['text_mid']};font-size:10px;")
        defl_row.addWidget(self.chk_auto)
        lay.addLayout(defl_row, 2, 1)

        # 反向應力
        lay.addWidget(row_label("反向應力"), 3, 0)
        back_row = QHBoxLayout()
        self.spin_back_force = QSpinBox()
        self.spin_back_force.setRange(0, 9999)
        back_row.addWidget(self.spin_back_force)
        back_row.addWidget(_label("N", C['text_lo'], size=10))
        lay.addLayout(back_row, 3, 1)

        # 速率
        lay.addWidget(row_label("速率 (°C/h)"), 4, 0)
        self.cbo_rate = QComboBox()
        self.cbo_rate.addItems([str(r) for r in RATES])
        self.cbo_rate.setStyleSheet(_combo_style())
        lay.addWidget(self.cbo_rate, 4, 1)

        # 負載單位
        lay.addWidget(row_label("負載單位"), 5, 0)
        self.cbo_load_unit = QComboBox()
        self.cbo_load_unit.addItems(LOAD_UNITS)
        self.cbo_load_unit.setStyleSheet(_combo_style())
        lay.addWidget(self.cbo_load_unit, 5, 1)

        # Two temperature
        self.chk_two_temp = QCheckBox("Two temperature")
        self.chk_two_temp.setStyleSheet(f"color:{C['text_mid']};font-size:10px;")
        lay.addWidget(self.chk_two_temp, 6, 0, 1, 2)

        lay.setRowStretch(7, 1)

        # 操作按鈕
        btn_row = QHBoxLayout()
        btn_del = QPushButton("刪除")
        btn_del.setStyleSheet(_btn_style(C['red']))
        btn_del.clicked.connect(self._on_delete)
        btn_row.addWidget(btn_del)

        btn_save = QPushButton("存儲")
        btn_save.setStyleSheet(_btn_style(C['amber']))
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        lay.addLayout(btn_row, 8, 0, 1, 2)
        return grp

    # ─────────────────────────────────────────────
    def _make_pressure_span_panel(self) -> QWidget:
        frame = QWidget()
        frame.setStyleSheet(f"background:{C['bg_panel']};border:1px solid {C['border']};border-radius:8px;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        # ── Pressure
        p_col = QVBoxLayout()
        p_col.addWidget(_label("Pressure", C['text_hi'], size=11, bold=True))

        self.lst_pressure = QListWidget()
        self.lst_pressure.setStyleSheet(_list_style())
        p_col.addWidget(self.lst_pressure, stretch=1)

        p_input_row = QHBoxLayout()
        self.le_pressure_input = QLineEdit()
        self.le_pressure_input.setPlaceholderText("數值")
        self.le_pressure_input.setStyleSheet(_input_style())
        p_input_row.addWidget(self.le_pressure_input)
        p_col.addLayout(p_input_row)

        p_btn_row = QHBoxLayout()
        btn_p_add = QPushButton("新增")
        btn_p_add.setStyleSheet(_btn_style(C['green'], small=True))
        btn_p_add.clicked.connect(self._add_pressure)
        btn_p_rem = QPushButton("移除")
        btn_p_rem.setStyleSheet(_btn_style(C['red'], small=True))
        btn_p_rem.clicked.connect(self._remove_pressure)
        p_btn_row.addWidget(btn_p_add)
        p_btn_row.addWidget(btn_p_rem)
        p_col.addLayout(p_btn_row)

        self.lbl_pressure_default = _label("預設：  ─", C['text_lo'], size=9)
        p_col.addWidget(self.lbl_pressure_default)

        lay.addLayout(p_col)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{C['border']};")
        lay.addWidget(sep)

        # ── Span
        s_col = QVBoxLayout()
        s_col.addWidget(_label("Span", C['text_hi'], size=11, bold=True))

        self.lst_span = QListWidget()
        self.lst_span.setStyleSheet(_list_style())
        s_col.addWidget(self.lst_span, stretch=1)

        s_input_row = QHBoxLayout()
        self.le_span_input = QLineEdit()
        self.le_span_input.setPlaceholderText("數值")
        self.le_span_input.setStyleSheet(_input_style())
        s_input_row.addWidget(self.le_span_input)
        s_col.addLayout(s_input_row)

        s_btn_row = QHBoxLayout()
        btn_s_add = QPushButton("新增")
        btn_s_add.setStyleSheet(_btn_style(C['green'], small=True))
        btn_s_add.clicked.connect(self._add_span)
        btn_s_rem = QPushButton("移除")
        btn_s_rem.setStyleSheet(_btn_style(C['red'], small=True))
        btn_s_rem.clicked.connect(self._remove_span)
        s_btn_row.addWidget(btn_s_add)
        s_btn_row.addWidget(btn_s_rem)
        s_col.addLayout(s_btn_row)

        self.lbl_span_default = _label("預設：  ─        單位=mm", C['text_lo'], size=9)
        s_col.addWidget(self.lbl_span_default)

        lay.addLayout(s_col)
        return frame

    # ─────────────────────────────────────────────
    def _make_report_fields_panel(self) -> QGroupBox:
        grp = QGroupBox("報告欄位設定")
        outer = QHBoxLayout(grp)
        outer.setSpacing(20)
        outer.setContentsMargins(12, 16, 12, 12)

        # ── 左側欄位
        left_col = QVBoxLayout()
        left_col.addWidget(_label("基本資訊", C['text_mid'], size=9, spacing=1))
        self.chk_left: Dict[str, QCheckBox] = {}
        for field in LEFT_FIELDS:
            chk = QCheckBox(field)
            chk.setChecked(True)
            self.chk_left[field] = chk
            left_col.addWidget(chk)
        left_col.addStretch()
        outer.addLayout(left_col)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color:{C['border']};")
        outer.addWidget(sep)

        # ── 右側欄位（兩欄排列）
        right_area = QWidget()
        right_area.setStyleSheet("background:transparent;")
        right_grid = QGridLayout(right_area)
        right_grid.setSpacing(4)
        right_grid.setContentsMargins(0, 0, 0, 0)

        right_title = _label("測試資料欄位", C['text_mid'], size=9, spacing=1)
        right_grid.addWidget(right_title, 0, 0, 1, 2)

        self.chk_right: Dict[str, QCheckBox] = {}
        for idx, field in enumerate(RIGHT_FIELDS):
            chk = QCheckBox(field)
            chk.setChecked(True)
            self.chk_right[field] = chk
            r = (idx // 2) + 1
            c = idx % 2
            right_grid.addWidget(chk, r, c)

        outer.addWidget(right_area, stretch=1)
        return grp

    # ─────────────────────────────────────────────
    #  資料載入 / 儲存
    # ─────────────────────────────────────────────
    def _load_method(self, name: str):
        if name not in self.methods:
            return
        self._current_method = name
        m = self.methods[name]

        self.le_method_name.setText(name)
        idx = self.cbo_standard.findText(m.get("standard", "HDT-ISO"))
        if idx >= 0:
            self.cbo_standard.setCurrentIndex(idx)

        self.spin_deflection.setValue(m.get("deflection", 1.0))
        self.chk_auto.setChecked(m.get("deflection_auto", False))
        self.spin_back_force.setValue(m.get("back_force", 0))

        rate_str = str(m.get("rate", 120))
        rate_idx = self.cbo_rate.findText(rate_str)
        if rate_idx >= 0:
            self.cbo_rate.setCurrentIndex(rate_idx)

        unit_idx = self.cbo_load_unit.findText(m.get("load_unit", "MPa"))
        if unit_idx >= 0:
            self.cbo_load_unit.setCurrentIndex(unit_idx)

        self.chk_two_temp.setChecked(m.get("two_temp", False))

        # Pressure list
        self.lst_pressure.clear()
        for p in m.get("pressures", []):
            self.lst_pressure.addItem(f"{p:.3f}")
        # 選中 default
        default_p = m.get("default_pressure", None)
        if default_p is not None:
            self.lbl_pressure_default.setText(f"預設：  {default_p}")
            for i in range(self.lst_pressure.count()):
                if abs(float(self.lst_pressure.item(i).text()) - default_p) < 0.001:
                    self.lst_pressure.setCurrentRow(i)
                    break

        # Span list
        self.lst_span.clear()
        for s in m.get("spans", []):
            self.lst_span.addItem(f"{s}")
        default_s = m.get("default_span", None)
        if default_s is not None:
            self.lbl_span_default.setText(f"預設：  {default_s}        單位=mm")
            for i in range(self.lst_span.count()):
                if abs(float(self.lst_span.item(i).text()) - default_s) < 0.001:
                    self.lst_span.setCurrentRow(i)
                    break

        # 報告欄位
        for field, chk in self.chk_left.items():
            chk.setChecked(field in m.get("report_fields_left", LEFT_FIELDS))
        for field, chk in self.chk_right.items():
            chk.setChecked(field in m.get("report_fields_right", RIGHT_FIELDS))

    def _collect_current(self) -> dict:
        """從 UI 收集目前的設定值"""
        pressures = []
        for i in range(self.lst_pressure.count()):
            try:
                pressures.append(float(self.lst_pressure.item(i).text()))
            except ValueError:
                pass

        spans = []
        for i in range(self.lst_span.count()):
            try:
                spans.append(float(self.lst_span.item(i).text()))
            except ValueError:
                pass

        cur_p = self.lst_pressure.currentItem()
        default_pressure = float(cur_p.text()) if cur_p else (pressures[0] if pressures else 0)
        cur_s = self.lst_span.currentItem()
        default_span = float(cur_s.text()) if cur_s else (spans[0] if spans else 0)

        return {
            "standard":       self.cbo_standard.currentText(),
            "deflection":     self.spin_deflection.value(),
            "deflection_auto": self.chk_auto.isChecked(),
            "back_force":     self.spin_back_force.value(),
            "rate":           int(self.cbo_rate.currentText()),
            "load_unit":      self.cbo_load_unit.currentText(),
            "pressures":      pressures,
            "spans":          spans,
            "default_pressure": default_pressure,
            "default_span":   default_span,
            "two_temp":       self.chk_two_temp.isChecked(),
            "report_fields_left": [f for f, c in self.chk_left.items() if c.isChecked()],
            "report_fields_right": [f for f, c in self.chk_right.items() if c.isChecked()],
        }

    # ─────────────────────────────────────────────
    #  槽函式
    # ─────────────────────────────────────────────
    def _on_method_selected(self, name: str):
        if name and name in self.methods:
            self._load_method(name)

    def _on_save(self):
        name = self.le_method_name.text().strip()
        if not name:
            QMessageBox.warning(self, "錯誤", "測試方法名稱不能為空。")
            return

        data = self._collect_current()
        is_new = name not in self.methods
        self.methods[name] = data

        if is_new:
            self.tree.addItem(name)
        self._current_method = name

        # 更新 tree 選中
        for i in range(self.tree.count()):
            if self.tree.item(i).text() == name:
                self.tree.setCurrentRow(i)
                break

        self.methods_changed.emit(self.methods)
        QMessageBox.information(self, "儲存成功", f"測試方法「{name}」已儲存。")

    def _on_delete(self):
        cur = self.tree.currentItem()
        if not cur:
            return
        name = cur.text()
        if len(self.methods) <= 1:
            QMessageBox.warning(self, "無法刪除", "至少需保留一個測試方法。")
            return
        reply = QMessageBox.question(
            self, "確認刪除", f"確定要刪除「{name}」？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            del self.methods[name]
            row = self.tree.currentRow()
            self.tree.takeItem(row)
            new_row = max(0, row - 1)
            self.tree.setCurrentRow(new_row)
            self.methods_changed.emit(self.methods)

    def _add_pressure(self):
        txt = self.le_pressure_input.text().strip()
        try:
            val = float(txt)
        except ValueError:
            QMessageBox.warning(self, "格式錯誤", "請輸入有效數字。")
            return
        self.lst_pressure.addItem(f"{val:.3f}")
        self.le_pressure_input.clear()

    def _remove_pressure(self):
        row = self.lst_pressure.currentRow()
        if row >= 0:
            self.lst_pressure.takeItem(row)

    def _add_span(self):
        txt = self.le_span_input.text().strip()
        try:
            val = float(txt)
        except ValueError:
            QMessageBox.warning(self, "格式錯誤", "請輸入有效數字。")
            return
        self.lst_span.addItem(f"{val}")
        self.le_span_input.clear()

    def _remove_span(self):
        row = self.lst_span.currentRow()
        if row >= 0:
            self.lst_span.takeItem(row)

    # ─────────────────────────────────────────────
    #  公開 API（供 report_panel / monitor 使用）
    # ─────────────────────────────────────────────
    def get_method_names(self) -> List[str]:
        return list(self.methods.keys())

    def get_method(self, name: str) -> Optional[dict]:
        return self.methods.get(name)