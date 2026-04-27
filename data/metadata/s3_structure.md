## S3 Storage Model

This file defines the S3 source layout used by this repo.

## Shared Source Material

Source material lives directly under the configured bucket by source area.

```text
s3://<S3_BUCKET>/
└── <source-area>/
    ├── primary-source.ext
    ├── supplementary-source.ext
    └── rules.ext
```
