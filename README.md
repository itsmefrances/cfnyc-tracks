# CFNYC Tracks

Dashboard of CrossFit NYC weekly programming, split by track (CrossFit, ATHX, Strength, Olympic Weightlifting), with a per-day track picker so you can compose your training week.

Live: https://itsmefrances.github.io/cfnyc-tracks/

## How it works

- `index.html` — self-contained static dashboard. Loads `data/index.json`, then the selected week file. Picks (which track on which day) are saved per week in the browser's `localStorage`.
- `data/index.json` — list of available weeks (the page sorts them).
- `data/weeks/YYYY-MM-DD.json` — one file per week, keyed by the Monday of that week. Schema in `docs/UPDATING.md`.

## Weekly update (automated)

Every Sunday around 12:00 pm ET the CrossFit NYC newsletter (`newsletter@crossfitnyc.com`) lands in Gmail. The GitHub Actions workflow `.github/workflows/sync.yml` runs at ~12:45 pm ET (with later retries the same day):

1. `scripts/sync_newsletter.py` fetches the newest newsletter over Gmail IMAP.
2. Parses it into the week schema with the Claude API (`scripts/PARSE_PROMPT.md`).
3. Validates dates/structure, writes `data/weeks/<monday>.json`, appends to `data/index.json`, commits to `main`.
4. GitHub Pages redeploys.

The run is idempotent: if the week file already exists it exits without changes.

### One-time setup (repo → Settings → Secrets and variables → Actions)

| Name | Type | Value |
|---|---|---|
| `GMAIL_USER` | secret | the Gmail address the newsletter is delivered to |
| `GMAIL_APP_PASSWORD` | secret | a Gmail **App password** (Google Account → Security → 2-Step Verification → App passwords) |
| `ANTHROPIC_API_KEY` | secret | Anthropic API key |
| `CLAUDE_MODEL` | variable (optional) | model id; defaults to `claude-sonnet-4-5` |

Then run the workflow once by hand (Actions → "Sync newsletter → data" → Run workflow) with **dry_run** checked to confirm parsing before the first scheduled run.

Manual update without Actions: follow `docs/UPDATING.md`.
