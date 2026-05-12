# Prospecting Runbook

This is the dumb-proof operating manual for creating prospect lists.

The workflow is:

```text
edit ICP/search config
-> run tiny preview
-> inspect saved files
-> run small batch
-> run larger paid batch only if the small batch looks good
-> review CSV
-> sync approved prospects to Lightfield
```

Nothing should go to Lightfield until you run the explicit sync command.

## 1. Where The Search Query Lives

The natural-language search is not typed directly into the command.

It lives in:

```text
prospecting_lists.example.json
```

That file defines the lists to build.

Example:

```json
{
  "name": "placement_agents_europe_london",
  "display_name": "Placement agents in Europe including London",
  "geography": "Europe, explicitly including London and the United Kingdom",
  "target_count": 20,
  "candidate_pool": 60,
  "max_headcount": 10,
  "require_contact_email": true,
  "require_contact_linkedin": true
}
```

The code turns that into the actual search objective:

```text
Find boutique placement agents in Europe, including London.
Only include firms with no more than 10 people.
Find decision makers with email and LinkedIn.
```

So:

```text
edit prospecting_lists.example.json = change the search
run prospect-engine = execute the search
```

## 2. Your Current Lists

The current config has two lists:

```text
1. placement_agents_europe_london
   Placement agents in Europe, including London
   Max headcount: 10
   Final target: 20 prospects
   Contact must have email and LinkedIn

2. placement_agents_ny
   Placement agents in New York
   Max headcount: 10
   Final target: 20 prospects
   Contact must have email and LinkedIn
```

## 3. Add Your API Keys

Create or edit `.env` in the repo root.

Minimum:

```env
PARALLEL_API_KEY=your_parallel_key_here
LIGHTFIELD_API_KEY=your_lightfield_key_here
DRY_RUN=true
```

Use `DRY_RUN=true` by default.

## 4. Start With A Tiny Preview

Run this first:

```bash
uv run prospect-engine prospecting-review \
  --config prospecting_lists.example.json \
  --max-reviewed-per-list 1
```

What this does:

```text
- uses the cheap preview generator
- searches both lists
- researches 1 candidate per list
- saves output files immediately
- does not write to Lightfield
```

## 5. Inspect The Output

After the preview, check:

```bash
ls exports/prospecting_reviews
```

You should see files like:

```text
placement_agents_europe_london_candidates.json
placement_agents_europe_london_review.csv
placement_agents_europe_london_review.json
placement_agents_europe_london_review_partial.jsonl
placement_agents_ny_candidates.json
placement_agents_ny_review.csv
placement_agents_ny_review.json
placement_agents_ny_review_partial.jsonl
```

Open the CSV files first:

```text
exports/prospecting_reviews/placement_agents_europe_london_review.csv
exports/prospecting_reviews/placement_agents_ny_review.csv
```

Look for:

```text
qualified = True
primary_contact_email filled
primary_contact_linkedin filled
headcount evidence makes sense
geography evidence makes sense
placement agent evidence makes sense
```

## 6. Run A Small Batch

If the tiny preview looks sane:

```bash
uv run prospect-engine prospecting-review \
  --config prospecting_lists.example.json \
  --max-reviewed-per-list 5 \
  --resume
```

What `--resume` means:

```text
reuse saved candidate files
skip already reviewed prospects
continue from where the previous run stopped
```

## 7. Run A Larger Paid Batch

Only do this after the preview and small batch look good.

```bash
uv run prospect-engine prospecting-review \
  --config prospecting_lists.example.json \
  --generator core \
  --max-reviewed-per-list 25 \
  --resume \
  --confirm-paid-run
```

Why `--confirm-paid-run` exists:

```text
core/pro can spend more Parallel credits
the command will refuse to run core/pro unless you explicitly confirm it
```

## 8. What Gets Saved

The workflow saves as it goes.

```text
*_candidates.json
```

Saved immediately after candidate discovery.

```text
*_review_partial.jsonl
```

One line per researched candidate. This is the emergency checkpoint.

```text
*_review.json
```

Full structured review output.

```text
*_review.csv
```

Human review spreadsheet.

If a run fails halfway, do not start over. Use `--resume`.

## 9. What Counts As Qualified

A prospect is approved only if:

```text
- it is verified as a placement agent / fundraising advisor
- it is in the target geography
- it is boutique
- headcount is not above 10
- it appears active
- the selected contact has email
- the selected contact has LinkedIn
```

If any of those fail, the row is rejected and `rejection_reasons` explains why.

## 10. Sync To Lightfield

Do not sync until you reviewed the CSV.

Dry run first:

```bash
uv run prospect-engine prospecting-sync-approved \
  --review-json exports/prospecting_reviews/placement_agents_europe_london_review.json \
  --dry-run
```

If that looks good, live sync:

```bash
uv run prospect-engine prospecting-sync-approved \
  --review-json exports/prospecting_reviews/placement_agents_europe_london_review.json \
  --live
```

Repeat for NY:

```bash
uv run prospect-engine prospecting-sync-approved \
  --review-json exports/prospecting_reviews/placement_agents_ny_review.json \
  --dry-run
```

Then:

```bash
uv run prospect-engine prospecting-sync-approved \
  --review-json exports/prospecting_reviews/placement_agents_ny_review.json \
  --live
```

## 11. Common Mistakes

Do not start with:

```bash
--generator core --confirm-paid-run
```

Start with preview.

Do not delete `exports/prospecting_reviews` unless you intentionally want to lose checkpoints.

Do not run live Lightfield sync before reviewing the CSV.

Do not put API keys in Git.

## 12. Recovery

If the run fails:

```bash
uv run prospect-engine prospecting-review \
  --config prospecting_lists.example.json \
  --max-reviewed-per-list 5 \
  --resume
```

If you want to continue with core after a failure:

```bash
uv run prospect-engine prospecting-review \
  --config prospecting_lists.example.json \
  --generator core \
  --max-reviewed-per-list 25 \
  --resume \
  --confirm-paid-run
```

## 13. The Short Version

```bash
# 1. tiny test
uv run prospect-engine prospecting-review --config prospecting_lists.example.json --max-reviewed-per-list 1

# 2. small batch
uv run prospect-engine prospecting-review --config prospecting_lists.example.json --max-reviewed-per-list 5 --resume

# 3. larger paid batch
uv run prospect-engine prospecting-review --config prospecting_lists.example.json --generator core --max-reviewed-per-list 25 --resume --confirm-paid-run

# 4. dry-run sync Europe
uv run prospect-engine prospecting-sync-approved --review-json exports/prospecting_reviews/placement_agents_europe_london_review.json --dry-run

# 5. live sync Europe
uv run prospect-engine prospecting-sync-approved --review-json exports/prospecting_reviews/placement_agents_europe_london_review.json --live
```
