1. Установите зависимости:
python -m venv venv source venv/bin/activate pip install -r requirements.txt
2. Установите PostgreSQL, создайте БД (данные — в config.py)
3. Примените миграции или выполните созданные модели.
4. Запустите backend:
uvicorn app.main:app --reload
5. Запустите Telegram-бота:
python app/routers/telegram_bot.py
6. Для теста GPT нужна переменная окружения `GPT4_OCR_URL` (если нет — запускается mock).
