
import subprocess
import os

# Try to find ffmpeg
ffmpeg = "ffmpeg"
try:
    subprocess.run(["ffmpeg", "-version"], capture_output=True)
except:
    # Use the one from the project if we can find it
    # But let's just try to get duration via python-opencv or similar if available
    # Or just use the logs.
    pass

video_path = "output/the_future_of_humanity_final.mp4"
if os.path.exists(video_path):
    print(f"File exists: {video_path}")
    print(f"Size: {os.path.getsize(video_path) / (1024*1024):.2f} MB")
else:
    print("File not found.")
