SELECT c.region, SUM(o.revenue) AS total_revenue
FROM orders AS o
JOIN customers AS c ON o.customer_id = c.customer_id
GROUP BY c.region;