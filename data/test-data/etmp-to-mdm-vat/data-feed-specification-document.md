# Data Feed Specification Document  

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

---

## Table of Contents

1. [Introduction](#1-introduction)  
    1.1 [Purpose and Background](#11-purpose-and-background)  
    1.2 [Scope](#12-scope)  
    1.3 [Audience](#13-audience)  
2. [Description](#2-description)  
3. [Data Feed Extract & Load Process](#3-data-feed-extract--load-process)  
4. [Data Feed Overview](#4-data-feed-overview)  
5. [Data Feed Structure](#5-data-feed-structure)  
    5.1 [Feed Content](#51-feed-content)  
    5.1.1 [File Listing](#511-file-listing)  
    5.1.2 [File Requirements](#512-file-requirements)  
    5.1.3 [File Specification](#513-file-specification)  
6. [Source System Overview](#6-source-system-overview)  
    6.1 [Data Model](#61-data-model)  
    6.2 [Tables](#62-tables)  
    6.3 [Relationships](#63-relationships)  
7. [Appendix A – Sample Files](#7-appendix-a--sample-files)  

---

## 1. Introduction

### 1.1 Purpose and Background

This document specifies the data feed that extracts VAT return data from the Enterprise Tax Management Platform (ETMP) and loads it into the Master Data Management (MDM) Data Warehouse. The feed supports analytical reporting, compliance monitoring, and business intelligence requirements for VAT operations across HMRC.

**Assumption:** The feed was created to replace a legacy batch process that previously extracted VAT data monthly, now requiring daily updates to support real-time compliance dashboards.

### 1.2 Scope

This document covers the VAT Returns data feed (Feed Ref: VAT-ETMP-001) which includes:

- VAT return header information
- VAT return line item details
- Associated taxpayer registration data

### 1.3 Audience

- Data Architects (HMRC & NTT DATA)
- ETL Developers
- Data Analysts
- Business Analysts (VAT Operations)

---

## 2. Description

The VAT Returns data feed extracts daily incremental VAT return submission data from ETMP and delivers it to the MDM Data Warehouse. The feed supports downstream reporting systems including the VAT Compliance Dashboard and the Tax Analytics Platform. Data consumers include VAT Operations teams, Compliance Officers, and Business Intelligence teams.

**Assumption:** The feed processes all VAT returns submitted in the previous 24-hour period, identified by the submission timestamp in ETMP.

---

## 3. Data Feed Extract & Load Process

The data feed is extracted from ETMP using an Oracle SQL extraction query executed by the Informatica PowerCenter ETL platform. The extraction runs daily at 02:00 GMT, capturing all VAT returns with a submission timestamp from the previous day (00:00 to 23:59).

The extracted data is written to three CSV files, compressed using GZIP, and encrypted using AES-256 encryption. Files are transferred to the MDM landing zone via SFTP. Upon successful transfer, the MDM orchestration layer (Control-M) triggers the transformation and load pipeline.

**Assumption:** Network connectivity between ETMP and MDM uses a dedicated secure connection with 99.9% uptime SLA.

---

## 4. Data Feed Overview

| Attribute | Description |
|------------|-------------|
| **Data Feed Ref** | VAT-ETMP-001 |
| **Data Feed Name** | VAT Returns Daily Extract |
| **Source System** | ETMP (Enterprise Tax Management Platform) |
| **Target System** | MDM Data Warehouse |
| **Feed Format** | CSV (pipe-delimited) |
| **Load Type** | Incremental (Daily Delta) |
| **Frequency** | Daily |
| **Delivery Method** | SFTP |
| **Description** | Daily extract of VAT return submissions including header, line item, and taxpayer data |

---

## 5. Data Feed Structure

### 5.1 Feed Content

The feed consists of three CSV files delivered daily. All files are pipe-delimited with a header row, compressed (GZIP), and encrypted (AES-256).

---

### 5.1.1 File Listing

| File Name | Source Table Name | Description | Approximate File Size |
|------------|------------------|--------------|-----------------------|
| VAT_RETURN_HEADER_YYYYMMDD.csv | ETMP.VAT_RETURN_HEADER | VAT return header records including return ID, period, and submission details | 50 MB (uncompressed) |
| VAT_RETURN_LINE_YYYYMMDD.csv | ETMP.VAT_RETURN_LINE | Line-level detail for each VAT return including box numbers and amounts | 200 MB (uncompressed) |
| TAXPAYER_REG_YYYYMMDD.csv | ETMP.TAXPAYER_REGISTRATION | Taxpayer registration information for businesses submitting VAT returns | 10 MB (uncompressed) |

---

### 5.1.2 File Requirements

**File Naming Convention:**  
`<FEED_NAME>_YYYYMMDD.csv.gz.enc`  
Where YYYYMMDD represents the business date of the extract.

**Format:**  

- CSV with pipe (|) delimiter
- UTF-8 character encoding
- Header row included
- No trailer row

**Compression:** GZIP compression applied before encryption

**Encryption:** AES-256 encryption with key rotation every 90 days

**Size Constraints:**  

- Maximum uncompressed file size: 5 GB per file
- If exceeded, files will be split with suffix _PART01,_PART02, etc.

**Header Row:** Column names matching the field names in section 5.1.3

**Assumption:** File retention in the SFTP landing zone is 7 days, after which files are automatically purged.

---

### 5.1.3 File Specification

#### File: VAT_RETURN_HEADER_YYYYMMDD.csv

| File Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) | Source Table |
|------------|-------------|-------------|--------------------|----------------|-----------|------------|---------------|
| VAT_RETURN_HEADER | RETURN_ID | Unique identifier for VAT return | VARCHAR2(20) | N | Y | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | VRN | VAT Registration Number | VARCHAR2(9) | N | N | Y | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | PERIOD_KEY | VAT period key (YYYYMM format) | VARCHAR2(6) | N | N | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | SUBMISSION_DATE | Date return was submitted | DATE | N | N | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | SUBMISSION_TIME | Time return was submitted (HH24:MI:SS) | VARCHAR2(8) | N | N | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | RETURN_TYPE | Type of return (Standard, Correction, Nil) | VARCHAR2(20) | N | N | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | FILING_FREQUENCY | Filing frequency (Monthly, Quarterly, Annual) | VARCHAR2(10) | N | N | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | TOTAL_VAT_DUE | Total VAT due (sum of all boxes) | NUMBER(15,2) | Y | N | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | CREATED_DATE | Record creation date in ETMP | DATE | N | N | N | ETMP.VAT_RETURN_HEADER |
| VAT_RETURN_HEADER | UPDATED_DATE | Record last update date in ETMP | DATE | Y | N | N | ETMP.VAT_RETURN_HEADER |

#### File: VAT_RETURN_LINE_YYYYMMDD.csv

| File Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) | Source Table |
|------------|-------------|-------------|--------------------|----------------|-----------|------------|---------------|
| VAT_RETURN_LINE | RETURN_LINE_ID | Unique identifier for line item | VARCHAR2(20) | N | Y | N | ETMP.VAT_RETURN_LINE |
| VAT_RETURN_LINE | RETURN_ID | Foreign key to VAT_RETURN_HEADER | VARCHAR2(20) | N | N | N | ETMP.VAT_RETURN_LINE |
| VAT_RETURN_LINE | BOX_NUMBER | VAT return box number (1-9) | VARCHAR2(2) | N | N | N | ETMP.VAT_RETURN_LINE |
| VAT_RETURN_LINE | BOX_DESCRIPTION | Description of box content | VARCHAR2(100) | Y | N | N | ETMP.VAT_RETURN_LINE |
| VAT_RETURN_LINE | BOX_VALUE | Monetary value for the box | NUMBER(15,2) | Y | N | N | ETMP.VAT_RETURN_LINE |
| VAT_RETURN_LINE | CURRENCY_CODE | Currency code (default GBP) | VARCHAR2(3) | N | N | N | ETMP.VAT_RETURN_LINE |
| VAT_RETURN_LINE | CREATED_DATE | Record creation date in ETMP | DATE | N | N | N | ETMP.VAT_RETURN_LINE |

#### File: TAXPAYER_REG_YYYYMMDD.csv

| File Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) | Source Table |
|------------|-------------|-------------|--------------------|----------------|-----------|------------|---------------|
| TAXPAYER_REG | VRN | VAT Registration Number | VARCHAR2(9) | N | Y | Y | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | BUSINESS_NAME | Registered business name | VARCHAR2(200) | N | N | Y | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | TRADE_NAME | Trading name if different | VARCHAR2(200) | Y | N | Y | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | REGISTRATION_DATE | VAT registration date | DATE | N | N | N | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | DEREGISTRATION_DATE | VAT deregistration date | DATE | Y | N | N | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | BUSINESS_TYPE | Type of business entity | VARCHAR2(50) | Y | N | N | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | SECTOR_CODE | Business sector classification | VARCHAR2(10) | Y | N | N | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | STATUS | Registration status (Active, Inactive, Suspended) | VARCHAR2(20) | N | N | N | ETMP.TAXPAYER_REGISTRATION |
| TAXPAYER_REG | UPDATED_DATE | Record last update date in ETMP | DATE | Y | N | N | ETMP.TAXPAYER_REGISTRATION |

---

## 6. Source System Overview

### 6.1 Data Model

**Assumption:** The ETMP data model follows a standard star schema for VAT processing with a central fact table (VAT_RETURN_HEADER) and dimension tables (TAXPAYER_REGISTRATION).

```text
┌──────────────────────────┐
│ TAXPAYER_REGISTRATION    │
│ (Dimension)              │
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
│ (Fact)                   │ 1:N     │ (Detail)                 │
├──────────────────────────┤◄────────┤──────────────────────────┤
│ PK: RETURN_ID            │         │ PK: RETURN_LINE_ID       │
│ FK: VRN                  │         │ FK: RETURN_ID            │
│     PERIOD_KEY           │         │     BOX_NUMBER           │
│     SUBMISSION_DATE      │         │     BOX_VALUE            │
│     TOTAL_VAT_DUE        │         │                          │
└──────────────────────────┘         └──────────────────────────┘
```

---

### 6.2 Tables

#### a) Table Summary  

| Table Name | Description | Approximate Size |
|-------------|-------------|------------------|
| ETMP.VAT_RETURN_HEADER | Header information for VAT returns | 150 million rows |
| ETMP.VAT_RETURN_LINE | Line-level detail for VAT return boxes | 1.2 billion rows |
| ETMP.TAXPAYER_REGISTRATION | Taxpayer registration master data | 2.5 million rows |

#### b) Field-Level Details  

##### Table: ETMP.VAT_RETURN_HEADER

| Table Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) |
|-------------|-------------|-------------|--------------------|----------------|-----------|------------|
| VAT_RETURN_HEADER | RETURN_ID | Unique identifier for VAT return | VARCHAR2(20) | N | Y | N |
| VAT_RETURN_HEADER | VRN | VAT Registration Number | VARCHAR2(9) | N | N | Y |
| VAT_RETURN_HEADER | PERIOD_KEY | VAT period key (YYYYMM format) | VARCHAR2(6) | N | N | N |
| VAT_RETURN_HEADER | SUBMISSION_DATE | Date return was submitted | DATE | N | N | N |
| VAT_RETURN_HEADER | SUBMISSION_TIME | Time return was submitted (HH24:MI:SS) | VARCHAR2(8) | N | N | N |
| VAT_RETURN_HEADER | RETURN_TYPE | Type of return (Standard, Correction, Nil) | VARCHAR2(20) | N | N | N |
| VAT_RETURN_HEADER | FILING_FREQUENCY | Filing frequency (Monthly, Quarterly, Annual) | VARCHAR2(10) | N | N | N |
| VAT_RETURN_HEADER | TOTAL_VAT_DUE | Total VAT due (sum of all boxes) | NUMBER(15,2) | Y | N | N |
| VAT_RETURN_HEADER | CREATED_DATE | Record creation date in ETMP | DATE | N | N | N |
| VAT_RETURN_HEADER | UPDATED_DATE | Record last update date in ETMP | DATE | Y | N | N |

##### Table: ETMP.VAT_RETURN_LINE

| Table Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) |
|-------------|-------------|-------------|--------------------|----------------|-----------|------------|
| VAT_RETURN_LINE | RETURN_LINE_ID | Unique identifier for line item | VARCHAR2(20) | N | Y | N |
| VAT_RETURN_LINE | RETURN_ID | Foreign key to VAT_RETURN_HEADER | VARCHAR2(20) | N | N | N |
| VAT_RETURN_LINE | BOX_NUMBER | VAT return box number (1-9) | VARCHAR2(2) | N | N | N |
| VAT_RETURN_LINE | BOX_DESCRIPTION | Description of box content | VARCHAR2(100) | Y | N | N |
| VAT_RETURN_LINE | BOX_VALUE | Monetary value for the box | NUMBER(15,2) | Y | N | N |
| VAT_RETURN_LINE | CURRENCY_CODE | Currency code (default GBP) | VARCHAR2(3) | N | N | N |
| VAT_RETURN_LINE | CREATED_DATE | Record creation date in ETMP | DATE | N | N | N |

##### Table: ETMP.TAXPAYER_REGISTRATION

| Table Name | Field Name | Description | Data Type (length) | Nullable (Y/N) | PK (Y/N) | PII (Y/N) |
|-------------|-------------|-------------|--------------------|----------------|-----------|------------|
| TAXPAYER_REGISTRATION | VRN | VAT Registration Number | VARCHAR2(9) | N | Y | Y |
| TAXPAYER_REGISTRATION | BUSINESS_NAME | Registered business name | VARCHAR2(200) | N | N | Y |
| TAXPAYER_REGISTRATION | TRADE_NAME | Trading name if different | VARCHAR2(200) | Y | N | Y |
| TAXPAYER_REGISTRATION | REGISTRATION_DATE | VAT registration date | DATE | N | N | N |
| TAXPAYER_REGISTRATION | DEREGISTRATION_DATE | VAT deregistration date | DATE | Y | N | N |
| TAXPAYER_REGISTRATION | BUSINESS_TYPE | Type of business entity | VARCHAR2(50) | Y | N | N |
| TAXPAYER_REGISTRATION | SECTOR_CODE | Business sector classification | VARCHAR2(10) | Y | N | N |
| TAXPAYER_REGISTRATION | STATUS | Registration status (Active, Inactive, Suspended) | VARCHAR2(20) | N | N | N |
| TAXPAYER_REGISTRATION | UPDATED_DATE | Record last update date in ETMP | DATE | Y | N | N |

---

### 6.3 Relationships

| Parent Table | Parent Field Name | Child Table | Child Field Name | Description |
|---------------|-------------------|--------------|------------------|--------------|
| TAXPAYER_REGISTRATION | VRN | VAT_RETURN_HEADER | VRN | Links VAT returns to registered taxpayers |
| VAT_RETURN_HEADER | RETURN_ID | VAT_RETURN_LINE | RETURN_ID | Links line items to their parent return |

---

## 7. Appendix A – Sample Files

### Sample: VAT_RETURN_HEADER_20260414.csv

```csv
RETURN_ID|VRN|PERIOD_KEY|SUBMISSION_DATE|SUBMISSION_TIME|RETURN_TYPE|FILING_FREQUENCY|TOTAL_VAT_DUE|CREATED_DATE|UPDATED_DATE
VR202604140001|123456789|202603|2026-04-13|14:23:45|Standard|Quarterly|12500.50|2026-04-13|
VR202604140002|987654321|202603|2026-04-13|16:45:12|Correction|Quarterly|8750.25|2026-04-13|2026-04-13
VR202604140003|456789123|202603|2026-04-13|18:30:00|Nil|Quarterly|0.00|2026-04-13|
```

### Sample: VAT_RETURN_LINE_20260414.csv

```csv
RETURN_LINE_ID|RETURN_ID|BOX_NUMBER|BOX_DESCRIPTION|BOX_VALUE|CURRENCY_CODE|CREATED_DATE
VRL20260414001|VR202604140001|1|VAT due on sales and other outputs|15000.00|GBP|2026-04-13
VRL20260414002|VR202604140001|4|VAT reclaimed on purchases and other inputs|2500.50|GBP|2026-04-13
VRL20260414003|VR202604140002|1|VAT due on sales and other outputs|10000.00|GBP|2026-04-13
```

### Sample: TAXPAYER_REG_20260414.csv

```csv
VRN|BUSINESS_NAME|TRADE_NAME|REGISTRATION_DATE|DEREGISTRATION_DATE|BUSINESS_TYPE|SECTOR_CODE|STATUS|UPDATED_DATE
123456789|ABC Manufacturing Ltd|ABC Widgets|2020-01-15||Limited Company|C25|Active|2026-03-10
987654321|XYZ Services PLC||2018-06-01||Public Limited Company|G47|Active|2026-04-01
456789123|Smith & Sons Trading|Smith's Store|2021-11-20||Partnership|G46|Active|2025-12-15
```

---

*© NTT DATA, Inc. — 2025*  
*Page 1 of 3*
