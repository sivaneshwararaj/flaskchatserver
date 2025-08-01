import os
import re
import subprocess

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
VIDEOS_DATA = [
    # Corresponds to Medical_Training_Day.json
    {"title": "Medical Training Day", "src": "https://videodata3.s3.us-east-2.amazonaws.com/Medical+Content.mp4"},

    # Corresponds to Bike_Footage.json
    {"title": "Bike Footage", "src": "https://videodata3.s3.us-east-2.amazonaws.com/bike_footage.mp4"},

    # Corresponds to Teardown.json
    {"title": "Teardown", "src": "https://videodata3.s3.us-east-2.amazonaws.com/teardown.mp4"},

    # Corresponds to Construction.json
    {"title": "Construction", "src": "https://videodata3.s3.us-east-2.amazonaws.com/carpentary+floor.mp4"},

    # Extra videos (no matching JSON in this example)
    {"title": "Medical Content", "src": "https://videodata3.s3.us-east-2.amazonaws.com/Medical+Training+Day.mp4"},
    {"title": "Building FPV",    "src": "https://videodata3.s3.us-east-2.amazonaws.com/clip_04_web.mp4"},
    {"title": "Night Market",    "src": "https://videodata3.s3.us-east-2.amazonaws.com/night_market_cropped.mp4"},
]

THUMB_TIME = 1          # second
QUALITY    = 2          # lower = better (1-31)

output_folder = "media"
os.makedirs(output_folder, exist_ok=True)

html_thumbnail_paths = []

print("Starting thumbnail generation (FFmpeg, compatible flags)…\n")

for info in VIDEOS_DATA:
    title = info["title"]
    url   = info["src"]
    safe  = re.sub(r'[^A-Za-z0-9]+', '_', title)
    thumb = os.path.join(output_folder, f"{safe}.jpg")

    cmd = [
        "ffmpeg",
        "-v", "error",         # suppress banner & warnings
        "-ss", str(THUMB_TIME), # seek BEFORE opening input
        "-i", url,              # the video URL
        "-vframes", "1",        # exactly one frame
        "-q:v", str(QUALITY),   # JPEG quality
        "-y",                   # overwrite existing file
        thumb
    ]

    try:
        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)
        html_thumbnail_paths.append(f'thumbnail: "{thumb}"')
        print(f"✅ {title}")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg failed for '{title}': {e}")

print("\n--- HTML Thumbnail Paths ---")
for line in html_thumbnail_paths:
    print(line)
print("----------------------------\n")