import subprocess
import json
import os
import re
import time
import sys

# -------------------------------------------------
# CHANNEL CONFIG (EDIT PER SITE)
# -------------------------------------------------

CHANNEL = {
    "name": "o3djeeps",
    "url": "https://www.youtube.com/@o3djeeps",
    "min_duration": 90,  # skip shorts
    "delay_between": 30  # seconds
}

# -------------------------------------------------
# Helpers
# -------------------------------------------------

def slugify(title):
    title = title.lower()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", "-", title.strip())
    return title


# -------------------------------------------------
# Fetch videos using yt-dlp
# -------------------------------------------------

cmd = [
    "yt-dlp",
    "--dump-json",
    CHANNEL["url"]
]

print(f"Fetching videos from {CHANNEL['url']}...")

result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    print("❌ Failed to fetch channel data")
    print(result.stderr)
    sys.exit(1)

videos = result.stdout.splitlines()

print(f"Found {len(videos)} videos\n")

# -------------------------------------------------
# Process each video
# -------------------------------------------------

for i, video in enumerate(videos, start=1):
    data = json.loads(video)

    video_id = data["id"]
    title = data["title"]
    duration = data.get("duration")

    # Skip Shorts
    if duration and duration < CHANNEL["min_duration"]:
        print(f"⏭️  Skipping short: {title}")
        continue

    slug = slugify(title)
    page_path = f"src/pages/reviews/{slug}.astro"

    # Skip if already exists
    if os.path.exists(page_path):
        print(f"✅ Skipping existing: {title}")
        continue

    print(f"\n[{i}/{len(videos)}] Importing: {title}")

    try:
        subprocess.run([
            sys.executable,
            "scripts/new_review.py",
            video_id
        ], check=True)

        print(f"⏳ Waiting {CHANNEL['delay_between']}s before next video...\n")
        time.sleep(CHANNEL["delay_between"])

    except subprocess.CalledProcessError:
        print(f"❌ Failed to process: {title}")
        continue

print("\n✅ Channel import complete.")