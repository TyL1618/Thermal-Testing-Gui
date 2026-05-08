"""
login_panel.py  ─  Thermal Testing System 登入頁面

帳號資料（硬編碼開發者模式，正式版請接資料庫）：
  - 帳號：admin   密碼：123abc   顯示名稱：Demo User
"""
from __future__ import annotations
import hashlib
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QSizePolicy,
    QSpacerItem,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent

# ── 色彩（與其他 panel 一致）
C = {
    'bg_deep':   '#080a0d',
    'bg_panel':  '#0e1117',
    'bg_card':   '#141820',
    'bg_card2':  '#1a1f2a',
    'border':    '#2a3345',
    'border_hi': '#3d4f6a',
    'amber':     '#ffc233',
    'amber_dim': '#7a5500',
    'green':     '#00f080',
    'red':       '#ff6060',
    'text_hi':   '#f0f4ff',
    'text_mid':  '#b0bcd4',
    'text_lo':   '#6a7a96',
}

# ── 硬編碼帳號（sha256 比對，原始密碼不明文存在記憶體）
# 格式：{ 帳號小寫: (顯示名稱, 密碼 sha256) }
_PWD_SHA256 = hashlib.sha256(b"123abc").hexdigest()
_ACCOUNTS: dict[str, tuple[str, str]] = {
    "admin": ("Demo User", _PWD_SHA256),
}


def _verify(username: str, password: str) -> Optional[tuple[str, str]]:
    """
    驗證帳密，成功回傳 (username_original, display_name)，失敗回傳 None。
    """
    key = username.strip().lower()
    if key not in _ACCOUNTS:
        return None
    display, pw_hash = _ACCOUNTS[key]
    if hashlib.sha256(password.encode()).hexdigest() == pw_hash:
        return (username.strip(), display)
    return None


# ── 工具
def _label(text: str, color=None, size=10, bold=False, spacing=1) -> QLabel:
    c = color or C['text_lo']
    w = "700" if bold else "400"
    lbl = QLabel(text)
    lbl.setStyleSheet(f"""
        color:{c};
        font-family:'Consolas','Courier New',monospace;
        font-size:{size}px; font-weight:{w};
        letter-spacing:{spacing}px;
        background:transparent;
    """)
    return lbl


def _input_style() -> str:
    return f"""
        background:{C['bg_card2']};
        color:{C['text_hi']};
        border:1px solid {C['border_hi']};
        border-radius:4px;
        padding:6px 10px;
        font-family:'Consolas','Courier New',monospace;
        font-size:12px;
    """


def _btn_style(color: str) -> str:
    return f"""
        QPushButton {{
            background: transparent;
            color: {color};
            border: 1px solid {color};
            border-radius: 4px;
            padding: 8px 28px;
            font-family: 'Consolas','Courier New',monospace;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 2px;
        }}
        QPushButton:hover  {{ background: {color}33; }}
        QPushButton:pressed {{ background: {color}; color: #000; }}
    """


class LoginPanel(QWidget):
    """
    登入頁面。
    成功登入後發射 login_success(username, display_name)。
    """
    login_success: pyqtSignal = pyqtSignal(str, str)   # (username, display_name)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet(f"background:{C['bg_deep']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # ── 垂直置中
        root.addStretch(2)

        # ── 登入卡片（固定寬度，水平置中）
        card_wrap = QHBoxLayout()
        card_wrap.addStretch()

        card = QFrame()
        card.setFixedWidth(380)
        card.setStyleSheet(f"""
            QFrame {{
                background:{C['bg_panel']};
                border:1px solid {C['border_hi']};
                border-radius:10px;
            }}
        """)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(36, 36, 36, 36)
        card_lay.setSpacing(16)

        # Logo / 標題
        logo = _label("ThermalTest", C['amber'], size=22, bold=True, spacing=4)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(logo)

        sub = _label("HDT / VICAT  Testing System", C['text_lo'], size=9, spacing=2)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(sub)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']};")
        card_lay.addWidget(sep)

        # 帳號
        card_lay.addWidget(_label("ACCOUNT", C['text_mid'], size=9, spacing=2))
        self.le_user = QLineEdit()
        self.le_user.setPlaceholderText("輸入帳號")
        self.le_user.setStyleSheet(_input_style())
        self.le_user.returnPressed.connect(self._do_login)
        card_lay.addWidget(self.le_user)

        # 密碼
        card_lay.addWidget(_label("PASSWORD", C['text_mid'], size=9, spacing=2))
        self.le_pass = QLineEdit()
        self.le_pass.setPlaceholderText("輸入密碼")
        self.le_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.le_pass.setStyleSheet(_input_style())
        self.le_pass.returnPressed.connect(self._do_login)
        card_lay.addWidget(self.le_pass)

        # 錯誤提示
        self.lbl_err = _label("", C['red'], size=10)
        self.lbl_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_err.hide()
        card_lay.addWidget(self.lbl_err)

        # 登入按鈕
        self.btn_login = QPushButton("LOGIN")
        self.btn_login.setStyleSheet(_btn_style(C['amber']))
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.clicked.connect(self._do_login)
        card_lay.addWidget(self.btn_login)

        card_wrap.addWidget(card)
        card_wrap.addStretch()
        root.addLayout(card_wrap)

        root.addStretch(3)

    # ────────────────────────────────────────
    def _do_login(self):
        username = self.le_user.text().strip()
        password = self.le_pass.text()

        if not username or not password:
            self._show_err("請輸入帳號與密碼")
            return

        result = _verify(username, password)
        if result is None:
            self._show_err("帳號或密碼錯誤")
            self.le_pass.clear()
            self.le_pass.setFocus()
            return

        # 成功
        self.lbl_err.hide()
        self.le_pass.clear()
        u, display = result
        self.login_success.emit(u, display)

    def _show_err(self, msg: str):
        self.lbl_err.setText(f"⚠  {msg}")
        self.lbl_err.show()

    def reset(self):
        """登出後重置欄位"""
        self.le_user.clear()
        self.le_pass.clear()
        self.lbl_err.hide()
        self.le_user.setFocus()