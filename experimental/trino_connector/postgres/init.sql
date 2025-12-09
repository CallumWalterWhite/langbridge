CREATE TABLE IF NOT EXISTS customers (
    customer_id INT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    region TEXT
);

INSERT INTO customers (customer_id, name, email, region) VALUES
    (1, 'Ada Lovelace', 'ada@example.com', 'EMEA'),
    (2, 'Alan Turing', 'alan@example.com', 'EMEA'),
    (3, 'Grace Hopper', 'grace@example.com', 'NA'),
    (4, 'Margaret Hamilton', 'margaret@example.com', 'NA')
ON CONFLICT (customer_id) DO NOTHING;
