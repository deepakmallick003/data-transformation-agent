# Data Feed Transformation Document  

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

---

## Table of Contents

1. [Introduction](#1-introduction)  
    1.1 [Purpose and Background](#11-purpose-and-background)  
    1.2 [Scope](#12-scope)  
    1.3 [Audience](#13-audience)  
2. [Description](#2-description)  
3. [Source System Overview](#3-source-system-overview)  
    3.1 [Source System Data Model](#31-source-system-data-model)  
    3.2 [Source Data Feed](#32-source-data-feed)  
4. [Target Data Model](#4-target-data-model)  
5. [Data Load Overview](#5-data-load-overview)  
6. [Source to Target Mapping](#6-source-to-target-mapping)  
7. [Transformation Rules](#7-transformation-rules)  
8. [Error Handling & Rejection Rules](#8-error-handling--rejection-rules)  
9. [Load Dependencies & Schedule](#9-load-dependencies--schedule)  
10. [Appendix A – Reference Data](#10-appendix-a--reference-data)  
11. [Appendix B – Sample Files](#11-appendix-b--sample-files)  

---

## 1. Introduction

### 1.1 Purpose and Background

This document defines the transformation logic for loading VAT return data from the ETMP system into the MDM Data Warehouse. The transformation supports business intelligence and compliance reporting by standardizing, enriching, and validating VAT data before loading it into dimensional and fact tables in the target warehouse.

**Assumption:** The transformation was designed to support Type 2 slowly changing dimensions (SCD) for taxpayer data to maintain historical accuracy for audit purposes.

### 1.2 Scope

This transformation document covers the VAT Returns data feed (Feed Ref: VAT-ETMP-001) which includes:

- Transformation of VAT return header data into the FACT_VAT_RETURN table
- Transformation of VAT return line data into the FACT_VAT_RETURN_LINE table
- Transformation of taxpayer registration data into the DIM_TAXPAYER table

### 1.3 Audience

- Data Engineers (HMRC & NTT DATA)
- ETL Developers
- Data Warehouse Architects
- Business Analysts (VAT Operations)

---

## 2. Description

This transformation processes the daily incremental VAT Returns data feed from ETMP and loads it into the MDM Data Warehouse. The transformation includes data quality checks, business rule validations, reference data lookups, and dimension lookups. The target schema follows a dimensional model (star schema) optimized for analytical queries and reporting.

**Assumption:** The transformation is implemented using Informatica PowerCenter with reusable transformation logic stored in the shared library.

---

## 3. Source System Overview

### 3.1 Source System Data Model

The source system (ETMP) follows a transactional data model with the following key entities:

```text
┌──────────────────────────┐
│ TAXPAYER_REGISTRATION    │
├──────────────────────────┤
│ PK: VRN                  │
│     BUSINESS_NAME        │
│     REGISTRATION_DATE    │
│     STATUS               │
└────────┬─────────────────┘
         │
         │ 1:N
         │
┌────────▼─────────────────┐         ┌──────────────────────────┐
│ VAT_RETURN_HEADER        │         │ VAT_RETURN_LINE          │
├──────────────────────────┤◄────────┤──────────────────────────┤
│ PK: RETURN_ID            │  1:N    │ PK: RETURN_LINE_ID       │
│ FK: VRN                  │         │ FK: RETURN_ID            │
│     PERIOD_KEY           │         │     BOX_NUMBER           │
│     SUBMISSION_DATE      │         │     BOX_VALUE            │
│     TOTAL_VAT_DUE        │         │                          │
└──────────────────────────┘         └──────────────────────────┘
```

### 3.2 Source Data Feed

The source data feed consists of three CSV files as detailed in the Data Feed Specification document (VAT-ETMP-001):

- **VAT_RETURN_HEADER_YYYYMMDD.csv**: Contains VAT return header information
- **VAT_RETURN_LINE_YYYYMMDD.csv**: Contains line-level detail for each return
- **TAXPAYER_REG_YYYYMMDD.csv**: Contains taxpayer registration master data

**Reference:** See Data Feed Specification document VAT-ETMP-001 for complete field definitions.

---

## 4. Target Data Model

The target data warehouse uses a dimensional model (star schema) with the following entities:

```text
┌──────────────────────────┐       ┌──────────────────────────┐
│ DIM_TAXPAYER             │       │ DIM_DATE                 │
├──────────────────────────┤       ├──────────────────────────┤
│ PK: TAXPAYER_KEY         │       │ PK: DATE_KEY             │
│     VRN                  │       │     DATE_VALUE           │
│     BUSINESS_NAME        │       │     YEAR                 │
│     REGISTRATION_DATE    │       │     QUARTER              │
│     EFFECTIVE_FROM_DATE  │       │     MONTH                │
│     EFFECTIVE_TO_DATE    │       │                          │
│     CURRENT_FLAG         │       └────────┬─────────────────┘
└────────┬─────────────────┘                │
         │                                  │
         │ N:1                           N:1│
         │                                  │
┌────────▼──────────────────────────────────▼──┐
│ FACT_VAT_RETURN                              │
├──────────────────────────────────────────────┤
│ PK: VAT_RETURN_KEY                           │
│ FK: TAXPAYER_KEY                             │
│ FK: SUBMISSION_DATE_KEY                      │
│ FK: PERIOD_DATE_KEY                          │
│     RETURN_ID                                │
│     RETURN_TYPE                              │
│     TOTAL_VAT_DUE                            │
│     LOAD_DATE                                │
└────────┬─────────────────────────────────────┘
         │
         │ 1:N
         │
┌────────▼──────────────────────────────────────┐
│ FACT_VAT_RETURN_LINE                          │
├───────────────────────────────────────────────┤
│ PK: VAT_RETURN_LINE_KEY                       │
│ FK: VAT_RETURN_KEY                            │
│     RETURN_LINE_ID                            │
│     BOX_NUMBER                                │
│     BOX_DESCRIPTION                           │
│     BOX_VALUE                                 │
│     LOAD_DATE                                 │
└───────────────────────────────────────────────┘
```

### Table: MDM_DW.DIM_TAXPAYER (Type 2 SCD)

| Table Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) | Example Values |
|-------------|-------------|-------------|--------------------|----------------|-----------|------------|----------------|
| DIM_TAXPAYER | TAXPAYER_KEY | Surrogate key for taxpayer dimension | NUMBER(10) | N | Y | N | 100234 |
| DIM_TAXPAYER | VRN | VAT Registration Number | VARCHAR2(9) | N | N | Y | 123456789 |
| DIM_TAXPAYER | BUSINESS_NAME | Registered business name | VARCHAR2(200) | N | N | Y | ABC Manufacturing Ltd |
| DIM_TAXPAYER | TRADE_NAME | Trading name if different | VARCHAR2(200) | Y | N | Y | ABC Widgets |
| DIM_TAXPAYER | REGISTRATION_DATE | VAT registration date | DATE | N | N | N | 2020-01-15 |
| DIM_TAXPAYER | DEREGISTRATION_DATE | VAT deregistration date | DATE | Y | N | N | NULL |
| DIM_TAXPAYER | BUSINESS_TYPE | Type of business entity | VARCHAR2(50) | Y | N | N | Limited Company |
| DIM_TAXPAYER | SECTOR_CODE | Business sector classification | VARCHAR2(10) | Y | N | N | C25 |
| DIM_TAXPAYER | SECTOR_DESCRIPTION | Business sector description | VARCHAR2(100) | Y | N | N | Manufacture of fabricated metal products |
| DIM_TAXPAYER | STATUS | Registration status | VARCHAR2(20) | N | N | N | Active |
| DIM_TAXPAYER | EFFECTIVE_FROM_DATE | SCD effective from date | DATE | N | N | N | 2020-01-15 |
| DIM_TAXPAYER | EFFECTIVE_TO_DATE | SCD effective to date | DATE | Y | N | N | NULL |
| DIM_TAXPAYER | CURRENT_FLAG | Indicates current record (Y/N) | CHAR(1) | N | N | N | Y |
| DIM_TAXPAYER | LOAD_DATE | Date record was loaded | DATE | N | N | N | 2026-04-14 |

### Table: MDM_DW.FACT_VAT_RETURN

| Table Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) | Example Values |
|-------------|-------------|-------------|--------------------|----------------|-----------|------------|----------------|
| FACT_VAT_RETURN | VAT_RETURN_KEY | Surrogate key for fact table | NUMBER(15) | N | Y | N | 500012345 |
| FACT_VAT_RETURN | TAXPAYER_KEY | Foreign key to DIM_TAXPAYER | NUMBER(10) | N | N | N | 100234 |
| FACT_VAT_RETURN | SUBMISSION_DATE_KEY | Foreign key to DIM_DATE (submission) | NUMBER(8) | N | N | N | 20260413 |
| FACT_VAT_RETURN | PERIOD_DATE_KEY | Foreign key to DIM_DATE (period) | NUMBER(8) | N | N | N | 20260331 |
| FACT_VAT_RETURN | RETURN_ID | Business key from source | VARCHAR2(20) | N | N | N | VR202604140001 |
| FACT_VAT_RETURN | RETURN_TYPE | Type of return | VARCHAR2(20) | N | N | N | Standard |
| FACT_VAT_RETURN | FILING_FREQUENCY | Filing frequency | VARCHAR2(10) | N | N | N | Quarterly |
| FACT_VAT_RETURN | SUBMISSION_TIMESTAMP | Combined submission date and time | TIMESTAMP | N | N | N | 2026-04-13 14:23:45 |
| FACT_VAT_RETURN | TOTAL_VAT_DUE | Total VAT due | NUMBER(15,2) | Y | N | N | 12500.50 |
| FACT_VAT_RETURN | LOAD_DATE | Date record was loaded | DATE | N | N | N | 2026-04-14 |

### Table: MDM_DW.FACT_VAT_RETURN_LINE

| Table Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) | Example Values |
|-------------|-------------|-------------|--------------------|----------------|-----------|------------|----------------|
| FACT_VAT_RETURN_LINE | VAT_RETURN_LINE_KEY | Surrogate key for line fact | NUMBER(18) | N | Y | N | 700012345678 |
| FACT_VAT_RETURN_LINE | VAT_RETURN_KEY | Foreign key to FACT_VAT_RETURN | NUMBER(15) | N | N | N | 500012345 |
| FACT_VAT_RETURN_LINE | RETURN_LINE_ID | Business key from source | VARCHAR2(20) | N | N | N | VRL20260414001 |
| FACT_VAT_RETURN_LINE | BOX_NUMBER | VAT return box number | VARCHAR2(2) | N | N | N | 1 |
| FACT_VAT_RETURN_LINE | BOX_DESCRIPTION | Description of box content | VARCHAR2(100) | Y | N | N | VAT due on sales and other outputs |
| FACT_VAT_RETURN_LINE | BOX_VALUE | Monetary value for the box | NUMBER(15,2) | Y | N | N | 15000.00 |
| FACT_VAT_RETURN_LINE | CURRENCY_CODE | Currency code | VARCHAR2(3) | N | N | N | GBP |
| FACT_VAT_RETURN_LINE | LOAD_DATE | Date record was loaded | DATE | N | N | N | 2026-04-14 |

**Assumption:** DIM_DATE is a pre-populated date dimension table spanning from 2000-01-01 to 2050-12-31.

---

## 5. Data Load Overview

The data load process follows these steps:

1. **Extract**: Three CSV files are extracted from ETMP and delivered to MDM landing zone via SFTP
2. **Stage**: Files are decrypted, decompressed, and loaded into staging tables (STG_VAT_RETURN_HEADER, STG_VAT_RETURN_LINE, STG_TAXPAYER_REG)
3. **Validate**: Data quality checks are executed against staging data
4. **Transform**:
   - Load DIM_TAXPAYER dimension (Type 2 SCD logic)
   - Lookup dimension keys (TAXPAYER_KEY, DATE_KEY)
   - Combine date and time fields into timestamp
   - Enrich with reference data (sector descriptions)
   - Generate surrogate keys for facts
5. **Load**: Insert records into FACT_VAT_RETURN and FACT_VAT_RETURN_LINE
6. **Audit**: Log load statistics and data lineage metadata

**Orchestration**: Control-M triggers the load pipeline upon successful file delivery. The pipeline runs sequentially with failure notifications sent to the support team.

**Assumption:** Staging tables are truncated at the start of each load and retained for 30 days for troubleshooting purposes.

---

## 6. Source to Target Mapping

### Mapping 1: TAXPAYER_REG → DIM_TAXPAYER

| Target Database Name | Target Table Name | Target Field Name | Source Data Feed Name | Source Field Name | Transformation Logic | Comments |
|-----------------------|------------------|-------------------|-----------------------|-------------------|----------------------|-----------|
| MDM_DW | DIM_TAXPAYER | TAXPAYER_KEY | N/A | N/A | Generate from sequence SEQ_TAXPAYER_KEY | Surrogate key |
| MDM_DW | DIM_TAXPAYER | VRN | TAXPAYER_REG | VRN | Direct mapping | Natural key |
| MDM_DW | DIM_TAXPAYER | BUSINESS_NAME | TAXPAYER_REG | BUSINESS_NAME | TRIM(UPPER(BUSINESS_NAME)) | Standardize to uppercase |
| MDM_DW | DIM_TAXPAYER | TRADE_NAME | TAXPAYER_REG | TRADE_NAME | TRIM(UPPER(TRADE_NAME)) | Standardize to uppercase |
| MDM_DW | DIM_TAXPAYER | REGISTRATION_DATE | TAXPAYER_REG | REGISTRATION_DATE | Direct mapping | - |
| MDM_DW | DIM_TAXPAYER | DEREGISTRATION_DATE | TAXPAYER_REG | DEREGISTRATION_DATE | Direct mapping | - |
| MDM_DW | DIM_TAXPAYER | BUSINESS_TYPE | TAXPAYER_REG | BUSINESS_TYPE | Direct mapping | - |
| MDM_DW | DIM_TAXPAYER | SECTOR_CODE | TAXPAYER_REG | SECTOR_CODE | Direct mapping | - |
| MDM_DW | DIM_TAXPAYER | SECTOR_DESCRIPTION | REF_SECTOR_CODES | SECTOR_DESCRIPTION | Lookup using SECTOR_CODE | Reference data enrichment |
| MDM_DW | DIM_TAXPAYER | STATUS | TAXPAYER_REG | STATUS | Direct mapping | - |
| MDM_DW | DIM_TAXPAYER | EFFECTIVE_FROM_DATE | TAXPAYER_REG | UPDATED_DATE | COALESCE(UPDATED_DATE, SYSDATE) | Use update date or current date |
| MDM_DW | DIM_TAXPAYER | EFFECTIVE_TO_DATE | N/A | N/A | NULL for new/current records | SCD Type 2 logic |
| MDM_DW | DIM_TAXPAYER | CURRENT_FLAG | N/A | N/A | 'Y' for new/current, 'N' for expired | SCD Type 2 logic |
| MDM_DW | DIM_TAXPAYER | LOAD_DATE | N/A | N/A | SYSDATE | System-generated |

### Mapping 2: VAT_RETURN_HEADER → FACT_VAT_RETURN

| Target Database Name | Target Table Name | Target Field Name | Source Data Feed Name | Source Field Name | Transformation Logic | Comments |
|-----------------------|------------------|-------------------|-----------------------|-------------------|----------------------|-----------|
| MDM_DW | FACT_VAT_RETURN | VAT_RETURN_KEY | N/A | N/A | Generate from sequence SEQ_VAT_RETURN_KEY | Surrogate key |
| MDM_DW | FACT_VAT_RETURN | TAXPAYER_KEY | DIM_TAXPAYER | TAXPAYER_KEY | Lookup using VRN where CURRENT_FLAG='Y' | Dimension lookup |
| MDM_DW | FACT_VAT_RETURN | SUBMISSION_DATE_KEY | DIM_DATE | DATE_KEY | Lookup using SUBMISSION_DATE | Date dimension lookup |
| MDM_DW | FACT_VAT_RETURN | PERIOD_DATE_KEY | DIM_DATE | DATE_KEY | Lookup using last day of PERIOD_KEY month | Convert YYYYMM to date |
| MDM_DW | FACT_VAT_RETURN | RETURN_ID | VAT_RETURN_HEADER | RETURN_ID | Direct mapping | Business key |
| MDM_DW | FACT_VAT_RETURN | RETURN_TYPE | VAT_RETURN_HEADER | RETURN_TYPE | Direct mapping | - |
| MDM_DW | FACT_VAT_RETURN | FILING_FREQUENCY | VAT_RETURN_HEADER | FILING_FREQUENCY | Direct mapping | - |
| MDM_DW | FACT_VAT_RETURN | SUBMISSION_TIMESTAMP | VAT_RETURN_HEADER | SUBMISSION_DATE, SUBMISSION_TIME | TO_TIMESTAMP(SUBMISSION_DATE \|\| ' ' \|\| SUBMISSION_TIME, 'YYYY-MM-DD HH24:MI:SS') | Combine date and time |
| MDM_DW | FACT_VAT_RETURN | TOTAL_VAT_DUE | VAT_RETURN_HEADER | TOTAL_VAT_DUE | Direct mapping | - |
| MDM_DW | FACT_VAT_RETURN | LOAD_DATE | N/A | N/A | SYSDATE | System-generated |

### Mapping 3: VAT_RETURN_LINE → FACT_VAT_RETURN_LINE

| Target Database Name | Target Table Name | Target Field Name | Source Data Feed Name | Source Field Name | Transformation Logic | Comments |
|-----------------------|------------------|-------------------|-----------------------|-------------------|----------------------|-----------|
| MDM_DW | FACT_VAT_RETURN_LINE | VAT_RETURN_LINE_KEY | N/A | N/A | Generate from sequence SEQ_VAT_RETURN_LINE_KEY | Surrogate key |
| MDM_DW | FACT_VAT_RETURN_LINE | VAT_RETURN_KEY | FACT_VAT_RETURN | VAT_RETURN_KEY | Lookup using RETURN_ID | Fact table lookup |
| MDM_DW | FACT_VAT_RETURN_LINE | RETURN_LINE_ID | VAT_RETURN_LINE | RETURN_LINE_ID | Direct mapping | Business key |
| MDM_DW | FACT_VAT_RETURN_LINE | BOX_NUMBER | VAT_RETURN_LINE | BOX_NUMBER | Direct mapping | - |
| MDM_DW | FACT_VAT_RETURN_LINE | BOX_DESCRIPTION | VAT_RETURN_LINE | BOX_DESCRIPTION | TRIM(BOX_DESCRIPTION) | Remove leading/trailing spaces |
| MDM_DW | FACT_VAT_RETURN_LINE | BOX_VALUE | VAT_RETURN_LINE | BOX_VALUE | COALESCE(BOX_VALUE, 0) | Default null to zero |
| MDM_DW | FACT_VAT_RETURN_LINE | CURRENCY_CODE | VAT_RETURN_LINE | CURRENCY_CODE | Direct mapping | - |
| MDM_DW | FACT_VAT_RETURN_LINE | LOAD_DATE | N/A | N/A | SYSDATE | System-generated |

---

## 7. Transformation Rules

The following transformation rules apply globally across all feeds:

1. **String Standardization**:
   - Trim leading and trailing whitespace from all VARCHAR fields
   - Convert business names to uppercase for consistency
   - Remove non-printable characters (ASCII < 32)

2. **Date Handling**:
   - All source dates must be in YYYY-MM-DD format
   - Invalid dates (e.g., 9999-12-31, NULL) trigger rejection
   - Period key (YYYYMM) is converted to the last day of the month for dimension lookup

3. **Null Handling**:
   - Nullable fields: NULL values are preserved
   - Non-nullable fields: NULL values trigger rejection
   - Numeric fields with business meaning: NULL values are converted to 0 where appropriate (e.g., BOX_VALUE)

4. **Data Type Conversion**:
   - All numeric fields are validated for valid number format before loading
   - Timestamps are constructed from separate date and time fields
   - Currency codes default to 'GBP' if NULL

5. **Business Rules**:
   - TOTAL_VAT_DUE must be >= 0 for 'Standard' returns
   - BOX_NUMBER must be in range 1-9
   - VRN must be exactly 9 characters and numeric
   - RETURN_TYPE must be in ('Standard', 'Correction', 'Nil')

6. **Surrogate Key Generation**:
   - All surrogate keys are generated from Oracle sequences
   - Sequences are cached (cache size = 1000) for performance

7. **SCD Type 2 Logic for DIM_TAXPAYER**:
   - Compare incoming record with current record (CURRENT_FLAG='Y')
   - If no change: no action
   - If change detected: Expire current record (set EFFECTIVE_TO_DATE, CURRENT_FLAG='N'), insert new record with CURRENT_FLAG='Y'
   - Change detection fields: BUSINESS_NAME, TRADE_NAME, BUSINESS_TYPE, SECTOR_CODE, STATUS

**Assumption:** Reference data tables (e.g., REF_SECTOR_CODES) are maintained separately and updated quarterly by the Data Governance team.

---

## 8. Error Handling & Rejection Rules

| Error Type | Rejection Rule | Comments |
|-------------|----------------|-----------|
| Missing mandatory field (e.g., RETURN_ID, VRN) | Reject entire record | Log to error table with error code 'MISSING_FIELD' |
| Invalid date format | Reject entire record | Log to error table with error code 'INVALID_DATE' |
| Invalid VRN (not 9 digits) | Reject entire record | Log to error table with error code 'INVALID_VRN' |
| Invalid BOX_NUMBER (not 1-9) | Reject entire record | Log to error table with error code 'INVALID_BOX' |
| Invalid RETURN_TYPE | Reject entire record | Log to error table with error code 'INVALID_RETURN_TYPE' |
| TOTAL_VAT_DUE < 0 for Standard returns | Reject entire record | Log to error table with error code 'INVALID_VAT_AMOUNT' |
| Orphan VAT_RETURN_LINE (no matching RETURN_ID) | Reject entire record | Log to error table with error code 'ORPHAN_RECORD' |
| Taxpayer not found (VRN not in DIM_TAXPAYER) | Reject entire record | Log to error table with error code 'TAXPAYER_NOT_FOUND' |
| Duplicate RETURN_ID | Reject duplicate record | Log to error table with error code 'DUPLICATE_KEY' |
| Date dimension lookup failure | Reject entire record | Log to error table with error code 'DATE_LOOKUP_FAILED' |

**Error Table**: MDM_DW.ERROR_LOG

All rejected records are inserted into ERROR_LOG with the following attributes:

- ERROR_ID (PK)
- FEED_NAME
- FILE_NAME
- RECORD_KEY (e.g., RETURN_ID)
- ERROR_CODE
- ERROR_MESSAGE
- SOURCE_RECORD (full record as CLOB)
- ERROR_TIMESTAMP

**Assumption:** Error records are reviewed daily by the Data Quality team and resolved within 48 hours. Once corrected, records can be manually reprocessed.

---

## 9. Load Dependencies & Schedule

**Load Schedule:**

- Extract from ETMP: Daily at 02:00 GMT
- File delivery to MDM: Completes by 02:30 GMT
- Transformation and load: Triggered at 03:00 GMT, completes by 05:00 GMT
- Downstream reporting refresh: Triggered at 06:00 GMT

**Dependencies:**

1. **Pre-requisite Loads:**
   - DIM_DATE must be pre-populated (one-time setup, extended annually)
   - REF_SECTOR_CODES must be loaded (quarterly refresh)

2. **Load Sequence within VAT-ETMP-001:**
   - Step 1: Load staging tables (STG_TAXPAYER_REG, STG_VAT_RETURN_HEADER, STG_VAT_RETURN_LINE) in parallel
   - Step 2: Process DIM_TAXPAYER (SCD Type 2)
   - Step 3: Process FACT_VAT_RETURN (depends on DIM_TAXPAYER completion)
   - Step 4: Process FACT_VAT_RETURN_LINE (depends on FACT_VAT_RETURN completion)

3. **Downstream Consumers:**
   - VAT Compliance Dashboard: Depends on FACT_VAT_RETURN completion
   - Tax Analytics Platform: Depends on FACT_VAT_RETURN_LINE completion
   - Monthly reporting aggregates: Depends on both facts completion

**Failure Handling:**

- If any step fails, the entire load is rolled back
- Alert is sent to <dl-vat-data-support@hmrc.gov.uk>
- Manual intervention required to investigate and rerun
- SLA: 95% of loads must complete successfully within the scheduled window

**Assumption:** Network downtime or ETMP unavailability triggers an automatic retry mechanism (3 attempts with 15-minute intervals) before alerting the support team.

---

## 10. Appendix A – Reference Data

**REF_SECTOR_CODES**: Business sector classification lookup table

| SECTOR_CODE | SECTOR_DESCRIPTION |
|--------------|-------------------|
| C25 | Manufacture of fabricated metal products |
| G46 | Wholesale trade, except of motor vehicles and motorcycles |
| G47 | Retail trade, except of motor vehicles and motorcycles |
| J62 | Computer programming, consultancy and related activities |
| M69 | Legal and accounting activities |

**Assumption:** This reference table contains approximately 300 sector codes aligned with UK SIC (Standard Industrial Classification) codes.

---

## 11. Appendix B – Sample Files

### Sample Transformation Output: DIM_TAXPAYER

| TAXPAYER_KEY | VRN | BUSINESS_NAME | TRADE_NAME | REGISTRATION_DATE | SECTOR_CODE | SECTOR_DESCRIPTION | STATUS | EFFECTIVE_FROM_DATE | EFFECTIVE_TO_DATE | CURRENT_FLAG | LOAD_DATE |
|--------------|-----|---------------|------------|-------------------|-------------|-------------------|--------|---------------------|-------------------|--------------|-----------|
| 100234 | 123456789 | ABC MANUFACTURING LTD | ABC WIDGETS | 2020-01-15 | C25 | Manufacture of fabricated metal products | Active | 2020-01-15 | NULL | Y | 2026-04-14 |
| 100567 | 987654321 | XYZ SERVICES PLC | NULL | 2018-06-01 | G47 | Retail trade, except of motor vehicles and motorcycles | Active | 2018-06-01 | NULL | Y | 2026-04-14 |

### Sample Transformation Output: FACT_VAT_RETURN

| VAT_RETURN_KEY | TAXPAYER_KEY | SUBMISSION_DATE_KEY | PERIOD_DATE_KEY | RETURN_ID | RETURN_TYPE | SUBMISSION_TIMESTAMP | TOTAL_VAT_DUE | LOAD_DATE |
|----------------|--------------|---------------------|-----------------|-----------|-------------|----------------------|---------------|-----------|
| 500012345 | 100234 | 20260413 | 20260331 | VR202604140001 | Standard | 2026-04-13 14:23:45 | 12500.50 | 2026-04-14 |
| 500012346 | 100567 | 20260413 | 20260331 | VR202604140002 | Correction | 2026-04-13 16:45:12 | 8750.25 | 2026-04-14 |

### Sample Transformation Output: FACT_VAT_RETURN_LINE

| VAT_RETURN_LINE_KEY | VAT_RETURN_KEY | RETURN_LINE_ID | BOX_NUMBER | BOX_DESCRIPTION | BOX_VALUE | CURRENCY_CODE | LOAD_DATE |
|---------------------|----------------|----------------|------------|-----------------|-----------|---------------|-----------|
| 700012345678 | 500012345 | VRL20260414001 | 1 | VAT due on sales and other outputs | 15000.00 | GBP | 2026-04-14 |
| 700012345679 | 500012345 | VRL20260414002 | 4 | VAT reclaimed on purchases and other inputs | 2500.50 | GBP | 2026-04-14 |

---

*© NTT DATA, Inc. — 2025*  
*Page 1 of 3*
