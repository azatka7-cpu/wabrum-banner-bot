"""
Seedream 5.0 Lite API integration via BytePlus.
Supports text-to-image with multiple reference images (up to 14).
"""

import asyncio
import base64
import logging
from io import BytesIO

import aiohttp

from config import BYTEPLUS_API_KEY, BYTEPLUS_ENDPOINT
from parser import download_image

logger = logging.getLogger(__name__)

# BytePlus task polling settings
POLL_INTERVAL = 3  # seconds
MAX_POLL_ATTEMPTS = 60  # max ~3 minutes

# Seedream model ID (from official BytePlus docs)
SEEDREAM_MODEL = "seedream-5-0-lite-260128"


async def _image_url_to_base64(image_url: str) -> str:
    """Download an image and return its base64-encoded string."""
    image_bytes = await download_image(image_url)
    return base64.b64encode(image_bytes).decode("utf-8")


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
    headers = {
        "Authorization": f"Bearer {BYTEPLUS_API_KEY}",
        "Content-Type": "application/json",
    }

    # Prepare reference images (max 14 per API docs)
    reference_images = []
    for url in image_urls[:14]:
        try:
            b64 = await _image_url_to_base64(url)
            reference_images.append(b64)
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

    # Build request payload (only documented parameters)
    payload = {
        "model": SEEDREAM_MODEL,
        "prompt": enhanced_prompt,
        "size": size,
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "watermark": False,
    }

    # Add reference images if available
    if reference_images:
        payload["image"] = [
            f"data:image/jpeg;base64,{img}" for img in reference_images
        ]

    logger.info(
        "Calling Seedream API: model=%s, size=%s, refs=%d, prompt_len=%d",
        SEEDREAM_MODEL,
        size,
        len(reference_images),
        len(enhanced_prompt),
    )

    async with aiohttp.ClientSession() as session:
        # Submit generation task
        async with session.post(
            BYTEPLUS_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            result = await resp.json()

            if resp.status != 200:
                error_msg = result.get("error", result.get("message", "Unknown error"))
                raise RuntimeError(f"Seedream API error ({resp.status}): {error_msg}")

        # Check if result is immediate or async
        if "data" in result and result["data"]:
            # Immediate result
            return await _extract_image(result, session)

        # Async task — poll for completion
        task_id = result.get("task_id") or result.get("id")
        if not task_id:
            raise RuntimeError(f"No task_id in Seedream response: {result}")

        logger.info("Seedream task submitted: %s, polling for result...", task_id)
        return await _poll_task(session, headers, task_id)


async def _poll_task(
    session: aiohttp.ClientSession,
    headers: dict,
    task_id: str,
) -> bytes:
    """Poll BytePlus for task completion."""
    status_url = BYTEPLUS_ENDPOINT.rsplit("/", 1)[0] + f"/tasks/{task_id}"

    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL)

        async with session.get(
            status_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            result = await resp.json()

        status = result.get("status", "").lower()
        logger.debug("Task %s status: %s (attempt %d)", task_id, status, attempt + 1)

        if status in ("completed", "succeeded", "success"):
            return await _extract_image(result, session)
        elif status in ("failed", "error", "cancelled"):
            error = result.get("error", result.get("message", "Unknown"))
            raise RuntimeError(f"Seedream task failed: {error}")

    raise TimeoutError(f"Seedream task {task_id} timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL}s")


async def _extract_image(result: dict, session: aiohttp.ClientSession) -> bytes:
    """Extract image bytes from API response (URL or base64)."""
    data = result.get("data", [])
    if isinstance(data, list) and data:
        item = data[0]
    elif isinstance(data, dict):
        item = data
    else:
        # Try alternative response structures
        images = result.get("images", result.get("output", {}).get("images", []))
        if images:
            item = images[0] if isinstance(images, list) else images
        else:
            raise RuntimeError(f"No image data in response: {list(result.keys())}")

    # Option 1: Image URL
    image_url = item.get("url") or item.get("image_url")
    if image_url:
        logger.info("Downloading generated banner from URL")
        async with session.get(
            image_url,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            resp.raise_for_status()
            return await resp.read()

    # Option 2: Base64 encoded
    b64_data = item.get("b64_json") or item.get("base64") or item.get("data")
    if b64_data:
        logger.info("Decoding base64 banner image")
        return base64.b64decode(b64_data)

    raise RuntimeError(f"Could not extract image from response item: {list(item.keys())}")
