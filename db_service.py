import sqlite3

import pandas as pd

DB_NAME = "smartcart.db"


def connect():
    """Подключается к базе данных."""
    conn = sqlite3.connect(DB_NAME)
    return conn


def get_users():
    """Возвращает список всех пользователей."""
    conn = connect()
    df = pd.read_sql_query(
        "SELECT id, username, full_name FROM app_user ORDER BY username;",
        conn
    )
    conn.close()
    return df


def get_products():
    """Возвращает все продукты из каталога."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            id,
            name,
            category,
            unit,
            price,
            calories,
            protein,
            fat,
            carbs
        FROM product
        ORDER BY category, name;
        """,
        conn
    )
    conn.close()
    return df


def get_budget(user_id):
    """Возвращает текущий бюджет пользователя."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            id,
            amount,
            period_days,
            starts_at
        FROM budget
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1;
        """,
        conn,
        params=[user_id]
    )
    conn.close()
    return df


def get_stock(user_id):
    """Возвращает запасы пользователя (что есть дома)."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            s.id AS stock_id,
            p.id AS product_id,
            p.name,
            p.category,
            p.unit,
            s.quantity,
            s.expires_at
        FROM stock s
        JOIN product p ON p.id = s.product_id
        WHERE s.user_id = ?
        ORDER BY p.name;
        """,
        conn,
        params=[user_id]
    )
    conn.close()
    return df


def get_purchase_history(user_id):
    """Возвращает историю покупок пользователя."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            id,
            store,
            total_amount,
            purchased_at
        FROM purchase
        WHERE user_id = ?
        ORDER BY purchased_at DESC;
        """,
        conn,
        params=[user_id]
    )
    conn.close()
    return df


def get_purchase_items(purchase_id):
    """Возвращает товары из конкретной покупки."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            p.id AS product_id,
            p.name,
            pi.quantity,
            pi.price
        FROM purchase_item pi
        JOIN product p ON p.id = pi.product_id
        WHERE pi.purchase_id = ?
        ORDER BY p.name;
        """,
        conn,
        params=[purchase_id]
    )
    conn.close()
    return df


def get_all_purchase_items(user_id):
    """Возвращает все купленные товары пользователя (для анализа истории)."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            p.id AS product_id,
            p.name,
            p.category,
            pi.quantity,
            pur.purchased_at
        FROM purchase_item pi
        JOIN product p ON p.id = pi.product_id
        JOIN purchase pur ON pur.id = pi.purchase_id
        WHERE pur.user_id = ?
        ORDER BY pur.purchased_at DESC;
        """,
        conn,
        params=[user_id]
    )
    conn.close()
    return df


def save_shopping_list(user_id, title, budget_amount, items):
    """
    Сохраняет сгенерированный список покупок в базу.
    items - список словарей с product_id, quantity, estimated_price, reason.
    """
    conn = connect()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO shopping_list (user_id, title, budget_amount, status)
        VALUES (?, ?, ?, 'generated');
        """,
        (user_id, title, budget_amount)
    )
    shopping_list_id = cursor.lastrowid

    for item in items:
        cursor.execute(
            """
            INSERT INTO shopping_list_item
                (shopping_list_id, product_id, quantity, estimated_price, reason, priority)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                shopping_list_id,
                item['product_id'],
                item['quantity'],
                item['estimated_price'],
                item['reason'],
                item.get('priority', 1)
            )
        )

    conn.commit()
    conn.close()

    return shopping_list_id


def get_shopping_lists(user_id):
    """Возвращает все сохранённые списки покупок пользователя."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            id,
            title,
            budget_amount,
            status,
            created_at
        FROM shopping_list
        WHERE user_id = ?
        ORDER BY created_at DESC;
        """,
        conn,
        params=[user_id]
    )
    conn.close()
    return df


def get_shopping_list_items(shopping_list_id):
    """Возвращает товары из сохранённого списка."""
    conn = connect()
    df = pd.read_sql_query(
        """
        SELECT
            p.name,
            p.category,
            p.unit,
            sli.quantity,
            sli.estimated_price,
            sli.reason,
            sli.is_checked
        FROM shopping_list_item sli
        JOIN product p ON p.id = sli.product_id
        WHERE sli.shopping_list_id = ?
        ORDER BY p.category, p.name;
        """,
        conn,
        params=[shopping_list_id]
    )
    conn.close()
    return df