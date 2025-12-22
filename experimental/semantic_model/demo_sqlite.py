import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path(__file__).with_name("semantic_demo.db")


def create_demo_db(db_path: Optional[Path] = None) -> Path:
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    random.seed(42)

    cursor.executescript(
        """
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS products;

        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            region TEXT,
            signup_date DATE
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price REAL
        );

        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date DATE,
            status TEXT,
            channel TEXT,
            total_amount REAL,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            line_total REAL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
        """
    )

    regions = ["North", "South", "East", "West"]
    customers = []
    for customer_id in range(1, 21):
        customers.append(
            (
                customer_id,
                f"Customer {customer_id}",
                random.choice(regions),
                (date(2023, 1, 1) + timedelta(days=random.randint(0, 365))).isoformat(),
            )
        )
    cursor.executemany(
        "INSERT INTO customers (customer_id, name, region, signup_date) VALUES (?, ?, ?, ?)",
        customers,
    )

    categories = ["Electronics", "Home", "Accessories", "Sports"]
    products = []
    for product_id in range(1, 16):
        price = round(random.uniform(10.0, 250.0), 2)
        products.append(
            (
                product_id,
                f"Product {product_id}",
                random.choice(categories),
                price,
            )
        )
    cursor.executemany(
        "INSERT INTO products (product_id, name, category, price) VALUES (?, ?, ?, ?)",
        products,
    )

    statuses = ["completed", "pending", "cancelled"]
    channels = ["online", "store", "partner"]
    orders = []
    order_items = []
    order_id = 1
    order_item_id = 1
    start_date = date(2023, 6, 1)

    for _ in range(60):
        customer_id = random.randint(1, 20)
        order_date = start_date + timedelta(days=random.randint(0, 180))
        status = random.choices(statuses, weights=[0.75, 0.2, 0.05], k=1)[0]
        channel = random.choice(channels)
        orders.append((order_id, customer_id, order_date.isoformat(), status, channel, 0.0))

        item_count = random.randint(1, 4)
        total_amount = 0.0
        for _ in range(item_count):
            product_id = random.randint(1, 15)
            unit_price = next(p[3] for p in products if p[0] == product_id)
            quantity = random.randint(1, 3)
            line_total = round(unit_price * quantity, 2)
            total_amount += line_total
            order_items.append(
                (
                    order_item_id,
                    order_id,
                    product_id,
                    quantity,
                    unit_price,
                    line_total,
                )
            )
            order_item_id += 1

        orders[-1] = (order_id, customer_id, order_date.isoformat(), status, channel, round(total_amount, 2))
        order_id += 1

    cursor.executemany(
        "INSERT INTO orders (order_id, customer_id, order_date, status, channel, total_amount) VALUES (?, ?, ?, ?, ?, ?)",
        orders,
    )
    cursor.executemany(
        "INSERT INTO order_items (order_item_id, order_id, product_id, quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?, ?)",
        order_items,
    )

    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    db_path = create_demo_db()
    print(f"Created demo SQLite database at {db_path}")
