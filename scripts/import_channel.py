import subprocess
import json
import os
import re
import time
import sys

CHANNEL_URL = "https://www.youtube.com/@blasterKRAFT"


def slugify(title):
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", "-", title.strip())
    return title


cmd = [
    "yt-dlp",
    "--dump-json",
    "--playlist-end", "200",
    CHANNEL_URL
]

result = subprocess.run(cmd, capture_output=True, text=True)

videos = result.stdout.splitlines()

for video in videos:
    data = json.loads(video)

    video_id = data["id"]
    title = data["title"]
    duration = data.get("duration")

    # Skip Shorts
    if duration and duration < 90:
        print(f"Skipping short: {title}")
        continue

    slug = slugify(title)

    page_path = f"src/pages/reviews/{slug}.astro"

    if os.path.exists(page_path):
        print(f"Skipping existing: {title}")
        continue

    print(f"Importing: {title}")

    subprocess.run([
        sys.executable,
        "scripts/new_review.py",
        video_id
    ])

    print("Waiting 30 seconds before next video...")
    time.sleep(30)