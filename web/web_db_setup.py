# web_db_setup.py
import sqlite3

def setup_database():
    conn = sqlite3.connect('iphones_catalog.db')
    cursor = conn.cursor()
    
    # Existing tables (ensure they are defined as in parsing.py)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS iphones_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE,
            model TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            currency TEXT DEFAULT 'RUB',
            old_price TEXT,
            current_color TEXT,
            current_memory TEXT,
            current_sim TEXT,
            image_url TEXT,
            product_url TEXT,
            parsed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            category TEXT, -- Added category for filtering
            is_featured INTEGER DEFAULT 0, -- For featured products
            display_order INTEGER DEFAULT 0 -- For sorting
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS iphone_catalog_colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            color_name TEXT,
            FOREIGN KEY (product_id) REFERENCES iphones_catalog (product_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS iphone_catalog_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT,
            memory_size TEXT,
            FOREIGN KEY (product_id) REFERENCES iphones_catalog (product_id)
        )
    ''')

    # New table for orders
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            charge_code TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES iphones_catalog (product_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database setup complete. 'orders' table created or already exists.")

if __name__ == '__main__':
    setup_database()