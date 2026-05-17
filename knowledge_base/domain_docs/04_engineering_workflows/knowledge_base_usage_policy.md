# Knowledge Base Usage Policy

This Agent uses the knowledge base as a public-source reference and evidence
retrieval system. It must not treat public documents, images, extracted text, or
archive contents as authoritative manufacturing data.

## Retrieval Chain

1. Identify the task intent.
2. Normalize terms with the glossary when available.
3. Search indexed text chunks with `/searchdocs`.
4. Prefer documents with clear source metadata and higher reliability.
5. Use product cards, structured tables, and processed text as the main reading layer.
6. Use archive metadata and source paths only for evidence tracing.
7. Mark uncertain, inferred, image-estimated, or unreviewed information explicitly.

## Safety Boundary

Documents tagged `restricted_reference` may be used for:

- public-source cataloging;
- high-level comparison;
- evidence tracing;
- conceptual, non-operational discussion.

They must not be used for:

- detailed weapon structure design;
- internal layout reconstruction;
- manufacturing or assembly guidance;
- weapon effectiveness optimization;
- launch, deployment, warhead, seeker, propulsion, or guidance implementation.

## Source Reliability

Default imported material is tagged `unreviewed_public_source` until manually
checked. Agent answers should avoid presenting those sources as verified design
truth.
