#!/usr/bin/env python3
"""
Скрипт для исправления строки подключения к БД и загрузки данных
"""
import os
import re
import argparse
import csv
import sqlite3
from pathlib import Path


def fix_env_connection_string():
    """Исправляет строку подключения в .env файле"""
    # Проверка файла .env
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        print(f"Обновляем .env файл: {env_path}")
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Заменяем sqlite:/// на sqlite+aiosqlite:///
        if 'DATABASE_URL=sqlite:///' in content:
            content = re.sub(r'DATABASE_URL=sqlite:///', 'DATABASE_URL=sqlite+aiosqlite:///', content)
            print("Заменено sqlite:/// на sqlite+aiosqlite:///")
        
        with open(env_path, 'w') as f:
            f.write(content)
        
        print("✅ Файл .env обновлен с правильным драйвером")
    else:
        print("❌ Файл .env не найден")


def get_db_path():
    """Получает путь к файлу БД из .env или использует значение по умолчанию"""
    env_path = os.path.join(os.getcwd(), ".env")
    db_path = None
    
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith('DATABASE_URL='):
                    db_url = line.strip().split('=', 1)[1]
                    # Извлекаем путь к файлу из URL
                    if '///' in db_url:
                        db_path = db_url.split('///')[-1]
                        break
    
    if not db_path:
        db_path = os.path.join(os.getcwd(), "notav2.db")
        print(f"❗ Путь к БД не найден, используем значение по умолчанию: {db_path}")
    else:
        print(f"📂 Найден путь к БД: {db_path}")
    
    # Убедимся, что директория для БД существует
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"📁 Создана директория для БД: {db_dir}")
    
    return db_path


def create_tables(db_path):
    """Создает таблицы в базе данных"""
    print(f"🔧 Создаем таблицы в базе данных: {db_path}")
    
    # Подключаемся к БД
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # SQL для создания таблиц
    sql = """
    -- Suppliers table
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR NOT NULL,
        code VARCHAR(64) UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Products table
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(255) UNIQUE NOT NULL,
        unit VARCHAR(16) NOT NULL,
        price DECIMAL(14,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Product name lookup table
    CREATE TABLE IF NOT EXISTS product_name_lookup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        alias VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    -- Invoices table
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        number VARCHAR(64),
        date DATE NOT NULL,
        total_sum DECIMAL(14,2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
    );

    -- Invoice items table
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity DECIMAL(14,3) NOT NULL,
        price DECIMAL(14,2) NOT NULL,
        sum DECIMAL(14,2) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
    );

    -- Create indexes
    CREATE INDEX IF NOT EXISTS ix_suppliers_name ON suppliers(name);
    CREATE INDEX IF NOT EXISTS ix_suppliers_code ON suppliers(code);
    CREATE INDEX IF NOT EXISTS ix_products_name ON products(name);
    CREATE INDEX IF NOT EXISTS ix_product_name_lookup_alias ON product_name_lookup(alias);
    CREATE INDEX IF NOT EXISTS ix_product_name_lookup_product_id ON product_name_lookup(product_id);
    CREATE INDEX IF NOT EXISTS ix_invoices_supplier_id ON invoices(supplier_id);
    CREATE INDEX IF NOT EXISTS ix_invoices_number ON invoices(number);
    CREATE INDEX IF NOT EXISTS ix_invoices_date ON invoices(date);
    CREATE INDEX IF NOT EXISTS ix_invoice_items_invoice_id ON invoice_items(invoice_id);
    CREATE INDEX IF NOT EXISTS ix_invoice_items_product_id ON invoice_items(product_id);
    """
    
    cursor.executescript(sql)
    conn.commit()
    conn.close()
    
    print("✅ Таблицы созданы успешно!")


def parse_csv(path):
    """Парсит CSV-файл и возвращает список словарей."""
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_data(db_path, data_type, csv_path):
    """Загружает данные из CSV в базу данных"""
    print(f"📊 Загружаем {data_type} из {csv_path}")
    
    # Проверяем, что файл существует
    if not os.path.exists(csv_path):
        print(f"❌ Файл не найден: {csv_path}")
        return False
    
    # Читаем данные из CSV
    rows = parse_csv(csv_path)
    print(f"📋 Прочитано {len(rows)} строк из CSV")
    
    # Подключаемся к БД
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Подготавливаем запросы в зависимости от типа
    if data_type == "suppliers":
        for row in rows:
            cursor.execute(
                "INSERT OR IGNORE INTO suppliers (name, code) VALUES (?, ?)",
                (row.get("name", ""), row.get("code", ""))
            )
    elif data_type == "products":
        for row in rows:
            cursor.execute(
                "INSERT OR IGNORE INTO products (name, unit) VALUES (?, ?)",
                (row.get("name", ""), row.get("measureName", ""))
            )
    elif data_type == "lookups":
        for row in rows:
            cursor.execute(
                "INSERT OR IGNORE INTO product_name_lookup (product_id, alias) VALUES (?, ?)",
                (row.get("product_id", ""), row.get("alias", ""))
            )
    
    # Коммитим изменения
    conn.commit()
    conn.close()
    
    print(f"✅ Вставлено {len(rows)} строк в таблицу {data_type}")
    return True


def check_data(db_path):
    """Проверяет количество загруженных данных"""
    print("\n📊 Проверка загруженных данных:")
    
    # Подключаемся к БД
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверяем таблицы
    cursor.execute('SELECT COUNT(*) FROM suppliers')
    suppliers_count = cursor.fetchone()[0]
    print(f'Количество поставщиков: {suppliers_count}')
    
    cursor.execute('SELECT COUNT(*) FROM products')
    products_count = cursor.fetchone()[0]
    print(f'Количество товаров: {products_count}')
    
    cursor.execute('SELECT COUNT(*) FROM product_name_lookup')
    lookups_count = cursor.fetchone()[0]
    print(f'Количество lookup-записей: {lookups_count}')
    
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Исправляет строку подключения и загружает данные")
    parser.add_argument("--fix-only", action="store_true", help="Только исправить строку подключения, без загрузки данных")
    parser.add_argument("--suppliers", type=str, help="Путь к CSV с поставщиками", default="data/base_suppliers.csv")
    parser.add_argument("--products", type=str, help="Путь к CSV с товарами", default="data/base_products.csv")
    args = parser.parse_args()
    
    # Исправляем строку подключения
    fix_env_connection_string()
    
    # Получаем путь к БД
    db_path = get_db_path()
    
    # Создаем таблицы
    create_tables(db_path)
    
    if not args.fix_only:
        # Загружаем данные
        load_data(db_path, "suppliers", args.suppliers)
        load_data(db_path, "products", args.products)
        
        # Проверяем загруженные данные
        check_data(db_path)
    
    print("\n🎉 Процесс успешно завершен!")
    print("\nТеперь вы можете запустить приложение:")
    print("python -m app")


if __name__ == "__main__":
    main()
