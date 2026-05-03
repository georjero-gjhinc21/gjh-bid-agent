"""Gmail tools — IMAP read for Scout, SMTP send for digest delivery.

Uses Google App Passwords. No OAuth flow needed.
"""
from __future__ import annotations
import imaplib
import email
import smtplib
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any

import config
from agents.base import Tool


def _imap_connect():
    m = imaplib.IMAP4_SSL("imap.gmail.com")
    m.login(config.secret("GMAIL_USER"), config.secret("GMAIL_APP_PASSWORD"))
    return m


def _decode(part) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _body_text(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return _decode(part)
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                return _decode(part)
        return ""
    return _decode(msg)


# ---------- tool: search recent bid-alert emails ----------
def _search_alerts(state, hours: int = 26, max_results: int = 50) -> list[dict]:
    """Search inbox for bid-aggregator alerts in the last N hours."""
    since_dt = datetime.now(timezone.utc).timestamp() - hours * 3600
    senders = config.ALERT_SENDERS

    m = _imap_connect()
    try:
        m.select("INBOX", readonly=True)
        criteria = "OR " * (len(senders) - 1) + " ".join(
            f'FROM "{s}"' for s in senders
        )
        criteria = f"({criteria})"
        typ, data = m.search(None, criteria)
        if typ != "OK":
            return []
        ids = data[0].split()
        results: list[dict] = []
        for msg_id in reversed(ids[-200:]):  # newest first, cap scan
            typ, msg_data = m.fetch(msg_id, "(RFC822)")
            if typ != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            try:
                ts = parsedate_to_datetime(msg["Date"]).timestamp()
            except Exception:
                continue
            if ts < since_dt:
                break  # newest-first, we've gone past the window
            results.append({
                "from": msg.get("From", ""),
                "subject": msg.get("Subject", ""),
                "date": msg.get("Date", ""),
                "body_excerpt": _body_text(msg)[:4000],
            })
            if len(results) >= max_results:
                break
        return results
    finally:
        try:
            m.logout()
        except Exception:
            pass


def _save_opportunity(state, **opp) -> dict:
    """Persist an opportunity. Idempotent on (source, source_detail)."""
    required = ("source", "title")
    for k in required:
        if not opp.get(k):
            return {"error": f"missing required field: {k}"}
    opp_id = state.upsert_opportunity(opp)
    return {"saved": True, "id": opp_id}


def _send_digest(state, subject: str, body: str, to: str | None = None) -> dict:
    """Send the daily digest email."""
    msg = EmailMessage()
    msg["From"] = config.secret("GMAIL_USER")
    msg["To"] = to or config.secret("DIGEST_TO", required=False) or config.secret("GMAIL_USER")
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(config.secret("GMAIL_USER"), config.secret("GMAIL_APP_PASSWORD"))
        s.send_message(msg)
    state.log_digest(body)
    return {"sent": True, "to": msg["To"]}


# ---------- exported Tool definitions ----------
search_alerts = Tool(
    name="search_alerts",
    description=(
        "Search the inbox for recent bid-aggregator alert emails. Returns a "
        "list of {from, subject, date, body_excerpt}. Use this once per run "
        "to find new opportunities."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "hours": {"type": "integer", "description": "Lookback window in hours (default 26)."},
            "max_results": {"type": "integer", "description": "Cap results (default 50)."},
        },
    },
    fn=_search_alerts,
)

save_opportunity = Tool(
    name="save_opportunity",
    description=(
        "Save a discovered opportunity to the database. Required fields: "
        "source ('gmail'|'web'), title. Optional: source_detail, buyer, "
        "bid_number, deadline (ISO), url, raw_text, fit_score (0-100), "
        "fit_rationale (one sentence)."
    ),
    input_schema={
        "type": "object",
        "required": ["source", "title"],
        "properties": {
            "source":         {"type": "string", "enum": ["gmail", "web", "manual"]},
            "source_detail":  {"type": "string"},
            "title":          {"type": "string"},
            "buyer":          {"type": "string"},
            "bid_number":     {"type": "string"},
            "deadline":       {"type": "string"},
            "url":            {"type": "string"},
            "raw_text":       {"type": "string"},
            "fit_score":      {"type": "integer", "minimum": 0, "maximum": 100},
            "fit_rationale":  {"type": "string"},
        },
    },
    fn=_save_opportunity,
)

send_digest = Tool(
    name="send_digest",
    description="Send the daily digest email to the CEO.",
    input_schema={
        "type": "object",
        "required": ["subject", "body"],
        "properties": {
            "subject": {"type": "string"},
            "body":    {"type": "string", "description": "Plain-text digest body."},
            "to":      {"type": "string", "description": "Override recipient."},
        },
    },
    fn=_send_digest,
)
