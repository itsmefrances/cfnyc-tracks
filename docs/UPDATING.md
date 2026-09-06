# Updating the data

## Files

- `data/weeks/YYYY-MM-DD.json` — one file per week; `YYYY-MM-DD` is the **Monday** the programming starts (the newsletter says "week of September 7th" → `2026-09-07.json`).
- `data/index.json` — `{ "updated": ISO-8601, "weeks": [ { "week_of", "label", "file", "tracks": [...] } ] }`. Append the new week; never remove old ones.

## Week file schema

```jsonc
{
  "week_of": "2026-09-07",                       // Monday, ISO date
  "label": "Week of Sep 7, 2026",
  "source": { "subject", "sender", "received" /* ISO */, "gmail_message_id" },
  "cycle": {                                      // optional; omit if the newsletter has no cycle framing
    "track": "crossfit", "name": "New 6-week cycle", "week": 1, "of": 6,
    "focus": ["short bullet", "..."],
    "full_text": "the full cycle / programming write-up, verbatim (optional)"
  },
  "tracks": {
    "crossfit":  { "name": "CrossFit",               "note": "", "days": { "mon": DAY, ... } },
    "athx":      { "name": "ATHX",                   "note": "", "days": { "tue": DAY, "sat": DAY } },
    "strength":  { "name": "Strength",               "note": "", "days": { "thu": DAY } },
    "oly":       { "name": "Olympic Weightlifting",  "note": "", "days": { "wed": DAY } }
  },
  "announcements": [ { "title", "detail" } ]
}
```

`DAY`:

```jsonc
{
  "date": "2026-09-07",
  "title": "short human title (≤ 60 chars)",
  "sections": [
    { "label": "Strength", "est_minutes": 20, "lines": ["A1. ...", "A2. ..."],
      "stimulus": [ { "quality": "power", "regions": ["full body"], "minutes": 12 },
                    { "quality": "hypertrophy", "regions": ["upper push"], "minutes": 8 } ] },
    { "label": "Conditioning", "est_minutes": 13, "lines": ["4 Rounds, 2:30 AMRAP each:", "20 ...", "..."],
      "stimulus": [ { "quality": "hiit", "minutes": 13 } ] }
  ],
  "coach_notes": "the FULL coach write-up for this workout, verbatim from the newsletter, paragraphs separated by blank lines; empty string if none",
  "tags": ["barbell", "dumbbell", "kettlebell", "gymnastics", "jump rope", "run", "row", "ski", "bike", "sled", "sandbag", "wall ball", "box", "bodyweight"]
}
```

## Rules

1. Day keys are `mon`..`sat` (Sunday is never programmed). Only include a day for a track if the newsletter actually programmed it.
2. Track keys are fixed: `crossfit`, `athx`, `strength`, `oly`. Omit a track entirely if it has no programming that week. If a genuinely new track appears, add it with a new key and tell Frances.
3. `lines` are verbatim movements, reps, loads (keep `(95/65, 115/75)` style loads and `[Pro ...]` scaling). A line ending in `:` renders as a bold header (e.g. `"8 minute AMRAP:"`). Keep coach chatter out of `lines` — it goes in `coach_notes`.
   `coach_notes` is the complete coach write-up for that day, copied verbatim (every paragraph, original wording, blank line between paragraphs). Never summarize. For tracks whose commentary is written once for the whole week (ATHX, Strength), put that full text on each of that track's days. The dashboard shows it in a popup.
4. Section labels for CrossFit days: `Strength` and `Conditioning`. For multi-part days use `Part A — 10:00`, etc. Keep the newsletter's own labels for ATHX (`ATHX Strength (9–10 RPE)`, `ATHX MetCon / Endurance`, `ATHX Flow (Recovery)`) and Strength (`Main Lift`, `Successory — 3 × 10–14`, `Open Gym`). The dashboard counts a section as lifting if its label matches `/strength|lift|successory|open gym/i`.
5. `est_minutes` is an estimate of programmed work time (not class length): AMRAP/EMOM/interval totals are exact; "for time" pieces are a reasonable Rx estimate; strength blocks 20–25 min; open-gym strength 40; Oly class 60.
6. `tags` use the fixed vocabulary above. Add a new tag only when no existing one fits.
8. `stimulus` (per section) drives the "Week stimulus" panel. It is a list of `{quality, regions?, minutes}` items whose `minutes` sum to the section's `est_minutes`. One item per distinct piece (e.g. A1 and A2 get separate items when their quality or region differs).
   - Lifting qualities: `power` (Olympic lifts, jumps, throws — force fast), `strength` (heavy work ≤ 6 reps, RM tests, clusters), `hypertrophy` (8–15 reps, tempo work, accessories), `skill` (gymnastics/skill practice: pull-up → muscle-up progressions, HSPU practice).
   - Conditioning qualities (by dominant energy system / intensity): `aerobic` (steady or long mixed-modal ≥ 20 min, runs, hybrid race-style pieces), `threshold` (sustained hard 8–20 min pieces, AMRAPs 8–15 min, 2k row + swings), `vo2` (hard repeats of 2–5 min with rest), `hiit` (short intervals under ~2:30 with rest — EMOM/E2M bursts, 4 × 2:30 AMRAPs, station circuits), `sprint` (max-effort efforts under 60 s with full recovery).
   - `regions` (lifting only) from: `quads`, `posterior chain`, `upper push`, `upper pull`, `core`, `arms`, `full body`. Omit `regions` on conditioning items.
   - Mobility / flow / stretching sections get no `stimulus` key.
7. Validate before pushing: every file must parse as JSON, every `date` must be inside the week, and `index.json` must reference the new file.

## Commit

Push `data/weeks/YYYY-MM-DD.json` and the updated `data/index.json` to `main` in one commit:
`data: week of YYYY-MM-DD (tracks: crossfit, athx, strength, oly)`.
