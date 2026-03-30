"""
Seedream 5.0 Lite API integration via BytePlus.
Supports text-to-image with multiple reference images (up to 14).
"""

import base64
import logging

import aiohttp

from config import BYTEPLUS_API_KEY

logger = logging.getLogger(__name__)

# Seedream model ID (from official BytePlus docs)
SEEDREAM_MODEL = "seedream-5-0-260128"

# Official BytePlus API endpoint
API_URL = "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations"


async def generate_banner(
    prompt: str,
    image_urls: list[str],
    size: str = "2560x1440",
) -> bytes:
    """
    Generate a banner using Seedream 5.0 Lite via BytePlus API.

    Args:
        prompt: The image generation prompt
        image_urls: List of reference image URLs (product photos, max 14)
        size: Target pixel size (e.g., "2560x1440", "2048x2048")
              Must satisfy: total pixels in [3,686,400 .. 16,777,216]

    Returns:
        Generated image as bytes
    """
    ref_urls = image_urls[:14]

    # Build the prompt with composition instructions for multi-product banners
    if len(ref_urls) > 1:
        enhanced_prompt = (
            f"Create a professional e-commerce banner compositing {len(ref_urls)} "
            f"product items from the reference images into one cohesive scene. "
            f"{prompt}"
        )
    else:
        enhanced_prompt = prompt

    # Build request payload — matches official curl example exactly
    payload = {
        "model": SEEDREAM_MODEL,
        "prompt": enhanced_prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "disabled",
    }

    # Add reference images as direct URLs (API accepts accessible URLs)
    if len(ref_urls) == 1:
        payload["image"] = ref_urls[0]
    elif len(ref_urls) > 1:
        payload["image"] = ref_urls

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BYTEPLUS_API_KEY}",
    }

    logger.info(
        "Calling Seedream API: url=%s, model=%s, size=%s, refs=%d, prompt_len=%d",
        API_URL,
        SEEDREAM_MODEL,
        size,
        len(ref_urls),
        len(enhanced_prompt),
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            API_URL,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            result = await resp.json()

            if resp.status != 200:
                error_msg = result.get("error", result.get("message", "Unknown error"))
                raise RuntimeError(f"Seedream API error ({resp.status}): {error_msg}")

        # Extract image from response
        data = result.get("data", [])
        if not data:
            raise RuntimeError(f"No image data in Seedream response: {result}")

        item = data[0]

        # Check for per-image error
        if "error" in item and item["error"]:
            raise RuntimeError(f"Seedream image generation failed: {item['error']}")

        # Option 1: Image URL
        image_url = item.get("url")
        if image_url:
            logger.info("Downloading generated banner from URL")
            async with session.get(
                image_url,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as img_resp:
                img_resp.raise_for_status()
                return await img_resp.read()

        # Option 2: Base64 encoded
        b64_data = item.get("b64_json")
        if b64_data:
            logger.info("Decoding base64 banner image")
            return base64.b64decode(b64_data)

        raise RuntimeError(f"No image URL or b64_json in response item: {item}")
