# Data Feed Specification Document

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
3. [Data Feed Extract & Load Process](#3-data-feed-extract--load-process)  
4. [Data Feed Overview](#4-data-feed-overview)  
5. [Data Feed Structure](#5-data-feed-structure)  
6. [Source System Overview](#6-source-system-overview)  
7. [Appendix A – Sample Extracts](#7-appendix-a--sample-extracts)

---

## 1. Introduction

### 1.1 Purpose and Background

This document specifies the data feed used to extract compliance case analytics data from an Oracle
operational data store via PL/SQL and publish curated output files to a SharePoint document
library for HMRC compliance operations.

### 1.2 Scope

This feed covers:

- open compliance case details
- officer workload summaries
- risk band trend summaries

### 1.3 Audience

- Data Engineers
- Compliance MI Analysts
- Platform Operations
- Business Users consuming curated SharePoint reports

---

## 2. Description

The feed uses an Oracle PL/SQL package to extract daily compliance case analytics data. The
transformation logic normalizes and validates the extracted result sets, then publishes curated CSV
and XLSX outputs to a SharePoint document library used by compliance performance teams.

**Assumption:** The Python implementation calls Oracle result sets and then uploads generated output
files to SharePoint using a service identity.

---

## 3. Data Feed Extract & Load Process

1. Connect to Oracle using configured runtime credentials.
2. Execute the PL/SQL export package for the requested business date.
3. Retrieve three logical result sets from the package execution.
4. Normalize and validate the records.
5. Produce curated output files for business consumption.
6. Upload the output files and summary metadata to SharePoint.

---

## 4. Data Feed Overview

| Attribute | Description |
|-----------|-------------|
| **Data Feed Ref** | CMP-SA-031 |
| **Data Feed Name** | Compliance Case Analytics Publish Feed |
| **Source System** | Oracle Compliance Case Mart |
| **Target System** | SharePoint Compliance Analytics Library |
| **Feed Format** | Oracle result sets to CSV/XLSX outputs |
| **Load Type** | Incremental (Daily Delta) |
| **Frequency** | Daily |
| **Delivery Method** | Oracle PL/SQL extraction and SharePoint upload |
| **Description** | Daily publication of curated compliance analytics extracts for business reporting |

---

## 5. Data Feed Structure

### 5.1 Feed Content

The PL/SQL package returns three logical extracts.

#### 5.1.1 Extract Listing

| Extract Name | Logical Format | Description |
|--------------|----------------|-------------|
| `OPEN_CASE_DETAIL` | Tabular result set | One row per active compliance case |
| `OFFICER_WORKLOAD_SUMMARY` | Tabular result set | Summary of assigned workload by officer and team |
| `RISK_TREND_SUMMARY` | Tabular result set | Daily and weekly movement of risk-band counts |

#### 5.1.2 Package Contract

| Contract Item | Description |
|---------------|-------------|
| `PACKAGE_NAME` | `HMRC_COMPLIANCE_ANALYTICS_PKG` |
| `PROCEDURE_NAME` | `EXPORT_CASE_ANALYTICS` |
| `PARAM_BUSINESS_DATE` | Business date used to scope the export |
| `PARAM_REGION_CODE` | Optional regional filter |

#### 5.1.3 Published Output Files

| Output File | Description |
|-------------|-------------|
| `open_case_detail_YYYYMMDD.csv` | Detailed case-level output |
| `officer_workload_summary_YYYYMMDD.csv` | Officer and team workload summary |
| `risk_trend_summary_YYYYMMDD.xlsx` | Business-friendly trend summary workbook |

---

## 6. Source System Overview

### 6.1 Data Model

```text
Oracle Case Mart
   |
   +--> PL/SQL Package Result Set 1: Open Case Detail
   +--> PL/SQL Package Result Set 2: Officer Workload Summary
   +--> PL/SQL Package Result Set 3: Risk Trend Summary
```

### 6.2 Source Characteristics

| Component | Description |
|-----------|-------------|
| Case detail result set | Active case facts and assignments |
| Workload summary result set | Officer and team-level aggregates |
| Risk trend result set | Time-series summary by risk band |

### 6.3 Access Method

Oracle access requires runtime configuration for host, service name, schema, package execution
credentials, and optional regional filters. SharePoint publication requires site, library, and
folder configuration.

---

## 7. Appendix A – Sample Extracts

### Sample open case detail row

```text
CASE_ID|TAXPAYER_REF|CASE_TYPE|RISK_BAND|ASSIGNED_OFFICER|OPEN_DATE|CASE_STATUS
CMP00018452|1234567890|SELF_ASSESSMENT|HIGH|JSMITH|2026-04-22|OPEN
```

### Sample officer workload summary row

```text
OFFICER_ID|TEAM_CODE|OPEN_CASE_COUNT|HIGH_RISK_CASE_COUNT|OVERDUE_CASE_COUNT
JSMITH|WM-COMPLIANCE|42|8|5
```
