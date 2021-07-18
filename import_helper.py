import subprocess
import sys
import re
import logging

# ====== Exceptions ====== #
class NoInternet(Exception):
    pass


class NotInstalled(Exception):
    pass


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

