import sys
import json
import re
import os
from pathlib import Path
from openai import OpenAI
import requests
from bs4 import BeautifulSoup

client = OpenAI()

title = sys.argv[1]
slug = sys.argv[2]
youtube = sys.argv[3]
publish_date = sys.argv[4]

# -------------------------------------------------
# Fixed categories for the entire site
# -------------------------------------------------

CATEGORIES = [
    "Firearms",
    "Shooting & Training",
    "Optics",
    "AR-15",
    "Concealed Carry",
    "Gear & Accessories",
    "Knives"
]

# -------------------------------------------------
# Load transcript
# -------------------------------------------------

transcript_path = Path(f"transcripts/{slug}.txt")

if not transcript_path.exists():
    print("Transcript not found.")
    sys.exit(1)

transcript_raw = transcript_path.read_text(encoding="utf-8")

# -------------------------------------------------
# Load description
# -------------------------------------------------

desc_file = f"transcripts/{slug}-description.txt"
description_text = ""

if os.path.exists(desc_file):
    with open(desc_file, encoding="utf-8") as f:
        description_text = f.read()

# -------------------------------------------------
# Extract links
# -------------------------------------------------

links = re.findall(r"https?://[^\s]+", description_text)
links = [l.rstrip(".,)") for l in links]

buy_link = "#"
external_links = []

if links:
    buy_link = links[0]
    external_links = links[1:]

# -------------------------------------------------
# Extract discount code
# -------------------------------------------------

discount_code = None

discount_patterns = [
    r"code[:\s]+([A-Z0-9]+)",
    r"discount[:\s]+([A-Z0-9]+)"
]

for pattern in discount_patterns:
    match = re.search(pattern, description_text, re.IGNORECASE)
    if match:
        discount_code = match.group(1)
        break

# -------------------------------------------------
# Compress transcript
# -------------------------------------------------

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

    joined = "\n".join(filtered)

    return joined[:15000]


transcript = compress_transcript(transcript_raw)

# -------------------------------------------------
# Scrape specs from product page
# -------------------------------------------------

def scrape_product_specs(url):

    if not url or url == "#":
        return []

    try:

        r = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        soup = BeautifulSoup(r.text, "html.parser")

        specs = []

        tables = soup.find_all("table")

        for table in tables:

            rows = table.find_all("tr")

            for row in rows:

                cols = row.find_all(["td", "th"])

                if len(cols) == 2:

                    label = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)

                    specs.append({
                        "label": label,
                        "value": value
                    })

        return specs

    except Exception:
        return []


scraped_specs = scrape_product_specs(buy_link)

# -------------------------------------------------
# LLM prompt
# -------------------------------------------------

prompt = f"""
You are writing an article for blasterKRAFT.com, a gear-focused website that accompanies a YouTube channel reviewing shooting gear, EDC equipment, and technical demonstrations.

The article may be one of three types:

1. PRODUCT REVIEW
2. DEMONSTRATION / HOW-TO
3. DISCUSSION / OPINION

First determine the correct type using BOTH the YouTube description and transcript.

IMPORTANT CATEGORY RULES

Choose exactly ONE category from this list:

Firearms
Shooting & Training
Optics
AR-15
Concealed Carry
Gear & Accessories
Knives

Do NOT invent new categories.
The category must be returned exactly as written.

STYLE GUIDELINES

• Write like an experienced enthusiast explaining gear.
• Do NOT summarize the transcript.
• Expand ideas with real-world insight and context.
• Use natural paragraphs.
• Avoid filler language.
• Use clean HTML headings and sections.

ARTICLE LENGTH

Target **800–1200 words**.

If the video is a PRODUCT REVIEW include sections:

<h2>Quick Verdict</h2>
<h2>What Makes This Review Different</h2>
<h2>Design and Layout</h2>
<h2>Real-World Use</h2>
<h2>Who This Product May Be For</h2>
<h2>Key Takeaways</h2>

If it is a DEMONSTRATION or HOW-TO include:

<h2>Overview</h2>
<h2>What This Video Demonstrates</h2>
<h2>Step-by-Step Explanation</h2>
<h2>Key Tips</h2>
<h2>Key Takeaways</h2>

If it is a DISCUSSION include:

<h2>Overview</h2>
<h2>Main Discussion Points</h2>
<h2>Practical Implications</h2>
<h2>Key Takeaways</h2>

Return ONLY valid JSON in this format:

{{
  "description": "SEO meta description under 160 characters",
  "content_type": "review | tutorial | discussion",
  "category": "ONE OF THE FIXED CATEGORIES ABOVE",
  "specs": [
    {{"label": "Brand", "value": "value"}},
    {{"label": "Product", "value": "value"}},
    {{"label": "Use Case", "value": "value"}}
  ],
  "article_html": "<HTML content>"
}}

YouTube Title:
{title}

YouTube Description:
{description_text}

Transcript:
{transcript}
"""

# -------------------------------------------------
# Call OpenAI
# -------------------------------------------------

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}]
)

raw = response.choices[0].message.content.strip()

raw = re.sub(r"^```[a-zA-Z]*", "", raw)
raw = re.sub(r"```$", "", raw)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    raw = raw.replace("\n", "\\n")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("Model returned invalid JSON:")
        print(raw)
        sys.exit(1)

# -------------------------------------------------
# Extract LLM values
# -------------------------------------------------

description = data.get("description", f"Review of {title}.")
category = data.get("category", "Gear & Accessories")

specs = scraped_specs or data.get("specs", [])

specs.insert(0, {
    "label": "Category",
    "value": category
})

article_html = data.get(
    "article_html",
    "<h2>Quick Verdict</h2><p>Review content unavailable.</p>"
)

specs_json = json.dumps(specs, ensure_ascii=False, indent=2)
external_links_json = json.dumps(external_links, ensure_ascii=False)

# -------------------------------------------------
# Generate Astro page
# -------------------------------------------------

page = f"""---
import SiteLayout from "../../layouts/SiteLayout.astro";
import ReviewHero from "../../components/ReviewHero.astro";

export const title = {json.dumps(title)};
export const description = {json.dumps(description)};
const youtubeId = {json.dumps(youtube)};
const discountCode = {json.dumps(discount_code)};
export const date = "{publish_date}";
const specs = {specs_json};
const externalLinks = {external_links_json};
---

<SiteLayout title={{`${{title}} | blasterKRAFT`}} description={{description}}>

<article>

<ReviewHero
  title={{title}}
  description={{description}}
  youtubeId={{youtubeId}}
  buyLink={json.dumps(buy_link)}
  buyText="View Product →"
  discountCode={{discountCode}}
  showPromo={{Boolean(discountCode)}}
  specs={{specs}}
  externalLinks={{externalLinks}}
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