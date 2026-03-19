import sys
import json
import re
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

client = OpenAI()

if len(sys.argv) < 5:
    print("Usage: python generate_review.py <title> <slug> <youtube_id> <publish_date>")
    sys.exit(1)

title = sys.argv[1]
slug = sys.argv[2]
youtube = sys.argv[3]
publish_date = sys.argv[4]

# -------------------------------------------------
# CHANNEL CONFIG (EDIT THIS PER SITE)
# -------------------------------------------------

CHANNEL = {
    "site_name": "o3djeeps",
    "site_url": "o3djeeps.com",
    "youtube_handle": "@o3djeeps",
    "niche": "Jeep builds, off-road adventures, gear reviews, trail upgrades, recovery equipment, and real-world vehicle modifications",
    "categories": [
        "Builds",
        "Off-Road",
        "Gear",
        "Mods",
        "Reviews",
        "Maintenance"
    ],
    "default_category": "Reviews",
    "affiliate_name": "o3djeeps"
}

CATEGORIES = CHANNEL["categories"]

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
# Extract labeled links
# -------------------------------------------------

def unwrap_youtube_redirect(url):
    """
    Convert YouTube redirect URLs into the real destination.
    """
    if "youtube.com/redirect" not in url:
        return url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if "q" in qs:
        return unquote(qs["q"][0])

    return url


def extract_labeled_links(description_text):
    lines = [line.rstrip() for line in description_text.splitlines()]
    results = []

    heading_patterns = [
        r"^links?:?$",
        r"^helpful links?:?$",
        r"^useful links?:?$",
        r"^links that you might find helpful.*$",
    ]

    def is_heading(text):
        lowered = text.lower().strip()
        return any(re.match(p, lowered) for p in heading_patterns)

    def clean_prefix(text):
        return re.sub(r"^[\s▶•\-–—👉💥🔥]+", "", text).strip()

    def is_url_line(text):
        return bool(re.search(r"https?://[^\s]+", text))

    def extract_discount_code(text):
        m = re.search(
            r"(?:with\s+code|use\s+code|code)\s*[:\-]?\s*([A-Z0-9_-]+)",
            text,
            flags=re.IGNORECASE,
        )
        return m.group(1) if m else None

    for i, line in enumerate(lines):
        match = re.search(r"https?://[^\s]+", line)
        if not match:
            continue

        raw_url = match.group(0).rstrip(".,)")
        url = unwrap_youtube_redirect(raw_url)

        label = None
        context_line = None
        found_discount_code = None
        is_buy_link = False

        j = i - 1
        while j >= 0:
            prev = lines[j].strip()

            if not prev:
                j -= 1
                continue

            if is_heading(prev):
                break

            if is_url_line(prev):
                j -= 1
                continue

            cleaned = clean_prefix(prev)

            if not cleaned:
                j -= 1
                continue

            context_line = cleaned
            found_discount_code = extract_discount_code(cleaned)

            if found_discount_code:
                is_buy_link = True
                label = "View Product →"
            else:
                label = cleaned

            break

        results.append({
            "label": label or "Helpful Link",
            "url": url,
            "is_buy_link": is_buy_link,
            "discount_code": found_discount_code,
            "context_line": context_line,
        })

    seen = set()
    deduped = []

    for item in results:
        key = (item["label"], item["url"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped


labeled_links = extract_labeled_links(description_text)

buy_link = None
buy_text = "View Product →"
discount_text = None
discount_code = None
useful_links = []

buy_candidate = next((x for x in labeled_links if x["is_buy_link"]), None)

if buy_candidate:
    buy_link = buy_candidate["url"]
    discount_text = buy_candidate["context_line"]
    discount_code = buy_candidate["discount_code"]

    useful_links = [
        {"label": x["label"], "url": x["url"]}
        for x in labeled_links
        if x["url"] != buy_link
    ]
else:
    useful_links = [
        {"label": x["label"], "url": x["url"]}
        for x in labeled_links
    ]

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
        r.raise_for_status()

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

                    if label and value:
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

category_list = "\n".join(CATEGORIES)

prompt = f"""
You are writing an article for {CHANNEL["site_url"]}, a website that accompanies a YouTube channel focused on {CHANNEL["niche"]}.

Return ONLY valid JSON.

The goal is to create a strong companion article based on the YouTube title, description, and transcript.

WRITING STYLE
- Write like an experienced enthusiast speaking to interested readers.
- Do NOT just summarize the transcript line-by-line.
- Expand ideas with practical context and useful observations.
- Avoid fluff and repetition.
- Be specific and natural.

HTML RULES
- article_html must be valid HTML only.
- Use <h2>, <p>, <strong>, <ul>, <ol>, and <li>.
- Do NOT use Markdown.
- Do NOT wrap the response in code fences.

CONTENT TYPE
First determine whether the video is primarily:
1. review
2. tutorial
3. discussion

CATEGORY RULES
Choose 1 to 3 categories from this fixed list only:

{category_list}

- Do NOT invent new categories.
- Categories must be returned exactly as written.
- Return the most relevant categories first.

ARTICLE LENGTH
- Target roughly 800–1200 words when enough source material exists.
- If the source material is thin, still produce a useful article with clear structure.

SECTION GUIDANCE

If content_type is "review", include sections like:
<h2>Quick Verdict</h2>
<h2>What Stands Out</h2>
<h2>Design and Features</h2>
<h2>Real-World Use</h2>
<h2>Who This Is For</h2>
<h2>Key Takeaways</h2>

If content_type is "tutorial", include sections like:
<h2>Overview</h2>
<h2>What This Covers</h2>
<h2>Step-by-Step Breakdown</h2>
<h2>Helpful Tips</h2>
<h2>Key Takeaways</h2>

If content_type is "discussion", include sections like:
<h2>Overview</h2>
<h2>Main Points</h2>
<h2>Practical Implications</h2>
<h2>Key Takeaways</h2>

SPECS
If applicable, return a short specs array with useful structured fields.
If no formal specs are obvious, return a few practical fields such as:
- Brand
- Product
- Platform
- Use Case
- Category

Return JSON in exactly this format:

{{
  "description": "SEO meta description under 160 characters",
  "content_type": "review | tutorial | discussion",
  "categories": ["1 to 3 categories from the fixed list above"],
  "specs": [
    {{"label": "Brand", "value": "value"}},
    {{"label": "Product", "value": "value"}},
    {{"label": "Use Case", "value": "value"}}
  ],
  "article_html": "<h2>...</h2><p>...</p>"
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

categories = data.get("categories", [])
if not isinstance(categories, list):
    categories = []

categories = [c for c in categories if c in CATEGORIES]

if not categories:
    legacy_category = data.get("category")
    if legacy_category in CATEGORIES:
        categories = [legacy_category]
    else:
        categories = [CHANNEL["default_category"]]

specs = scraped_specs or data.get("specs", [])
if not isinstance(specs, list):
    specs = []

specs.insert(0, {
    "label": "Category",
    "value": ", ".join(categories)
})

article_html = data.get(
    "article_html",
    "<h2>Quick Verdict</h2><p>Review content unavailable.</p>"
)

specs_json = json.dumps(specs, ensure_ascii=False, indent=2)
external_links_json = json.dumps(useful_links, ensure_ascii=False)

# -------------------------------------------------
# Generate Astro page
# -------------------------------------------------

page = f"""---
import SiteLayout from "../../layouts/SiteLayout.astro";
import ReviewHero from "../../components/ReviewHero.astro";

export const title = {json.dumps(title)};
export const description = {json.dumps(description)};
const youtubeId = {json.dumps(youtube)};
const buyLink = {json.dumps(buy_link)};
const buyText = {json.dumps(buy_text)};
const discountCode = {json.dumps(discount_code)};
const discountText = {json.dumps(discount_text)};
export const date = "{publish_date}";
export const specs = {specs_json};
const externalLinks = {external_links_json};
---

<SiteLayout title={{`${{title}} | {CHANNEL["site_name"]}`}} description={{description}}>

<article>

<ReviewHero
  title={{title}}
  description={{description}}
  youtubeId={{youtubeId}}
  buyLink={{buyLink}}
  buyText={{buyText}}
  discountCode={{discountCode}}
  discountText={{discountText}}
  showPromo={{Boolean(discountCode && buyLink)}}
  specs={{specs}}
  externalLinks={{externalLinks}}
  date={{date}}
/>

{article_html}

</article>

</SiteLayout>
"""

file = Path(f"src/pages/reviews/{slug}.astro")
file.write_text(page, encoding="utf-8")

print(f"Created {file}")