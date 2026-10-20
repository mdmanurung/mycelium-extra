# Analysis Journal implementation

Base: 72b85c3 (audit a8830d8 plus opt-in confirm_writes, skill guidance and the
concurrent init default-mirror fix, carried into the isolated candidate).
Work in an isolated clone: the source checkout serves live hooks. No gate or
oracle changes; preserve verify write confirmation and publication recovery.

1. Freeze source contracts with one source-shaped multi-session fixture. Export
   a compact allowlisted verification projection through the existing publisher.
2. Collect all historical approvals/instances, receipts, repins, focus episodes,
   coherent handoffs and immutable checkpoints. Identity uses full SHA256 over
   source context plus native identity; conflicting content remains a variant.
3. Save explicit content-addressed checkpoints; validate on read, merge embedded
   observations without nesting checkpoints. Notes are contained inert references.
4. Add overview-first offline Journal, search and evidence disclosure; retain
   ordinary reporting. Update schemas, consumer and synthetic demonstrations.
5. Run affected suites, full CI collection, gate-diff, ablations, links, examples,
   Node and documentation checks available locally; record actual visual QA.

Contract decisions before UI: no durable display caps; canonical JSON uses sorted
keys and compact separators. Local/committed copies deduplicate only by native
identity and full source-record digest; legacy records use that digest as identity.
Unknown occurrence and first observation stay null. A scan time is freshness only;
checkpoint save time is separate. Source errors are coverage, never inferred events.
Publication interrupted/legacy is explicit. File mtime never establishes occurrence.
Multi-analysis plan links are explicit; shared script paths alone establish none.


Completed: source-shaped fixture, allowlisted handoff publication, historical
collection, explicit checkpoints, notes, overview/detail/evidence UI, offline
consumer, documentation and generated examples. Validation and observation
limits are recorded in [the delivery receipt](2026-10-20-analysis-journal-validation.md).
