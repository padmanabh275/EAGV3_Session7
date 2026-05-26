#!/usr/bin/env python3
"""Generate 55 synthetic product sheets (India / INR) under sandbox/corpus/products/.

Run from S7code/:
    uv run python scripts/build_shopping_corpus.py

Five products are eval anchors; the rest flesh out a 50+ item price-comparison corpus.
All prices are in Indian Rupees (INR, ₹).
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / "sandbox" / "corpus" / "products"

# Indian retailers used across the corpus
STORES = (
    "Flipkart",
    "Amazon.in",
    "Croma",
    "Reliance Digital",
    "Vijay Sales",
    "Tata Cliq",
    "Snapdeal",
    "JioMart",
)

# Eval-anchor products (see eval/shopping_queries.json)
ANCHORS: list[dict] = [
    {
        "slug": "quietwave-pro",
        "title": "QuietWave Pro",
        "sku": "ELEC-HEAD-8842",
        "category": "Audio",
        "body": """
QuietWave Pro — over-ear closed-back headphones for daily commuters and open-plan staff.

Acoustic design: adaptive feed-forward dampening for low-frequency rumble (Mumbai suburban
local train vibration, metro corridor thrum) and steady chatter in coworking bays and IT
parks. Memory-foam cushions with pressure-relief vent.

Pricing snapshot (INR, inclusive of typical online discount; check GST invoice at checkout):
- Flipkart: ₹15,999 — Plus members free delivery, 10-day replacement
- Croma: ₹16,290 — store pickup available in Bengaluru / Pune
- Reliance Digital: ₹15,750 — festive exchange bonus up to ₹2,000
- Vijay Sales: ₹16,100 — extended warranty add-on ₹499

Specs: 32-hour rated playback, USB-C, dual-device multipoint, fold-flat hinge.
Warranty: 24 months national carry-in. Model year 2025. Made for India voltage 230V charger bundle N/A (USB).
""",
    },
    {
        "slug": "voltendure-a54",
        "title": "VoltEndure A54",
        "sku": "PHON-AND-5521",
        "category": "Mobile",
        "body": """
VoltEndure A54 — mid-tier Android handset tuned for battery endurance, not mobile gaming scores.

Power: 5200 mAh silicon-carbon cell; vendor quotes 48 hours typical mixed use between full
charges (Wi‑Fi, VoLTE, UPI alerts). In-box 45W Dart-style brick; 15W wireless Qi.

Display: 6.6-inch 90Hz IPS, Gorilla Glass 3. Storage 128 GB + microSD up to 1 TB.

Online pricing (INR, unlocked Indian unit):
- Vijay Sales: ₹36,499 — bank offer extra ₹1,500 off select cards
- Flipkart: ₹36,999 — SBI card no-cost EMI 6 months
- Amazon.in: ₹37,199 — Prime next-day in metros
- Tata Cliq: ₹37,450 — Cliq Cash 5% for repeat buyers

Chipset: octa-core 2.4 GHz; 8 GB RAM. IP67. Ships with Android 15; Jio / Airtel / Vi certified.
""",
    },
    {
        "slug": "portacharge-mini",
        "title": "PortaCharge Mini 5000",
        "sku": "ACC-PWR-1099",
        "category": "Accessories",
        "body": """
PortaCharge Mini 5000 — pocket 5000 mAh power bank, 22.5W USB-C PD, BIS certification mark.

Retail offers (INR):
- Snapdeal: ₹899 — lightning deal tier, limit 2 per account
- Flipkart: ₹1,099 — usually delivered in 3–5 days nationwide
- Amazon.in: ₹1,049 — Fulfilled by Amazon
- JioMart: ₹1,150 — same-day in select pin codes

Weight 98 g; short USB-C cable included. Cabin-safe for domestic flights. Colours: black, sage.
""",
    },
    {
        "slug": "letterplay-softblocks",
        "title": "LetterPlay SoftBlocks Set",
        "sku": "TOY-EDU-7720",
        "category": "Toys",
        "body": """
LetterPlay SoftBlocks — EVA foam tiles with embossed Devanagari-friendly Latin letter forms
for early literacy play (English alphabet).

Age band: 24–48 months. 26 tiles + storage tote. ISI-labelled child-safe materials; BPA-free.

Educational positioning: pre-literacy motor exploration; balvatika / preschool classrooms use
for phoneme introduction. Washable surface.

Pricing (INR):
- FirstCry: ₹1,799 — free shipping above ₹799
- Hamleys India: ₹1,899 — mall stores in major metros
- Amazon.in: ₹1,699 — lowest online shelf in last 30-day scrape
- Reliance Smart Bazaar: ₹1,750 — occasional bundle with storybook
""",
    },
    {
        "slug": "brewmaster-12",
        "title": "BrewMaster 12-Cup Thermal",
        "sku": "HOME-KET-3310",
        "category": "Kitchen",
        "body": """
BrewMaster 12-Cup Thermal — drip coffee maker for Indian 230V, stainless thermal carafe.

Programmable bloom; keeps heat ~4 hours. Suitable for filter coffee decoction or ground coffee.

Pricing (INR):
- Reliance Digital: ₹6,499 — installation not required
- Croma: ₹6,790 — Croma Card 5% off
- Amazon.in: ₹6,550 — during Great Indian Festival

1200 W; gold-tone filter; descale alert. Matte black or white. GST 18% category as per HSN.
""",
    },
]

# (slug, title, sku, category, tagline, base_inr)
FILLER_TEMPLATES = [
    ("nova-laptop-14", "NovaBook 14", "COMP-LAP-1001", "Computing", "14-inch ultralight laptop", 58999),
    ("pulse-watch-s", "PulseWatch S", "WEAR-FT-2202", "Wearables", "AMOLED fitness band", 12499),
    ("terra-blender-pro", "TerraBlend Pro", "KIT-APP-3303", "Kitchen", "1400W mixer-grinder compatible blender", 7499),
    ("skydrone-mini", "SkyDrone Mini", "CAM-DRN-4404", "Cameras", "249g FPV quad (DGCA nano rules apply)", 27999),
    ("cozy-throw-xl", "CozyThrow XL", "HOME-TXT-5505", "Home", "heated fleece throw for North India winters", 4999),
    ("spark-gaming-mouse", "Spark GX Mouse", "GAM-PER-6606", "Gaming", "26K DPI optical mouse", 3799),
    ("pure-air-300", "PureAir 300 HEPA", "HOME-AR-7707", "Home", "CADR 220 room purifier", 16999),
    ("ridge-hiking-boot", "RidgeTrail Boot", "OUT-FW-8808", "Outdoors", "monsoon-ready mid hikers", 10999),
    ("luma-desk-lamp", "LumaDesk Lamp", "OFF-LGT-9909", "Office", "USB-C study lamp", 3199),
    ("frost-chest-7cu", "FrostChest 7 cu ft", "APP-FRZ-1010", "Appliances", "deep freezer 7 cu ft", 38499),
]

FILLER_STORE_PAIRS = [
    ("Flipkart", "Amazon.in"),
    ("Croma", "Reliance Digital"),
    ("Vijay Sales", "Tata Cliq"),
    ("Snapdeal", "JioMart"),
    ("Flipkart", "Croma"),
]


def _render(p: dict) -> str:
    return f"""# {p['title']}

SKU: {p['sku']}
Category: {p['category']}
Market: India (INR / ₹)

{p['body'].strip()}
"""


def _filler_from_template(t: tuple, idx: int) -> dict:
    slug, title, sku, cat, tagline, base = t
    delta_a = 400 + (idx % 7) * 150
    delta_b = 600 + (idx % 5) * 120
    price_a = base + delta_a
    price_b = max(499, base - delta_b)
    store_a, store_b = FILLER_STORE_PAIRS[idx % len(FILLER_STORE_PAIRS)]
    return {
        "slug": slug,
        "title": title,
        "sku": sku,
        "category": cat,
        "body": f"""
{title} — {tagline}.

Feature notes: India model {2024 + (idx % 2)}; 1-year national warranty; BIS / regulatory labels as applicable.

Street pricing (INR):
- {store_a}: ₹{price_a:,}
- {store_b}: ₹{price_b:,}
- PriceAggregate India median: ₹{base:,}

Compare MRP vs offer; card cashback and EMI vary by bank (HDFC, ICICI, SBI common on Flipkart / Amazon.in).
""",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    products: list[dict] = list(ANCHORS)
    n = 55 - len(ANCHORS)
    for i in range(n):
        t = FILLER_TEMPLATES[i % len(FILLER_TEMPLATES)]
        cycle = i // len(FILLER_TEMPLATES)
        p = _filler_from_template(t, i + cycle)
        if cycle > 0:
            p["slug"] = f"{p['slug']}-v{cycle + 1}"
            p["sku"] = p["sku"][:-2] + f"{cycle:02d}"
        products.append(p)

    manifest = []
    for p in products:
        path = OUT / f"{p['slug']}.md"
        path.write_text(_render(p), encoding="utf-8")
        manifest.append({"slug": p["slug"], "sku": p["sku"], "path": str(path.relative_to(HERE))})

    (OUT.parent / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(products)} product files (India / INR) to {OUT}")
    print(f"Manifest: {OUT.parent / 'manifest.json'}")


if __name__ == "__main__":
    main()
