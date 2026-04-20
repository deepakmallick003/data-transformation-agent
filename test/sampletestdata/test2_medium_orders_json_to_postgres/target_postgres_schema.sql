CREATE TABLE staging_order_header (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    customer_name TEXT,
    customer_email TEXT,
    shipping_country TEXT,
    shipping_city TEXT,
    order_status TEXT,
    created_at TIMESTAMP,
    item_count INTEGER,
    order_total NUMERIC(12,2),
    has_discount BOOLEAN,
    discount_code TEXT,
    source_batch_id TEXT
);

CREATE TABLE staging_order_item (
    order_id TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    sku TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    line_total NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (order_id, line_number)
);
