# Telegram Web App Setup

## Что такое Telegram Web App?

Это встроенное веб-приложение Telegram, которое:
- Открывается прямо в Telegram
- Автоматически передает данные пользователя (ID, имя, username)
- Не требует ввода данных — все работает волшебно ✨

## Как настроить (5 минут)

### 1. Создать или обновить бота через @BotFather

```
1. Откройте @BotFather в Telegram
2. Нажмите /start или выберите существующего бота
3. Выберите бота или создайте нового (/newbot)
```

### 2. Зарегистрировать Web App

```
В @BotFather:
1. Выберите ваш бот
2. Edit Bot → Web App
3. Укажите URL:
   - Локально: http://localhost:3000
   - Продакшен: https://yourdomain.com
```

### 3. Добавить кнопку в бота (опционально)

Бот может просто иметь одну кнопку "Открыть приложение" через [Inline Keyboard](https://core.telegram.org/bots#inline-keyboards).

Пример простого Python бота:

```python
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command

TOKEN = "YOUR_BOT_TOKEN"
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="📖 Открыть Postbox",
                web_app=types.WebAppInfo(
                    url="https://yourdomain.com"  # or http://localhost:3000 for local
                )
            )]
        ]
    )
    
    await message.answer(
        "👋 Добро пожаловать в Postbox!\n\n"
        "Нажмите кнопку ниже, чтобы открыть приложение:",
        reply_markup=keyboard
    )
```

## Как юзер входит

1. **Открывает** бота: https://t.me/YourBotName
2. **Нажимает** кнопку "Открыть Postbox"
3. **Автоматически** авторизуется (без ввода ID!)
4. **Пользуется** приложением

## Для разработки (без бота)

Сейчас работает форма с ручным вводом ID:

```
http://localhost:3000/login
→ Введите Telegram ID из @userinfobot
→ Готово!
```

## Для продакшена

1. Зарегистрировать Web App в @BotFather
2. Деплоить фронт на https://yourdomain.com
3. Бот ссылается на https://yourdomain.com/login (или просто /)

## Безопасность

⚠️ **Важно:** Telegram передает подписанные данные с `hash`:
- Фронт отправляет эту подпись на бэкенд
- Бэкенд валидирует подпись через `validate_telegram_signature()`
- Это гарантирует что данные от настоящего Telegram

Для разработки используется `dev_hash_*` (см. auth.py).

## Ссылки

- [Telegram Web Apps docs](https://core.telegram.org/bots/webapps)
- [@BotFather](https://t.me/BotFather)
- [Inline Keyboards](https://core.telegram.org/bots#inline-keyboards)
