"""Seedream 5.0 API integration via BytePlus."""

import asyncio
import base64
import logging

import aiohttp

from config import BYTEPLUS_API_KEY, BYTEPLUS_ENDPOINT, BannerSize

logger = logging.getLogger(__name__)

SEEDREAM_MODEL = "seedream-5-0-260128"
POLL_INTERVAL = 3
MAX_POLL_ATTEMPTS = 60


def _encode_image_base64(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def _build_prompt(original_prompt: str, num_images: int) -> str:
    if num_images > 1:
        return (
            f"Create a professional e-commerce banner compositing {num_images} "
            f"product items from the reference images into one cohesive scene. "
            f"{original_prompt}"
        )
    return original_prompt


async def generate_banner(
    prompt: str,
    banner_size: BannerSize,
    product_images: list[bytes],
) -> bytes:
    final_prompt = _build_prompt(prompt, len(product_images))

    payload: dict = {
        "model": SEEDREAM_MODEL,
        "prompt": final_prompt,
        "size": f"{banner_size.width}x{banner_size.height}",
        "response_format": "b64_json",
        "watermark": False,
        "sequential_image_generation": "disabled",
    }

    if product_images:
        if len(product_images) == 1:
            payload["image"] = _encode_image_base64(product_images[0])
        else:
            payload["image"] = [_encode_image_base64(img) for img in product_images]

    headers = {
        "Authorization": f"Bearer {BYTEPLUS_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info(
        "Sending Seedream request: size=%s, images=%d",
        f"{banner_size.width}x{banner_size.height}",
        len(product_images),
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            BYTEPLUS_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=300),
        ) as resp:
            result = await resp.json()

        if "error" in result and result["error"]:
            err = result["error"]
            raise RuntimeError(f"Seedream API error: {err.get('code')} - {err.get('message')}")

        # Synchronous response with data
        if "data" in result and result["data"]:
            return _extract_image(result["data"][0], session)

        # Async response with task_id — poll for result
        task_id = result.get("task_id")
        if task_id:
            return await _poll_task(session, headers, task_id)

        raise RuntimeError(f"Unexpected Seedream response: {str(result)[:500]}")


async def _extract_image(data_item: dict, session: aiohttp.ClientSession | None = None) -> bytes:
    if "error" in data_item:
        err = data_item["error"]
        raise RuntimeError(f"Seedream image error: {err.get('code')} - {err.get('message')}")

    if "b64_json" in data_item and data_item["b64_json"]:
        return base64.b64decode(data_item["b64_json"])

    if "url" in data_item and data_item["url"]:
        if session is None:
            async with aiohttp.ClientSession() as s:
                async with s.get(data_item["url"], timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    return await resp.read()
        async with session.get(data_item["url"], timeout=aiohttp.ClientTimeout(total=60)) as resp:
            return await resp.read()

    raise RuntimeError("Seedream response contains no image data")


async def _poll_task(
    session: aiohttp.ClientSession,
    headers: dict,
    task_id: str,
) -> bytes:
    logger.info("Polling Seedream task %s", task_id)

    for attempt in range(MAX_POLL_ATTEMPTS):
        await asyncio.sleep(POLL_INTERVAL)

        async with session.get(
            f"{BYTEPLUS_ENDPOINT}/{task_id}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            result = await resp.json()

        if "error" in result and result["error"]:
            err = result["error"]
            raise RuntimeError(f"Seedream poll error: {err.get('code')} - {err.get('message')}")

        if "data" in result and result["data"]:
            return await _extract_image(result["data"][0], session)

        logger.debug("Poll attempt %d/%d for task %s", attempt + 1, MAX_POLL_ATTEMPTS, task_id)

    raise RuntimeError(f"Seedream generation timed out after {MAX_POLL_ATTEMPTS * POLL_INTERVAL}s")
