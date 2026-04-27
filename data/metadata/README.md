# Domain Data Contract

Place any reference material your skills need here. Common patterns:

This folder is for metadata and source-location guidance, not request-scoped generated output.
Store example transformation document sets under `data/test-data/` instead.

## Athena / SQL tables

- `<table_name>.yaml` — column definitions, types, and possible values
- `<table_name>_sample_data.csv` — sample rows showing real data format

## Knowledge Base

- `knowledge_base_overview.md` — topics covered, when to use each KB

## S3

- `s3_structure.md` — bucket layout, key prefixes, file formats

## Other source descriptors

- `sharepoint_structure.md` — site, library, folder, and filename conventions
- `knowledge_base_overview.md` — topics covered and retrieval hints
- `<source>_structure.md` — naming and location conventions for any other external repository

Skills should read the relevant metadata file here before searching external sources so the agent
knows what data is available, how it is named, and which location to inspect first.
