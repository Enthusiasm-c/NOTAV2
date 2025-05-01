# Nota V2 Telegram-bot MVP

## Установка

```sh
# Создание виртуального окружения
python -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

## Обновление после git pull

```sh
# Активация виртуального окружения
source venv/bin/activate

# Обновление зависимостей
pip install -r requirements.txt --upgrade

# Для systemd-службы
sudo systemctl restart notav2-bot
```

## Запуск бота

1. Скопируйте и настройте переменные окружения:
```sh
cp .env.example .env  # и заполните значения
```

2. Запустите бота:
```sh
python bot_runner.py
```

## Структура данных

Бот использует CSV-файлы для хранения данных:

- `data/base_products.csv` - справочник товаров
- `data/base_suppliers.csv` - справочник поставщиков
- `data/learned_products.csv` - обученные соответствия товаров
- `data/learned_suppliers.csv` - обученные соответствия поставщиков

## Тестирование

```sh
# Запуск тестов
pytest

# Запуск тестов с покрытием
pytest --cov=app tests/
```
