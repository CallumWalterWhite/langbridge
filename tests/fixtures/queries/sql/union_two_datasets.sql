SELECT DISTINCT customer_id
FROM orders
UNION ALL
SELECT DISTINCT customer_id
FROM customers;