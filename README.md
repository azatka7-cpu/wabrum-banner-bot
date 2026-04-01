# Wabrum Banner Bot

Telegram-бот для автоматической генерации веб-баннеров для маркетплейса [Wabrum.com](https://wabrum.com) (Туркменистан).

## Возможности

- Парсинг товаров с Wabrum.com (CS-Cart MultiVendor)
- Генерация промптов и текстов через Claude AI (русский + туркменский)
- Создание баннеров через Seedream 5.0 (BytePlus) с реальными фото товаров
- 7 пресетов размеров (десктоп, мобайл, сайдбар, stories и др.)
- Регенерация в другом размере без повторного парсинга

## Стек

- Python 3.11+, aiogram 3.x, aiohttp
- Anthropic Claude API (генерация промптов)
- Seedream 5.0 через BytePlus (генерация изображений)

## Установка и запуск

```bash
# Клонировать и перейти в директорию
sudo mkdir -p /opt/wabrum-banner-bot
sudo cp -r . /opt/wabrum-banner-bot/
cd /opt/wabrum-banner-bot

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Настроить переменные окружения
cp .env.example .env
nano .env  # заполнить ключи

# Тестовый запуск
python bot.py

# Установить как systemd сервис
sudo cp wabrum-banner-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wabrum-banner-bot
sudo systemctl start wabrum-banner-bot
```

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота |
| `ANTHROPIC_API_KEY` | API ключ Anthropic Claude |
| `BYTEPLUS_API_KEY` | API ключ BytePlus (Seedream) |
| `BYTEPLUS_ENDPOINT` | URL эндпоинта Seedream API |
| `ALLOWED_USER_IDS` | ID разрешённых пользователей через запятую (пусто = доступ для всех) |

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие и список команд |
| `/banner` | Начать создание баннера |
| `/sizes` | Показать доступные размеры |
| `/cancel` | Отменить текущую операцию |
| `/help` | Подробная справка |

## Размеры баннеров

| Размер | Соотношение | Пиксели |
|---|---|---|
| Главный слайдер (десктоп) | 21:9 | 3136x1344 |
| Главный слайдер (мобайл) | 4:3 | 2304x1728 |
| Категория (десктоп) | 16:9 | 2848x1600 |
| Категория (мобайл) | 4:3 | 2304x1728 |
| Боковой баннер | 3:4 | 1728x2304 |
| Промо (квадрат) | 1:1 | 2048x2048 |
| Stories / вертикальный | 9:16 | 1600x2848 |
