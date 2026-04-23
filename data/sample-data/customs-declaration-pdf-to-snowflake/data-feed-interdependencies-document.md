# Data Feed Interdependencies Document

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
2. [Data Landscape Overview](#2-data-landscape-overview)  
3. [Data Feed Listing](#3-data-feed-listing)  
4. [Data Feed Interdependencies](#4-data-feed-interdependencies)  
5. [Data Feed Load Sequence](#5-data-feed-load-sequence)

---

## 1. Introduction

This document defines the dependencies for the Customs Declaration PDF Daily Feed into Snowflake.

---

## 2. Data Landscape Overview

```text
S3 Manifest / Index / PDF Objects
             |
             v
   Python Extraction And Validation Layer
             |
             v
      Snowflake Curated Tables
             |
             v
   Customs Analytics And Exception Reporting
```

---

## 3. Data Feed Listing

| Data Feed Ref | Data Feed Name | Source System | Target System | Frequency |
|---------------|----------------|---------------|---------------|-----------|
| DOC-CUS-019 | Customs Declaration PDF Daily Feed | S3 Document Archive | Snowflake | Daily |
| REF-CUS-001 | Customs Procedure Code Reference | Reference Repository | Snowflake | Daily |
| REF-CUS-002 | Country Code Reference | Reference Repository | Snowflake | Daily |

---

## 4. Data Feed Interdependencies

| Data Feed Ref | Dependent On | Dependency Logic |
|---------------|--------------|------------------|
| DOC-CUS-019 | REF-CUS-001 | Procedure codes must be available to validate commodity-line procedure mappings |
| DOC-CUS-019 | REF-CUS-002 | Country code validation requires current country reference data |
| DOC-CUS-019 | Manifest publication | Manifest must exist before any PDF processing begins |
| DOC-CUS-019 | Snowflake schema readiness | Target curated and rejection tables must exist |

---

## 5. Data Feed Load Sequence

| Order | Step | Description |
|-------|------|-------------|
| 1 | Reference data refresh | Country and procedure code reference data available |
| 2 | Manifest arrival | Manifest controls the processing batch |
| 3 | Index retrieval | Index file provides routing metadata |
| 4 | PDF parsing | Documents are parsed and validated |
| 5 | Header load | Curated header rows written to Snowflake |
| 6 | Line load | Curated line rows written to Snowflake |
| 7 | Rejection log load | Rejected rows and diagnostics written |

**Failure Scenarios**

| Scenario | Impact | Resolution |
|----------|--------|------------|
| Manifest missing | Batch blocked | Retry manifest retrieval then alert |
| PDF parser library unavailable | Batch blocked | Platform issue requiring engineering support |
| Snowflake authentication failure | Load blocked | Validate runtime credentials and role configuration |
| Reference data stale | Validation degraded | Proceed only if operating rules permit stale reference use |
