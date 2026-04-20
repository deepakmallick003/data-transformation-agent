# Mapping expectations

## Source
- top-level batch metadata
- orders array
- customer object
- shippingAddress object
- items array

## Target
Two Postgres staging tables:
1. staging_order_header
2. staging_order_item

## Key rules
- one header row per order
- one item row per item
- item_count = number of items
- order_total = sum(quantity * unitPrice)
- has_discount = true when discountCode exists
- cancelled orders with no items should still produce a header row
- missing customer email should be flagged in validation
