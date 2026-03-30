"""
Seedream 5.0 Lite API integration via BytePlus (official SDK).
Supports text-to-image with multiple reference images (up to 14).
"""

import base64
import logging

import aiohttp
from byteplussdkarkruntime import AsyncArk

from config import BYTEPLUS_API_KEY, BYTEPLUS_ENDPOINT
from parser import download_image

logger = logging.getLogger(__name__)

# Seedream model ID (from official BytePlus docs)
SEEDREAM_MODEL = "seedream-5-0-260128"


async def _image_url_to_base64(image_url: str) -> str:
    """Download an image and return its base64-encoded data URI string."""
    image_bytes = await download_image(image_url)
    return f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode('utf-8')}"


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
              Must satisfy: total pixels in [3,686,400 .. 10,404,496]

    Returns:
        Generated image as bytes
    """
    # Prepare reference images (max 14 per API docs)
    ref_urls = image_urls[:14]
    reference_images = []
    for url in ref_urls:
        try:
            b64_uri = await _image_url_to_base64(url)
            reference_images.append(b64_uri)
            logger.info("Downloaded reference image: %s", url[:80])
        except Exception as e:
            logger.warning("Failed to download reference image %s: %s", url[:80], e)

    # Build the prompt with composition instructions for multi-product banners
    if len(reference_images) > 1:
        enhanced_prompt = (
            f"Create a professional e-commerce banner compositing {len(reference_images)} "
            f"product items from the reference images into one cohesive scene. "
            f"{prompt}"
        )
    else:
        enhanced_prompt = prompt

    logger.info(
        "Calling Seedream API: model=%s, size=%s, refs=%d, prompt_len=%d",
        SEEDREAM_MODEL,
        size,
        len(reference_images),
        len(enhanced_prompt),
    )

    # Determine base URL: strip /images/generations suffix if present in BYTEPLUS_ENDPOINT
    base_url = BYTEPLUS_ENDPOINT
    for suffix in ("/images/generations", "/images/generations/"):
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
            break

    client = AsyncArk(
        base_url=base_url,
        api_key=BYTEPLUS_API_KEY,
    )

    try:
        kwargs = {
            "model": SEEDREAM_MODEL,
            "prompt": enhanced_prompt,
            "size": size,
            "response_format": "url",
            "watermark": False,
        }

        # Add reference images if available (as base64 data URIs)
        if reference_images:
            kwargs["image"] = reference_images

        result = await client.images.generate(**kwargs)

        # Extract image from SDK response
        if result.data and len(result.data) > 0:
            item = result.data[0]

            # Option 1: Image URL
            if item.url:
                logger.info("Downloading generated banner from URL")
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        item.url,
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp:
                        resp.raise_for_status()
                        return await resp.read()

            # Option 2: Base64 encoded
            if item.b64_json:
                logger.info("Decoding base64 banner image")
                return base64.b64decode(item.b64_json)

        raise RuntimeError("No image data in Seedream response")

    finally:
        await client.close()
