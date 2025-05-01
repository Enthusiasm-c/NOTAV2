BEGIN TRANSACTION;
DROP TABLE IF EXISTS product_name_lookup;
DROP TABLE IF EXISTS invoice_items;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;

CREATE TABLE suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL,
    inn VARCHAR(12) UNIQUE,
    kpp VARCHAR(9),
    address TEXT,
    phone VARCHAR(20),
    email VARCHAR(100),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(64) UNIQUE,
    unit VARCHAR(16) NOT NULL,
    price DECIMAL(14,2),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    number VARCHAR(64),
    date DATE NOT NULL,
    total_sum DECIMAL(14,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

CREATE TABLE invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    product_id INTEGER,
    name VARCHAR(255) NOT NULL,
    quantity DECIMAL(14,3) NOT NULL,
    unit VARCHAR(16) NOT NULL,
    price DECIMAL(14,2) NOT NULL,
    sum DECIMAL(14,2) NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

CREATE TABLE product_name_lookup (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    alias VARCHAR(255) NOT NULL UNIQUE,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX ix_suppliers_name ON suppliers(name);
CREATE INDEX ix_suppliers_inn ON suppliers(inn);
CREATE INDEX ix_products_name ON products(name);
CREATE INDEX ix_products_code ON products(code);
CREATE INDEX ix_invoices_supplier_id ON invoices(supplier_id);
CREATE INDEX ix_invoices_number ON invoices(number);
CREATE INDEX ix_invoices_date ON invoices(date);
CREATE INDEX ix_invoice_items_invoice_id ON invoice_items(invoice_id);
CREATE INDEX ix_invoice_items_product_id ON invoice_items(product_id);
CREATE INDEX ix_product_name_lookup_product_id ON product_name_lookup(product_id);
CREATE INDEX ix_product_name_lookup_alias ON product_name_lookup(alias);

COMMIT; 