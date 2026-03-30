"""
Parser for Wabrum.com product pages (CS-Cart MultiVendor with UniTheme2).
Extracts the main product image URL, product name, category, price, and vendor.

Tested against real Wabrum.com HTML structure (March 2026).
"""

import re
import logging
from dataclasses import dataclass
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://wabrum.com"

# Zero-width characters that appear in CS-Cart price elements
ZWJ_CHARS = re.compile(r"[\u200d\u200b\u200c\u200e\u200f\ufeff]")


@dataclass
class ProductData:
    url: str
    name: str
    image_url: str
    category: str = ""
    price: str = ""
    vendor: str = ""


async def fetch_page(url: str) -> str:
    """Fetch HTML content of a product page."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            resp.raise_for_status()
            return await resp.text()


def parse_product_page(html: str, url: str) -> ProductData:
    """
    Parse a Wabrum.com (CS-Cart UniTheme2) product page.

    Verified selectors against real HTML:
    - Full-res image: <a class="cm-image-previewer"> href (best quality)
    - Fallback image: og:image meta tag
    - Product name: <h1> (og:title includes breadcrumb path)
    - Category: ty-breadcrumbs → 3rd <a> link (subcategory)
    - Price: #sec_discounted_price_XXXXX (contains zwj chars to strip)
    - Vendor: div.ut2-vendor-block__name > a
    """
    soup = BeautifulSoup(html, "html.parser")

    # --- Main image (full resolution) ---
    image_url = ""

    # Strategy 1: Full-res from previewer link (highest quality)
    previewer = soup.find("a", class_=re.compile(r"cm-image-previewer"))
    if previewer and previewer.get("href"):
        image_url = previewer["href"]

    # Strategy 2: Open Graph image
    if not image_url:
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

    # Strategy 3: Product image container
    if not image_url:
        img_container = soup.find("div", class_=re.compile(r"ty-product-img"))
        if img_container:
            img = img_container.find("img")
            if img:
                image_url = img.get("src", "")

    # Make URL absolute
    if image_url and not image_url.startswith("http"):
        image_url = urljoin(BASE_URL, image_url)

    # --- Product name ---
    name = ""
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(strip=True)

    if not name:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            parts = og_title["content"].split("::")
            name = parts[-1].strip() if parts else og_title["content"]

    # --- Category (from breadcrumbs) ---
    category = ""
    breadcrumbs = soup.find("div", class_=re.compile(r"ty-breadcrumbs"))
    if breadcrumbs:
        crumbs = breadcrumbs.find_all("a", class_="ty-breadcrumbs__a")
        # Structure: Главная / Женщинам / Рубашки и блузки / Brand / [Product]
        # Index 2 = subcategory (e.g., "Рубашки и блузки")
        if len(crumbs) >= 3:
            category = crumbs[2].get_text(strip=True)
        elif len(crumbs) >= 2:
            category = crumbs[-1].get_text(strip=True)

    # --- Price ---
    price = ""
    price_el = soup.find("span", id=re.compile(r"sec_discounted_price_\d+"))
    if price_el:
        raw_price = price_el.get_text(strip=True)
        price = ZWJ_CHARS.sub("", raw_price).strip()
        next_sib = price_el.find_next_sibling("span", class_="ty-price-num")
        if next_sib:
            currency = ZWJ_CHARS.sub("", next_sib.get_text(strip=True)).strip()
            if currency:
                price = f"{price} {currency}"

    # --- Vendor ---
    vendor = ""
    vendor_block = soup.find("div", class_=re.compile(r"ut2-vendor-block__name"))
    if vendor_block:
        vendor_link = vendor_block.find("a")
        if vendor_link:
            vendor = vendor_link.get_text(strip=True)

    if not vendor:
        vendor_el = soup.find("a", class_=re.compile(r"ty-company-title"))
        if vendor_el:
            vendor = vendor_el.get_text(strip=True)

    if not image_url:
        raise ValueError(f"Не удалось найти изображение товара на странице: {url}")

    return ProductData(
        url=url,
        name=name or "Товар",
        image_url=image_url,
        category=category,
        price=price,
        vendor=vendor,
    )


async def parse_product_url(url: str) -> ProductData:
    """Full pipeline: fetch + parse a product URL."""
    logger.info("Parsing product URL: %s", url)
    html = await fetch_page(url)
    product = parse_product_page(html, url)
    logger.info(
        "Parsed: name=%s, image=%s, category=%s, price=%s, vendor=%s",
        product.name,
        product.image_url[:80],
        product.category,
        product.price,
        product.vendor,
    )
    return product


async def download_image(image_url: str) -> bytes:
    """Download product image as bytes."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": BASE_URL,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(
            image_url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            resp.raise_for_status()
            return await resp.read()
