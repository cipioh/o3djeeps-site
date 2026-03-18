import sys
import re
import subprocess
import requests
import os

if len(sys.argv) < 2:
    print("Usage: python scripts/new_review.py VIDEO_ID")
    sys.exit(1)

video_id = sys.argv[1]
API_KEY = os.environ.get("YOUTUBE_API_KEY")

if not API_KEY:
    print("Missing YOUTUBE_API_KEY")
    sys.exit(1)

# ----------------------------------------
# FETCH METADATA FROM YOUTUBE API
# ----------------------------------------

url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={API_KEY}"

res = requests.get(url)
data = res.json()

if "items" not in data or not data["items"]:
    print("Error retrieving video metadata")
    print(data)
    sys.exit(1)

snippet = data["items"][0]["snippet"]

title = snippet["title"]
description = snippet.get("description", "")
publish_date = snippet.get("publishedAt", "")[:10]

# ----------------------------------------
# SLUG CLEANING (unchanged logic)
# ----------------------------------------

def clean_slug(title: str) -> str:
    title = title.lower()

    remove_phrases = [
        "just dropped",
        "first look",
        "range test",
        "hands on",
        "preview",
        "review",
        "quick",
    ]

    for phrase in remove_phrases:
        title = re.sub(rf"\b{re.escape(phrase)}\b", " ", title)

    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()

    return "-".join(title.split())

slug = clean_slug(title)

print(f"Title: {title}")
print(f"Slug: {slug}")

# ----------------------------------------
# SAVE DESCRIPTION
# ----------------------------------------

desc_path = f"transcripts/{slug}-description.txt"

with open(desc_path, "w", encoding="utf-8") as f:
    f.write(description)

# ----------------------------------------
# RUN EXISTING PIPELINE
# ----------------------------------------

subprocess.run(
    [sys.executable, "scripts/get_transcript.py", video_id, slug],
    check=True,
)

subprocess.run(
    [sys.executable, "scripts/get_thumbnail.py", video_id, slug],
    check=True,
)

subprocess.run(
    [
        sys.executable,
        "scripts/generate_review.py",
        title,
        slug,
        video_id,
        publish_date
    ],
    check=True,
)
subprocess.run(
    [sys.executable, "scripts/generate_review.py", title, slug, video_id, publish_date],
    check=True,
)
