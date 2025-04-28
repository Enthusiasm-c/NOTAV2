#!/bin/bash
# Скрипт для полной пересборки базы данных
# Использование: bash scripts/rebuild_db.sh

set -e  # Прерывать скрипт при ошибках

# Получаем директорию проекта
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$PROJECT_DIR"

echo "🔄 Пересоздание базы данных..."

# Создаём таблицы
python -m scripts.create_tables

# Загружаем начальные данные
if [ -f "data/base_suppliers.csv" ]; then
    echo "📝 Загрузка поставщиков..."
    python -m scripts.load_seed_data suppliers data/base_suppliers.csv
fi

if [ -f "data/base_products.csv" ]; then
    echo "📝 Загрузка товаров..."
    python -m scripts.load_seed_data products data/base_products.csv
fi

echo "✅ База данных пересоздана успешно!"
