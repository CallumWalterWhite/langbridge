import os
import sqlite3
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
            join_date DATE
        );

        CREATE TABLE shops (
            shop_id INTEGER PRIMARY KEY,
            shop_name TEXT NOT NULL,
            location TEXT,
            manager TEXT
        );

        CREATE TABLE products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT,
            price DECIMAL(10,2),
            stock INTEGER
        );

        CREATE TABLE sales (
            sale_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            shop_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            sale_date DATE,
            total_amount DECIMAL(10,2),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
            FOREIGN KEY (shop_id) REFERENCES shops(shop_id),
            FOREIGN KEY (product_id) REFERENCES products(product_id)
        );
    ''')

    # Insert sample data
    c.executescript('''
        INSERT INTO customers (name, email, phone, join_date) VALUES 
            ('John Doe', 'john@example.com', '555-0101', '2023-01-01'),
            ('Jane Smith', 'jane@example.com', '555-0102', '2023-01-15'),
            ('Bob Wilson', 'bob@example.com', '555-0103', '2023-02-01');

        INSERT INTO shops (shop_name, location, manager) VALUES
            ('Downtown Store', 'City Center', 'Alice Johnson'),
            ('Mall Shop', 'West Mall', 'Bob Brown'),
            ('Express Store', 'East Side', 'Carol White');

        INSERT INTO products (name, category, price, stock) VALUES
            ('Laptop', 'Electronics', 999.99, 50),
            ('Smartphone', 'Electronics', 599.99, 100),
            ('Headphones', 'Accessories', 99.99, 200),
            ('Tablet', 'Electronics', 399.99, 75);

        INSERT INTO sales (customer_id, shop_id, product_id, quantity, sale_date, total_amount) VALUES
            (1, 1, 1, 1, '2023-03-01', 999.99),
            (2, 2, 2, 2, '2023-03-02', 1199.98),
            (3, 3, 3, 3, '2023-03-03', 299.97);
    ''')

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
