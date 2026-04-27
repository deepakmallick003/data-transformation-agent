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

This document defines the transformation logic for extracting compliance case analytics from Oracle
PL/SQL and publishing curated operational outputs to SharePoint.

---

## 2. Description

The transformation executes a PL/SQL export package, converts the returned result sets into
business-ready curated files, applies validation and standardization rules, and uploads the final
outputs to the SharePoint Compliance Analytics document library.

**Assumption:** The implementation creates local temporary output files before uploading them to
SharePoint.

---

## 3. Source System Overview

### 3.1 Source Result Sets

| Result Set | Description |
|------------|-------------|
| `OPEN_CASE_DETAIL` | Case-level analytical extract |
| `OFFICER_WORKLOAD_SUMMARY` | Workload metrics grouped by officer and team |
| `RISK_TREND_SUMMARY` | Trend metrics grouped by date and risk band |

### 3.2 Extraction Logic

The Oracle package accepts business date and optional region code parameters and returns structured
result sets from a governed reporting layer.

---

## 4. Target Data Model

The target is a SharePoint document library containing curated analytics outputs and a small upload
manifest payload.

### Published Artifact: `open_case_detail_YYYYMMDD.csv`

| Field Name | Description |
|------------|-------------|
| `CASE_ID` | Compliance case id |
| `TAXPAYER_REF` | Taxpayer reference |
| `CASE_TYPE` | Case category |
| `RISK_BAND` | Low, medium, high, critical |
| `ASSIGNED_OFFICER` | Officer login or identifier |
| `OPEN_DATE` | Case open date |
| `CASE_STATUS` | Case state |
| `AGE_DAYS` | Derived number of days open |

### Published Artifact: `officer_workload_summary_YYYYMMDD.csv`

| Field Name | Description |
|------------|-------------|
| `OFFICER_ID` | Officer login or identifier |
| `TEAM_CODE` | Team code |
| `OPEN_CASE_COUNT` | Count of open cases |
| `HIGH_RISK_CASE_COUNT` | Count of high-risk cases |
| `OVERDUE_CASE_COUNT` | Count of overdue cases |

### Published Artifact: `risk_trend_summary_YYYYMMDD.xlsx`

Workbook tabs:

- `daily_summary`
- `weekly_summary`
- `exceptions`

---

## 5. Data Load Overview

1. connect to Oracle
2. execute package `HMRC_COMPLIANCE_ANALYTICS_PKG.EXPORT_CASE_ANALYTICS`
3. materialize result sets
4. validate and normalize records
5. derive aging and summary fields
6. write curated output files
7. upload files to SharePoint

---

## 6. Source to Target Mapping

### Mapping 1: `OPEN_CASE_DETAIL` → `open_case_detail_YYYYMMDD.csv`

| Target Field | Source Field | Transformation Logic |
|--------------|--------------|----------------------|
| `CASE_ID` | `CASE_ID` | Direct mapping |
| `TAXPAYER_REF` | `TAXPAYER_REF` | Trim whitespace |
| `CASE_TYPE` | `CASE_TYPE` | Uppercase normalization |
| `RISK_BAND` | `RISK_SCORE_BAND` | Map values to LOW, MEDIUM, HIGH, CRITICAL |
| `ASSIGNED_OFFICER` | `OFFICER_LOGIN` | Direct mapping |
| `OPEN_DATE` | `OPEN_DATE` | ISO date normalization |
| `CASE_STATUS` | `CASE_STATUS` | Uppercase normalization |
| `AGE_DAYS` | `OPEN_DATE` | Business date minus open date |

### Mapping 2: `OFFICER_WORKLOAD_SUMMARY` → `officer_workload_summary_YYYYMMDD.csv`

| Target Field | Source Field | Transformation Logic |
|--------------|--------------|----------------------|
| `OFFICER_ID` | `OFFICER_LOGIN` | Direct mapping |
| `TEAM_CODE` | `TEAM_CODE` | Direct mapping |
| `OPEN_CASE_COUNT` | `OPEN_CASE_COUNT` | Integer validation |
| `HIGH_RISK_CASE_COUNT` | `HIGH_RISK_COUNT` | Integer validation |
| `OVERDUE_CASE_COUNT` | `OVERDUE_COUNT` | Integer validation |

### Mapping 3: `RISK_TREND_SUMMARY` → `risk_trend_summary_YYYYMMDD.xlsx`

| Target Section | Source | Transformation Logic |
|----------------|--------|----------------------|
| `daily_summary` | `RISK_TREND_SUMMARY` | Filter current business date rows |
| `weekly_summary` | `RISK_TREND_SUMMARY` | Aggregate trailing 7-day values |
| `exceptions` | validation output | Include rejected or incomplete summary rows |

---

## 7. Transformation Rules

1. `CASE_ID` must be unique within the business date export.
2. `RISK_BAND` must resolve to one of LOW, MEDIUM, HIGH, CRITICAL.
3. `OPEN_DATE` must not be in the future relative to the business date.
4. Workload counts must be non-negative integers.
5. SharePoint file naming must match the business date naming convention.
6. Empty result sets are allowed only for regional filtered runs and must still produce an upload manifest.

---

## 8. Error Handling & Rejection Rules

| Error Type | Rejection Rule | Comments |
|------------|----------------|----------|
| Oracle connection failure | Fail batch | Extraction cannot proceed |
| Package execution failure | Fail batch | Log package error text |
| Duplicate `CASE_ID` | Reject row | Log `DUPLICATE_CASE_ID` |
| Invalid `OPEN_DATE` | Reject row | Log `INVALID_OPEN_DATE` |
| Invalid risk-band mapping | Reject row | Log `INVALID_RISK_BAND` |
| SharePoint upload failure | Retry then fail step | Curated files must not be marked successful until upload completes |

---

## 9. Load Dependencies & Schedule

- officer hierarchy reference data must be current before workload outputs are published
- regional taxonomy lookup must be available before SharePoint folder routing
- Oracle package execution window opens daily at 04:00 UTC
- SharePoint publication should complete before 06:00 UTC

**Assumption:** SharePoint site id, library id, target folder path, and Oracle connection settings
are runtime configuration items rather than hard-coded values.
