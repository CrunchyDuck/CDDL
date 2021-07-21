import subprocess
import re
import logging
import importlib
import PyQt5.QtWidgets as wid
import PyQt5.QtCore as qcore
import PyQt5.QtGui as qgui
import sys
import requests
from webbrowser import open as web_open
import time
import os
from pathlib import Path

out = subprocess.run(["venv\\Scripts\\pyuic5.exe", 'ui.ui', '-o', 'designer_ui.py'], capture_output=True, text=True)
import designer_ui
import pytube
from pytube import exceptions as pt_exceptions

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


class CDDL_ui(designer_ui.Ui_MainWindow):
    def __init__(self, window):
        self.MainWindow = window  # Used for a few things.
        self.setupUi(self.MainWindow)  # Designer UI file.
        self.updating_thread = qcore.QThread()
        self.worker = None  # This is a pain and I can't be bothered to learn how it works right now.
        self.downloadStatusLog = StatusLog(self.tdownloadLog, fade_enable=False)
        #self.thread_modify_table.started.connect(self.disable_update_buttons)
        #self.thread_modify_table.finished.connect(self.enable_update_buttons)

        with open("current_version.txt", "r") as f:
            self.tytdlVersion.setText(f.read())

        self.MainWindow.setWindowTitle("CDDL")
        self.MainWindow.setWindowIcon(qgui.QIcon("images/window_icon.png"))  # Window icon

        self.idownloadConvert.addItems([".mp3", ".flac", ".wav", ".mp4"])

        # Assign buttons
        self.brefreshVersions.clicked.connect(self.refresh_versions)
        self.bupdatePytube.clicked.connect(self.update_pytube)
        self.bopenGit.clicked.connect(self.open_github)
        self.bdownloadURL.clicked.connect(self.download)

        # Run the updateGUI loop
        self.timer = qcore.QTimer()
        self.timer.timeout.connect(self.downloadStatusLog.update)
        self.timer.start(34)  # about 30 fps ish. QTimer is quite inaccurate though.

        self.refresh_versions()

    # ====== Buttons ====== #
    def update_buttons_enable(self):
        self.bupdatePytube.setEnabled(True)
        self.brefreshVersions.setEnabled(True)
        self.bdownloadURL.setEnabled(True)

    def update_buttons_disable(self):
        self.bupdatePytube.setEnabled(False)
        self.brefreshVersions.setEnabled(False)
        self.bdownloadURL.setEnabled(False)

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
        self.tcurrentVersion.setText("Updating...")
        self.tpytubeStatus.setStyleSheet("")
        self.tpytubeStatus.setText("Updating...")

        self.worker = self.UpdatePytubeWorker(target_version)
        t = self.updating_thread
        w = self.worker

        w.moveToThread(t)
        t.started.connect(w.run)
        w.version.connect(self.update_pytube_version_info)
        w.finished.connect(t.quit)
        w.finished.connect(w.deleteLater)
        w.finished.connect(lambda: importlib.reload(pytube))  # This might not work.
        w.finished.connect(self.update_buttons_enable)

        t.start()

    def open_github(self):
        web_open("https://github.com/CrunchyDuck/YTDL/releases/latest")

    def download(self):
        """Triggered when the download button is pressed."""
        if self.bdownloadModePlaylist.isChecked():
            mode = "playlist"
        elif self.bdownloadModeVideo.isChecked():
            mode = "video"
        else:
            logging.error("Download mode not found.")
            self.downloadStatusLog.add_message(
                "Download mode not recognized. This is a big problem! Tell me it happened.")
            return

        self.update_buttons_disable()
        self.worker = self.DownloadWorker(self.downloadStatusLog, self.idownloadURL.text(), self.iaudioOnly.isChecked(),
                                          self.ioutputPath.text(), self.idownloadConvert.currentText(), mode)
        t = self.updating_thread
        w = self.worker

        w.moveToThread(t)
        t.started.connect(w.run)
        w.finished.connect(t.quit)
        w.finished.connect(w.deleteLater)
        w.finished.connect(self.update_buttons_enable)

        t.start()



    # ====== General functions ====== #
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

    # ====== Workers ====== #
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

    class DownloadWorker(qcore.QObject):
        finished = qcore.pyqtSignal()

        def __init__(self, output_log, url, audio_only, output_path, convert_to, mode):
            super().__init__()
            self.log = output_log
            self.url = url
            self.audio_only = audio_only
            self.output_path = output_path
            self.convert_to = convert_to
            self.mode = mode

        def run(self):
            target_url = self.url
            if self.mode == "video":
                self.download_video(target_url)
            else:  # Playlist
                try:
                    # list=PLeSM-rQ-jVpulMI3sas4GE6Xh2XH4pwqD
                    re.search(r"(?:list=)([0-9A-Za-z_-]{34})", target_url).group(1)
                except AttributeError:
                    logging.warning(f"Could not find playlist URL in {target_url}")
                    self.downloadStatusLog.add_message(f"Could not find playlist URL in {target_url}"
                                                       f"\nI'm doing this weirdly, so definitely let me know if this persists.")
                    return
            # Is output path valid?
            # Is convert format valid?
            self.finished.emit()

        def download_video(self, url):
            """Handles actually downloading the video."""
            # Load youtube object
            try:
                YouTubeObj = pytube.YouTube(url)
                file_name = YouTubeObj.title
                file_directory = self.output_path
                self.log.add_message(f"Downloading {YouTubeObj.title}...")
            except pt_exceptions.RegexMatchError:
                self.downloadStatusLog.add_message(f"Could not find url in {url}")
                logging.warning(f"Could not find url in {url}")
                return
            except pt_exceptions.VideoPrivate:
                self.downloadStatusLog.add_message(f"Video is private: {url}")
                return
            except Exception as e:
                self.downloadStatusLog.add_message(f"Error finding {url}, skipping...")
                logging.error(f"Unknown error fetching {url}\n{e}")
                return

            # TODO: Implement converting.
            try:
                audio = YouTubeObj.streams.order_by("abr")[-1]
                audio_path = audio.download(output_path=self.output_path)
                self.log.add_message("Downloaded audio")
                if not self.audio_only:
                    video = YouTubeObj.streams.order_by("resolution")[-1]
                    video_path = video.download(output_path=self.output_path)
                    self.log.add_message("Downloaded video")

                    if self.convert_to != "":
                        suffix = self.convert_to
                    else:
                        suffix = str(Path(video_path).suffix)

                    output_path = file_directory + file_name + suffix
                    subprocess.run(["ffmpeg", '-i', video_path, "-i", audio_path, "-c", "copy", output_path], capture_output=True, text=True, input="y")
                    logging.info(f"Downloaded {video.default_filename}")
                    self.log.add_message(f"Downloaded {video.default_filename}")
                    os.remove(audio_path)
                    os.remove(video_path)
                else:
                    if self.convert_to != "":
                        suffix = self.convert_to
                        output_path = file_directory + file_name + suffix
                        subprocess.run(["ffmpeg", "-i", audio_path, output_path], capture_output=True, text=True, input="y")
                    self.log.add_message(f"Downloaded {audio.default_filename}")

                    os.remove(audio_path)
            except Exception as e:
                logging.error(f"Could not download {url}.\n{e}")
                self.log.add_message(f"Unknown error downloading {url}, details in log.txt")
                return


class StatusLog:
    """
    Displays messages in a given text box for a given amount of time.

    Properties:
        label - The text box to display information in.
        last_time - Used for delta-time calculations
    """
    message_list = []  # See add_message

    def __init__(self, label, fade_enable=True, background_color="FFFFFF", default_duration=5):
        self.label = label
        self.last_time = time.time()
        self.default_duration = default_duration
        self.background_colour = background_color
        self.fade_enable = fade_enable

    def update(self):
        t = time.time()
        delta_time = (t - self.last_time) * 1000
        self.last_time = t
        fade_threshold = 500  # Point at which text starts to fade out.
        scroll_before = self.label.verticalScrollBar().value()  # Where the scroll bar is right now.
        # TODO: Make it auto scroll if at the bottom of the scroll bar.

        label_content = "<html><head/><body>"
        self.message_list = [x for x in self.message_list if x["duration"] > 0]  # Clear list of "dead" entries.
        # Fade text, add text to the label_content
        for m in self.message_list:
            if self.fade_enable:
                if m["duration"] < fade_threshold:
                    message_color = color_lerp(m["color"], self.background_colour, m["duration"] / fade_threshold)
                else:
                    message_color = m["color"]
                label_content += f"<p><span style=\"color:#{message_color};\">{m['message']}</p>"
                m["duration"] -= delta_time
            else:
                message_color = m["color"]
                label_content += f"<p><span style=\"color:#{message_color};\">{m['message']}</p>"

        label_content += "</body></html>"
        self.label.setText(label_content)

        # If this isn't done, scroll will be set to the top constantly.
        self.label.verticalScrollBar().setValue(scroll_before)

    def add_message(self, message, duration=-1, color="000000"):
        """Add a message to the text box.

        Arguments:
            message - The message to add.
            duration - How long to display the message for
            color - The color of the text. Returned to fade the text out.
        """
        if duration == -1:
            duration = self.default_duration
        self.message_list.append({"message": message, "duration": duration, "color": color})


def color_lerp(color1, color2, t):
    """A very basic linear interp between two colours.
    Color values should be hex string.

    Arguments:
        color1 - from
        color2 - to
        t - percent between

    Return: Hex string formatted as "FFF00FF"
    """
    # Convert from hex string to int.
    color1 = int(color1, 16)
    color2 = int(color2, 16)

    # Create a list of R, G and B with bitwise and.
    colors1 = [(color1 & 0xFF0000) >> 16, (color1 & 0x00FF00) >> 8, color1 & 0x0000FF]
    colors2 = [(color2 & 0xFF0000) >> 16, (color2 & 0x00FF00) >> 8, color2 & 0x0000FF]

    # Linear interpolation of R G and B
    new_color = ""  # Hex value of new colour.
    for c1, c2 in zip(colors1, colors2):
        new_color += pad_hex(round(c2 + (c1 - c2) * t))

    return new_color


def pad_hex(number, size=2):
    """Pads and strips a hex value, E.G:
    0xF -> 0F"""
    h = hex(number)[2:]
    return ("0" * (size - len(h))) + h


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


if __name__ == "__main__":
    # NOTE: Naming scheme.
    # GUI objects are given a prefix based on their function.
    # t - General, non-editable text
    # i - Input field/editable text
    # b - Button
    # w - Widget/container

    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    #out = subprocess.run([sys.executable, '-m', 'pip', 'install', 'pytube==10.9.0'], capture_output=True, text=True)

    app = wid.QApplication([])
    window = wid.QMainWindow()
    s = CDDL_ui(window)  # Creates the SLS window.
    window.show()
    try:
        app.exec()
    except Exception as e:
        logging.critical(f"Program closed. Exception: {e}")
