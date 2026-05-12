# Experimental MVV: Aggregate Trucking Buyer Match

This folder validates one Parallel FindAll workflow for a single deal:

- Business: Aggregate Trucking
- Revenue: $31.0M
- Adjusted EBITDA: $3.4M
- Location: Northern US

The goal is to find PE firms or PE-backed platform companies that are plausible buyers based on public portfolio exposure, acquisition history, deal-size fit, and actionable contacts.

## Run A Dry Validation

```bash
uv run python experimental-mvv/aggregate_trucking_findall.py --dry-run
```

This prints the exact FindAll objective, match conditions, and enrichment schema without calling Parallel.

## Run One Live Search

Set `PARALLEL_API_KEY`, then run:

```bash
uv run python experimental-mvv/aggregate_trucking_findall.py
```

By default this uses:

- `generator=preview` to validate the query shape first
- `match_limit=5`, the smallest FindAll run limit currently accepted by the SDK/API
- one FindAll run for the Aggregate Trucking deal
- one enrichment schema for buyer rationale and public contact fields

Results are written under `experimental-mvv/results/`.

## Useful Options

```bash
uv run python experimental-mvv/aggregate_trucking_findall.py --generator core
uv run python experimental-mvv/aggregate_trucking_findall.py --no-enrich
uv run python experimental-mvv/aggregate_trucking_findall.py --poll-interval 10 --timeout 1200
```

Start with `preview`. If preview generates too many standalone trucking operators, use the updated buyer-first prompt in this folder and rerun. If the matched candidates look directionally right, rerun with `core` for a more serious buyer list:

```bash
uv run python experimental-mvv/aggregate_trucking_findall.py --generator core --match-limit 10
```

For this use case, `core` is usually the better validation once the prompt is shaped correctly. `preview` only evaluates a small candidate pool, so low matched counts are expected.
