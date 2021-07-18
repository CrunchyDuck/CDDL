import import_helper
import logging
import os
import importlib
import PyQt5.QtWidgets as wid
import PyQt5.QtCore as qcore
import sys

os.system("venv\\Scripts\\pyuic5.exe ui.ui -o designer_ui.py")  # Update UI file.
import designer_ui
import pytube

logging.basicConfig(filename="log.txt", filemode="w", format="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y/%m/%d %I:%M:%S %p")


class YTDL_ui(designer_ui.Ui_MainWindow):
    def __init__(self, window):
        self.MainWindow = window  # Used for a few things.
        self.setupUi(self.MainWindow)  # Designer UI file.
        self.updating_thread = qcore.QThread()
        #self.thread_modify_table.started.connect(self.disable_update_buttons)
        #self.thread_modify_table.finished.connect(self.enable_update_buttons)



    class UpdateWorker(qcore.QObject):
        """Checks for updates in PyTube"""
        finished = qcore.pyqtSignal()

        def run(self):
            self.finished.emit()


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


if __name__ == "__main__":
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    # pytube_version_data = import_helper.get_module_version_data("pytube")

    app = wid.QApplication([])
    window = wid.QMainWindow()
    s = YTDL_ui(window)  # Creates the SLS window.
    window.show()
    try:
        app.exec()
    except Exception as e:
        logging.critical(f"Program closed. Exception: {e}")
