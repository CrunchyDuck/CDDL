import subprocess
import re
import logging
import os
import importlib
import PyQt5.QtWidgets as wid
import PyQt5.QtCore as qcore
import PyQt5.QtGui as qgui
import sys
import requests
from webbrowser import open as web_open

os.system("venv\\Scripts\\pyuic5.exe ui.ui -o designer_ui.py")  # Update UI file.
import designer_ui
import pytube

logging.basicConfig(filename="log.txt", filemode="w", format="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y/%m/%d %I:%M:%S %p")


def get_module_version_data(module_name):
    """Returns: [list_of_versions, last_version, current_version, is_module_up_to_date]"""
    # Code based on https://stackoverflow.com/questions/58648739/how-to-check-if-python-package-is-latest-version-programmatically

    # This forces an error, and the error returns a list of all of the version of this module.
    # Surely there has to be a better way, but this is what I found online, and it functions.
    latest_version = subprocess.run([sys.executable, '-m', 'pip', 'install', f'{module_name}==random'], capture_output=True, text=True)
    try:
        # Gets the last version listed in the error.
        all_versions = re.search(r"from versions: (.*?)(?:\))", latest_version.stderr).group(1).split(", ")
        last_version = all_versions[-1]
    except AttributeError:  # Internet error, as far as I know.
        logging.error(f"Could not get latest version of {module_name}. Return:\n" + str(latest_version))
        all_versions = []
        last_version = ""

    current_version = subprocess.run([sys.executable, "-m", "pip", "show", f"{module_name}"], capture_output=True, text=True)
    try:
        current_version = re.search(r"Version: ?([\d.]*)", current_version.stdout).group(1)
    except AttributeError:  # Not installed
        logging.error(f"Could not get current version of {module_name}. Return:\n" + str(current_version))
        current_version = ""

    up_to_date = False if last_version != current_version else True
    return [all_versions, last_version, current_version, up_to_date]


class YTDL_ui(designer_ui.Ui_MainWindow):
    def __init__(self, window):
        self.MainWindow = window  # Used for a few things.
        self.setupUi(self.MainWindow)  # Designer UI file.
        self.updating_thread = qcore.QThread()
        self.worker = None  # This is a pain and I can't be bothered to learn how it works right now.
        #self.thread_modify_table.started.connect(self.disable_update_buttons)
        #self.thread_modify_table.finished.connect(self.enable_update_buttons)

        with open("current_version.txt", "r") as f:
            self.tytdlVersion.setText(f.read())

        self.MainWindow.setWindowTitle("YTDL")
        self.MainWindow.setWindowIcon(qgui.QIcon("images/window_icon.png"))  # Window icon

        # Assign buttons
        self.brefreshVersions.clicked.connect(self.refresh_versions)
        self.bupdatePytube.clicked.connect(self.update_pytube)
        self.bopenGit.clicked.connect(self.open_github)

        self.refresh_versions()

    def refresh_versions(self):
        self.update_buttons_disable()
        self.tversionList.clear()
        self.tversionList.addItem("Fetching...")
        self.tcurrentVersion.setText("Fetching...")
        self.tytdlLatest.setText("Fetching...")
        self.tytdlStatus.setStyleSheet("")
        self.tytdlStatus.setText("Fetching...")
        self.tpytubeStatus.setStyleSheet("")
        self.tpytubeStatus.setText("Fetching...")

        self.worker = self.UpdateCheckWorker()
        t = self.updating_thread
        w = self.worker

        w.moveToThread(t)
        t.started.connect(w.run)
        w.version_data.connect(self.update_pytube_version_info)
        w.git_version.connect(self.update_git_version_info)
        w.finished.connect(t.quit)
        w.finished.connect(w.deleteLater)
        w.finished.connect(self.update_buttons_enable)

        t.start()

    def update_pytube(self):
        target_version = self.tversionList.currentText()
        self.update_buttons_disable()
        self.tcurrentVersion.setText("Fetching...")
        self.tpytubeStatus.setStyleSheet("")
        self.tpytubeStatus.setText("Fetching...")

        self.worker = self.UpdatePytubeWorker(target_version)
        t = self.updating_thread
        w = self.worker

        w.moveToThread(t)
        t.started.connect(w.run)
        w.version.connect(self.update_pytube_version_info)
        w.finished.connect(t.quit)
        w.finished.connect(w.deleteLater)
        w.finished.connect(lambda: importlib.reload(pytube))  # This should work.
        w.finished.connect(self.update_buttons_enable)

        t.start()

    def update_buttons_enable(self):
        self.bupdatePytube.setEnabled(True)
        self.brefreshVersions.setEnabled(True)

    def update_buttons_disable(self):
        self.bupdatePytube.setEnabled(False)
        self.brefreshVersions.setEnabled(False)

    def open_github(self):
        web_open("https://github.com/CrunchyDuck/YTDL/releases/latest")

    def update_git_version_info(self, version):
        self.tytdlLatest.setText(version)
        if version == "Unknown":
            self.tytdlStatus.setText("Unknown")
            self.tytdlStatus.setStyleSheet("color:#800080")
        elif version != self.tytdlVersion.text():
            self.tytdlStatus.setText("Outdated")
            self.tytdlStatus.setStyleSheet("color:#f64452")
        else:
            self.tytdlStatus.setText("Up to date")
            self.tytdlStatus.setStyleSheet("color:green")

    def update_pytube_version_info(self, current, version_list=None):
        self.tcurrentVersion.setText(current)

        # Update version list.
        if version_list:
            self.tversionList.clear()  # Remove fetching message.
            self.tversionList.addItems(version_list)
            self.tversionList.setCurrentIndex(len(version_list) - 1)

        if self.tversionList.itemText(self.tversionList.count()-1) != current:
            self.tpytubeStatus.setText("Outdated")
            self.tpytubeStatus.setStyleSheet("color:#f64452")
        else:
            self.tpytubeStatus.setText("Up to date")
            self.tpytubeStatus.setStyleSheet("color:green")

    class UpdateCheckWorker(qcore.QObject):
        """Checks for updates in PyTube/GitHub"""
        finished = qcore.pyqtSignal()
        version_data = qcore.pyqtSignal(str, list)
        git_version = qcore.pyqtSignal(str)

        def run(self):
            # Github version
            status_code = -1
            try:
                x = requests.get("https://api.github.com/repos/CrunchyDuck/YTDL/releases")
                status_code = x.status_code
                self.git_version.emit(x.json()[0]["tag_name"])
            except Exception as e:
                logging.error(f"Could not get latest github version.\nStatus code: {status_code}\nException: {e}")
                self.git_version.emit("Unknown")

            # PyTube version.
            data = get_module_version_data("pytube")
            self.version_data.emit(data[2], data[0])
            self.finished.emit()

    class UpdatePytubeWorker(qcore.QObject):
        finished = qcore.pyqtSignal()
        version = qcore.pyqtSignal(str)

        def __init__(self, target_version):
            super().__init__()
            self.target_version = target_version

        def run(self):
            out = subprocess.run([sys.executable, '-m', 'pip', 'install', f'pytube=={self.target_version}'],
                                 capture_output=True, text=True)
            self.version.emit(self.target_version)
            self.finished.emit()


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


if __name__ == "__main__":
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    #out = subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytube==10.9.0'], capture_output=True, text=True)

    app = wid.QApplication([])
    window = wid.QMainWindow()
    s = YTDL_ui(window)  # Creates the SLS window.
    window.show()
    try:
        app.exec()
    except Exception as e:
        logging.critical(f"Program closed. Exception: {e}")
