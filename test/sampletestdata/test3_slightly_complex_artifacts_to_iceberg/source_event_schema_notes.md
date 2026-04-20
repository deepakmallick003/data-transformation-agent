# Source event schema notes

## customer_profile_events
- event_id: string
- customer_id: string
- event_ts: timestamp
- event_type: string
- source_system: string
- profile.country: string
- profile.marketing_opt_in: boolean
- profile.loyalty_tier: string|null

## customer_session_events
- event_id: string
- customer_id: string
- session_id: string
- event_ts: timestamp
- session.device_type: string
- session.channel: string
- session.duration_seconds: integer|null

## customer_purchase_events
- event_id: string
- customer_id: string
- order_id: string
- event_ts: timestamp
- currency: string
- total_amount: decimal(12,2)
- purchase_items: array<struct<sku:string, quantity:int, unit_price:decimal(12,2)>>
- coupon_code: string|null

## Known issues
- event_type values are not consistently documented across teams
- some older producers omit source_system
- duration_seconds may be missing
