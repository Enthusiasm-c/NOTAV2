#!/usr/bin/env python3
"""
Скрипт для создания таблиц в базе данных.
"""
import os
import sys
import asyncio
import sqlite3
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import engine
from app.models import Base
from app.config.settings import get_settings

# Добавляем текущую директорию в путь
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Выводим информацию о путях для диагностики
print(f"Текущая директория: {current_dir}")
print(f"PYTHONPATH: {sys.path}")

# Функция для создания таблиц через ORM SQLAlchemy
async def create_tables_orm():
    try:
        print("Начинаем создание таблиц через SQLAlchemy ORM...")
        async with engine.begin() as conn:
            # Удаляем существующие таблицы (чтобы начать с чистого листа)
            await conn.run_sync(Base.metadata.drop_all)
            print("Существующие таблицы удалены.")
            
            # Создаем таблицы заново
            await conn.run_sync(Base.metadata.create_all)
            print("✅ Таблицы успешно созданы через ORM!")
        return True
    except Exception as e:
        print(f"❌ Ошибка при создании через ORM: {e}")
        return False

# Функция для создания таблиц напрямую через SQL
def create_tables_sql():
    # Определяем путь к базе данных
    try:
        settings = get_settings()
        db_url = settings.database_url
        
        # Парсим URL для SQLite
        if db_url.startswith('sqlite'):
            db_path = db_url.split(':///')[-1]
            print(f"Найден путь к БД из настроек: {db_path}")
        else:
            raise ValueError(f"Неподдерживаемый тип БД: {db_url}")
    except Exception as e:
        print(f"Ошибка при получении настроек БД: {e}")
        # Используем значение по умолчанию
        db_path = os.path.join(current_dir, "notav2.db")
        print(f"Используем путь к БД по умолчанию: {db_path}")
    
    try:
        print(f"Создаем таблицы напрямую через SQL в {db_path}...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Удаляем существующие таблицы
        cursor.executescript('''
            DROP TABLE IF EXISTS invoice_items;
            DROP TABLE IF EXISTS invoices;
            DROP TABLE IF EXISTS product_name_lookup;
            DROP TABLE IF EXISTS products;
            DROP TABLE IF EXISTS suppliers;
        ''')
        print("Существующие таблицы удалены.")
        
        # Создаем таблицы
        cursor.executescript('''
            CREATE TABLE suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                unit TEXT NOT NULL,
                price NUMERIC(14,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE product_name_lookup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                alias TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER,
                number TEXT,
                date DATE NOT NULL,
                total_sum NUMERIC(14,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
            );

            CREATE TABLE invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity NUMERIC(14,3) NOT NULL,
                price NUMERIC(14,2) NOT NULL,
                sum NUMERIC(14,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            -- Создаем индексы
            CREATE INDEX ix_suppliers_name ON suppliers(name);
            CREATE INDEX ix_suppliers_code ON suppliers(code);
            CREATE INDEX ix_products_name ON products(name);
            CREATE INDEX ix_product_name_lookup_alias ON product_name_lookup(alias);
            CREATE INDEX ix_product_name_lookup_product_id ON product_name_lookup(product_id);
            CREATE INDEX ix_invoices_supplier_id ON invoices(supplier_id);
            CREATE INDEX ix_invoices_number ON invoices(number);
            CREATE INDEX ix_invoices_date ON invoices(date);
            CREATE INDEX ix_invoice_items_invoice_id ON invoice_items(invoice_id);
            CREATE INDEX ix_invoice_items_product_id ON invoice_items(product_id);
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Таблицы успешно созданы через прямой SQL!")
        
        # Обновляем .env файл с правильным путем к БД, если он существует
        env_path = os.path.join(current_dir, ".env")
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                env_content = f.read()
            
            # Заменяем строку DATABASE_URL, если она есть
            if 'DATABASE_URL=' in env_content:
                env_content = re.sub(
                    r'DATABASE_URL=.*', 
                    f'DATABASE_URL=sqlite+aiosqlite:///{db_path}', 
                    env_content
                )
            else:
                # Добавляем строку, если её нет
                env_content += f'\nDATABASE_URL=sqlite+aiosqlite:///{db_path}\n'
            
            with open(env_path, 'w') as f:
                f.write(env_content)
            
            print(f"✅ Файл .env обновлен с правильным путем к БД")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка при создании через SQL: {e}")
        return False

async def main():
    """Основная функция - пробует разные методы создания таблиц."""
    print("=" * 60)
    print("Запуск процесса создания таблиц NOTA V2")
    print("=" * 60)
    
    # Сначала пробуем через ORM
    orm_success = await create_tables_orm()
    
    # Если ORM не сработал, пробуем через прямой SQL
    if not orm_success:
        print("\nПробуем создать таблицы через прямой SQL...")
        sql_success = create_tables_sql()
        
        if not sql_success:
            print("\n❌ Не удалось создать таблицы ни одним из методов.")
            print("Проверьте настройки подключения к базе данных и права доступа.")
            return False
    
    print("\n✅ Создание таблиц завершено успешно!")
    print("Теперь можно загрузить тестовые данные командами:")
    print("  python -m scripts.load_seed_data suppliers data/base_suppliers.csv")
    print("  python -m scripts.load_seed_data products data/base_products.csv")
    return True

if __name__ == "__main__":
    import re  # Импортируем здесь, чтобы не вызывать ошибку в async функции
    try:
        success = asyncio.run(main())
        if success:
            print("\nПроцесс завершен успешно!")
            sys.exit(0)
        else:
            print("\nПроцесс завершен с ошибками.")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nПрервано пользователем.")
        sys.exit(2)
    except Exception as e:
        print(f"\n\n❌ Необработанная ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(3)
