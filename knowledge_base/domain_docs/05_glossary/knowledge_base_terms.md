# Knowledge Base Terms

## Library Layers

- Raw source archive: original ZIP, PDF, Word, spreadsheet, image, video, or code package kept as evidence.
- Processed text: Markdown, OCR text, transcript, or extracted text that the Agent can read reliably.
- Structured data: JSON, CSV, Excel, or database tables used for filtering and comparison.
- Product card: a standardized human-readable and machine-readable summary of one public case.
- Metadata: identity, source, reliability, safety class, task applicability, and traceability labels.
- Evidence map: a link from a claim, parameter, or note back to its source file and location.
- Vector index: semantic search index. This project currently uses offline keyword search; embedding can be added later.
- Workflow library: rules that tell the Agent how to route, search, filter, cite, and refuse unsafe uses.

## Retrieval Roles

- Glossary: makes the question more precise.
- Search index: finds relevant text.
- Metadata: filters and ranks what can be used.
- Evidence map: traces claims back to original sources.
- Raw archive: lets a human verify the evidence.

## Controlled Safety Labels

- general_reference: ordinary engineering reference material.
- engineering_reference: technical material that still requires review before design use.
- restricted_reference: public material that may be sensitive and is limited to cataloging, high-level discussion, and evidence tracing.
- unreviewed_public_source: imported source not yet checked by a human.
