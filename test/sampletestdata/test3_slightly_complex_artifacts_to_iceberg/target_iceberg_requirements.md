# Target analytics requirement: Iceberg customer_activity_gold

## Target platform
Apache Iceberg table stored in the analytics lakehouse.

## Proposed table name
customer_activity_gold

## Required output columns
- activity_id
- customer_id
- activity_ts
- activity_domain
- source_system
- country
- loyalty_tier
- device_type
- channel
- session_duration_seconds
- order_id
- total_amount
- currency
- item_count
- coupon_code
- is_marketing_opt_in
- ingestion_date

## Transformation expectations
- unify the three source entities into one analytic activity table
- preserve sparse/null fields when a source entity does not provide them
- derive activity_domain from source entity type
- item_count = number of purchase_items
- ingestion_date should align to processing date partition
- output should be partitioned for Iceberg by ingestion_date
