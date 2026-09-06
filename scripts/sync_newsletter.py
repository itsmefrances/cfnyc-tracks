#!/usr/bin/env python3
"""Fetch the latest CrossFit NYC newsletter from Gmail (IMAP), parse it into a week file
with the Claude API, validate, and write data/weeks/<week_of>.json + data/index.json.

Env:
  GMAIL_USER, GMAIL_APP_PASSWORD   Gmail address + app password (2-Step Verification required)
  ANTHROPIC_API_KEY                Anthropic API key
  CLAUDE_MODEL                     model id (default claude-sonnet-4-5)
  DRY_RUN=1                        parse + print, do not write
  FORCE=1                          re-parse even if the week file exists
  LOOKBACK_DAYS                    default 3
  NEWSLETTER_FROM                  default newsletter@crossfitnyc.com
  NEWSLETTER_FILE                  skip IMAP and parse this local text file (for testing)
"""
from __future__ import annotations

import datetime as dt
import email
import email.utils
import html
import imaplib
import json
import os
import re
import sys
from email.header import decode_header, make_header
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WEEKS = DATA / "weeks"
INDEX = DATA / "index.json"
PROMPT_FILE = ROOT / "scripts" / "PARSE_PROMPT.md"
SCHEMA_FILE = ROOT / "docs" / "UPDATING.md"

TRACKS = ["crossfit", "athx", "strength", "oly"]
DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat"]
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def set_output(k, v):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"{k}={v}\n")


# ---------------------------------------------------------------- fetch
def fetch_newsletter() -> dict:
    path = os.environ.get("NEWSLETTER_FILE")
    if path:
        text = Path(path).read_text()
        return {"text": text, "subject": "Crossfit NYC Newsletter (local file)", "message_id": "",
                "received": dt.datetime.now(dt.timezone.utc).isoformat()}

    user = os.environ["GMAIL_USER"]
    pw = os.environ["GMAIL_APP_PASSWORD"]
    sender = os.environ.get("NEWSLETTER_FROM", "newsletter@crossfitnyc.com")
    lookback = int(os.environ.get("LOOKBACK_DAYS", "3"))
    since = (dt.date.today() - dt.timedelta(days=lookback)).strftime("%d-%b-%Y")

    m = imaplib.IMAP4_SSL("imap.gmail.com")
    m.login(user, pw)
    # All Mail so an archived (non-INBOX) newsletter is still found.
    typ, _ = m.select('"[Gmail]/All Mail"', readonly=True)
    if typ != "OK":
        m.select("INBOX", readonly=True)
    typ, data = m.search(None, "FROM", f'"{sender}"', "SINCE", since)
    ids = data[0].split() if typ == "OK" else []
    if not ids:
        log(f"No newsletter from {sender} since {since}")
        return {}

    best = None
    for mid in ids:
        typ, raw = m.fetch(mid, "(INTERNALDATE RFC822)")
        if typ != "OK":
            continue
        msg = email.message_from_bytes(raw[0][1])
        received = email.utils.parsedate_to_datetime(msg.get("Date"))
        if best is None or received > best[0]:
            best = (received, msg)
    m.logout()
    received, msg = best
    subject = str(make_header(decode_header(msg.get("Subject", ""))))

    plain, htmlbody = None, None
    for part in msg.walk():
        ct = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        body = payload.decode(charset, errors="replace")
        if ct == "text/plain" and plain is None:
            plain = body
        elif ct == "text/html" and htmlbody is None:
            htmlbody = body
    text = plain or html_to_text(htmlbody or "")
    text = re.sub(r"\[https?://\S+?\]", "", text)          # strip tracking-link brackets
    text = re.sub(r"https?://email\.replies\.\S+", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return {"text": text, "subject": subject, "message_id": msg.get("Message-ID", ""),
            "received": received.astimezone(dt.timezone.utc).isoformat()}


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


# ---------------------------------------------------------------- week key
def next_monday(d: dt.date) -> dt.date:
    return d + dt.timedelta(days=(7 - d.weekday()) % 7 or 7)


def week_of_from_text(text: str, received: dt.datetime) -> dt.date:
    m = re.search(r"week of\s+([A-Za-z]+)\s+(\d{1,2})", text, re.I)
    if m and m.group(1).lower() in MONTHS:
        year = received.year
        d = dt.date(year, MONTHS[m.group(1).lower()], int(m.group(2)))
        if (d - received.date()).days < -30:            # December email about January
            d = dt.date(year + 1, d.month, d.day)
        if d.weekday() != 0:
            log(f"'week of' date {d} is not a Monday; snapping back to Monday")
            d = d - dt.timedelta(days=d.weekday())
        return d
    return next_monday(received.date())


# ---------------------------------------------------------------- parse
def parse_with_claude(text: str, week_of: dt.date, subject: str) -> dict:
    import anthropic

    system = PROMPT_FILE.read_text()
    schema = SCHEMA_FILE.read_text()
    example = ""
    prior = sorted(WEEKS.glob("*.json"))
    if prior:
        example = prior[-1].read_text()
    user = (
        f"WEEK_OF: {week_of.isoformat()} (Monday)\nSUBJECT: {subject}\n\n"
        f"=== SCHEMA (docs/UPDATING.md) ===\n{schema}\n\n"
        + (f"=== EXAMPLE OF A PREVIOUS WEEK FILE ===\n{example}\n\n" if example else "")
        + f"=== NEWSLETTER TEXT ===\n{text}\n\n"
        "Return ONLY the JSON object for this week. No prose, no code fences."
    )
    client = anthropic.Anthropic()
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
    resp = client.messages.create(model=model, max_tokens=16000, temperature=0,
                                  system=system, messages=[{"role": "user", "content": user}])
    out = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out)
    start, end = out.find("{"), out.rfind("}")
    return json.loads(out[start:end + 1])


# ---------------------------------------------------------------- validate
def validate(week: dict, week_of: dt.date) -> list[str]:
    errs = []
    if week.get("week_of") != week_of.isoformat():
        errs.append(f"week_of {week.get('week_of')!r} != {week_of}")
    if not week.get("label"):
        errs.append("missing label")
    tracks = week.get("tracks") or {}
    if not tracks:
        errs.append("no tracks")
    for t, tr in tracks.items():
        if t not in TRACKS:
            log(f"WARNING: unknown track key {t!r} — allowed but review it")
        if not tr.get("name"):
            errs.append(f"{t}: missing name")
        days = tr.get("days") or {}
        if not days:
            errs.append(f"{t}: no days")
        for d, w in days.items():
            if d not in DAY_KEYS:
                errs.append(f"{t}.{d}: bad day key")
                continue
            exp = week_of + dt.timedelta(days=DAY_KEYS.index(d))
            if w.get("date") != exp.isoformat():
                errs.append(f"{t}.{d}: date {w.get('date')} != {exp}")
            if not w.get("title"):
                errs.append(f"{t}.{d}: missing title")
            secs = w.get("sections") or []
            if not secs:
                errs.append(f"{t}.{d}: no sections")
            for s in secs:
                if not s.get("label") or not s.get("lines"):
                    errs.append(f"{t}.{d}: section missing label/lines")
                if not isinstance(s.get("est_minutes", 0), (int, float)):
                    errs.append(f"{t}.{d}: est_minutes not numeric")
            w.setdefault("coach_notes", "")
            w.setdefault("tags", [])
    week.setdefault("announcements", [])
    return errs


# ---------------------------------------------------------------- main
def main() -> int:
    dry = os.environ.get("DRY_RUN") == "1"
    force = os.environ.get("FORCE") == "1"
    nl = fetch_newsletter()
    if not nl:
        set_output("changed", "false")
        return 0
    received = dt.datetime.fromisoformat(nl["received"])
    week_of = week_of_from_text(nl["text"], received)
    target = WEEKS / f"{week_of.isoformat()}.json"
    log(f"Newsletter '{nl['subject']}' received {nl['received']} → week_of {week_of}")
    if target.exists() and not force:
        log(f"{target.name} already exists; nothing to do")
        set_output("changed", "false")
        return 0

    week = parse_with_claude(nl["text"], week_of, nl["subject"])
    week["source"] = {"subject": nl["subject"], "sender": os.environ.get("NEWSLETTER_FROM", "newsletter@crossfitnyc.com"),
                      "received": nl["received"], "message_id": nl["message_id"]}
    errs = validate(week, week_of)
    if errs:
        log("VALIDATION FAILED:\n  " + "\n  ".join(errs))
        log(json.dumps(week, indent=2)[:4000])
        set_output("changed", "false")
        return 1

    tracks = [t for t in TRACKS if t in week["tracks"]] + [t for t in week["tracks"] if t not in TRACKS]
    if dry:
        print(json.dumps(week, indent=2, ensure_ascii=False))
        set_output("changed", "false")
        return 0

    WEEKS.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(week, indent=2, ensure_ascii=False) + "\n")
    index = json.loads(INDEX.read_text()) if INDEX.exists() else {"weeks": []}
    entry = {"week_of": week_of.isoformat(), "label": week["label"],
             "file": f"weeks/{week_of.isoformat()}.json", "tracks": tracks}
    index["weeks"] = [w for w in index["weeks"] if w["week_of"] != entry["week_of"]] + [entry]
    index["weeks"].sort(key=lambda w: w["week_of"])
    index["updated"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    log(f"Wrote {target.name} and updated index ({len(index['weeks'])} weeks)")
    set_output("changed", "true")
    set_output("week_of", week_of.isoformat())
    set_output("tracks", ", ".join(tracks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
