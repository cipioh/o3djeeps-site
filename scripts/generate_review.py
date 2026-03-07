import sys
import json
import re
import os
from pathlib import Path
from openai import OpenAI

client = OpenAI()

title = sys.argv[1]
slug = sys.argv[2]
youtube = sys.argv[3]
publish_date = sys.argv[4]

transcript_path = Path(f"transcripts/{slug}.txt")

if not transcript_path.exists():
    print("Transcript not found.")
    sys.exit(1)

desc_file = f"transcripts/{slug}-description.txt"

description_text = ""
if os.path.exists(desc_file):
    with open(desc_file) as f:
        description_text = f.read()

def compress_transcript(text: str) -> str:
    lines = text.split("\n")
    filtered = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if len(line) < 30:
            continue

        filtered.append(line)

    joined = " ".join(filtered)
    return joined[:15000]


def strip_code_fences(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    return text.strip()


transcript = compress_transcript(transcript_path.read_text(encoding="utf-8"))

prompt = f"""
You are writing a gear review article for a website that accompanies a YouTube channel.

Use ONLY the transcript below.
Do not invent facts that are not supported by the transcript.
Return ONLY valid JSON with this exact shape:

{{
  "description": "one-sentence meta description",
  "specs": [
    {{"label": "Brand", "value": "value"}},
    {{"label": "Product", "value": "value"}},
    {{"label": "Category", "value": "value"}},
    {{"label": "Use Case", "value": "value"}}
  ],
  "article_html": "<h2>Quick Verdict</h2><p>...</p><h2>What Makes This Review Different</h2><p>...</p><h2>Design and Layout</h2><p>...</p><h2>Real-World Testing</h2><p>...</p><h2>Who This Product May Be For</h2><ul><li>...</li></ul><h2>Key Takeaways</h2><ul><li>...</li></ul>"
}}

Rules:
- article_html must contain ONLY valid HTML, no markdown fences
- include these sections in article_html:
  Quick Verdict
  What Makes This Review Different
  Design and Layout
  Real-World Testing
  Who This Product May Be For
  Key Takeaways
- specs should be filled only with details clearly supported by the transcript
- if a spec is unknown, omit it rather than inventing it

YouTube Description:
{description_text}

Transcript:
{transcript}

"""

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
)

raw = response.choices[0].message.content
raw = strip_code_fences(raw)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("Model did not return valid JSON:")
    print(raw)
    sys.exit(1)

description = data.get("description", f"Review of {title}.")
specs = data.get("specs", [])
article_html = data.get("article_html", "<h2>Quick Verdict</h2><p>Review content unavailable.</p>")

specs_json = json.dumps(specs, ensure_ascii=False, indent=2)

page = f"""---
import SiteLayout from "../../layouts/SiteLayout.astro";
import PromoBox from "../../components/PromoBox.astro";
import ReviewHero from "../../components/ReviewHero.astro";

export const title = {json.dumps(title, ensure_ascii=False)};
export const description = {json.dumps(description, ensure_ascii=False)};
const youtubeId = {json.dumps(youtube)};
const discountCode = null;
export const date = "{publish_date}";
const specs = {specs_json};
---

<SiteLayout title={{`${{title}} | blasterKRAFT`}} description={{description}}>

<article>

<ReviewHero
  title={{title}}
  description={{description}}
  youtubeId={{youtubeId}}
  buyLink="#"
  buyText="View Product →"
  discountCode={{discountCode}}
  specs={{specs}}
  date={{date}}
/>

{article_html}

</article>

</SiteLayout>
"""

file = Path(f"src/pages/reviews/{slug}.astro")

if file.exists():
    print("Review already exists. Skipping.")
    sys.exit(0)

file.write_text(page, encoding="utf-8")

print(f"Created {file}")