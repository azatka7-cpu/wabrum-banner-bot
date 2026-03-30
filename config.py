import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# BytePlus Seedream
BYTEPLUS_API_KEY = os.getenv("BYTEPLUS_API_KEY")
BYTEPLUS_ENDPOINT = os.getenv(
    "BYTEPLUS_ENDPOINT",
    "https://ark.ap-southeast.bytepluses.com/api/v3/images/generations",
)

# Access control
ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
]

# Banner size presets
# IMPORTANT: Pixel sizes must satisfy Seedream 5.0 Lite API requirements:
#   - Total pixels (W×H) in range [3,686,400 .. 10,404,496]
#   - Aspect ratio (W/H) in range [1/16 .. 16]
# Values below are taken from the official API recommended 2K sizes.
BANNER_SIZES = {
    "main_desktop": {
        "label": "🖥 Главный слайдер (десктоп)",
        "ratio": "21:9",
        "size": "3136x1344",
        "description": "Широкоформатный баннер для главной",
    },
    "main_mobile": {
        "label": "📱 Главный слайдер (мобайл)",
        "ratio": "4:3",
        "size": "2304x1728",
        "description": "Компактный баннер для мобильной версии",
    },
    "category_desktop": {
        "label": "🏷 Категория (десктоп)",
        "ratio": "16:9",
        "size": "2848x1600",
        "description": "Баннер страницы категории",
    },
    "category_mobile": {
        "label": "🏷 Категория (мобайл)",
        "ratio": "4:3",
        "size": "2304x1728",
        "description": "Баннер категории для мобильных",
    },
    "sidebar": {
        "label": "📐 Боковой баннер",
        "ratio": "3:4",
        "size": "1728x2304",
        "description": "Вертикальный баннер для сайдбара",
    },
    "promo_square": {
        "label": "⬜ Промо (квадрат)",
        "ratio": "1:1",
        "size": "2048x2048",
        "description": "Универсальный квадратный баннер",
    },
    "stories": {
        "label": "📲 Stories / вертикальный",
        "ratio": "9:16",
        "size": "1600x2848",
        "description": "Для Instagram Stories и мобильных баннеров",
    },
}

# Max number of product URLs per banner
MAX_PRODUCTS_PER_BANNER = 10
