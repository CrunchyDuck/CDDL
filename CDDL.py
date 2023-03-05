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
import traceback
import json
from distutils.version import StrictVersion  # Used to sort in get_module_versions

#out = subprocess.run(["venv\\Scripts\\pyuic5.exe", 'ui.ui', '-o', 'designer_ui.py'], capture_output=True, text=True)
import designer_ui
import pytube
from pytube import request
from pytube import exceptions as pt_exceptions

logging.basicConfig(filename="log.txt", filemode="w", format="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y/%m/%d %I:%M:%S %p")


def get_module_versions(module_name):
    url = f"https://pypi.org/pypi/{module_name}/json"
    data = requests.get(url).json()
    versions = list(data["releases"].keys())
    versions.sort(key=StrictVersion)
    return versions


# TODO: Simplify the file formats to remove the audio only check
# TODO: Try to move dependency for FFMPEG to the python wrapper
# TODO: Bandcamp, soundcloud.
class CDDL_ui(designer_ui.Ui_MainWindow):
    subprocess_no_window = 0x08000000
    def __init__(self, window):
        try:
            self.user_settings = json.load(open("user_settings.json", "r"))
        except FileNotFoundError:
            self.user_settings = {}

        self.MainWindow = window  # Used for a few things.
        self.setupUi(self.MainWindow)  # Designer UI file.
        # TODO: I accidentally put downloading on the updating thread; I should move it to its own at some point.
        self.updating_thread = qcore.QThread()
        self.worker = None  # This is a pain and I can't be bothered to learn how it works right now.
        self.downloadStatusLog = StatusLog(self.tdownloadLog, fade_enable=False)

        with open("current_version.txt", "r") as f:
            self.tytdlVersion.setText(f.read())

        self.MainWindow.setWindowTitle("CDDL")
        self.MainWindow.setWindowIcon(qgui.QIcon("images/window_icon.png"))  # Window icon

        self.idownloadConvert.addItems([".mp3", ".flac", ".wav", ".mp4"])
        self.progress_bar = wid.QProgressBar()
        self.statusbar.addPermanentWidget(self.progress_bar)

        # Assign buttons
        self.brefreshVersions.clicked.connect(self.refresh_versions)
        self.bupdatePytube.clicked.connect(self.update_pytube)
        self.bopenGit.clicked.connect(self.open_github)
        self.bdownloadURL.clicked.connect(self.download)
        self.boutputPath.clicked.connect(self.output_path_explorer)
        self.bstopDownload.clicked.connect(self.stop_download)

        # Apply default settings
        self.ioutputPath.setText(self.get_json("download path", str(Path(".").resolve())))
        self.idownloadConvert.setCurrentText(self.get_json("download format", ".mp3"))
        self.idownloadURL.setText(self.get_json("download url", ""))
        self.iaudioOnly.setCheckState(self.get_json("audio only", 2))
        self.iprefix.setCheckState(self.get_json("prefix", 2))
        self.set_download_mode()

        # Other signals
        self.ioutputPath.textChanged.connect(lambda text: self.update_json("download path", str(text)))
        self.idownloadConvert.currentTextChanged.connect(lambda text: self.update_json("download format", str(text)))
        self.idownloadURL.textChanged.connect(lambda text: self.update_json("download url", str(text)))
        self.iaudioOnly.stateChanged.connect(lambda state: self.update_json("audio only", state))
        self.iprefix.stateChanged.connect(lambda state: self.update_json("prefix", state))
        self.bdownloadModePlaylist.clicked.connect(self.get_download_mode)
        self.bdownloadModeVideo.clicked.connect(self.get_download_mode)

        self.updating_thread.started.connect(lambda: self.bstopDownload.setEnabled(True))
        self.updating_thread.finished.connect(lambda: self.bstopDownload.setEnabled(False))

        # Run the updateGUI loop
        self.timer = qcore.QTimer()
        self.timer.timeout.connect(self.downloadStatusLog.update)
        self.timer.start(34)  # about 30 fps ish. QTimer is quite inaccurate though.

        self.refresh_versions()

    # ====== Connections ====== #
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

    def set_download_mode(self):
        mode = self.get_json("mode", "")

        self.bdownloadModeVideo.setChecked(False)
        self.bdownloadModePlaylist.setChecked(False)

        if mode == "playlist":
            self.iprefix.setEnabled(True)
            self.bdownloadModePlaylist.setChecked(True)
        else:  # Video
            self.iprefix.setEnabled(False)
            self.bdownloadModeVideo.setChecked(True)

    def get_download_mode(self):
        if self.bdownloadModePlaylist.isChecked():
            self.update_json("mode", "playlist")
        elif self.bdownloadModeVideo.isChecked():
            self.update_json("mode", "video")

        self.set_download_mode()

    def download(self):
        """Triggered when the download button is pressed."""
        self.get_download_mode()
        mode = self.get_json("mode", "")
        if not mode:
            logging.error("Download mode not found.")
            self.downloadStatusLog.add_message(
                "Download mode not recognized. This is a big problem! Tell me it happened.")
            return

        self.update_buttons_disable()
        if self.iprefix.isEnabled():
            prefix = self.get_json("prefix", 2)
        else:
            prefix = 0
        self.worker = self.DownloadWorker(self.downloadStatusLog, self.idownloadURL.text(), self.iaudioOnly.isChecked(),
                                          self.ioutputPath.text(), self.idownloadConvert.currentText(), mode, prefix)
        t = self.updating_thread
        w = self.worker

        w.moveToThread(t)
        t.started.connect(w.run)
        w.download_status.connect(self.update_download_bar)
        w.finished.connect(t.quit)
        w.finished.connect(w.deleteLater)
        w.finished.connect(self.update_buttons_enable)

        t.start()

    def stop_download(self):
        try:
            self.worker.stop = True
            self.downloadStatusLog.add_message("Stopping downloads...")
        except Exception as e:
            logging.error("Stopping download failed.")

    def output_path_explorer(self):
        """Opens up an explorer, allows user to select the Starbound folder."""
        explorer = wid.QFileDialog()
        explorer.setFileMode(wid.QFileDialog.DirectoryOnly)
        cur_dir = self.ioutputPath.text()
        # explorer.setDirectoryUrl(QUrl(cur_dir if cur_dir else "."))  # FIXME: This doesn't work properly.
        if explorer.exec():
            path = explorer.selectedFiles()[0]
            self.ioutputPath.setText(path)

    def update_download_bar(self, current, max):
        self.progress_bar.setMaximum(max)
        self.progress_bar.setValue(current)

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

    def save_json(self):
        json.dump(self.user_settings, open("user_settings.json", "w"))

    def update_json(self, key, value):
        self.user_settings[key] = value
        self.save_json()

    def get_json(self, key, default):
        try:
            return self.user_settings[key]
        except KeyError:
            return default

    # ====== Workers ====== #
    class UpdateCheckWorker(qcore.QObject):
        """Checks for updates in PyTube/GitHub"""
        finished = qcore.pyqtSignal()
        version_data = qcore.pyqtSignal(str, list)  # Current version, list of versions.
        git_version = qcore.pyqtSignal(str)

        def run(self):
            # Github version
            status_code = -1
            try:
                x = requests.get("https://api.github.com/repos/CrunchyDuck/YTDL/releases")
                status_code = x.status_code
                self.git_version.emit(x.json()[0]["tag_name"])
            except Exception as e:
                logging.error(f"Could not get latest github version.\nStatus code: {status_code}\nException: {traceback.format_exc()}")
                self.git_version.emit("Unknown")

            self.version_data.emit(pytube.__version__, get_module_versions("pytube"))
            self.finished.emit()

    class UpdatePytubeWorker(qcore.QObject):
        finished = qcore.pyqtSignal()
        version = qcore.pyqtSignal(str)

        def __init__(self, target_version):
            super().__init__()
            self.target_version = target_version

        def run(self):
            subprocess.run(['pip', 'install', f'pytube=={self.target_version}'])
            self.version.emit(self.target_version)
            self.finished.emit()

    class DownloadWorker(qcore.QObject):
        finished = qcore.pyqtSignal()
        download_status = qcore.pyqtSignal(int, int)
        # TODO: Find a way to make the stop function intercept downloads. Let it stop 1 hour long download songs.

        def __init__(self, output_log, url, audio_only, output_path, convert_to, mode, prefix):
            super().__init__()
            self.log = output_log
            self.url = url
            self.audio_only = audio_only
            self.output_path = output_path
            self.convert_to = convert_to
            self.mode = mode
            self.prefix = prefix

            self.stop = False

        def run(self):
            target_url = self.url
            if self.mode == "video":
                self.log.add_message(f"Downloading {self.url}")
                for i in range(5):
                    if self.stop:
                        break
                    final_attempt = True if i == 4 else False
                    worked = self.download_video(target_url, final_attempt=final_attempt)
                    if worked or self.stop:
                        break
                    self.log.append_message("Failed, retrying...")
            else:  # Playlist
                try:
                    playlist = pytube.Playlist(target_url)
                    i = 1
                    num_in_playlist = len(playlist.video_urls)
                    for x in range(num_in_playlist):
                        if self.stop: break

                        self.log.add_message(f"Downloading {self.url}")

                        if self.prefix:
                            pl_num = f"000{i + 1} "[-4:]
                        else:
                            pl_num = ""
                        for j in range(5):
                            if self.stop: break
                            final_attempt = True if i == 4 else False
                            worked = self.download_video(playlist.video_urls[i], pl_num, final_attempt)
                            if worked or self.stop:
                                break
                            self.log.append_message("Failed, retrying...")
                except Exception as e:
                    logging.warning(f"Error downloading playlist: {target_url}\n{traceback.format_exc()}")
                    self.log.append_message(f"Unknown error downloading playlist. Details in log.txt.")
            # Is output path valid?
            # Is convert format valid?
            self.finished.emit()

        def download_video(self, url, prefix="", final_attempt=False):
            """Handles actually downloading the video.
            If final_attempt is false, don't log errors.
            """
            # Load youtube object
            try:
                YouTubeObj = pytube.YouTube(url)
            except pt_exceptions.RegexMatchError:
                if final_attempt:
                    logging.warning(f"Could not find url in {url}")
                self.log.append_message(f"Could not find url in {url}")
                return
            except pt_exceptions.VideoPrivate:
                if final_attempt:
                    self.log.append_message(f"Video is private: {url}")
                return
            except Exception as e:
                if final_attempt:
                    logging.error(f"Unknown error fetching {url}\n{traceback.format_exc()}")
                self.log.append_message(f"Error finding {url}, skipping...")
                return

            try:
                file_name = prefix + YouTubeObj.title + self.convert_to
                file_name = "".join(x for x in file_name if x not in "\\/:*?\"<>|")
                file_directory = self.output_path
                output_path = os.path.join(file_directory, file_name)
                if Path(output_path).exists():
                    self.log.append_message(f"{file_name} already downloaded.")
                    return True

                self.log.append_message(f"Downloading {YouTubeObj.title}...")

                audio = YouTubeObj.streams.order_by("abr")[-1]  # MP4 if progressive, WEBM otherwise.
                # MP4
                if audio.is_progressive:
                    # Download to extract audio
                    if self.audio_only:
                        path = f"{self.file_directory}/cddl.mp4"
                    # Download directly
                    else:
                        path = output_path
                    self.download_stream(audio, path)
                    if self.stop:
                        return

                    # Extract audio from mp4
                    if self.audio_only:
                        subprocess.run(["ffmpeg -i", path, "-vn -acodec copy", output_path], creationflags=CDDL_ui.subprocess_no_window)
                    logging.info(f"Downloaded {file_name}")
                    self.log.append_message(f"Downloaded {file_name}")
                # WEBM
                else:
                    audio_path = f"{self.file_directory}/cddl_audio"
                    self.download_stream(audio, audio_path)
                    if self.stop:
                        return

                    # Convert
                    if self.audio_only:
                        subprocess.run(["ffmpeg", "-i", audio_path, output_path], creationflags=CDDL_ui.subprocess_no_window)
                    # Download video
                    else:
                        video_path = f"{self.file_directory}/cddl_video"
                        video = YouTubeObj.streams.filter(progressive=False).order_by("resolution")[-1]  # Get best video
                        self.download_stream(video, video_path)
                        if self.stop:
                            os.remove(audio_path)
                            return
                        # Combine audio and video
                        subprocess.run(["ffmpeg -i", video_path, "-i", audio_path, "-c:v copy -c:a aac", output_path], creationflags=CDDL_ui.subprocess_no_window)
                        os.remove(video_path)
                    os.remove(audio_path)

                    logging.info(f"Downloaded {file_name}")
                    self.log.append_message(f"Downloaded {file_name}")
            except Exception as e:
                if final_attempt:
                    self.log.append_message(f"Unknown error downloading {url}, details in log.txt")
                logging.error(f"Could not download {url}.\n{traceback.format_exc()}")
                return
            return True

        def download_stream(self, stream, filepath):
            amount_downloaded = 0
            amount_to_download = stream.filesize
            stream = pytube.request.stream(stream.url)
            with open(filepath, "wb") as f:
                while amount_downloaded < amount_to_download:
                    if self.stop:
                        break
                    chunk = next(stream, None)
                    if chunk:
                        f.write(chunk)
                        amount_downloaded += len(chunk)
                    else:
                        break
                    self.download_status.emit(amount_downloaded, amount_to_download)
            self.download_status.emit(0, 1)  # Finished.
            if self.stop:
                os.remove(filepath)


class StatusLog:
    """
    Displays messages in a given text box for a given amount of time.

    Properties:
        label - The text box to display information in.
        last_time - Used for delta-time calculations
    """
    message_list = []

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
        # text_cursor = self.label.textCursor().position()  # TODO: Make text reselect.
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
        #self.label.setTextCursor(text_cursor)

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

    def append_message(self, message):
        """Adds the given text to the last message."""
        if self.message_list:
            self.message_list[-1]["message"] += f"<br/>{message}"
        else:
            self.add_message(message, self.default_duration, "000000")


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
    logging.exception(f"{exctype} {value} {traceback}")
    sys._excepthook(exctype, value, traceback)
    sys.exit(1)


def main():
    # NOTE: Naming scheme.
    # GUI objects are given a prefix based on their function.
    # t - General, non-editable text
    # i - Input field/editable text
    # b - Button
    # w - Widget/container
    sys._excepthook = sys.excepthook
    sys.excepthook = exception_hook

    # out = subprocess.run(['pip', 'install', 'pytube==10.9.0'], capture_output=True, text=True)

    app = wid.QApplication([])
    window = wid.QMainWindow()
    s = CDDL_ui(window)  # Creates the SLS window.
    window.show()
    try:
        app.exec()
    except Exception as e:
        logging.critical(f"Program closed. Exception: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
