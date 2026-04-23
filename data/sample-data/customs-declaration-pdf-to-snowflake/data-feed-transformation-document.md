# Data Feed Transformation Document

*HMRC / KANO Document Generation PoC*  
*Version: v0.1*  
*Date: 23 Apr 2026*  
*Author: D. Mallick*  
*Status: Draft*

---

## Document Properties

| Property | Value |
|-----------|-------|
| **Author** | D. Mallick |
| **Date** | 23 Apr 2026 |
| **Version** | 0.1 |
| **Status** | Draft |

---

## Table of Contents

1. [Introduction](#1-introduction)  
2. [Description](#2-description)  
3. [Source System Overview](#3-source-system-overview)  
4. [Target Data Model](#4-target-data-model)  
5. [Data Load Overview](#5-data-load-overview)  
6. [Source to Target Mapping](#6-source-to-target-mapping)  
7. [Transformation Rules](#7-transformation-rules)  
8. [Error Handling & Rejection Rules](#8-error-handling--rejection-rules)  
9. [Load Dependencies & Schedule](#9-load-dependencies--schedule)

---

## 1. Introduction

### 1.1 Purpose and Background

This document defines the transformation logic for converting customs declaration PDFs and related
metadata into structured Snowflake tables for customs analytics and exception monitoring.

### 1.2 Scope

This transformation covers:

- declaration header extraction from PDFs
- commodity-line extraction from PDFs
- ingestion audit and rejection logging

---

## 2. Description

The transformation retrieves daily customs declaration PDFs from S3, extracts structured content,
joins each PDF with its manifest and index metadata, validates the extracted rows, and writes the
curated results into Snowflake.

**Assumption:** The generated Python implementation uses a PDF parsing library and Snowflake
connector rather than relying on external ETL tooling.

---

## 3. Source System Overview

### 3.1 Source Inputs

| Source | Purpose |
|--------|---------|
| Manifest JSON | Declares batch-level completeness and expected object keys |
| Declaration Index CSV | Supplies declaration identifiers and submission metadata |
| Declaration PDF | Provides the declaration content to be parsed into structured rows |

### 3.2 Parsed PDF Sections

The PDF is expected to contain:

- declaration header
- consignor and consignee details
- declarant details
- one or more commodity lines
- goods value and duty-related fields

---

## 4. Target Data Model

The target Snowflake database contains these curated tables.

### Table: `CURATED_CUSTOMS_DECLARATION_HEADER`

| Field Name | Description |
|------------|-------------|
| `DECLARATION_KEY` | Surrogate key |
| `MRN` | Movement Reference Number |
| `DECLARANT_EORI` | Declarant identifier |
| `DECLARATION_TYPE` | Import, export, or transit |
| `SUBMISSION_TIMESTAMP` | Submission time from metadata |
| `GOODS_LOCATION_CODE` | Parsed goods location |
| `TOTAL_CUSTOMS_VALUE` | Parsed declaration total |
| `SOURCE_DOCUMENT_KEY` | S3 object key |
| `LOAD_TIMESTAMP` | Curated load timestamp |

### Table: `CURATED_CUSTOMS_DECLARATION_LINE`

| Field Name | Description |
|------------|-------------|
| `DECLARATION_LINE_KEY` | Surrogate key |
| `DECLARATION_KEY` | Foreign key to header table |
| `LINE_NUMBER` | Commodity line number |
| `COMMODITY_CODE` | Parsed commodity code |
| `ORIGIN_COUNTRY_CODE` | Parsed origin country |
| `PROCEDURE_CODE` | Parsed procedure code |
| `NET_MASS_KG` | Parsed net mass |
| `STATISTICAL_VALUE` | Parsed value |
| `LOAD_TIMESTAMP` | Curated load timestamp |

### Table: `CUSTOMS_DECLARATION_REJECTION_LOG`

| Field Name | Description |
|------------|-------------|
| `REJECTION_ID` | Surrogate key |
| `BATCH_ID` | Source batch |
| `DOCUMENT_KEY` | Source S3 object key |
| `MRN` | Record identifier where available |
| `ERROR_CODE` | Rejection category |
| `ERROR_MESSAGE` | Rejection detail |
| `RAW_CONTEXT` | Raw snippet or metadata payload |
| `REJECTED_AT` | Rejection timestamp |

---

## 5. Data Load Overview

The transformation runs in this order:

1. load manifest metadata
2. load declaration index metadata
3. read and parse each PDF
4. build declaration header rows
5. build declaration line rows
6. write accepted rows to Snowflake
7. write rejected rows to the rejection log

---

## 6. Source to Target Mapping

### Mapping 1: Index/Manifest/PDF → `CURATED_CUSTOMS_DECLARATION_HEADER`

| Target Field | Source | Transformation Logic |
|--------------|--------|----------------------|
| `DECLARATION_KEY` | N/A | Generated surrogate key |
| `MRN` | Index CSV or parsed PDF | Prefer index MRN, validate against parsed value if present |
| `DECLARANT_EORI` | Index CSV | Direct mapping |
| `DECLARATION_TYPE` | Index CSV | Uppercase normalization |
| `SUBMISSION_TIMESTAMP` | Index CSV | ISO timestamp parsing |
| `GOODS_LOCATION_CODE` | PDF | Extract from declaration header block |
| `TOTAL_CUSTOMS_VALUE` | PDF | Parse decimal from declaration summary |
| `SOURCE_DOCUMENT_KEY` | Manifest/Index | Direct mapping |
| `LOAD_TIMESTAMP` | N/A | System-generated timestamp |

### Mapping 2: PDF → `CURATED_CUSTOMS_DECLARATION_LINE`

| Target Field | Source | Transformation Logic |
|--------------|--------|----------------------|
| `DECLARATION_LINE_KEY` | N/A | Generated surrogate key |
| `DECLARATION_KEY` | Header target | Lookup via generated header row |
| `LINE_NUMBER` | PDF | Parse integer line number |
| `COMMODITY_CODE` | PDF | Strip whitespace; validate length and digits |
| `ORIGIN_COUNTRY_CODE` | PDF | Uppercase ISO country code |
| `PROCEDURE_CODE` | PDF | Normalize to 4-character procedure code |
| `NET_MASS_KG` | PDF | Parse decimal |
| `STATISTICAL_VALUE` | PDF | Parse decimal |
| `LOAD_TIMESTAMP` | N/A | System-generated timestamp |

---

## 7. Transformation Rules

1. Manifest and index files must agree on batch id.
2. Only PDFs listed in the manifest may be processed.
3. `MRN` must match the customs reference pattern and be unique within the batch.
4. Commodity code must be numeric and 8 to 10 digits.
5. PDF parsing failures must not stop the batch; they must be rejected per document.
6. Missing mandatory declaration header fields cause declaration-level rejection.
7. Invalid commodity-line values cause line-level rejection unless the document-level header is also invalid.

**Assumption:** Parsed PDF values are text-first and require normalization before validation.

---

## 8. Error Handling & Rejection Rules

| Error Type | Rejection Rule | Comments |
|------------|----------------|----------|
| Manifest missing | Fail batch | No documents can be trusted without manifest control |
| Index missing | Fail batch | Routing metadata is required |
| PDF object missing from S3 | Reject document | Log missing object key |
| PDF parse failure | Reject document | Log parser error and document key |
| Invalid MRN | Reject document | Log `INVALID_MRN` |
| Invalid commodity code | Reject line | Log `INVALID_COMMODITY_CODE` |
| Manifest/index count mismatch | Warn and log | Batch may proceed with explicit discrepancy log |
| Snowflake load failure | Retry then fail step | Curated load must be atomic per table step |

---

## 9. Load Dependencies & Schedule

- Source object arrival in S3 must complete before processing starts
- Customs reference data for country and procedure codes must already be available
- Snowflake target schema must exist before write operations begin
- Daily processing window starts at 03:30 UTC after manifest publication

**Assumption:** Snowflake connection properties, warehouse name, database, schema, and role are
provided through runtime configuration rather than hard-coded in the implementation.
