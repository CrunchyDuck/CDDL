import subprocess
from pathlib import Path
import re
import os

# Only on Linux systems, adds relevant metadata to the files in the provided folder.
# lame is needed to run this.
re_pattern = r"(\d\d\d) - (.+).mp3"
album_folder = Path("/home/duck/Audio/Music/Albums/2 Mello/Memories Of Tokyo-To/")
album_name = album_folder.name
artist_name = album_folder.parent
album_cover = Path(album_folder, "album.jpg")

songs = album_folder.glob("**/*.mp3")
for song in songs:
    print("Processing " + song.name + "...")
    re_result = re.search(re_pattern, song.name)

    track_num = str(int(re_result.group(1)))
    track_name = re_result.group(2)
    new_file = Path(album_folder, f"{track_name}.mp3")

    subprocess.call(["lame",
                     "--ti", str(album_cover),
                     "--ta", artist_name,
                     "--tl", album_name,
                     "--tt", track_name,
                     "--tn", track_num,
                     #"--ty", ,  # year
                     song, new_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT)
    #print("Deleting original file...")
    #os.remove(song)
    print(f"Finished processing song: {new_file}")
    # Could you make this bulkier, subprocess?
    # subprocess.call(["ffmpeg", "-i", file, "-i", album_cover, "-map_metadata", "0", "-map", "0", "-map", "1", "-acodec", "copy", new_file])
    # subprocess.call(["id3v2", "--artist", artist_name, new_file])
    # subprocess.call(["id3v2", "--album", album_name, new_file])
    # subprocess.call(["id3v2", "--song", track_name, new_file])
    # subprocess.call(["id3v2", "--track", track_num, new_file])
    # "ffmpeg -i input.mp3 -i cover.jpg -map_metadata 0 -map 0 -map 1 output.mp3"

