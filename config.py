"""Configuration: environment variables, banner sizes, constants."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
BYTEPLUS_API_KEY: str = os.getenv("BYTEPLUS_API_KEY", "")
BYTEPLUS_ENDPOINT: str = os.getenv(
    "BYTEPLUS_ENDPOINT",
    "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations",
)
ALLOWED_USER_IDS: list[int] = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip().isdigit()
]

MAX_PRODUCTS = 10
WABRUM_URL_PATTERN = r"https?://(?:www\.)?wabrum\.com/\S+"


@dataclass(frozen=True)
class BannerSize:
    key: str
    label: str
    ratio: str
    width: int
    height: int
    description: str


BANNER_SIZES: dict[str, BannerSize] = {
    "main_desktop": BannerSize(
        key="main_desktop",
        label="\U0001f5a5 \u0413\u043b\u0430\u0432\u043d\u044b\u0439 \u0441\u043b\u0430\u0439\u0434\u0435\u0440 (\u0434\u0435\u0441\u043a\u0442\u043e\u043f)",
        ratio="21:9",
        width=3136,
        height=1344,
        description="\u0428\u0438\u0440\u043e\u043a\u043e\u0444\u043e\u0440\u043c\u0430\u0442\u043d\u044b\u0439 \u0431\u0430\u043d\u043d\u0435\u0440 \u0434\u043b\u044f \u0433\u043b\u0430\u0432\u043d\u043e\u0439",
    ),
    "main_mobile": BannerSize(
        key="main_mobile",
        label="\U0001f4f1 \u0413\u043b\u0430\u0432\u043d\u044b\u0439 \u0441\u043b\u0430\u0439\u0434\u0435\u0440 (\u043c\u043e\u0431\u0430\u0439\u043b)",
        ratio="4:3",
        width=2304,
        height=1728,
        description="\u041a\u043e\u043c\u043f\u0430\u043a\u0442\u043d\u044b\u0439 \u0431\u0430\u043d\u043d\u0435\u0440 \u0434\u043b\u044f \u043c\u043e\u0431\u0438\u043b\u044c\u043d\u043e\u0439 \u0432\u0435\u0440\u0441\u0438\u0438",
    ),
    "category_desktop": BannerSize(
        key="category_desktop",
        label="\U0001f3f7 \u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f (\u0434\u0435\u0441\u043a\u0442\u043e\u043f)",
        ratio="16:9",
        width=2848,
        height=1600,
        description="\u0411\u0430\u043d\u043d\u0435\u0440 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438",
    ),
    "category_mobile": BannerSize(
        key="category_mobile",
        label="\U0001f3f7 \u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f (\u043c\u043e\u0431\u0430\u0439\u043b)",
        ratio="4:3",
        width=2304,
        height=1728,
        description="\u0411\u0430\u043d\u043d\u0435\u0440 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u0438 \u0434\u043b\u044f \u043c\u043e\u0431\u0438\u043b\u044c\u043d\u044b\u0445",
    ),
    "sidebar": BannerSize(
        key="sidebar",
        label="\U0001f4d0 \u0411\u043e\u043a\u043e\u0432\u043e\u0439 \u0431\u0430\u043d\u043d\u0435\u0440",
        ratio="3:4",
        width=1728,
        height=2304,
        description="\u0412\u0435\u0440\u0442\u0438\u043a\u0430\u043b\u044c\u043d\u044b\u0439 \u0431\u0430\u043d\u043d\u0435\u0440 \u0434\u043b\u044f \u0441\u0430\u0439\u0434\u0431\u0430\u0440\u0430",
    ),
    "promo_square": BannerSize(
        key="promo_square",
        label="\u2b1c \u041f\u0440\u043e\u043c\u043e (\u043a\u0432\u0430\u0434\u0440\u0430\u0442)",
        ratio="1:1",
        width=2048,
        height=2048,
        description="\u0423\u043d\u0438\u0432\u0435\u0440\u0441\u0430\u043b\u044c\u043d\u044b\u0439 \u043a\u0432\u0430\u0434\u0440\u0430\u0442\u043d\u044b\u0439 \u0431\u0430\u043d\u043d\u0435\u0440",
    ),
    "stories": BannerSize(
        key="stories",
        label="\U0001f4f2 Stories / \u0432\u0435\u0440\u0442\u0438\u043a\u0430\u043b\u044c\u043d\u044b\u0439",
        ratio="9:16",
        width=1600,
        height=2848,
        description="\u0414\u043b\u044f Instagram Stories \u0438 \u043c\u043e\u0431\u0438\u043b\u044c\u043d\u044b\u0445",
    ),
}


def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS
