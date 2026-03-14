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
# Extract labeled links
# -------------------------------------------------

from urllib.parse import urlparse, parse_qs, unquote


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

            # Only classify as a buy link if there is an actual code
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

Return the article body as valid HTML only.

Rules:
- Use <p>, <strong>, <ul>, <ol>, and <li> tags.
- Do NOT use Markdown.
- Do NOT include **bold** or # headings.
- Use semantic HTML formatting.

The article may be one of three types:

1. PRODUCT REVIEW
2. DEMONSTRATION / HOW-TO
3. DISCUSSION / OPINION

First determine the correct type using BOTH the YouTube description and transcript.

IMPORTANT CATEGORY RULES

Choose 1 to 3 categories from this fixed list only:

Firearms
Shooting & Training
Optics
Concealed Carry
Gear & Accessories
Knives

Do NOT invent new categories.
Categories must be returned exactly as written.
Return the most relevant categories first.

VERY IMPORTANT:
Use the MOST SPECIFIC categories available.
Do NOT choose "Gear & Accessories" when a more specific category clearly applies.
"Gear & Accessories" should usually be a secondary or tertiary category, not the primary one.

CATEGORY DECISION RULES

- Firearms:
  Use for rifles, pistols, AR builds, firearm modifications, gun parts, gun setup, firearm-specific installation, and videos centered on the weapon platform itself.

- Shooting & Training:
  Use for drills, marksmanship, instruction, range exercises, recoil control, movement, techniques, and skill development.

- Optics:
  Use for scopes, red dots, reticles, scope mounts, optic leveling, zeroing, sight alignment, and optic installation.

- Concealed Carry:
  Use for holsters, carry methods, concealment bags, off-body carry, AIWB, EDC carry comfort, and defensive carry setup.

- Gear & Accessories:
  Use only when the video is mainly about general gear, tools, bags, lights, mounts, or accessories and is NOT primarily about a firearm, optic, training topic, concealed carry topic, or knife.

- Knives:
  Use for knives, blades, sheaths, knife carry, and knife accessories.

CATEGORY PRIORITY GUIDANCE

When a video is about installing or adjusting an optic on a firearm:
- include Optics
- include Firearms
- do NOT make Gear & Accessories the primary category just because tools or mounts are mentioned

When a video is part of a firearm build series:
- Firearms should almost always be included

When a video is about a scope, red dot, reticle, mount, leveling, or zeroing:
- Optics should almost always be included

When a video mentions tools used during the process:
- tools alone do NOT make it Gear & Accessories primary

Examples:

- AR build + scope mount + reticle alignment
  => ["Firearms", "Optics"]

- Rifle optic installation using torque tools and levels
  => ["Optics", "Firearms"]

- Red dot zeroing at the range
  => ["Optics", "Shooting & Training", "Firearms"]

- Holster review for everyday carry
  => ["Concealed Carry", "Firearms"]

- Concealment bag review for off-body carry
  => ["Concealed Carry", "Gear & Accessories"]

- Knife review
  => ["Knives"]

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
  "categories": ["1 to 3 categories from the fixed list above"],
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

categories = data.get("categories", [])
if not isinstance(categories, list):
    categories = []

categories = [c for c in categories if c in CATEGORIES]

if not categories:
    legacy_category = data.get("category")
    if legacy_category in CATEGORIES:
        categories = [legacy_category]
    else:
        categories = ["Gear & Accessories"]

specs = scraped_specs or data.get("specs", [])

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

<SiteLayout title={{`${{title}} | blasterKRAFT`}} description={{description}}>

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

# if file.exists():
#     print("Review already exists. Skipping.")
#     sys.exit(0)

file.write_text(page, encoding="utf-8")

print(f"Created {file}")