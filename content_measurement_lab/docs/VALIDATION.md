# Validation evidence - September 22, 2026

## New lab only

- **20 unittest cases passed** using the bundled Python runtime. Hand-calculated
  fixtures cover return-window boundaries, maturity, deduplication, conflict
  quarantine, future-delivery isolation, invalid timestamps and payloads,
  equal-timestamp ordering, device and midnight boundaries, orphan telemetry,
  missing heartbeats, foreign-key enforcement, Wilson intervals, missing
  comparison cells and a known standardization example.
- **Two full builds agreed:** seven non-database output hashes and the canonical
  SQLite SQL dump matched. Physical database header/change counters can differ
  when overwriting an existing SQLite file; no byte-identical DB claim is made.
- **Raw-row accounting passed:** 26,974 = 23,761 accepted unique events + 290
  identical retry rows + 2 conflicting-ID rows + 3 invalid rows + 2,918 deliveries
  after the snapshot. Late accepted events and no-heartbeat sessions are
  overlapping diagnostics, not additional exclusions.
- **Browser checks passed:** initial totals; frequent-viewer filter; reset;
  August 25-28 filter showing 229 eligible but zero mature members and unavailable
  rates; desktop and phone-width rendering; CSV export of 1,600 rows identical
  to pipeline member metrics. No JavaScript errors were observed.
- **PDF checks passed:** two pages; text extraction; inspection of both rendered
  pages; labels, values, contact, provenance and scope reviewed.

These checks establish a working local demonstration, not production readiness,
security certification or scale performance. The older two projects are
documentation-reviewed examples; their suites were not rerun for this PDF.

## Reproduce

```console
python lab.py
python -m unittest discover -s tests -v
```

Open `output/dashboard.html`. Check the cohort filters and compare results to
`output/results.json`. For reproduction into a second directory use
`python lab.py --output output_second_run`; compare CSV, JSON, HTML and memo
hashes, then compare database table/schema content rather than header bytes.
