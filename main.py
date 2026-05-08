import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(ROOT_DIR))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from gui.main_window import MainWindow
from core.machine import TestingMachine


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("ThermalTestingGUI")
    app.setOrganizationName("ThermalTestingGUI")

    # 模擬模式（接不到機台時設 simulation=True）
    machine = TestingMachine(
        host="192.168.1.100",
        port=1500,
        simulation=False,   # ← 改成 True 可在離線時測試 GUI
    )

    window = MainWindow(machine)
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()