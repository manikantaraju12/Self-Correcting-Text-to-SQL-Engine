CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    region VARCHAR(80) NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    cust_id INTEGER NOT NULL REFERENCES customers(customer_id),
    total_amount NUMERIC(10, 2) NOT NULL
);

CREATE TABLE line_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price >= 0)
);

INSERT INTO customers (customer_id, name, region)
SELECT customer_id,
       'Customer ' || customer_id,
       CASE WHEN customer_id % 11 = 0 THEN NULL
            ELSE (ARRAY['New York', 'California', 'Texas', 'Florida', 'Washington'])[((customer_id - 1) % 5) + 1]
       END
FROM generate_series(1, 150) AS series(customer_id);

INSERT INTO orders (id, cust_id, total_amount)
SELECT order_id, ((order_id - 1) % 150) + 1, 25 + (order_id * 17 % 975)
FROM generate_series(1, 750) AS series(order_id);

INSERT INTO line_items (id, order_id, qty, unit_price)
SELECT item_id, ((item_id - 1) % 750) + 1, (item_id % 5) + 1, 5 + (item_id * 3 % 95)
FROM generate_series(1, 1500) AS series(item_id);

CREATE INDEX idx_orders_cust_id ON orders(cust_id);
CREATE INDEX idx_line_items_order_id ON line_items(order_id);