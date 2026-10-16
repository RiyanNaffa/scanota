"""app/synth/render_receipts.py – Render 40 synthetic receipt PNG images.

Renders receipts from a subset of offline_history.csv into data/sample_receipts/.
Includes ground_truth.json and realistic degradation.
5 receipts are intentionally wrong (total != sum of items).
"""

from __future__ import annotations

import csv
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

DATA_DIR = os.path.join("data", "sample_transactions")
OUTPUT_DIR = os.path.join("data", "sample_receipts")
FONTS_DIR = os.path.join("data", "fonts")

NUM_RECEIPTS = 40
NUM_INTENTIONAL_ERRORS = 5
RNG_SEED = 42


def _get_font(size: int = 16) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a font; fall back to default."""
    for font_path in [
        os.path.join(FONTS_DIR, "DejaVuSansMono.ttf"),
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _render_receipt(items: list[dict], meta: dict, intentional_error: bool) -> Image.Image:
    """Render a receipt as a PIL Image."""
    width = 400
    line_height = 22
    padding = 20
    header_lines = 5
    footer_lines = 3

    total_lines = header_lines + len(items) + footer_lines + 2
    height = total_lines * line_height + padding * 2

    img = Image.new("L", (width, height), color=240)
    draw = ImageDraw.Draw(img)
    font_small = _get_font(14)
    font_normal = _get_font(16)
    font_bold = _get_font(18)

    y = padding

    # Header
    draw.text((width // 2 - 80, y), "TOKO BANGUNAN JAYA", font=font_bold, fill=30, anchor="lt")
    y += line_height
    draw.text(
        (width // 2 - 60, y), "Jl. Raya No. 123, Jakarta", font=font_small, fill=60, anchor="lt"
    )
    y += line_height
    draw.text((padding, y), f"Tgl: {meta['date']}", font=font_normal, fill=30)
    draw.text((width - padding - 120, y), f"No: {meta['nota_no']}", font=font_normal, fill=30)
    y += line_height
    draw.text((padding, y), f"Kpd: {meta.get('customer') or '-'}", font=font_normal, fill=30)
    y += line_height
    draw.line([(padding, y), (width - padding, y)], fill=60, width=1)
    y += 6

    # Items
    item_sum = 0
    for item in items:
        name = item["item_name"][:28]
        qty = item["qty"]
        unit = item["unit"] or ""
        price = item["unit_price"]
        lt = item["line_total"]
        item_sum += lt

        draw.text((padding, y), f"{name}", font=font_small, fill=30)
        y += line_height - 4
        draw.text(
            (padding + 10, y),
            f"{qty} {unit} x Rp{price:,} = Rp{lt:,}",
            font=font_small,
            fill=50,
        )
        y += line_height + 2

    draw.line([(padding, y), (width - padding, y)], fill=60, width=1)
    y += 6

    # Total (intentionally wrong on error receipts)
    display_total = meta["total"]
    draw.text((padding, y), f"TOTAL: Rp {display_total:,}", font=font_bold, fill=30)
    y += line_height * 2

    # Footer
    draw.text((padding, y), "Terima kasih atas kunjungan Anda!", font=font_small, fill=80)

    return img


def _degrade_image(img: Image.Image, rng: random.Random) -> Image.Image:
    """Apply realistic degradation: rotation, blur, noise, lighting."""
    arr = np.array(img, dtype=np.float32)

    # Uneven lighting (vignette-like)
    h, w = arr.shape
    cx, cy = w // 2, h // 2
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    max_dist = math.sqrt(cx**2 + cy**2)
    vignette = 1.0 - 0.15 * (dist / max_dist)
    arr = arr * vignette

    # Noise
    noise = rng.gauss(0, 5)
    arr = arr + np.random.default_rng(rng.randint(0, 2**31)).normal(0, abs(noise), arr.shape)
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    img = Image.fromarray(arr)

    # Blur
    if rng.random() < 0.4:
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 1.0)))

    # Rotation ±5 degrees
    angle = rng.uniform(-5, 5)
    img = img.rotate(angle, fillcolor=240, expand=False)

    return img


def render_receipts() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    rng = random.Random(RNG_SEED)

    # Load offline history
    offline_path = os.path.join(DATA_DIR, "offline_history.csv")
    if not os.path.exists(offline_path):
        print(f"ERROR: {offline_path} not found. Run `python -m app.synth.generate` first.")
        return

    # Group rows into transactions (same date + customer + seed_ref prefix)
    with open(offline_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Group by (date, customer, seed_ref)
    groups: dict[str, list[dict]] = {}
    for row in rows:
        key = f"{row['date']}|{row['customer']}|{row['seed_ref']}"
        groups.setdefault(key, []).append(row)

    group_list = list(groups.values())
    rng.shuffle(group_list)
    selected = group_list[:NUM_RECEIPTS]

    ground_truth = []
    error_indices = set(rng.sample(range(NUM_RECEIPTS), NUM_INTENTIONAL_ERRORS))

    for i, group in enumerate(selected):
        items = [
            {
                "item_name": r["item_name"],
                "sku_id": r["sku_id"],
                "qty": float(r["qty"]),
                "unit": r["unit"],
                "unit_price": int(r["unit_price"]),
                "line_total": int(r["line_total"]),
            }
            for r in group
        ]
        true_total = sum(it["line_total"] for it in items)

        intentional_error = i in error_indices
        if intentional_error:
            # Off by a random amount
            display_total = true_total + rng.randint(1000, 9999) * rng.choice([-1, 1])
        else:
            display_total = true_total

        nota_no = f"N{i + 1:04d}"
        meta = {
            "date": group[0]["date"],
            "customer": group[0]["customer"] or None,
            "nota_no": nota_no,
            "total": display_total,
        }

        receipt_img = _render_receipt(items, meta, intentional_error)
        receipt_img = _degrade_image(receipt_img, rng)

        filename = f"receipt_{i + 1:04d}.png"
        filepath = os.path.join(OUTPUT_DIR, filename)
        receipt_img.save(filepath, "PNG", optimize=True)

        # Check file size < 400 KB; if not, resize
        if os.path.getsize(filepath) > 400 * 1024:
            w, h = receipt_img.size
            receipt_img = receipt_img.resize((w // 2, h // 2), Image.LANCZOS)
            receipt_img.save(filepath, "PNG", optimize=True)

        ground_truth.append(
            {
                "filename": filename,
                "date": group[0]["date"],
                "customer": group[0]["customer"] or None,
                "items": items,
                "total": display_total,
                "true_total": true_total,
                "intentional_error": intentional_error,
            }
        )

    with open(os.path.join(OUTPUT_DIR, "ground_truth.json"), "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, ensure_ascii=False, indent=2)

    print(f"Rendered {NUM_RECEIPTS} receipts to {OUTPUT_DIR}/")
    print(f"  {NUM_INTENTIONAL_ERRORS} receipts have intentional total errors")
    print("  ground_truth.json written")


if __name__ == "__main__":
    render_receipts()
