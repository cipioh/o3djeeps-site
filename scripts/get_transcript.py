import sys
from pathlib import Path
from youtube_transcript_api import YouTubeTranscriptApi

video_id = sys.argv[1]
slug = sys.argv[2]

output_file = Path(f"transcripts/{slug}.txt")

output_file.parent.mkdir(parents=True, exist_ok=True)

ytt = YouTubeTranscriptApi()
transcript = ytt.fetch(video_id)

text = "\n".join(chunk.text for chunk in transcript)

output_file.write_text(text, encoding="utf-8")

print(f"Saved transcript to: {output_file}")