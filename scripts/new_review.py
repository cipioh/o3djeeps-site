import sys
import re
import subprocess
import json

if len(sys.argv) < 2:
    print("Usage: python scripts/new_review.py VIDEO_ID")
    sys.exit(1)

video_id = sys.argv[1]

cmd = [
    "yt-dlp",
    "--dump-json",
    f"https://www.youtube.com/watch?v={video_id}",
]

result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode != 0:
    print("Error retrieving video metadata")
    print(result.stderr)
    sys.exit(1)

data = json.loads(result.stdout)
title = data["title"]
upload_date = data.get("upload_date")
description = data.get("description", "")
publish_date = None

if upload_date:
    publish_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    
def clean_slug(title: str) -> str:
    title = title.lower()

    # Remove whole phrases first
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

    # Keep only letters, numbers, and spaces
    title = re.sub(r"[^a-z0-9\s]", " ", title)

    # Collapse repeated whitespace
    title = re.sub(r"\s+", " ", title).strip()

    # Build slug from whole words only
    words = title.split()
    slug = "-".join(words)

    return slug


slug = clean_slug(title)

print(f"Title: {title}")
print(f"Slug: {slug}")

desc_path = f"transcripts/{slug}-description.txt"

with open(desc_path, "w") as f:
    f.write(description)

subprocess.run(
    ["python", "scripts/get_transcript.py", video_id, slug],
    check=True,
)

subprocess.run(
    ["python", "scripts/get_thumbnail.py", video_id, slug],
    check=True,
)

subprocess.run(
    [sys.executable, "scripts/generate_review.py", title, slug, video_id, publish_date],
    check=True,
)