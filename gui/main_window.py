"""
main_window.py  ─  GOTECH HV3000 主視窗（含登入 / 使用者列）
"""
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QLabel, QHBoxLayout,
    QStatusBar, QMessageBox, QPushButton, QVBoxLayout, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from core.machine import GotechMachine


class ReconnectOverlay(QWidget):
    """
    斷線時覆蓋在主視窗上的半透明倒數提示。
    連線成功後呼叫 hide() 隱藏。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: rgba(8, 10, 13, 180);")

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel("⚠️")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size:48px; background:transparent;")
        lay.addWidget(self._icon)

        self._title = QLabel("連線中斷")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            "color:#ffc233; font-size:20px; font-weight:700;"
            "font-family:'Consolas','Courier New',monospace;"
            "letter-spacing:4px; background:transparent;"
        )
        lay.addWidget(self._title)

        self._countdown = QLabel("")
        self._countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown.setStyleSheet(
            "color:#b0bcd4; font-size:13px;"
            "font-family:'Consolas','Courier New',monospace;"
            "letter-spacing:2px; background:transparent; margin-top:8px;"
        )
        lay.addWidget(self._countdown)
        self.hide()

    def show_countdown(self, seconds: int):
        self._countdown.setText(f"將在  {seconds}  秒後重新連線...")
        self.show()
        self.raise_()

    def show_connecting(self):
        self._title.setText("正在連線...")
        self._icon.setText("🔄")
        self._countdown.setText("")
        self.show()
        self.raise_()

    def reset(self):
        self._title.setText("連線中斷")
        self._icon.setText("⚠️")

C = {
    'bg_deep':   '#080a0d',
    'bg_panel':  '#0e1117',
    'border':    '#2a3345',
    'amber':     '#ffc233',
    'text_hi':   '#f0f4ff',
    'text_mid':  '#b0bcd4',
    'text_lo':   '#6a7a96',
    'green':     '#00f080',
    'red':       '#ff6060',
}

# 分頁索引常數（方便統一管理）
TAB_MONITOR = 0
TAB_SETUP   = 1
TAB_REPORT  = 2
TAB_LOGIN   = 3


class MainWindow(QMainWindow):
    def __init__(self, machine: GotechMachine):
        super().__init__()
        self.machine = machine
        self._current_user: str = ""        # 帳號
        self._current_display: str = ""     # 顯示名稱

        self.setWindowTitle("HDT / VICAT  Testing System")
        self.resize(1600, 960)
        self._setup_style()
        self._setup_user_bar()   # ← 右上角使用者列（放在 tab 之前建立）
        self._setup_tabs()
        self._setup_statusbar()
        self._apply_login_state(logged_in=False)

        self.machine.status_updated.connect(self._on_status)
        self.machine.connected.connect(self._on_connected)
        self.machine.reconnecting.connect(self._on_reconnecting)
        self.machine.connect()

        # ── 斷線重連 Overlay（蓋在所有 widget 上面）
        self._overlay = ReconnectOverlay(self)
        self._overlay.setGeometry(self.rect())

    # ────────────────────────────────────────
    def _setup_style(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background:{C['bg_deep']}; }}

            QTabWidget::pane {{
                border:1px solid {C['border']};
                background:{C['bg_deep']};
                border-radius:0px;
            }}
            QTabBar::tab {{
                background:{C['bg_panel']};
                color:{C['text_mid']};
                border:1px solid {C['border']};
                border-bottom:none;
                padding:10px 28px;
                font-family:'Consolas','Courier New',monospace;
                font-size:12px;
                letter-spacing:2px;
                min-width:160px;
            }}
            QTabBar::tab:selected {{
                background:{C['bg_deep']};
                color:{C['amber']};
                border-bottom:2px solid {C['amber']};
            }}
            QTabBar::tab:hover {{
                color:{C['text_hi']};
            }}
            QTabBar::tab:disabled {{
                color:{C['text_lo']}44;
                border-color:{C['border']}66;
            }}

            QStatusBar {{
                background:{C['bg_panel']};
                border-top:1px solid {C['border']};
                color:{C['text_lo']};
                font-family:'Consolas','Courier New',monospace;
                font-size:9px;
                letter-spacing:1px;
            }}
        """)

    # ── 右上角使用者列
    def _setup_user_bar(self):
        """
        使用 QTabWidget 的 setCornerWidget 把使用者資訊塞進 TabBar 右上角。
        在 _setup_tabs 之後才能呼叫 setCornerWidget，所以先把 widget 建好，
        _setup_tabs 結束後再掛上去。
        """
        self._corner = QWidget()
        self._corner.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(self._corner)
        lay.setContentsMargins(0, 0, 12, 0)
        lay.setSpacing(8)

        # 使用者名稱標籤
        self._lbl_user = QLabel("")
        self._lbl_user.setStyleSheet(f"""
            color:{C['amber']};
            font-family:'Consolas','Courier New',monospace;
            font-size:10px;
            letter-spacing:1px;
            background:transparent;
        """)
        lay.addWidget(self._lbl_user)

        # 登出按鈕
        self._btn_logout = QPushButton("LOGOUT")
        self._btn_logout.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                color:{C['text_lo']};
                border:1px solid {C['border']};
                border-radius:3px;
                padding:3px 10px;
                font-family:'Consolas','Courier New',monospace;
                font-size:9px;
                letter-spacing:1px;
            }}
            QPushButton:hover  {{ color:{C['red']}; border-color:{C['red']}; }}
            QPushButton:pressed {{ background:{C['red']}22; }}
        """)
        self._btn_logout.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_logout.clicked.connect(self._do_logout)
        self._btn_logout.hide()
        lay.addWidget(self._btn_logout)

    # ────────────────────────────────────────
    def _setup_tabs(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.setCentralWidget(self.tabs)

        # 掛右上角 corner widget
        self.tabs.setCornerWidget(self._corner, Qt.Corner.TopRightCorner)

        from gui.monitor_panel import MonitorPanel
        from gui.setup_panel   import SetupPanel
        from gui.report_panel  import ReportPanel
        from gui.login_panel   import LoginPanel

        # ── Monitor  (TAB_MONITOR = 0)
        self.monitor_tab = MonitorPanel(self.machine)
        self.tabs.addTab(self.monitor_tab, "◈  MONITOR")

        # ── Setup    (TAB_SETUP = 1)
        self.setup_tab = SetupPanel(self.machine)
        self.tabs.addTab(self.setup_tab, "⚙  SETUP")

        # ── Report   (TAB_REPORT = 2)
        self.report_tab = ReportPanel(self.machine)
        self.tabs.addTab(self.report_tab, "▤  REPORT")

        # ── Login    (TAB_LOGIN = 3)
        self.login_tab = LoginPanel()
        self.tabs.addTab(self.login_tab, "⏻  LOGIN")

        # ── 串接
        self.monitor_tab.test_finished.connect(self.report_tab.add_test_record)
        self.setup_tab.methods_changed.connect(self.monitor_tab.on_methods_updated)
        self.login_tab.login_success.connect(self._on_login_success)

    # ────────────────────────────────────────
    def _apply_login_state(self, logged_in: bool):
        """依登入狀態啟用/停用分頁，更新右上角顯示。"""
        # Setup / Report 分頁：未登入時 disable
        self.tabs.setTabEnabled(TAB_SETUP,  logged_in)
        self.tabs.setTabEnabled(TAB_REPORT, logged_in)

        if logged_in:
            # 顯示使用者
            self._lbl_user.setText(
                f"{self._current_display}  ({self._current_user})"
            )
            self._lbl_user.show()
            self._btn_logout.show()
            # 隱藏 Login 分頁（已登入不需要顯示）
            self.tabs.setTabVisible(TAB_LOGIN, False)
            # 切到 Monitor
            self.tabs.setCurrentIndex(TAB_MONITOR)
        else:
            self._lbl_user.hide()
            self._btn_logout.hide()
            # 顯示 Login 分頁並切過去
            self.tabs.setTabVisible(TAB_LOGIN, True)
            self.tabs.setCurrentIndex(TAB_LOGIN)

    def _on_login_success(self, username: str, display: str):
        self._current_user    = username
        self._current_display = display
        self._apply_login_state(logged_in=True)

    def _do_logout(self):
        reply = QMessageBox.question(
            self, "登出確認", f"確定要登出 {self._current_display} 嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._current_user    = ""
        self._current_display = ""
        self.login_tab.reset()
        # 若目前在被鎖定的分頁，先跳回 Monitor 再 disable
        self.tabs.setCurrentIndex(TAB_MONITOR)
        self._apply_login_state(logged_in=False)

    # ────────────────────────────────────────
    def _setup_statusbar(self):
        self.statusBar().showMessage("INITIALIZING ...")

    def _on_status(self, msg: str):
        self.statusBar().showMessage(msg)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_overlay'):
            self._overlay.setGeometry(self.rect())

    def _on_reconnecting(self, seconds: int):
        """machine 倒數重連時更新 overlay"""
        self._overlay.reset()
        self._overlay.show_countdown(seconds)

    def _on_connected(self, ok: bool):
        if ok:
            self._overlay.hide()
            self.statusBar().showMessage(
                f"CONNECTED  ─  {self.machine.host}:{self.machine.port}"
            )
        else:
            # 連線失敗：overlay 會由 _on_reconnecting 倒數顯示
            # 這裡只更新 status bar，不再彈 QMessageBox
            self._overlay.reset()
            self._overlay.show_connecting()
            self.statusBar().showMessage("CONNECTION FAILED  ─  RETRYING...")