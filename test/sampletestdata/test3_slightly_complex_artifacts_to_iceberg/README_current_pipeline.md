# Current telemetry ingestion pipeline

This service ingests customer activity events from multiple internal producers and writes normalized parquet files into an S3 landing zone every 15 minutes.

## Current source entities
- customer_profile_events
- customer_session_events
- customer_purchase_events

## Current storage layout
- s3://acme-raw-landing/customer_profile_events/dt=YYYY-MM-DD/
- s3://acme-raw-landing/customer_session_events/dt=YYYY-MM-DD/
- s3://acme-raw-landing/customer_purchase_events/dt=YYYY-MM-DD/

## Current format
Parquet, partitioned by dt.

## Current operational notes
- producer schemas are not always perfectly aligned
- some events may arrive late
- purchase events may contain nested item arrays
- GDPR deletions are handled separately by downstream jobs
