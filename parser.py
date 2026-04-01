"""Parser for Wabrum.com product pages (CS-Cart MultiVendor + UniTheme2)."""

import logging
import re
from dataclasses import dataclass

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://wabrum.com/",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}

UNICODE_JUNK = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]")


@dataclass
class ProductData:
    url: str
    name: str
    category: str
    price: str
    vendor: str
    image_url: str


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str | None:
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("Failed to fetch %s: HTTP %d", url, resp.status)
                return None
            return await resp.text()
    except Exception as e:
        logger.error("Error fetching %s: %s", url, e)
        return None


def parse_image_url(soup: BeautifulSoup) -> str | None:
    # Priority 1: cm-image-previewer link
    link = soup.select_one("a.cm-image-previewer")
    if link and link.get("href"):
        return link["href"]

    # Priority 2: og:image
    og = soup.select_one('meta[property="og:image"]')
    if og and og.get("content"):
        return og["content"]

    # Priority 3: product image div
    div = soup.select_one("div.ty-product-img")
    if div:
        img = div.select_one("img")
        if img and img.get("src"):
            return img["src"]

    return None


def parse_name(soup: BeautifulSoup) -> str:
    h1 = soup.select_one("h1")
    if h1:
        return h1.get_text(strip=True)

    og = soup.select_one('meta[property="og:title"]')
    if og and og.get("content"):
        parts = og["content"].split("::")
        return parts[-1].strip()

    return ""


def parse_category(soup: BeautifulSoup) -> str:
    breadcrumbs = soup.select("div.ty-breadcrumbs a.ty-breadcrumbs__a")
    if len(breadcrumbs) >= 3:
        return breadcrumbs[2].get_text(strip=True)
    if breadcrumbs:
        return breadcrumbs[-1].get_text(strip=True)
    return ""


def parse_price(soup: BeautifulSoup) -> str:
    price_span = soup.find("span", id=re.compile(r"sec_discounted_price_\d+"))
    if not price_span:
        price_span = soup.select_one("span.ty-price-num")

    if price_span:
        raw = price_span.get_text(strip=True)
        cleaned = UNICODE_JUNK.sub("", raw).strip()

        currency_span = price_span.find_next_sibling("span", class_="ty-price-num")
        if currency_span:
            currency = UNICODE_JUNK.sub("", currency_span.get_text(strip=True)).strip()
            return f"{cleaned} {currency}"

        if cleaned and not any(c.isalpha() for c in cleaned):
            return f"{cleaned} TMT"
        return cleaned

    return ""


def parse_vendor(soup: BeautifulSoup) -> str:
    # Priority 1
    block = soup.select_one("div.ut2-vendor-block__name")
    if block:
        a = block.select_one("a")
        if a:
            return a.get_text(strip=True)

    # Priority 2
    a = soup.select_one("a.ty-company-title")
    if a:
        return a.get_text(strip=True)

    return ""


async def parse_product(session: aiohttp.ClientSession, url: str) -> ProductData | None:
    html = await fetch_html(session, url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    image_url = parse_image_url(soup)
    if not image_url:
        logger.warning("No image found for %s", url)
        return None

    name = parse_name(soup)
    if not name:
        logger.warning("No name found for %s", url)
        return None

    return ProductData(
        url=url,
        name=name,
        category=parse_category(soup),
        price=parse_price(soup),
        vendor=parse_vendor(soup),
        image_url=image_url,
    )


async def download_image(session: aiohttp.ClientSession, url: str) -> bytes | None:
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                logger.warning("Failed to download image %s: HTTP %d", url, resp.status)
                return None
            return await resp.read()
    except Exception as e:
        logger.error("Error downloading image %s: %s", url, e)
        return None
