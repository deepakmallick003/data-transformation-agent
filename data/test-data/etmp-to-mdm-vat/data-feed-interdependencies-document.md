# Data Feed Interdependencies Document  

*HMRC / KANO Document Generation PoC*  
*Version: v0.1*  
*Date: 14 Apr 2026*  
*Author: D. Mallick*  
*Status: Draft*  

---

## Document Properties

| Property | Value |
|-----------|-------|
| **Author** | D. Mallick |
| **Date** | 14 Apr 2026 |
| **Version** | 0.1 |
| **Status** | Draft |

---

## Distribution List

| Name | Company | Reviewer | Approver |
|------|----------|-----------|-----------|
| Sarah Johnson | HMRC | Yes | No |
| Rajesh Patel | NTT DATA | Yes | No |
| Michael Chen | HMRC | No | Yes |
| Emma Williams | NTT DATA | Yes | No |
| David Thompson | HMRC | Yes | No |

---

## Table of Contents

1. [Introduction](#1-introduction)  
    1.1 [Purpose and Background](#11-purpose-and-background)  
    1.2 [Scope](#12-scope)  
    1.3 [Audience](#13-audience)  
2. [Data Landscape Overview](#2-data-landscape-overview)  
3. [Data Feed Listing](#3-data-feed-listing)  
4. [Data Feed Interdependencies](#4-data-feed-interdependencies)  
5. [Data Feed Load Sequence](#5-data-feed-load-sequence)  

---

## 1. Introduction

### 1.1 Purpose and Background

This document defines the interdependencies and sequencing of data feeds within the HMRC Tax Data Landscape, specifically focusing on feeds from the Enterprise Tax Management Platform (ETMP) to the Master Data Management (MDM) Data Warehouse. Understanding these dependencies is critical for ensuring data integrity, maintaining load schedules, and supporting operational and analytical reporting requirements.

**Assumption:** This document was created to support the transition from legacy batch processing to a modern event-driven data architecture, requiring clear definition of feed dependencies for orchestration automation.

### 1.2 Scope

This document covers the following systems within the HMRC Tax Data Landscape:

- **Source Systems**: ETMP (Enterprise Tax Management Platform), DMS (Document Management System), CRM (Customer Relationship Management)
- **Target System**: MDM Data Warehouse
- **Reference Data**: Central Reference Data Repository

The document focuses on VAT-related data feeds and their upstream/downstream dependencies.

### 1.3 Audience

- Data Architects (HMRC & NTT DATA)
- Data Engineers
- ETL Developers
- Business Analysts
- Operations Support Teams

---

## 2. Data Landscape Overview

The HMRC Tax Data Landscape consists of multiple source systems feeding into the MDM Data Warehouse, which serves as the central repository for analytical and reporting purposes. The diagram below illustrates the high-level data flow:

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         SOURCE SYSTEMS                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐      │
│  │    ETMP      │     │     DMS      │     │     CRM      │      │
│  │ (Tax Mgmt)   │     │  (Document)  │     │ (Customer)   │      │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘      │
│         │                    │                    │               │
└─────────┼────────────────────┼────────────────────┼───────────────┘
          │                    │                    │
          │ Daily              │ Daily              │ Weekly
          │ SFTP               │ SFTP               │ SFTP
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       MDM LANDING ZONE                              │
│                          (SFTP Server)                              │
└─────────────────────────────────────────────────────────────────────┘
          │
          │ Orchestrated Load (Control-M)
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MDM DATA WAREHOUSE                               │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │   Dimension     │  │   Fact Tables   │  │  Reference Data │   │
│  │    Tables       │  │                 │  │                 │   │
│  │  - DIM_TAXPAYER │  │ - FACT_VAT_RET  │  │ - REF_SECTOR    │   │
│  │  - DIM_DATE     │  │ - FACT_VAT_LINE │  │ - REF_COUNTRY   │   │
│  │  - DIM_CUSTOMER │  │ - FACT_PAYMENT  │  │                 │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │
          │ Downstream Consumption
          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   REPORTING & ANALYTICS                             │
├─────────────────────────────────────────────────────────────────────┤
│  - VAT Compliance Dashboard                                         │
│  - Tax Analytics Platform                                           │
│  - Business Intelligence Reports                                    │
│  - Regulatory Reporting                                             │
└─────────────────────────────────────────────────────────────────────┘
```

**System Descriptions:**

- **ETMP (Enterprise Tax Management Platform)**: Core tax administration system managing VAT returns, tax assessments, and taxpayer records
- **DMS (Document Management System)**: Stores and manages tax-related documents, correspondence, and supporting evidence
- **CRM (Customer Relationship Management)**: Manages customer interactions, support tickets, and communication history
- **MDM Data Warehouse**: Central data repository using dimensional modeling for analytical and reporting purposes
- **Central Reference Data Repository**: Maintains reference and master data (e.g., sector codes, country codes, tax rates)

**Assumption:** The data landscape supports approximately 2.5 million active VAT-registered businesses with an average of 50,000 daily VAT return submissions.

---

## 3. Data Feed Listing

The table below details all data feeds within the Tax Data Landscape that are in scope for this document.

| Data Feed Ref | Data Feed Name | Source System | Target System | Feed Format | Load Type | Frequency | Delivery Method | Status | Description |
|----------------|----------------|----------------|----------------|--------------|------------|-------------|------------------|----------|--------------|
| REF-CENTRAL-001 | Sector Codes Reference Data | Central Reference Data | MDM Data Warehouse | CSV | Full | Quarterly | SFTP | Active | Business sector classification codes and descriptions |
| REF-CENTRAL-002 | Country Codes Reference Data | Central Reference Data | MDM Data Warehouse | CSV | Full | Annually | SFTP | Active | ISO country codes and descriptions |
| REF-CENTRAL-003 | VAT Rate Reference Data | Central Reference Data | MDM Data Warehouse | CSV | Full | Monthly | SFTP | Active | Current and historical VAT rates by jurisdiction |
| DIM-ETMP-001 | Date Dimension | N/A (Generated) | MDM Data Warehouse | N/A | Full | One-time | N/A | Active | Pre-populated date dimension table spanning 2000-2050 |
| VAT-ETMP-001 | VAT Returns Daily Extract | ETMP | MDM Data Warehouse | CSV | Incremental | Daily | SFTP | Active | Daily extract of VAT return submissions including header, line item, and taxpayer data |
| PAY-ETMP-002 | VAT Payment Transactions | ETMP | MDM Data Warehouse | CSV | Incremental | Daily | SFTP | Active | VAT payment and refund transaction records |
| REG-ETMP-003 | Taxpayer Registration Changes | ETMP | MDM Data Warehouse | CSV | Incremental | Daily | SFTP | Active | New registrations, deregistrations, and updates to taxpayer details |
| DOC-DMS-001 | VAT Return Supporting Documents | DMS | MDM Data Warehouse | CSV | Incremental | Daily | SFTP | Active | Metadata for supporting documents linked to VAT returns |
| CUS-CRM-001 | Customer Interaction History | CRM | MDM Data Warehouse | CSV | Incremental | Weekly | SFTP | Active | Customer service interactions and support tickets |
| AGG-VAT-001 | VAT Monthly Aggregates | MDM Data Warehouse | MDM Data Warehouse | N/A | Full | Monthly | N/A | Active | Pre-calculated monthly VAT aggregates for reporting performance |

**Assumption:** Additional feeds from PAYE (Pay As You Earn) and Corporation Tax systems exist but are out of scope for this document version.

---

## 4. Data Feed Interdependencies

This section defines the dependencies between data feeds, indicating which feeds must be loaded before others to maintain referential integrity and data quality.

| Data Feed Ref | Data Feed Name | Dependent On Data Feed Ref | Dependent On Data Feed Name | Dependency Logic | Description |
|----------------|----------------|-----------------------------|-----------------------------|------------------|--------------|
| VAT-ETMP-001 | VAT Returns Daily Extract | REF-CENTRAL-001 | Sector Codes Reference Data | Sector code lookup required for taxpayer dimension enrichment | VAT Returns feed performs a lookup against REF_SECTOR_CODES to enrich DIM_TAXPAYER with sector descriptions |
| VAT-ETMP-001 | VAT Returns Daily Extract | DIM-ETMP-001 | Date Dimension | Date dimension keys required for submission date and period date | VAT Returns feed joins to DIM_DATE to obtain surrogate keys for FACT_VAT_RETURN |
| VAT-ETMP-001 | VAT Returns Daily Extract | REG-ETMP-003 | Taxpayer Registration Changes | Taxpayer dimension must be current before loading VAT returns | VAT Returns feed requires DIM_TAXPAYER to be fully updated with latest registrations and changes before lookup |
| PAY-ETMP-002 | VAT Payment Transactions | VAT-ETMP-001 | VAT Returns Daily Extract | Payment records reference VAT return IDs | Payment transactions link to VAT returns; FACT_VAT_RETURN must exist before loading FACT_VAT_PAYMENT |
| DOC-DMS-001 | VAT Return Supporting Documents | VAT-ETMP-001 | VAT Returns Daily Extract | Documents are linked to VAT return records | Document metadata references RETURN_ID from FACT_VAT_RETURN |
| AGG-VAT-001 | VAT Monthly Aggregates | VAT-ETMP-001 | VAT Returns Daily Extract | Aggregates are calculated from VAT return facts | Monthly aggregates require all daily VAT returns for the month to be loaded before calculation |
| AGG-VAT-001 | VAT Monthly Aggregates | PAY-ETMP-002 | VAT Payment Transactions | Aggregates include payment information | Monthly aggregates require all daily payment transactions for the month to be loaded |

**Assumption:** If a dependent feed fails to load, the downstream feed is automatically skipped by the Control-M orchestration layer and retried in the next scheduled window.

---

## 5. Data Feed Load Sequence

This section defines the order in which data feeds should be loaded into the MDM Data Warehouse to respect dependencies and ensure data integrity.

| Order | Data Feed Ref | Data Feed Name | Description |
|--------|----------------|----------------|--------------|
| 1 | DIM-ETMP-001 | Date Dimension | Pre-populated dimension table; one-time load, extended annually |
| 2 | REF-CENTRAL-001 | Sector Codes Reference Data | Reference data load (quarterly refresh) |
| 3 | REF-CENTRAL-002 | Country Codes Reference Data | Reference data load (annual refresh) |
| 4 | REF-CENTRAL-003 | VAT Rate Reference Data | Reference data load (monthly refresh) |
| 5 | REG-ETMP-003 | Taxpayer Registration Changes | Taxpayer dimension updates must occur before VAT returns |
| 6 | VAT-ETMP-001 | VAT Returns Daily Extract | Primary VAT data feed; loads FACT_VAT_RETURN and FACT_VAT_RETURN_LINE |
| 7 | PAY-ETMP-002 | VAT Payment Transactions | Dependent on VAT returns being loaded first |
| 8 | DOC-DMS-001 | VAT Return Supporting Documents | Dependent on VAT returns being loaded first |
| 9 | CUS-CRM-001 | Customer Interaction History | No hard dependency; can load in parallel with orders 6-8 |
| 10 | AGG-VAT-001 | VAT Monthly Aggregates | Runs monthly after all daily feeds are complete for the period |

**Load Windows:**

- **Reference Data (Orders 2-4)**: Loads run at scheduled intervals (monthly/quarterly/annually) typically during off-peak hours (Sunday 01:00 GMT)
- **Taxpayer Registration (Order 5)**: Daily at 02:00 GMT
- **VAT Returns (Order 6)**: Daily at 03:00 GMT (after taxpayer registration completes)
- **Payment Transactions (Order 7)**: Daily at 04:00 GMT (after VAT returns complete)
- **Supporting Documents (Order 8)**: Daily at 04:30 GMT (after VAT returns complete)
- **Customer Interaction History (Order 9)**: Weekly on Monday at 03:00 GMT
- **Monthly Aggregates (Order 10)**: Monthly on the 2nd day of the month at 06:00 GMT

**Parallel Processing:**

The following feeds can be loaded in parallel as they have no interdependencies:

- REF-CENTRAL-001, REF-CENTRAL-002, REF-CENTRAL-003 (when scheduled on the same day)
- PAY-ETMP-002, DOC-DMS-001, CUS-CRM-001 (once VAT-ETMP-001 is complete)

**Failure Scenarios:**

| Scenario | Impact | Resolution |
|----------|--------|------------|
| REF-CENTRAL-001 fails | VAT-ETMP-001 proceeds but sector descriptions will be NULL | Alert sent; manual resolution required; re-run enrichment process |
| DIM-ETMP-001 missing | VAT-ETMP-001 fails with date lookup errors | Critical failure; manual intervention required; dimension must be extended |
| REG-ETMP-003 fails | VAT-ETMP-001 proceeds but may have stale taxpayer data | Warning issued; proceed with load; investigate and reprocess if needed |
| VAT-ETMP-001 fails | PAY-ETMP-002, DOC-DMS-001 are skipped | Downstream feeds automatically skipped; retry in next window |
| PAY-ETMP-002 fails | AGG-VAT-001 skipped if running in same period | Monthly aggregates skipped; must be reprocessed once payment feed succeeds |

**Assumption:** The Control-M orchestration layer automatically manages feed dependencies using predecessor/successor job relationships and conditional logic. Manual overrides are available for emergency scenarios but require approval from the Data Architecture team.

---

*© NTT DATA, Inc. — 2025*  
*Page 1 of 3*
