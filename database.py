import sqlite3

def get_db():
    conn = sqlite3.connect('warehouse.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    
    # Таблица зон
    db.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица коробок
    db.execute('''
        CREATE TABLE IF NOT EXISTS boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            zone_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (zone_id) REFERENCES zones (id)
        )
    ''')
    
    # Таблица товаров в коробках
    db.execute('''
        CREATE TABLE IF NOT EXISTS box_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            box_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            barcode TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (box_id) REFERENCES boxes (id)
        )
    ''')
    
    # Новая таблица для приёмок
    db.execute('''
        CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_number TEXT NOT NULL UNIQUE,
            receipt_date DATE NOT NULL,
            total_quantity INTEGER NOT NULL DEFAULT 0,
            total_products INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица товаров в приёмках
    db.execute('''
        CREATE TABLE IF NOT EXISTS receipt_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            receipt_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            barcode TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            box_name TEXT,
            zone_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (receipt_id) REFERENCES receipts (id) ON DELETE CASCADE
        )
    ''')
    
    db.commit()