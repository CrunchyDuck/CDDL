import subprocess
from pathlib import Path
import re
import os


def process_mp3(input_file: str, output_file: str, artist_name: str, album_name: str, track_name: str, track_num: str):
    command = ["lame",
               "--ta", artist_name,
               "--tl", album_name,
               "--tt", track_name,
               "--tn", track_num]

    #if album_cover.is_file():
    #    command.extend(["--ti", str(album_cover)])

    command.extend([input_file, output_file])

    subprocess.call(command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT)
    # print("Deleting original file...")
    # os.remove(song)
    print(f"Finished processing song: {output_file}")


def process_flac(input_file: str, output_file: str, artist_name: str, album_name: str, track_name: str, track_num: str):
    command = [
        "metaflac",
        "--remove-all-tags",
        f'--set-tag=ARTIST={artist_name}',
        f'--set-tag=ALBUM={album_name}',
        f'--set-tag=TRACKNUMBER={track_num}',
        f'--set-tag=TITLE={track_name}',
        input_file
    ]
    subprocess.call(command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT)
    os.rename(input_file, output_file)

    print(f"Finished processing song: {output_file}")


def process(file_path):
    file_format = "flac"  # flac or mp3 supported
    re_pattern = r"(\d\d\d) - (.+)." + file_format
    album_folder = Path(file_path)
    album_name = album_folder.name
    artist_name = album_folder.parent.name

    songs = album_folder.glob("**/*." + file_format)
    for song in songs:
        print("Processing " + song.name + "...")
        re_result = re.search(re_pattern, song.name)

        try:
            track_num = str(int(re_result.group(1)))
            track_name = re_result.group(2)
            output_file = Path(album_folder, f"{track_name}.{file_format}")
        except:
            continue

        # lame is needed to run this.
        if file_format == "mp3":
            process_mp3(str(song), str(output_file), artist_name, album_name, track_name, track_num)
        # metaflac is needed to run this.
        elif file_format == "flac":
            process_flac(str(song), str(output_file), artist_name, album_name, track_name, track_num)


def main():
    process("F:\Libraries\Audio\Music\Albums\Disparition\Welcome To Night Vale")


if __name__ == "__main__":
    main()
