"""Claude API integration: generate Seedream prompt and banner texts."""

import json
import logging
import re

import anthropic

from config import ANTHROPIC_API_KEY, BannerSize
from parser import ProductData

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are the creative director of Wabrum.com — a fashion e-commerce marketplace in Turkmenistan selling clothing, shoes, and accessories.

Your task is to generate a professional banner concept based on the provided product data and banner format.

You must return a JSON object with exactly these fields:
- "seedream_prompt": An English prompt (up to 400 words) for Seedream 5.0 image generation model. Describe the scene, composition, lighting, background, mood, and color palette. Do NOT describe the products themselves (they will be provided as reference images). Do NOT include any text, typography, or lettering in the prompt (text overlays are added via CMS). Consider seasonality and current fashion trends.
- "title_ru": A catchy sales title in Russian (up to 6 words)
- "title_tk": The same title translated to Turkmen (up to 6 words)
- "description_ru": A description/CTA in Russian (up to 15 words)
- "description_tk": The same description translated to Turkmen (up to 15 words)

Return ONLY the raw JSON object, no markdown fences, no extra text."""


def _build_user_message(products: list[ProductData], banner_size: BannerSize) -> str:
    lines = [
        f"Banner format: {banner_size.label} ({banner_size.ratio}, {banner_size.width}x{banner_size.height}px)",
        f"Banner purpose: {banner_size.description}",
        "",
        "Products:",
    ]
    for i, p in enumerate(products, 1):
        lines.append(f"{i}. {p.name}")
        if p.category:
            lines.append(f"   Category: {p.category}")
        if p.price:
            lines.append(f"   Price: {p.price}")
        if p.vendor:
            lines.append(f"   Vendor: {p.vendor}")
        lines.append("")

    return "\n".join(lines)


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def generate_banner_content(
    products: list[ProductData],
    banner_size: BannerSize,
) -> dict[str, str]:
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    user_message = _build_user_message(products, banner_size)
    logger.info("Sending request to Claude API for %d products", len(products))

    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text
    cleaned = _strip_json_fences(raw_text)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Claude returned invalid JSON: %s\nRaw: %s", e, raw_text[:500])
        raise ValueError(f"Claude API returned invalid JSON: {e}") from e

    required_keys = {"seedream_prompt", "title_ru", "title_tk", "description_ru", "description_tk"}
    missing = required_keys - set(result.keys())
    if missing:
        raise ValueError(f"Claude response missing keys: {missing}")

    return result
