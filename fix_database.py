#!/usr/bin/env python3
"""
Скрипт для проверки конфигурации БД и создания таблиц
"""
import os
import sys
import sqlite3
import re

# Вывод текущей директории
print(f"Текущая директория: {os.getcwd()}")

# Проверка файла .env
env_path = os.path.join(os.getcwd(), ".env")
db_path = None

if os.path.exists(env_path):
    print(f"Найден файл .env: {env_path}")
    with open(env_path, 'r') as f:
        content = f.read()
        matches = re.findall(r'DATABASE_URL=sqlite:///([^\n]+)', content)
        if matches:
            db_path = matches[0]
            print(f"Найден путь к БД в .env: {db_path}")

# Проверка файла config.py
config_path = os.path.join(os.getcwd(), "app", "config.py")
if os.path.exists(config_path):
    print(f"Найден файл config.py: {config_path}")
    with open(config_path, 'r') as f:
        content = f.read()
        matches = re.findall(r'database_url: str = Field\s*\(\s*[\'"]sqlite:///([^\'"]+)', content)
        if matches:
            config_db_path = matches[0]
            print(f"Найден путь к БД в config.py: {config_db_path}")
            if not db_path:
                db_path = config_db_path

# Если путь не найден, используем значение по умолчанию
if not db_path:
    db_path = os.path.join(os.getcwd(), "notav2.db")
    print(f"Путь к БД не найден, используем значение по умолчанию: {db_path}")

# Убедимся, что директория для БД существует
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir)
    print(f"Создана директория для БД: {db_dir}")

print(f"\nИспользуем базу данных: {db_path}")

# Создаем и инициализируем БД
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

# Убедимся, что .env содержит правильный путь к БД
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        env_content = f.read()
    
    if 'DATABASE_URL=' in env_content:
        env_content = re.sub(r'DATABASE_URL=.*', f'DATABASE_URL=sqlite:///{db_path}', env_content)
    else:
        env_content += f'\nDATABASE_URL=sqlite:///{db_path}'
    
    with open(env_path, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Файл .env обновлен с правильным путем к БД")
else:
    with open(env_path, 'w') as f:
        f.write(f'DATABASE_URL=sqlite:///{db_path}\n')
    
    print(f"✅ Создан файл .env с путем к БД")

print("\nТеперь можно запустить скрипты загрузки данных:")
print("python -m scripts.load_seed_data suppliers data/base_suppliers.csv")
print("python -m scripts.load_seed_data products data/base_products.csv")
