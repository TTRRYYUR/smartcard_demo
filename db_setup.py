import sqlite3

DB_NAME = "smartcart.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'прочее',
    unit TEXT NOT NULL DEFAULT 'шт',
    price REAL NOT NULL DEFAULT 0,
    calories REAL NOT NULL DEFAULT 0,
    protein REAL NOT NULL DEFAULT 0,
    fat REAL NOT NULL DEFAULT 0,
    carbs REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    full_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS budget (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    period_days INTEGER NOT NULL DEFAULT 7,
    starts_at TEXT NOT NULL DEFAULT CURRENT_DATE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    expires_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id),
    FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS purchase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    store TEXT,
    total_amount REAL NOT NULL DEFAULT 0,
    purchased_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS purchase_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    price REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (purchase_id) REFERENCES purchase (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS shopping_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT 'Список покупок',
    budget_amount REAL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS shopping_list_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shopping_list_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    estimated_price REAL NOT NULL DEFAULT 0,
    reason TEXT,
    priority INTEGER NOT NULL DEFAULT 1,
    is_checked INTEGER NOT NULL DEFAULT 0,
    UNIQUE(shopping_list_id, product_id),
    FOREIGN KEY (shopping_list_id) REFERENCES shopping_list (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS recipe (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    servings INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_ingredient (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity REAL NOT NULL DEFAULT 0,
    unit TEXT,
    FOREIGN KEY (recipe_id) REFERENCES recipe (id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES product (id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ai_recommendation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    request_text TEXT,
    response_text TEXT,
    total_price REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES app_user (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_product_category ON product (category);
CREATE INDEX IF NOT EXISTS idx_stock_user ON stock (user_id);
CREATE INDEX IF NOT EXISTS idx_purchase_user ON purchase (user_id);
CREATE INDEX IF NOT EXISTS idx_purchase_item_purchase ON purchase_item (purchase_id);
CREATE INDEX IF NOT EXISTS idx_shopping_list_user ON shopping_list (user_id);
CREATE INDEX IF NOT EXISTS idx_shopping_list_item_list ON shopping_list_item (shopping_list_id);
CREATE INDEX IF NOT EXISTS idx_budget_user ON budget (user_id);
"""

# Каталог продуктов: название, категория, единица, цена, ккал, белки, жиры, углеводы
PRODUCTS = [
    ("Гречка", "крупы", "кг", 90.0, 330.0, 12.0, 3.0, 68.0),
    ("Рис", "крупы", "кг", 110.0, 350.0, 7.0, 1.0, 78.0),
    ("Овсянка", "крупы", "кг", 80.0, 360.0, 12.0, 6.0, 60.0),
    ("Макароны", "крупы", "кг", 120.0, 350.0, 10.0, 1.0, 70.0),
    ("Куриное филе", "мясо", "кг", 350.0, 165.0, 31.0, 3.6, 0.0),
    ("Яйца", "белки", "уп", 120.0, 155.0, 13.0, 11.0, 1.0),
    ("Молоко", "молочка", "л", 90.0, 60.0, 3.0, 3.2, 4.8),
    ("Творог", "молочка", "кг", 220.0, 120.0, 18.0, 2.0, 3.0),
    ("Сыр", "молочка", "кг", 650.0, 350.0, 25.0, 26.0, 2.0),
    ("Кефир", "молочка", "л", 70.0, 40.0, 3.0, 1.0, 4.0),
    ("Сметана", "молочка", "уп", 80.0, 200.0, 2.5, 20.0, 3.0),
    ("Хлеб", "выпечка", "шт", 45.0, 250.0, 8.0, 3.0, 45.0),
    ("Бананы", "фрукты", "кг", 130.0, 89.0, 1.1, 0.3, 23.0),
    ("Яблоки", "фрукты", "кг", 100.0, 52.0, 0.3, 0.2, 14.0),
    ("Картофель", "овощи", "кг", 40.0, 77.0, 2.0, 0.4, 17.0),
    ("Морковь", "овощи", "кг", 50.0, 41.0, 0.9, 0.2, 10.0),
    ("Лук", "овощи", "кг", 45.0, 40.0, 1.1, 0.1, 9.0),
    ("Помидоры", "овощи", "кг", 180.0, 20.0, 1.0, 0.2, 4.0),
    ("Подсолнечное масло", "масло", "л", 150.0, 884.0, 0.0, 100.0, 0.0),
]

# Что лежит дома у демо-пользователя: название, количество
DEMO_STOCK = [
    ("Гречка", 1.0),
    ("Рис", 0.5),
    ("Молоко", 1.0),
    ("Яйца", 1.0),
    ("Картофель", 2.0),
    ("Подсолнечное масло", 0.5),
]

# История покупок: сколько дней назад, список товаров (название, количество)
# Подобрано так, чтобы predictor видел повторяющиеся покупки:
# хлеб и курица "заканчиваются по статистике", молоко и яйца - нет.
DEMO_HISTORY = [
    (21, [("Хлеб", 1.0), ("Молоко", 2.0)]),
    (20, [("Картофель", 2.0)]),
    (18, [("Яйца", 1.0)]),
    (15, [("Куриное филе", 0.7)]),
    (14, [("Хлеб", 1.0), ("Молоко", 2.0)]),
    (12, [("Морковь", 1.0)]),
    (11, [("Яйца", 1.0)]),
    (10, [("Бананы", 1.0)]),
    (8, [("Куриное филе", 0.8)]),
    (7, [("Хлеб", 1.0), ("Молоко", 2.0)]),
    (6, [("Картофель", 1.0)]),
    (4, [("Яйца", 1.0)]),
    (3, [("Бананы", 1.0)]),
    (2, [("Молоко", 1.0)]),
]


def create_tables(conn):
    """Создаёт все таблицы и индексы."""
    conn.executescript(SCHEMA)


def insert_products(conn):
    """Заполняет каталог продуктов. Дубли игнорируются."""
    sql = """
        INSERT OR IGNORE INTO product
            (name, category, unit, price, calories, protein, fat, carbs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """
    conn.executemany(sql, PRODUCTS)


def insert_demo_user(conn):
    """Создаёт демо-пользователя и возвращает его id."""
    conn.execute(
        "INSERT OR IGNORE INTO app_user (username, full_name) VALUES (?, ?);",
        ("demo", "Демо Пользователь")
    )

    row = conn.execute(
        "SELECT id FROM app_user WHERE username = ?;",
        ("demo",)
    ).fetchone()

    if row is None:
        return None

    return row[0]


def insert_demo_budget(conn, user_id):
    """Добавляет демо-бюджет, если его ещё нет."""
    if user_id is None:
        return

    row = conn.execute(
        "SELECT COUNT(*) FROM budget WHERE user_id = ?;",
        (user_id,)
    ).fetchone()

    if row[0] == 0:
        conn.execute(
            """
            INSERT INTO budget
                (user_id, amount, period_days, starts_at)
            VALUES (?, ?, ?, date('now'));
            """,
            (user_id, 3000.0, 7)
        )


def insert_demo_stock(conn, user_id):
    """Добавляет домашние запасы демо-пользователю."""
    if user_id is None:
        return

    for product_name, quantity in DEMO_STOCK:
        conn.execute(
            """
            INSERT OR IGNORE INTO stock
                (user_id, product_id, quantity, expires_at)
            SELECT ?, id, ?, date('now', '+7 day')
            FROM product
            WHERE name = ?;
            """,
            (user_id, quantity, product_name)
        )


def insert_demo_history(conn, user_id):
    """
    Добавляет историю покупок.
    Каждая запись - отдельный чек со своей датой.
    Сумма чека считается автоматически по товарам.
    """
    if user_id is None:
        return

    row = conn.execute(
        "SELECT COUNT(*) FROM purchase WHERE user_id = ?;",
        (user_id,)
    ).fetchone()

    # Если история уже есть, не дублируем
    if row[0] > 0:
        return

    for days_ago, items in DEMO_HISTORY:
        cur = conn.execute(
            """
            INSERT INTO purchase
                (user_id, store, total_amount, purchased_at)
            VALUES (?, ?, 0, datetime('now', ?));
            """,
            (user_id, "Демо магазин", f"-{days_ago} day")
        )

        purchase_id = cur.lastrowid

        for product_name, quantity in items:
            conn.execute(
                """
                INSERT INTO purchase_item
                    (purchase_id, product_id, quantity, price)
                SELECT ?, id, ?, price
                FROM product
                WHERE name = ?;
                """,
                (purchase_id, quantity, product_name)
            )

        # Пересчитываем итоговую сумму чека
        conn.execute(
            """
            UPDATE purchase
            SET total_amount = (
                SELECT COALESCE(SUM(price * quantity), 0)
                FROM purchase_item
                WHERE purchase_id = ?
            )
            WHERE id = ?;
            """,
            (purchase_id, purchase_id)
        )


def print_summary(conn):
    """Выводит, сколько данных получилось в базе."""
    products = conn.execute("SELECT COUNT(*) FROM product;").fetchone()[0]
    users = conn.execute("SELECT COUNT(*) FROM app_user;").fetchone()[0]
    purchases = conn.execute("SELECT COUNT(*) FROM purchase;").fetchone()[0]
    stock = conn.execute("SELECT COUNT(*) FROM stock;").fetchone()[0]

    print(f"Продуктов в каталоге: {products}")
    print(f"Пользователей: {users}")
    print(f"Покупок в истории: {purchases}")
    print(f"Позиций в запасах: {stock}")


def create_database():
    """Создаёт базу и заполняет её демо-данными."""
    conn = sqlite3.connect(DB_NAME)

    conn.execute("PRAGMA foreign_keys = ON;")

    create_tables(conn)
    insert_products(conn)

    user_id = insert_demo_user(conn)

    insert_demo_budget(conn, user_id)
    insert_demo_stock(conn, user_id)
    insert_demo_history(conn, user_id)

    conn.commit()

    print(f"Файл {DB_NAME} создан.")
    print_summary(conn)

    conn.close()


def main():
    create_database()


if __name__ == "__main__":
    main()