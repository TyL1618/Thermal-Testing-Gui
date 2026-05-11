from pathlib import Path
import sys
import os
#----------------------------------
# 打包後確保專案根目錄在 sys.path 內
if getattr(sys, 'frozen', False):
    # 執行的是 PyInstaller 打包的 exe
    ROOT_DIR = os.path.dirname(sys.executable)
    sys._MEIPASS_ROOT = ROOT_DIR
else:
    # 一般開發執行
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
#----------------------------------

ROOT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from gui.main_window import MainWindow
from core.machine import GotechMachine


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Re_HV")
    app.setOrganizationName("Re_HV")

    # 模擬模式（接不到機台時設 simulation=True）
    # 連線資訊：請依實際機台設定修改 host / port
    machine = GotechMachine(
        host="192.168.1.100",   # ← 替換為機台實際 IP
        port=1500,
        simulation=False,       # ← 改成 True 可在離線時測試 GUI
    )

    window = MainWindow(machine)
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()