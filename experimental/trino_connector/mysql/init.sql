CREATE DATABASE IF NOT EXISTS ordersdb;
USE ordersdb;

CREATE TABLE IF NOT EXISTS orders (
    order_id INT PRIMARY KEY,
    customer_id INT NOT NULL,
    order_total DECIMAL(10,2) NOT NULL,
    status VARCHAR(32) NOT NULL
);

INSERT INTO orders (order_id, customer_id, order_total, status) VALUES
    (1, 1, 120.50, 'shipped'),
    (2, 1, 85.00, 'processing'),
    (3, 2, 42.25, 'canceled'),
    (4, 3, 305.10, 'shipped'),
    (5, 4, 22.00, 'processing')
ON DUPLICATE KEY UPDATE order_id = VALUES(order_id);

CREATE INDEX idx_orders_customer_id ON orders(customer_id);
