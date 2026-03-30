"""
Claude API integration for generating:
1. Seedream 4.5 image prompt (English, optimized for banner generation)
2. Banner title in Russian and Turkmen
3. Banner description in Russian and Turkmen
"""

import json
import logging
from dataclasses import dataclass

import anthropic

from config import ANTHROPIC_API_KEY
from parser import ProductData

logger = logging.getLogger(__name__)

client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


@dataclass
class BannerContent:
    seedream_prompt: str
    title_ru: str
    title_tk: str
    description_ru: str
    description_tk: str


SYSTEM_PROMPT = """\
You are a creative director for Wabrum.com, Turkmenistan's leading online fashion \
marketplace. Your job is to generate banner content for the website.

You will receive product data (names, categories, prices) and a target banner format. \
Based on this, generate:

1. **seedream_prompt** — An image generation prompt for Seedream 4.5 (in English). \
The prompt should describe a stylish, professional e-commerce banner composition. \
The banner will use the actual product photos as reference images, so focus on \
describing the overall scene, composition, lighting, background, mood, and layout — \
NOT the products themselves. Keep the prompt under 400 words. \
Important: Do NOT include any text/typography in the prompt — text will be overlaid \
separately via the CMS. \
Think about seasonal relevance, current fashion trends, and attractive visual compositions.

2. **title_ru** — A short, catchy banner headline in Russian (max 6 words). \
Should be engaging and sales-oriented.

3. **title_tk** — The same headline translated to Turkmen (max 6 words).

4. **description_ru** — A short banner description/CTA in Russian (max 15 words). \
Should motivate the customer to click.

5. **description_tk** — The same description translated to Turkmen (max 15 words).

Respond ONLY with a valid JSON object, no markdown fences, no preamble:
{
  "seedream_prompt": "...",
  "title_ru": "...",
  "title_tk": "...",
  "description_ru": "...",
  "description_tk": "..."
}
"""


async def generate_banner_content(
    products: list[ProductData],
    banner_size_key: str,
    banner_ratio: str,
) -> BannerContent:
    """
    Call Claude API to generate banner prompt and texts
    based on product data and target banner format.
    """
    # Build product context
    products_info = []
    for i, p in enumerate(products, 1):
        info = f"Product {i}: {p.name}"
        if p.category:
            info += f" | Category: {p.category}"
        if p.price:
            info += f" | Price: {p.price}"
        if p.vendor:
            info += f" | Vendor: {p.vendor}"
        products_info.append(info)

    user_message = (
        f"Generate banner content for Wabrum.com.\n\n"
        f"Banner format: {banner_size_key} (aspect ratio {banner_ratio})\n"
        f"Number of products featured: {len(products)}\n\n"
        f"Products:\n" + "\n".join(products_info) + "\n\n"
        f"Create a visually appealing banner concept that showcases "
        f"{'this product' if len(products) == 1 else 'these products together'} "
        f"in an attractive composition suitable for a {banner_ratio} banner."
    )

    logger.info("Calling Claude API for banner content generation")

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text.strip()

    # Clean potential markdown fences
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude response as JSON: %s\nRaw: %s", e, raw_text)
        raise ValueError(f"Claude вернул некорректный JSON: {e}")

    return BannerContent(
        seedream_prompt=data["seedream_prompt"],
        title_ru=data["title_ru"],
        title_tk=data["title_tk"],
        description_ru=data["description_ru"],
        description_tk=data["description_tk"],
    )
