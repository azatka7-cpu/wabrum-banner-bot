"""Wabrum Banner Bot: Telegram bot for e-commerce banner generation."""

import asyncio
import io
import logging
import re
from html import escape

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import BANNER_SIZES, MAX_PRODUCTS, TELEGRAM_BOT_TOKEN, WABRUM_URL_PATTERN, is_authorized
from parser import ProductData, download_image, parse_product
from prompt_generator import generate_banner_content
from seedream import generate_banner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

router = Router()


class BannerStates(StatesGroup):
    collecting_urls = State()
    selecting_size = State()
    generating = State()


# --- Keyboards ---

def urls_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="\u2705 \u0413\u043e\u0442\u043e\u0432\u043e", callback_data="urls_done"),
            InlineKeyboardButton(text="\U0001f5d1 \u041e\u0447\u0438\u0441\u0442\u0438\u0442\u044c \u0432\u0441\u0451", callback_data="urls_clear"),
        ],
        [InlineKeyboardButton(text="\u274c \u041e\u0442\u043c\u0435\u043d\u0430", callback_data="cancel")],
    ])


def sizes_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, size in BANNER_SIZES.items():
        buttons.append([InlineKeyboardButton(
            text=f"{size.label} ({size.ratio})",
            callback_data=f"size:{key}",
        )])
    buttons.append([InlineKeyboardButton(text="\u274c \u041e\u0442\u043c\u0435\u043d\u0430", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def regenerate_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, size in BANNER_SIZES.items():
        buttons.append([InlineKeyboardButton(
            text=f"{size.label} ({size.ratio})",
            callback_data=f"regen:{key}",
        )])
    buttons.append([InlineKeyboardButton(
        text="\U0001f195 \u041d\u043e\u0432\u044b\u0439 \u0431\u0430\u043d\u043d\u0435\u0440",
        callback_data="new_banner",
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Authorization check ---

def check_auth(user_id: int) -> bool:
    if not is_authorized(user_id):
        logger.warning("Unauthorized access attempt: user_id=%d", user_id)
        return False
    return True


# --- Commands ---

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not check_auth(message.from_user.id):
        await message.answer("\u26d4 \u0423 \u0432\u0430\u0441 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u044d\u0442\u043e\u043c\u0443 \u0431\u043e\u0442\u0443.")
        return

    await message.answer(
        "\U0001f44b <b>\u0414\u043e\u0431\u0440\u043e \u043f\u043e\u0436\u0430\u043b\u043e\u0432\u0430\u0442\u044c \u0432 Wabrum Banner Bot!</b>\n\n"
        "\u042f \u043f\u043e\u043c\u043e\u0433\u0443 \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u043f\u0440\u043e\u0444\u0435\u0441\u0441\u0438\u043e\u043d\u0430\u043b\u044c\u043d\u044b\u0435 \u0431\u0430\u043d\u043d\u0435\u0440\u044b \u0434\u043b\u044f Wabrum.com \u043d\u0430 \u043e\u0441\u043d\u043e\u0432\u0435 \u0440\u0435\u0430\u043b\u044c\u043d\u044b\u0445 \u0442\u043e\u0432\u0430\u0440\u043e\u0432.\n\n"
        "<b>\u041a\u043e\u043c\u0430\u043d\u0434\u044b:</b>\n"
        "/banner \u2014 \u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043d\u043e\u0432\u044b\u0439 \u0431\u0430\u043d\u043d\u0435\u0440\n"
        "/sizes \u2014 \u041f\u043e\u043a\u0430\u0437\u0430\u0442\u044c \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0440\u0430\u0437\u043c\u0435\u0440\u044b\n"
        "/cancel \u2014 \u041e\u0442\u043c\u0435\u043d\u0438\u0442\u044c \u0442\u0435\u043a\u0443\u0449\u0443\u044e \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u044e\n"
        "/help \u2014 \u041f\u043e\u0434\u0440\u043e\u0431\u043d\u0430\u044f \u0441\u043f\u0440\u0430\u0432\u043a\u0430",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if not check_auth(message.from_user.id):
        await message.answer("\u26d4 \u0423 \u0432\u0430\u0441 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u044d\u0442\u043e\u043c\u0443 \u0431\u043e\u0442\u0443.")
        return

    await message.answer(
        "\U0001f4d6 <b>\u041a\u0430\u043a \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u0431\u043e\u0442:</b>\n\n"
        "1. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 /banner\n"
        "2. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0438 \u043d\u0430 \u0442\u043e\u0432\u0430\u0440\u044b \u0441 wabrum.com (\u043e\u0442 1 \u0434\u043e 10)\n"
        "3. \u041d\u0430\u0436\u043c\u0438\u0442\u0435 \"\u0413\u043e\u0442\u043e\u0432\u043e \u2705\"\n"
        "4. \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0440\u0430\u0437\u043c\u0435\u0440 \u0431\u0430\u043d\u043d\u0435\u0440\u0430\n"
        "5. \u0414\u043e\u0436\u0434\u0438\u0442\u0435\u0441\u044c \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438\n\n"
        "\u0421\u0441\u044b\u043b\u043a\u0438 \u043c\u043e\u0436\u043d\u043e \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0442\u044c \u043f\u043e \u043e\u0434\u043d\u043e\u0439 \u0438\u043b\u0438 \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0432 \u043e\u0434\u043d\u043e\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0438.\n"
        "\u041f\u043e\u0441\u043b\u0435 \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438 \u043c\u043e\u0436\u043d\u043e \u0432\u044b\u0431\u0440\u0430\u0442\u044c \u0434\u0440\u0443\u0433\u043e\u0439 \u0440\u0430\u0437\u043c\u0435\u0440 \u0431\u0435\u0437 \u043f\u043e\u0432\u0442\u043e\u0440\u043d\u043e\u0433\u043e \u043f\u0430\u0440\u0441\u0438\u043d\u0433\u0430.",
        parse_mode="HTML",
    )


@router.message(Command("sizes"))
async def cmd_sizes(message: Message) -> None:
    if not check_auth(message.from_user.id):
        await message.answer("\u26d4 \u0423 \u0432\u0430\u0441 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u044d\u0442\u043e\u043c\u0443 \u0431\u043e\u0442\u0443.")
        return

    lines = ["\U0001f4d0 <b>\u0414\u043e\u0441\u0442\u0443\u043f\u043d\u044b\u0435 \u0440\u0430\u0437\u043c\u0435\u0440\u044b \u0431\u0430\u043d\u043d\u0435\u0440\u043e\u0432:</b>\n"]
    for size in BANNER_SIZES.values():
        lines.append(
            f"{size.label}\n"
            f"  \u0421\u043e\u043e\u0442\u043d\u043e\u0448\u0435\u043d\u0438\u0435: {size.ratio} | {size.width}x{size.height}px\n"
            f"  {size.description}\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        await message.answer("\u041d\u0435\u0442 \u0430\u043a\u0442\u0438\u0432\u043d\u043e\u0439 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438 \u0434\u043b\u044f \u043e\u0442\u043c\u0435\u043d\u044b.")
        return
    await state.clear()
    await message.answer("\u274c \u041e\u043f\u0435\u0440\u0430\u0446\u0438\u044f \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430.")


@router.message(Command("banner"))
async def cmd_banner(message: Message, state: FSMContext) -> None:
    if not check_auth(message.from_user.id):
        await message.answer("\u26d4 \u0423 \u0432\u0430\u0441 \u043d\u0435\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u0430 \u043a \u044d\u0442\u043e\u043c\u0443 \u0431\u043e\u0442\u0443.")
        return

    await state.clear()
    await state.set_state(BannerStates.collecting_urls)
    await state.update_data(urls=[])

    await message.answer(
        "\U0001f3a8 <b>\u0421\u043e\u0437\u0434\u0430\u043d\u0438\u0435 \u0431\u0430\u043d\u043d\u0435\u0440\u0430</b>\n\n"
        "\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0438 \u043d\u0430 \u0442\u043e\u0432\u0430\u0440\u044b \u0441 wabrum.com\n"
        f"\u041c\u0430\u043a\u0441\u0438\u043c\u0443\u043c: {MAX_PRODUCTS} \u0442\u043e\u0432\u0430\u0440\u043e\u0432\n\n"
        "\u041c\u043e\u0436\u043d\u043e \u043e\u0442\u043f\u0440\u0430\u0432\u043b\u044f\u0442\u044c \u043f\u043e \u043e\u0434\u043d\u043e\u0439 \u0438\u043b\u0438 \u043d\u0435\u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0441\u0441\u044b\u043b\u043e\u043a \u0432 \u043e\u0434\u043d\u043e\u043c \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0438.",
        parse_mode="HTML",
        reply_markup=urls_keyboard(),
    )


# --- URL collection ---

@router.message(BannerStates.collecting_urls)
async def collect_urls(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    urls: list[str] = data.get("urls", [])

    found = re.findall(WABRUM_URL_PATTERN, message.text or "")
    if not found:
        await message.answer(
            "\u26a0 \u041d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e \u0441\u0441\u044b\u043b\u043e\u043a \u043d\u0430 wabrum.com.\n"
            "\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0443 \u0432\u0438\u0434\u0430: https://wabrum.com/...",
            reply_markup=urls_keyboard(),
        )
        return

    added = 0
    for url in found:
        if url not in urls and len(urls) < MAX_PRODUCTS:
            urls.append(url)
            added += 1

    await state.update_data(urls=urls)

    status = f"\u2705 \u0414\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e: {added} | \u0412\u0441\u0435\u0433\u043e: {len(urls)}/{MAX_PRODUCTS}"
    if len(urls) >= MAX_PRODUCTS:
        status += "\n\u26a0 \u0414\u043e\u0441\u0442\u0438\u0433\u043d\u0443\u0442 \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c \u0442\u043e\u0432\u0430\u0440\u043e\u0432!"

    await message.answer(status, reply_markup=urls_keyboard())


# --- Callbacks ---

@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("\u274c \u041e\u043f\u0435\u0440\u0430\u0446\u0438\u044f \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430.")
    await callback.answer()


@router.callback_query(F.data == "urls_clear")
async def cb_urls_clear(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(urls=[])
    await callback.message.edit_text(
        "\U0001f5d1 \u0421\u043f\u0438\u0441\u043e\u043a \u043e\u0447\u0438\u0449\u0435\u043d. \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0438 \u043d\u0430 \u0442\u043e\u0432\u0430\u0440\u044b.",
        reply_markup=urls_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "urls_done")
async def cb_urls_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    urls: list[str] = data.get("urls", [])

    if not urls:
        await callback.answer("\u041d\u0435\u0442 \u0434\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043d\u044b\u0445 \u0441\u0441\u044b\u043b\u043e\u043a!", show_alert=True)
        return

    await state.set_state(BannerStates.selecting_size)

    url_list = "\n".join(f"{i}. {url}" for i, url in enumerate(urls, 1))
    await callback.message.edit_text(
        f"\U0001f4cb <b>\u0422\u043e\u0432\u0430\u0440\u044b ({len(urls)}):</b>\n{url_list}\n\n"
        "\U0001f4d0 <b>\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u0440\u0430\u0437\u043c\u0435\u0440 \u0431\u0430\u043d\u043d\u0435\u0440\u0430:</b>",
        parse_mode="HTML",
        reply_markup=sizes_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("size:"))
async def cb_select_size(callback: CallbackQuery, state: FSMContext) -> None:
    size_key = callback.data.split(":", 1)[1]
    if size_key not in BANNER_SIZES:
        await callback.answer("\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u044b\u0439 \u0440\u0430\u0437\u043c\u0435\u0440!", show_alert=True)
        return

    data = await state.get_data()
    urls = data.get("urls", [])
    if not urls:
        await callback.answer("\u041d\u0435\u0442 \u0442\u043e\u0432\u0430\u0440\u043e\u0432!", show_alert=True)
        return

    await state.set_state(BannerStates.generating)
    await callback.answer()

    await _run_generation(callback.message, state, urls, size_key)


@router.callback_query(F.data.startswith("regen:"))
async def cb_regenerate(callback: CallbackQuery, state: FSMContext) -> None:
    size_key = callback.data.split(":", 1)[1]
    if size_key not in BANNER_SIZES:
        await callback.answer("\u041d\u0435\u0438\u0437\u0432\u0435\u0441\u0442\u043d\u044b\u0439 \u0440\u0430\u0437\u043c\u0435\u0440!", show_alert=True)
        return

    data = await state.get_data()
    products_data = data.get("products_data")
    urls = data.get("urls", [])

    if not products_data and not urls:
        await callback.answer("\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f \u0440\u0435\u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438!", show_alert=True)
        return

    await state.set_state(BannerStates.generating)
    await callback.answer()

    await _run_generation(
        callback.message,
        state,
        urls,
        size_key,
        cached_products=products_data,
    )


@router.callback_query(F.data == "new_banner")
async def cb_new_banner(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BannerStates.collecting_urls)
    await state.update_data(urls=[])

    await callback.message.edit_text(
        "\U0001f3a8 <b>\u041d\u043e\u0432\u044b\u0439 \u0431\u0430\u043d\u043d\u0435\u0440</b>\n\n"
        "\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u0441\u044b\u043b\u043a\u0438 \u043d\u0430 \u0442\u043e\u0432\u0430\u0440\u044b \u0441 wabrum.com\n"
        f"\u041c\u0430\u043a\u0441\u0438\u043c\u0443\u043c: {MAX_PRODUCTS} \u0442\u043e\u0432\u0430\u0440\u043e\u0432",
        parse_mode="HTML",
        reply_markup=urls_keyboard(),
    )
    await callback.answer()


# --- Generation pipeline ---

async def _run_generation(
    message: Message,
    state: FSMContext,
    urls: list[str],
    size_key: str,
    cached_products: list[dict] | None = None,
) -> None:
    banner_size = BANNER_SIZES[size_key]

    status_msg = await message.answer(
        f"\u23f3 <b>\u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0431\u0430\u043d\u043d\u0435\u0440\u0430...</b>\n"
        f"\u0420\u0430\u0437\u043c\u0435\u0440: {banner_size.label} ({banner_size.ratio})\n"
        f"\u0422\u043e\u0432\u0430\u0440\u043e\u0432: {len(urls)}\n\n"
        f"\u0428\u0430\u0433 1/3: \u041f\u0430\u0440\u0441\u0438\u043d\u0433 \u0442\u043e\u0432\u0430\u0440\u043e\u0432...",
        parse_mode="HTML",
    )

    try:
        # Step 1: Parse products (or use cache)
        if cached_products:
            products = [ProductData(**p) for p in cached_products]
        else:
            async with aiohttp.ClientSession() as session:
                tasks = [parse_product(session, url) for url in urls]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            products = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error("Error parsing %s: %s", urls[i], result)
                elif result is not None:
                    products.append(result)

            if not products:
                await status_msg.edit_text("\u274c \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043f\u0430\u0440\u0441\u0438\u0442\u044c \u043d\u0438 \u043e\u0434\u0438\u043d \u0442\u043e\u0432\u0430\u0440. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0434\u0440\u0443\u0433\u0438\u0435 \u0441\u0441\u044b\u043b\u043a\u0438.")
                await state.clear()
                return

            # Cache products for regeneration
            await state.update_data(
                products_data=[
                    {
                        "url": p.url,
                        "name": p.name,
                        "category": p.category,
                        "price": p.price,
                        "vendor": p.vendor,
                        "image_url": p.image_url,
                    }
                    for p in products
                ]
            )

        failed_count = len(urls) - len(products) if not cached_products else 0
        step1_note = ""
        if failed_count > 0:
            step1_note = f" (\u26a0 {failed_count} \u043d\u0435 \u0441\u043f\u0430\u0440\u0441\u0438\u043b\u043e\u0441\u044c)"

        await status_msg.edit_text(
            f"\u23f3 <b>\u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0431\u0430\u043d\u043d\u0435\u0440\u0430...</b>\n"
            f"\u0420\u0430\u0437\u043c\u0435\u0440: {banner_size.label} ({banner_size.ratio})\n"
            f"\u0422\u043e\u0432\u0430\u0440\u043e\u0432: {len(products)}\n\n"
            f"\u2705 \u0428\u0430\u0433 1/3: \u0422\u043e\u0432\u0430\u0440\u044b \u0441\u043f\u0430\u0440\u0441\u0435\u043d\u044b{step1_note}\n"
            f"\u0428\u0430\u0433 2/3: \u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u043f\u0440\u043e\u043c\u043f\u0442\u0430 \u0438 \u0442\u0435\u043a\u0441\u0442\u043e\u0432 (Claude)...",
            parse_mode="HTML",
        )

        # Step 2: Generate prompt and texts via Claude
        content = await generate_banner_content(products, banner_size)

        await status_msg.edit_text(
            f"\u23f3 <b>\u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0431\u0430\u043d\u043d\u0435\u0440\u0430...</b>\n"
            f"\u0420\u0430\u0437\u043c\u0435\u0440: {banner_size.label} ({banner_size.ratio})\n"
            f"\u0422\u043e\u0432\u0430\u0440\u043e\u0432: {len(products)}\n\n"
            f"\u2705 \u0428\u0430\u0433 1/3: \u0422\u043e\u0432\u0430\u0440\u044b \u0441\u043f\u0430\u0440\u0441\u0435\u043d\u044b{step1_note}\n"
            f"\u2705 \u0428\u0430\u0433 2/3: \u041f\u0440\u043e\u043c\u043f\u0442 \u0438 \u0442\u0435\u043a\u0441\u0442\u044b \u0433\u043e\u0442\u043e\u0432\u044b\n"
            f"\u0428\u0430\u0433 3/3: \u0413\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u044f \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u044f (Seedream 5.0)...",
            parse_mode="HTML",
        )

        # Step 3: Download product images and generate banner
        async with aiohttp.ClientSession() as session:
            img_tasks = [download_image(session, p.image_url) for p in products]
            img_results = await asyncio.gather(*img_tasks, return_exceptions=True)

        product_images = []
        for result in img_results:
            if isinstance(result, bytes):
                product_images.append(result)

        if not product_images:
            await status_msg.edit_text("\u274c \u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043a\u0430\u0447\u0430\u0442\u044c \u0444\u043e\u0442\u043e \u0442\u043e\u0432\u0430\u0440\u043e\u0432.")
            await state.clear()
            return

        banner_bytes = await generate_banner(
            content["seedream_prompt"],
            banner_size,
            product_images,
        )

        # Delete status message
        try:
            await status_msg.delete()
        except Exception:
            pass

        # Send result
        title_ru = escape(content["title_ru"])
        title_tk = escape(content["title_tk"])
        desc_ru = escape(content["description_ru"])
        desc_tk = escape(content["description_tk"])

        caption = (
            f"\U0001f5bc <b>\u0411\u0430\u043d\u043d\u0435\u0440 \u0433\u043e\u0442\u043e\u0432!</b>\n"
            f"\u0420\u0430\u0437\u043c\u0435\u0440: {banner_size.label}\n\n"
            f"\U0001f4dd Title (RU):\n<code>{title_ru}</code>\n\n"
            f"\U0001f4dd Title (TK):\n<code>{title_tk}</code>\n\n"
            f"\U0001f4c4 Description (RU):\n<code>{desc_ru}</code>\n\n"
            f"\U0001f4c4 Description (TK):\n<code>{desc_tk}</code>"
        )

        await message.answer_photo(
            photo=BufferedInputFile(banner_bytes, filename="banner.jpg"),
            caption=caption,
            parse_mode="HTML",
        )

        # Debug message with prompt
        seedream_prompt_escaped = escape(content["seedream_prompt"])
        product_links = "\n".join(f"- {escape(p.url)}" for p in products)

        await message.answer(
            f"\U0001f50d <b>Seedream \u043f\u0440\u043e\u043c\u043f\u0442:</b>\n<pre>{seedream_prompt_escaped}</pre>\n\n"
            f"\U0001f517 <b>\u0422\u043e\u0432\u0430\u0440\u044b:</b>\n{product_links}",
            parse_mode="HTML",
        )

        # Regeneration keyboard
        await message.answer(
            "\U0001f504 <b>\u0421\u0433\u0435\u043d\u0435\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u0432 \u0434\u0440\u0443\u0433\u043e\u043c \u0440\u0430\u0437\u043c\u0435\u0440\u0435:</b>",
            parse_mode="HTML",
            reply_markup=regenerate_keyboard(),
        )

        await state.set_state(None)

    except Exception as e:
        logger.exception("Generation failed")
        try:
            await status_msg.edit_text(
                f"\u274c <b>\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438:</b>\n{escape(str(e))}",
                parse_mode="HTML",
            )
        except Exception:
            await message.answer(
                f"\u274c <b>\u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u0433\u0435\u043d\u0435\u0440\u0430\u0446\u0438\u0438:</b>\n{escape(str(e))}",
                parse_mode="HTML",
            )
        await state.clear()


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Starting Wabrum Banner Bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
