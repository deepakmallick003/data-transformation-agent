# Target contract: CRM Gold Customer View

## Required output
- customer_master.json

## Fields
- customerId: string
- firstName: string
- lastName: string
- emailAddress: string|null
- customerStatus: string
- region: string
- spendTier: string
- isActive: boolean
- lastOrderDate: string|null

## Rules
1. Split full_name into firstName and lastName.
2. status mapping:
   - active -> ACTIVE
   - inactive -> INACTIVE
   - pending -> PROSPECT
3. region mapping:
   - UK -> EMEA
   - Portugal -> EMEA
   - India -> APAC
   - else -> OTHER
4. isActive = true only when status is active.
5. spendTier:
   - >= 5000 -> PLATINUM
   - >= 1000 -> GOLD
   - > 0 -> SILVER
   - 0 -> NEW
6. blank last_order_date -> null
