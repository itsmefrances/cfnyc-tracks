# CFNYC Tracks

Dashboard of CrossFit NYC weekly programming, split by track (CrossFit, ATHX, Strength, Olympic Weightlifting), with a per-day track picker so you can compose your training week.

Live: https://itsmefrances.github.io/cfnyc-tracks/

## How it works

- `index.html` — self-contained static dashboard. Loads `data/index.json`, then the selected week file. Picks (which track on which day) are saved per week in the browser's `localStorage`. Data is re-fetched (cache-busted) every time the page is opened or re-focused.
- `data/index.json` — list of available weeks (the page sorts them).
- `data/weeks/YYYY-MM-DD.json` — one file per week, keyed by the Monday of that week. Schema in `docs/UPDATING.md`.

## Weekly update (automated)

Every Sunday around 12:06 pm ET the CrossFit NYC newsletter (`newsletter@crossfitnyc.com`) lands in Gmail. A Claude scheduled task ("CFNYC Tracks — Sunday sync") runs hourly from 12:15 pm to 4:15 pm ET on Sundays:

1. Checks `data/index.json` for next Monday's week; exits if it is already published.
2. Reads the newsletter from Gmail and parses it into the week schema (`scripts/PARSE_PROMPT.md`, `docs/UPDATING.md`).
3. Writes `data/weeks/<monday>.json`, appends to `data/index.json`, and commits both to `main` through the Claude GitHub connector (the **Claude Github MCP Connector** GitHub App must be installed on the account with read/write access to code).
4. GitHub Pages redeploys.

The run is idempotent: if the week file already exists it exits without changes.

### Alternative: GitHub Actions (optional)

`.github/workflows/sync.yml` + `scripts/sync_newsletter.py` do the same job on GitHub's runners (Gmail IMAP → Claude API → commit). The schedule is disabled by default; to use it, add the secrets below and re-enable the `schedule:` block.

| Name | Type | Value |
|---|---|---|
| `GMAIL_USER` | secret | the Gmail address the newsletter is delivered to |
| `GMAIL_APP_PASSWORD` | secret | a Gmail **App password** (Google Account → Security → 2-Step Verification → App passwords) |
| `ANTHROPIC_API_KEY` | secret | Anthropic API key |
| `CLAUDE_MODEL` | variable (optional) | model id; defaults to `claude-sonnet-4-5` |

Manual update: follow `docs/UPDATING.md`.
