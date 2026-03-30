"""
Wabrum Banner Bot — Telegram bot for automated banner generation.

Flow:
1. User sends /banner
2. User sends one or more product URLs (one per message, or multiple separated by newlines)
3. User presses "Готово ✅" when all URLs are added
4. User selects banner size from inline keyboard
5. Bot parses products, generates prompt via Claude, generates banner via Seedream
6. Bot sends back: banner image + titles + descriptions in RU/TK
"""

import asyncio
import logging
import re
from io import BytesIO

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from config import (
    ALLOWED_USER_IDS,
    BANNER_SIZES,
    MAX_PRODUCTS_PER_BANNER,
    TELEGRAM_BOT_TOKEN,
)
from parser import ProductData, parse_product_url
from prompt_generator import generate_banner_content
from seedream import generate_banner

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Bot setup
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# URL pattern for wabrum.com
WABRUM_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?wabrum\.com/\S+", re.IGNORECASE
)


# --- FSM States ---

class BannerStates(StatesGroup):
    collecting_urls = State()
    selecting_size = State()
    generating = State()


# --- Access control ---

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True  # No restrictions if list is empty
    return user_id in ALLOWED_USER_IDS


# --- Handlers ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    await message.answer(
        "👋 Привет! Я — Wabrum Banner Bot.\n\n"
        "Я помогу создать баннеры для Wabrum.com на основе реальных товаров.\n\n"
        "Команды:\n"
        "/banner — Создать новый баннер\n"
        "/cancel — Отменить текущую операцию\n"
        "/sizes — Показать доступные размеры баннеров\n"
        "/help — Справка"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_authorized(message.from_user.id):
        return

    await message.answer(
        "📖 <b>Как создать баннер:</b>\n\n"
        "1. Отправьте команду /banner\n"
        "2. Отправьте одну или несколько ссылок на товары с Wabrum.com\n"
        "   (по одной ссылке в сообщении или несколько через перенос строки)\n"
        "3. Нажмите «Готово ✅» когда все ссылки добавлены\n"
        "4. Выберите размер баннера\n"
        "5. Дождитесь генерации (~15-30 секунд)\n"
        "6. Получите баннер + тексты на русском и туркменском\n\n"
        f"📌 Максимум товаров на один баннер: {MAX_PRODUCTS_PER_BANNER}\n"
        "📌 Ссылки должны быть с wabrum.com",
        parse_mode="HTML",
    )


@router.message(Command("sizes"))
async def cmd_sizes(message: Message):
    if not is_authorized(message.from_user.id):
        return

    lines = ["📐 <b>Доступные размеры баннеров:</b>\n"]
    for key, info in BANNER_SIZES.items():
        lines.append(
            f"  {info['label']}\n"
            f"    Соотношение: {info['ratio']} | Размер: {info['size']}\n"
            f"    {info['description']}"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять. Используйте /banner для начала.")
        return

    await state.clear()
    await message.answer("❌ Операция отменена. Используйте /banner для нового баннера.")


@router.message(Command("banner"))
async def cmd_banner(message: Message, state: FSMContext):
    if not is_authorized(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этому боту.")
        return

    await state.set_state(BannerStates.collecting_urls)
    await state.update_data(urls=[], products=[])

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Готово ✅", callback_data="urls_done")],
        [InlineKeyboardButton(text="Отмена ❌", callback_data="cancel")],
    ])

    await message.answer(
        "🛒 <b>Создание нового баннера</b>\n\n"
        "Отправьте ссылки на товары с Wabrum.com.\n"
        "Можно отправить несколько ссылок — каждая в отдельном сообщении "
        "или несколько через перенос строки.\n\n"
        f"Максимум: {MAX_PRODUCTS_PER_BANNER} товаров на один баннер.\n\n"
        "Когда все ссылки добавлены — нажмите «Готово ✅»",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.message(BannerStates.collecting_urls)
async def collect_urls(message: Message, state: FSMContext):
    """Collect product URLs from the user."""
    text = message.text or ""
    found_urls = WABRUM_URL_PATTERN.findall(text)

    if not found_urls:
        await message.answer(
            "⚠️ Не нашёл ссылок на Wabrum.com в этом сообщении.\n"
            "Отправьте ссылку формата: https://wabrum.com/..."
        )
        return

    data = await state.get_data()
    current_urls = data.get("urls", [])

    added = 0
    skipped = 0
    for url in found_urls:
        if len(current_urls) >= MAX_PRODUCTS_PER_BANNER:
            break
        if url in current_urls:
            skipped += 1
            continue
        current_urls.append(url)
        added += 1

    await state.update_data(urls=current_urls)

    status_parts = [f"✅ Добавлено: {added}"]
    if skipped:
        status_parts.append(f"(пропущено дубликатов: {skipped})")
    status_parts.append(f"\n📦 Всего товаров: {len(current_urls)}/{MAX_PRODUCTS_PER_BANNER}")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Готово ✅", callback_data="urls_done")],
        [InlineKeyboardButton(text="Очистить всё 🗑", callback_data="clear_urls")],
        [InlineKeyboardButton(text="Отмена ❌", callback_data="cancel")],
    ])

    await message.answer(
        " ".join(status_parts),
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "clear_urls")
async def clear_urls(callback: CallbackQuery, state: FSMContext):
    await state.update_data(urls=[], products=[])
    await callback.message.edit_text(
        "🗑 Список ссылок очищен. Отправьте новые ссылки на товары."
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cancel_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Операция отменена. Используйте /banner для нового баннера.")
    await callback.answer()


@router.callback_query(F.data == "urls_done")
async def urls_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    urls = data.get("urls", [])

    if not urls:
        await callback.answer("⚠️ Добавьте хотя бы одну ссылку!", show_alert=True)
        return

    await callback.answer()

    # Show size selection
    await state.set_state(BannerStates.selecting_size)

    buttons = []
    for key, info in BANNER_SIZES.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{info['label']} ({info['ratio']})",
                callback_data=f"size:{key}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="Отмена ❌", callback_data="cancel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        f"📐 <b>Выберите размер баннера</b>\n\n"
        f"Товаров: {len(urls)}\n"
        f"Ссылки:\n" + "\n".join(f"  • {u}" for u in urls),
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("size:"))
async def size_selected(callback: CallbackQuery, state: FSMContext):
    size_key = callback.data.split(":", 1)[1]

    if size_key not in BANNER_SIZES:
        await callback.answer("⚠️ Неизвестный размер!", show_alert=True)
        return

    await callback.answer()
    await state.set_state(BannerStates.generating)

    data = await state.get_data()
    urls = data.get("urls", [])
    size_info = BANNER_SIZES[size_key]

    # Status message
    status_msg = await callback.message.edit_text(
        f"⏳ <b>Генерация баннера...</b>\n\n"
        f"Размер: {size_info['label']} ({size_info['ratio']})\n"
        f"Товаров: {len(urls)}\n\n"
        f"Шаг 1/3: Парсинг товаров...",
        parse_mode="HTML",
    )

    try:
        # Step 1: Parse all product URLs
        products: list[ProductData] = []
        for i, url in enumerate(urls):
            try:
                product = await parse_product_url(url)
                products.append(product)
            except Exception as e:
                logger.error("Failed to parse %s: %s", url, e)
                await bot.edit_message_text(
                    f"⚠️ Не удалось спарсить товар {i+1}: {url}\nОшибка: {e}\n\nПродолжаю с остальными...",
                    chat_id=status_msg.chat.id,
                    message_id=status_msg.message_id,
                )
                await asyncio.sleep(2)

        if not products:
            await bot.edit_message_text(
                "❌ Не удалось спарсить ни одного товара. Проверьте ссылки и попробуйте снова.",
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
            )
            await state.clear()
            return

        # Step 2: Generate prompt and texts via Claude
        await bot.edit_message_text(
            f"⏳ <b>Генерация баннера...</b>\n\n"
            f"Размер: {size_info['label']} ({size_info['ratio']})\n"
            f"Товаров: {len(products)}\n\n"
            f"✅ Шаг 1/3: Товары спарсены\n"
            f"Шаг 2/3: Генерация промпта и текстов (Claude)...",
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            parse_mode="HTML",
        )

        banner_content = await generate_banner_content(
            products=products,
            banner_size_key=size_key,
            banner_ratio=size_info["ratio"],
        )

        # Step 3: Generate banner via Seedream
        await bot.edit_message_text(
            f"⏳ <b>Генерация баннера...</b>\n\n"
            f"Размер: {size_info['label']} ({size_info['ratio']})\n"
            f"Товаров: {len(products)}\n\n"
            f"✅ Шаг 1/3: Товары спарсены\n"
            f"✅ Шаг 2/3: Промпт и тексты готовы\n"
            f"Шаг 3/3: Генерация изображения (Seedream 4.5)...",
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            parse_mode="HTML",
        )

        image_urls = [p.image_url for p in products]

        banner_bytes = await generate_banner(
            prompt=banner_content.seedream_prompt,
            image_urls=image_urls,
            size=size_info["size"],
        )

        # Step 4: Send result
        # Delete status message
        await bot.delete_message(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
        )

        # Send banner image
        photo = BufferedInputFile(
            banner_bytes,
            filename=f"wabrum_banner_{size_key}.png",
        )

        # Build caption with texts
        caption_lines = [
            f"🖼 <b>Баннер готов!</b>",
            f"Размер: {size_info['label']}",
            f"",
            f"📝 <b>Title (RU):</b>",
            f"<code>{banner_content.title_ru}</code>",
            f"",
            f"📝 <b>Title (TK):</b>",
            f"<code>{banner_content.title_tk}</code>",
            f"",
            f"📄 <b>Description (RU):</b>",
            f"<code>{banner_content.description_ru}</code>",
            f"",
            f"📄 <b>Description (TK):</b>",
            f"<code>{banner_content.description_tk}</code>",
        ]

        await bot.send_photo(
            chat_id=callback.message.chat.id,
            photo=photo,
            caption="\n".join(caption_lines),
            parse_mode="HTML",
        )

        # Send prompt details (for debugging/reference)
        await bot.send_message(
            chat_id=callback.message.chat.id,
            text=(
                f"🔧 <b>Seedream промпт:</b>\n"
                f"<pre>{_escape_html(banner_content.seedream_prompt[:3000])}</pre>\n\n"
                f"📦 Товары:\n"
                + "\n".join(
                    f"  • <a href='{p.url}'>{_escape_html(p.name)}</a>"
                    for p in products
                )
            ),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

        # Offer to generate another size
        buttons = []
        for key, info in BANNER_SIZES.items():
            if key != size_key:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"🔄 {info['label']} ({info['ratio']})",
                        callback_data=f"regen:{key}",
                    )
                ])
        if buttons:
            buttons.append([InlineKeyboardButton(text="🆕 Новый баннер", callback_data="new_banner")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons[:4])  # Limit to 4 options
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text="Сгенерировать этот же баннер в другом размере?",
                reply_markup=keyboard,
            )
            # Keep products in state for regeneration
            await state.update_data(products_data=[
                {"url": p.url, "name": p.name, "image_url": p.image_url,
                 "category": p.category, "price": p.price, "vendor": p.vendor}
                for p in products
            ])
            await state.set_state(BannerStates.selecting_size)
        else:
            await state.clear()

    except Exception as e:
        logger.exception("Banner generation failed")
        try:
            await bot.edit_message_text(
                f"❌ <b>Ошибка при генерации баннера:</b>\n<pre>{_escape_html(str(e)[:500])}</pre>\n\n"
                f"Попробуйте ещё раз: /banner",
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                parse_mode="HTML",
            )
        except Exception:
            await bot.send_message(
                chat_id=callback.message.chat.id,
                text=f"❌ Ошибка: {e}\n\nПопробуйте ещё раз: /banner",
            )
        await state.clear()


@router.callback_query(F.data.startswith("regen:"))
async def regenerate_size(callback: CallbackQuery, state: FSMContext):
    """Regenerate the same banner in a different size."""
    size_key = callback.data.split(":", 1)[1]
    if size_key not in BANNER_SIZES:
        await callback.answer("⚠️ Неизвестный размер!", show_alert=True)
        return

    data = await state.get_data()
    products_data = data.get("products_data", [])
    urls = data.get("urls", [])

    if not products_data and not urls:
        await callback.answer("⚠️ Нет данных для регенерации. Начните заново: /banner", show_alert=True)
        await state.clear()
        return

    # Reconstruct products from stored data
    if products_data:
        products = [ProductData(**pd) for pd in products_data]
        # Simulate the size selection flow
        await state.update_data(urls=[p.url for p in products])
        # Trigger size_selected logic
        callback.data = f"size:{size_key}"
        await size_selected(callback, state)
    else:
        callback.data = f"size:{size_key}"
        await size_selected(callback, state)


@router.callback_query(F.data == "new_banner")
async def new_banner_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    # Simulate /banner command
    await cmd_banner(callback.message, state)


def _escape_html(text: str) -> str:
    """Escape HTML special characters for Telegram."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


async def main():
    logger.info("Starting Wabrum Banner Bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
