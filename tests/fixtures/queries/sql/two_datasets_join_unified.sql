SELECT *
FROM orders o
JOIN campaigns c ON o.campaign_id = c.campaign_id
WHERE c.campaign_name = 'Summer Sale';