"""Build the session-summary e-mail (plain text + simple HTML + report attachments)."""

from __future__ import annotations

import html
import mimetypes
from collections.abc import Sequence
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from parkomate.config.settings import EmailSettings
from parkomate.core.clock import to_local
from parkomate.core.models import SessionSummary
from parkomate.i18n import tr
from parkomate.reports.layout import SUMMARY_FIELDS, summary_label
from parkomate.reports.writers import cell_text

_KNOWN_TYPES: dict[str, tuple[str, str]] = {
    ".xlsx": ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ".csv": ("text", "csv"),
}


def attachment_type(path: Path) -> tuple[str, str]:
    """MIME type of a report file. Fixed for our formats: the Windows registry maps .csv to
    ``application/vnd.ms-excel``, which some mail clients refuse to preview."""
    known = _KNOWN_TYPES.get(path.suffix.lower())
    if known is not None:
        return known
    guessed, _ = mimetypes.guess_type(path.name)
    maintype, _, subtype = (guessed or "application/octet-stream").partition("/")
    return maintype, subtype


def summary_lines(summary: SessionSummary, lang: str, station_id: str) -> list[tuple[str, str]]:
    """``(label, value)`` pairs, same fields and order as the Summary sheet."""
    lines: list[tuple[str, str]] = []
    for field_ in SUMMARY_FIELDS:
        value = field_.get(summary, lang, station_id)
        lines.append((summary_label(field_, lang), cell_text(field_.kind, value, lang)))
    return lines


def compose_session_email(
    summary: SessionSummary,
    attachments: Sequence[Path],
    *,
    settings: EmailSettings,
    station_id: str,
    lang: str,
) -> EmailMessage:
    started = to_local(summary.session.started_at)
    subject = tr(
        lang,
        "mail.subject",
        station=station_id,
        session=summary.session.id,
        date=f"{started:%Y-%m-%d}",
    )
    message = EmailMessage()
    message["Subject"] = f"{settings.subject_prefix} {subject}".strip()
    message["From"] = settings.sender
    message["To"] = ", ".join(settings.recipients)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="parkomate.station")

    lines = summary_lines(summary, lang, station_id)
    intro = tr(lang, "mail.intro", station=station_id, session=summary.session.id)
    footer = tr(lang, "mail.footer")
    width = max(len(label) for label, _ in lines)
    plain = "\n".join(
        [intro, "", *(f"{label.ljust(width)}  {value}" for label, value in lines), "", footer]
    )
    message.set_content(plain)

    rows = "\n".join(
        f'<tr><th align="left" style="padding:4px 12px 4px 0">{html.escape(label)}</th>'
        f'<td style="padding:4px 0">{html.escape(value)}</td></tr>'
        for label, value in lines
    )
    body = (
        '<!doctype html><html><body style="font-family:Segoe UI,Arial,sans-serif">'
        f"<p>{html.escape(intro)}</p>"
        f'<table style="border-collapse:collapse">{rows}</table>'
        f'<p style="color:#555">{html.escape(footer)}</p>'
        "</body></html>"
    )
    message.add_alternative(body, subtype="html")

    for path in attachments:
        maintype, subtype = attachment_type(path)
        message.add_attachment(
            path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name
        )
    return message
