# S3 Transformation Document Storage Pattern

Use this file when transformation documents may need to be discovered from an S3 bucket.

## Purpose

This metadata describes a realistic way transformation documents may be stored remotely so the
resolution skill can search by transformation identity instead of guessing bucket paths.

## Expected Bucket Pattern

- bucket purpose: central document store for transformation-analysis outputs
- objects are grouped first by environment, then by domain, then by transformation slug
- each transformation folder may contain one document or a related document set

Example layout:

```text
s3://hmrc-transformation-documents/
  prod/
    vat/
      etmp-to-mdm-vat/
        v1/
          data-feed-specification-document.md
          data-feed-transformation-document.md
          data-feed-interdependencies-document.md
    customs/
      customs-declaration-pdf-to-snowflake/
        v1/
          data-feed-specification-document.md
          data-feed-transformation-document.md
          data-feed-interdependencies-document.md
    compliance/
      compliance-cases-oracle-to-sharepoint/
        v2/
          data-feed-specification-document.md
          data-feed-transformation-document.md
          data-feed-interdependencies-document.md
```

## Search Hints

When resolving documents from S3, prefer this search order:

1. exact transformation slug
2. source-target system pairing
3. request identifier or feed reference if present
4. domain prefix such as `vat/`, `customs/`, or `compliance/`

## Version Selection

- prefer the version explicitly named by the user or current request evidence
- if multiple versions exist and none was specified, treat the result as unconfirmed and ask the user to approve the selected set before code generation
- prefer complete document sets over newer partial uploads

## Filename Expectations

Common filenames in one transformation set:

- `data-feed-specification-document.md`
- `data-feed-transformation-document.md`
- `data-feed-interdependencies-document.md`

Possible supporting files:

- `mapping-supplement.md`
- `validation-rules.md`
- `operational-notes.md`

## Retrieval Rule

Stage any chosen S3 documents under:

```text
results/raw/request<id>/transformation-documents/<transformation-slug>/
```

Keep the original filenames where possible and preserve enough provenance to explain which bucket,
prefix, and version were used.
