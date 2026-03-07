import sys
import requests
from pathlib import Path

video_id = sys.argv[1]
slug = sys.argv[2]

url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

path = Path(f"public/images/thumbs/{slug}.jpg")
path.parent.mkdir(parents=True, exist_ok=True)

img = requests.get(url)

with open(path, "wb") as f:
    f.write(img.content)

print(f"Thumbnail saved to {path}")