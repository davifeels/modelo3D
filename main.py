import os
import sys

os.environ["QT_API"] = "pyqt5"

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt

import src.logger as log_mod
from ui.main_window import MainWindow


def _dark_palette(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(30, 30, 40))
    p.setColor(QPalette.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.Base,            QColor(20, 20, 28))
    p.setColor(QPalette.AlternateBase,   QColor(38, 38, 50))
    p.setColor(QPalette.ToolTipBase,     QColor(50, 50, 70))
    p.setColor(QPalette.ToolTipText,     QColor(220, 220, 220))
    p.setColor(QPalette.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.Button,          QColor(45, 45, 60))
    p.setColor(QPalette.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.BrightText,      Qt.red)
    p.setColor(QPalette.Link,            QColor(42, 130, 218))
    p.setColor(QPalette.Highlight,       QColor(42, 130, 218))
    p.setColor(QPalette.HighlightedText, QColor(20, 20, 20))
    app.setPalette(p)


def main():
    log = log_mod.setup()
    log.info("=" * 60)
    log.info("ZefiroSplit iniciando. Python %s", sys.version.split()[0])
    log.info("Log salvo em: %s", log_mod.log_path())

    app = QApplication(sys.argv)
    app.setApplicationName("ZefiroSplit")
    _dark_palette(app)
    win = MainWindow()
    win.show()

    log.info("Interface carregada.")
    exit_code = app.exec_()
    log.info("ZefiroSplit encerrado (exit code %d).", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
