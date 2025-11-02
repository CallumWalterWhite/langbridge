import os
import random
import sqlite3
from datetime import datetime, timedelta

import yaml
from sqlglot import parse_one, transpile
from dotenv import load_dotenv
from openai import OpenAI

from llm import OpenAIClient
from generator import generate_base_sql

load_dotenv()

def create_openai_client():
    return OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )

def create_dummy_db():
    conn = sqlite3.connect('sales.db')
    c = conn.cursor()
    
    random.seed(42)

    c.executescript('''
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS shops;
        DROP TABLE IF EXISTS products;
        DROP TABLE IF EXISTS sales;
    ''')

    c.executescript('''
        CREATE TABLE customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            join_date DATE,
            loyalty_level TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            postal_code TEXT,
            birth_date DATE,
            marketing_opt_in INTEGER
        );

        CREATE TABLE shops (
            shop_id INTEGER PRIMARY KEY,
            shop_name TEXT NOT NULL,
            location TEXT,
            manager TEXT,
            region TEXT,
            opening_date DATE,
            square_feet INTEGER,
            floors INTEGER,
            is_flagship INTEGER,
            support_email TEXT
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price DECIMAL(10,2),
            stock INTEGER,
            brand TEXT,
            supplier TEXT,
            weight_kg DECIMAL(10,2),
            color TEXT,
            warranty_months INTEGER,
            release_date DATE,
            rating DECIMAL(3,2)
        );

        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            shop_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price DECIMAL(10,2),
            sale_date DATE,
            total_amount DECIMAL(10,2),
            discount_amount DECIMAL(10,2),
            tax_amount DECIMAL(10,2),
            payment_method TEXT,
            sales_channel TEXT,
            delivery_type TEXT,
            returned INTEGER,
            sales_rep TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    ''')

    loyalty_levels = ["Bronze", "Silver", "Gold", "Platinum"]
    cities = ["Springfield", "Riverside", "Franklin", "Greenville", "Madison", "Clinton"]
    states = ["CA", "NY", "TX", "WA", "IL", "FL"]
    streets = ["Oak", "Maple", "Pine", "Cedar", "Elm", "Willow", "Birch", "Walnut"]
    marketing_opt_in_rate = 0.7

    customer_count = 1000
    base_customer_join = datetime(2020, 1, 1)
    customer_rows = []
    for idx in range(customer_count):
        name = f"Customer {idx + 1}"
        email = f"customer{idx + 1}@example.com"
        phone = f"555-{1000 + idx:04d}"
        join_date = base_customer_join + timedelta(days=random.randint(0, 365 * 3))
        loyalty_level = random.choice(loyalty_levels)
        address = f"{random.randint(100, 9999)} {random.choice(streets)} St"
        city = random.choice(cities)
        state = random.choice(states)
        postal_code = f"{random.randint(10000, 99999)}"
        birth_date = datetime(1960, 1, 1) + timedelta(days=random.randint(0, 365 * 40))
        marketing_opt_in = 1 if random.random() < marketing_opt_in_rate else 0
        customer_rows.append(
            (
                name,
                email,
                phone,
                join_date.date().isoformat(),
                loyalty_level,
                address,
                city,
                state,
                postal_code,
                birth_date.date().isoformat(),
                marketing_opt_in,
            )
        )

    c.executemany(
        '''
        INSERT INTO customers (
            name,
            email,
            phone,
            join_date,
            loyalty_level,
            address,
            city,
            state,
            postal_code,
            birth_date,
            marketing_opt_in
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        customer_rows,
    )

    shop_names = [
        "Downtown Store",
        "Mall Shop",
        "Express Store",
        "Warehouse Outlet",
        "Airport Kiosk",
        "Suburban Plaza",
        "Tech Hub",
        "Uptown Flagship",
        "Harbor Boutique",
        "Campus Pop-up",
        "Industrial Annex",
        "Community Market",
    ]
    regions = ["West", "East", "Central", "South", "Midwest"]
    managers = ["Alex Johnson", "Taylor Smith", "Jordan Clark", "Morgan Lee", "Robin Davis"]
    base_opening = datetime(2015, 1, 1)
    shop_rows = []
    for idx, shop_name in enumerate(shop_names, start=1):
        location = f"{shop_name.split()[0]} District"
        manager = random.choice(managers)
        region = random.choice(regions)
        opening_date = base_opening + timedelta(days=random.randint(0, 365 * 5))
        square_feet = random.randint(1200, 5000)
        floors = random.randint(1, 3)
        is_flagship = 1 if "Flagship" in shop_name or idx % 5 == 0 else 0
        support_email = f"{shop_name.lower().replace(' ', '_')}@shops.example.com"
        shop_rows.append(
            (
                shop_name,
                location,
                manager,
                region,
                opening_date.date().isoformat(),
                square_feet,
                floors,
                is_flagship,
                support_email,
            )
        )

    c.executemany(
        '''
        INSERT INTO shops (
            shop_name,
            location,
            manager,
            region,
            opening_date,
            square_feet,
            floors,
            is_flagship,
            support_email
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        shop_rows,
    )

    categories = ["Electronics", "Accessories", "Home Office", "Gaming", "Audio", "Wearables"]
    brands = ["Acme", "Globex", "Initech", "Umbra", "Vortex", "Zenith"]
    suppliers = ["North Supply", "Delta Logistics", "Prime Wholesale", "Metro Distribution"]
    colors = ["Black", "White", "Silver", "Blue", "Red", "Gray"]
    product_count = 250
    base_release = datetime(2018, 1, 1)
    product_rows = []
    product_prices = []
    for idx in range(product_count):
        category = random.choice(categories)
        name = f"{category} Item {idx + 1}"
        price = round(random.uniform(25.0, 1999.0), 2)
        stock = random.randint(10, 1000)
        brand = random.choice(brands)
        supplier = random.choice(suppliers)
        weight_kg = round(random.uniform(0.1, 20.0), 2)
        color = random.choice(colors)
        warranty_months = random.choice([12, 24, 36, 48])
        release_date = base_release + timedelta(days=random.randint(0, 365 * 6))
        rating = round(random.uniform(2.5, 5.0), 2)
        product_rows.append(
            (
                name,
                category,
                price,
                stock,
                brand,
                supplier,
                weight_kg,
                color,
                warranty_months,
                release_date.date().isoformat(),
                rating,
            )
        )
        product_prices.append(price)

    c.executemany(
        '''
        INSERT INTO products (
            name,
            category,
            price,
            stock,
            brand,
            supplier,
            weight_kg,
            color,
            warranty_months,
            release_date,
            rating
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        product_rows,
    )

    payment_methods = ["Credit Card", "Debit Card", "Cash", "Gift Card", "Digital Wallet"]
    sales_channels = ["In-Store", "Online", "Mobile", "Partner"]
    delivery_types = ["In-Store Pickup", "Courier", "Same-Day", "Locker Pickup"]
    sales_reps = [f"Rep {i}" for i in range(1, 31)]
    base_sale_date = datetime(2021, 1, 1)
    sales_count = 10000
    sales_rows = []
    for sale_id in range(sales_count):
        customer_id = random.randint(1, customer_count)
        shop_id = random.randint(1, len(shop_rows))
        product_id = random.randint(1, product_count)
        quantity = random.randint(1, 5)
        base_price = product_prices[product_id - 1]
        # Simulate slight price fluctuations at sale time
        unit_price = round(base_price * random.uniform(0.95, 1.05), 2)
        sale_date = base_sale_date + timedelta(days=random.randint(0, 365 * 2))
        discount_rate = random.choice([0.0, 0.05, 0.1, 0.15])
        discount_amount = round(unit_price * quantity * discount_rate, 2)
        tax_amount = round((unit_price * quantity - discount_amount) * 0.0825, 2)
        total_amount = round(unit_price * quantity - discount_amount + tax_amount, 2)
        payment_method = random.choice(payment_methods)
        sales_channel = random.choice(sales_channels)
        delivery_type = random.choice(delivery_types)
        returned = 1 if random.random() < 0.03 else 0
        sales_rep = random.choice(sales_reps)
        sales_rows.append(
            (
                customer_id,
                shop_id,
                product_id,
                quantity,
                unit_price,
                sale_date.date().isoformat(),
                total_amount,
                discount_amount,
                tax_amount,
                payment_method,
                sales_channel,
                delivery_type,
                returned,
                sales_rep,
            )
        )

    c.executemany(
        '''
        INSERT INTO sales (
            customer_id,
            shop_id,
            product_id,
            quantity,
            unit_price,
            sale_date,
            total_amount,
            discount_amount,
            tax_amount,
            payment_method,
            sales_channel,
            delivery_type,
            returned,
            sales_rep
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        sales_rows,
    )

    conn.commit()
    conn.close()

def execute_sqlite_query(sql_query):
    conn = sqlite3.connect('sales.db')
    cursor = conn.cursor()
    
    try:
        # Convert to SQLite dialect
        sqlite_sql = transpile(sql_query, read='postgres', write='sqlite')[0]
        
        # Execute query
        cursor.execute(sqlite_sql)
        
        # Fetch column names from cursor description
        columns = [description[0] for description in cursor.description]
        
        # Fetch results
        results = cursor.fetchall()
        
        return {
            'columns': columns,
            'rows': results
        }
    except Exception as e:
        print(f"Error executing query: {e}")
        return None
    finally:
        conn.close()

if __name__ == "__main__":
    create_dummy_db()
    model_yaml = open('semantic_model.yml', 'r').read()
    request = "When was the last sale of a Electronics across all malls?"
    openai_client = OpenAIClient(OpenAI(api_key=os.environ.get("OPENAI_API_KEY")))
    
    sql = generate_base_sql(model_yaml, request, openai_client, dialect="ansi")
    print("Generated SQL:", sql)
    
    # Execute query and get results
    results = execute_sqlite_query(sql)
    
    if results:
        # Print results in a formatted way
        print("\nQuery Results:")
        print("Columns:", ", ".join(results['columns']))
        print("\nRows:")
        for row in results['rows']:
            print(row)
