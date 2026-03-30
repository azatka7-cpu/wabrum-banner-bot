# Wabrum Banner Bot 🖼

Telegram-бот для автоматической генерации баннеров для Wabrum.com.

## Как работает

1. Менеджер отправляет ссылки на товары с Wabrum.com
2. Бот парсит страницы и получает фотографии товаров
3. Claude API генерирует промпт для Seedream + тексты (Title/Description) на русском и туркменском
4. Seedream 5.0 API генерирует баннер, используя фото товаров как референсы
5. Бот отправляет готовый баннер + тексты для копирования в CS-Cart

## Требования

- Python 3.11+
- Telegram Bot Token (через @BotFather)
- Anthropic API Key (Claude)
- BytePlus API Key (Seedream 5.0)

## Установка на сервере (Ubuntu)

```bash
# 1. Клонировать/скопировать проект
sudo mkdir -p /opt/wabrum-banner-bot
sudo cp -r . /opt/wabrum-banner-bot/
cd /opt/wabrum-banner-bot

# 2. Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить переменные окружения
cp .env.example .env
nano .env  # Заполнить все ключи

# 5. Тестовый запуск
python bot.py

# 6. Установить как systemd-сервис
sudo cp wabrum-banner-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wabrum-banner-bot
sudo systemctl start wabrum-banner-bot

# 7. Проверить статус
sudo systemctl status wabrum-banner-bot
sudo journalctl -u wabrum-banner-bot -f
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие |
| `/banner` | Создать новый баннер |
| `/sizes` | Показать доступные размеры |
| `/cancel` | Отменить текущую операцию |
| `/help` | Справка |

## Доступные размеры баннеров

| Место | Соотношение | Размер (px) | Устройство |
|-------|-------------|-------------|------------|
| Главный слайдер | 21:9 | 2520×1080 | Десктоп |
| Главный слайдер | 4:3 | 1600×1200 | Мобайл |
| Категория | 16:9 | 1920×1080 | Десктоп |
| Категория | 4:3 | 1600×1200 | Мобайл |
| Боковой | 3:4 | 1200×1600 | Сайдбар |
| Промо | 1:1 | 1080×1080 | Универсальный |
| Stories | 9:16 | 1080×1920 | Мобайл |

## Структура проекта

```
wabrum-banner-bot/
├── bot.py                 # Основной файл бота (Telegram handlers)
├── config.py              # Конфигурация и размеры баннеров
├── parser.py              # Парсер страниц Wabrum.com (CS-Cart)
├── prompt_generator.py    # Генерация промптов через Claude API
├── seedream.py            # Интеграция с Seedream 5.0 (BytePlus)
├── requirements.txt       # Зависимости Python
├── .env.example           # Шаблон переменных окружения
├── wabrum-banner-bot.service  # Systemd service
└── README.md
```

## Стоимость

- Seedream 5.0: ~$0.035/изображение
- Claude Sonnet: ~$0.003-0.01 за запрос
- **Итого: ~$3-5/месяц при 3-5 баннерах в день**
