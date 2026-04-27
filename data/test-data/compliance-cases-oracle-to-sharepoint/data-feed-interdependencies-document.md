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

This document defines dependencies for the Compliance Case Analytics Publish Feed from Oracle to
SharePoint.

---

## 2. Data Landscape Overview

```text
Oracle Compliance Case Mart
           |
           v
  PL/SQL Export Package Execution
           |
           v
   Curated CSV/XLSX Output Build
           |
           v
 SharePoint Compliance Analytics Library
```

---

## 3. Data Feed Listing

| Data Feed Ref | Data Feed Name | Source System | Target System | Frequency |
|---------------|----------------|---------------|---------------|-----------|
| CMP-SA-031 | Compliance Case Analytics Publish Feed | Oracle Compliance Case Mart | SharePoint | Daily |
| REF-CMP-004 | Officer Hierarchy Reference | Reference Repository | Transformation runtime | Daily |
| REF-CMP-006 | Region Taxonomy Reference | Reference Repository | Transformation runtime | Daily |

---

## 4. Data Feed Interdependencies

| Data Feed Ref | Dependent On | Dependency Logic |
|---------------|--------------|------------------|
| CMP-SA-031 | REF-CMP-004 | Officer hierarchy enriches workload outputs |
| CMP-SA-031 | REF-CMP-006 | Regional taxonomy required for routing and labeling |
| CMP-SA-031 | Oracle package readiness | Package must be available for the business date window |
| CMP-SA-031 | SharePoint library readiness | Target folders and service identity permissions must exist |

---

## 5. Data Feed Load Sequence

| Order | Step | Description |
|-------|------|-------------|
| 1 | Refresh reference lookups | Officer and region references available |
| 2 | Execute PL/SQL package | Extract business-date result sets |
| 3 | Validate result sets | Apply row-level and aggregate checks |
| 4 | Build curated files | Produce CSV/XLSX outputs |
| 5 | Upload to SharePoint | Publish files to target library |
| 6 | Publish upload manifest | Log file names, timestamps, and row counts |

**Failure Scenarios**

| Scenario | Impact | Resolution |
|----------|--------|------------|
| Oracle package unavailable | Batch blocked | Retry during allowed extraction window |
| Reference lookup missing | Enrichment degraded | Fail or continue based on operating policy |
| SharePoint authentication failure | Publication blocked | Retry with service identity validation |
| Partial file upload | Target inconsistency | Remove partial file and retry upload |
