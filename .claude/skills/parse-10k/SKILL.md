---
name: 10k-chunking
description: Parse and chunk SEC 10-K filings. Use whenever processing 10-K
  documents from EDGAR. Covers section detection, table preservation,
  metadata tagging, and the 800-token / 10% overlap policy.
---

# 10-K Chunking Playbook

## Section detection
10-Ks follow a standard structure. Detect these section headers:
- Item 1. Business
- Item 1A. Risk Factors
- Item 7. Management's Discussion and Analysis (MD&A)
- Item 7A. Quantitative and Qualitative Disclosures
- Item 8. Financial Statements
...

## Chunking policy
- Chunk size: ~800 tokens (use tiktoken for counting)
- Overlap: 10% (80 tokens) between adjacent chunks
- Never split across an Item boundary — start fresh at each section
- For tables: keep the table as a single chunk even if it exceeds 800 tokens
- For the financial statements section: chunk by individual table

## Metadata
Every chunk must carry: ticker, fiscal_year, section, chunk_index, source_url

## Failure modes to handle
- HTML 10-Ks with inline XBRL: strip tags but preserve text content
- Filings older than 2018 sometimes have a different section ordering
- ...