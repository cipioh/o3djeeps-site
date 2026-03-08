from pathlib import Path
import re

# mapping from old categories -> new buckets
CATEGORY_MAP = {
    "Holster": "Concealed Carry",
    "Holsters": "Concealed Carry",
    "Concealment Holster": "Concealed Carry",
    "Concealed Carry Holsters": "Concealed Carry",
    "Concealment Bags": "Concealed Carry",
    "EDC Gear": "Concealed Carry",

    "Optics": "Optics",
    "Red Dot Sight": "Optics",
    "Optics Maintenance": "Optics",

    "AR-15 Upgrade": "AR-15",
    "AR-15 Upgrades": "AR-15",
    "AR-15 Accessories": "AR-15",

    "Knives": "Knives",
    "Fighting Knives": "Knives",

    "Firearms": "Firearms",
    "Handgun": "Firearms",
    "Pistol": "Firearms",
    "Rifles": "Firearms",
    "Firearms Upgrade": "Firearms",
    "Modification": "Firearms",
    "Firearm Disassembly": "Firearms",

    "Firearms Training": "Shooting & Training",
    "Firearm Training": "Shooting & Training",
    "Shooting Practice": "Shooting & Training",
    "Training Gear": "Shooting & Training",
    "Shooting Gear": "Shooting & Training",

    "Firearms Accessories": "Gear & Accessories",
    "Firearm Accessories": "Gear & Accessories",
    "Mag Pouches": "Gear & Accessories",
    "Grip Accessories": "Gear & Accessories",
    "Shooting Accessories": "Gear & Accessories",

    "Ear Protection": "Gear & Accessories",
    "Hearing Protection": "Gear & Accessories",
}

reviews = Path("src/pages/reviews")

for file in reviews.glob("*.astro"):

    text = file.read_text()

    match = re.search(
        r'("label":\s*"Category"\s*,\s*"value":\s*")([^"]+)(")',
        text
    )

    if not match:
        continue

    old_category = match.group(2)

    new_category = CATEGORY_MAP.get(old_category)

    if not new_category:
        print(f"⚠️  No mapping for: {old_category}")
        continue

    text = text.replace(
        f'"label": "Category", "value": "{old_category}"',
        f'"label": "Category", "value": "{new_category}"'
    )

    file.write_text(text)

    print(f"Updated {file.name}: {old_category} → {new_category}")