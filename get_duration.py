
import subprocess
import os
import re

video_path = "output/the_future_of_humanity_final.mp4"
# Using a dummy ffmpeg call to get metadata
try:
    # Need to find the ffmpeg exe
    # Let's check config.py's way
    import sys
    sys.path.append(os.getcwd())
    from config import FFMPEG_BIN
    
    result = subprocess.run([FFMPEG_BIN, "-i", video_path], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if match:
        print(f"Duration: {match.group(0)}")
    else:
        print("Duration not found in output.")
        print(result.stderr[-500:])
except Exception as e:
    print(f"Error: {e}")
