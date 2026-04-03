"""Send email notifications via Gmail SMTP."""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_report_email(
    area_name: str,
    recipients: list[str],
    new: list[dict],
    changed: list[dict],
    removed: list[dict],
    dashboard_url: str,
) -> None:
    """Send email notification for listing changes."""
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_pass:
        print("GMAIL_USER or GMAIL_APP_PASSWORD not set, skipping email")
        return

    subject = f"[Reality Monitor] {area_name}: "
    parts = []
    if new:
        parts.append(f"{len(new)} nové")
    if changed:
        parts.append(f"{len(changed)} změna ceny")
    if removed:
        parts.append(f"{len(removed)} smazané")
    subject += ", ".join(parts)

    html = _build_html(area_name, new, changed, removed, dashboard_url)
    plain = _build_plain(area_name, new, changed, removed, dashboard_url)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, recipients, msg.as_string())
    print(f"Email sent to {recipients}")


def _format_price(price: int | None) -> str:
    if price is None:
        return "Cena na vyžádání"
    return f"{price:,} Kč".replace(",", " ")


def _build_html(area: str, new: list, changed: list, removed: list, url: str) -> str:
    sections = [f"<h2>Reality Monitor — {area}</h2>"]
    sections.append(f'<p><a href="{url}">Otevřít dashboard</a></p>')

    if new:
        sections.append("<h3>Nové inzeráty</h3><ul>")
        for l in new:
            price = _format_price(l.get("price"))
            area_m2 = f'{l.get("area_m2", "?")} m²'
            sections.append(
                f'<li><a href="{l["url"]}">{l["title"]}</a> — {l.get("location", "")} — '
                f'{price} — {area_m2}</li>'
            )
        sections.append("</ul>")

    if changed:
        sections.append("<h3>Změny cen</h3><ul>")
        for l in changed:
            history = l.get("price_history", [])
            if len(history) >= 2:
                old_p = history[-2]["price"]
                new_p = history[-1]["price"]
                if old_p and new_p and old_p != 0:
                    pct = ((new_p - old_p) / old_p) * 100
                    arrow = "↓" if pct < 0 else "↑"
                    color = "green" if pct < 0 else "red"
                    sections.append(
                        f'<li><a href="{l["url"]}">{l["title"]}</a> — '
                        f'{_format_price(old_p)} → {_format_price(new_p)} '
                        f'<span style="color:{color}">{arrow} {pct:+.1f}%</span></li>'
                    )
        sections.append("</ul>")

    if removed:
        sections.append("<h3>Smazané</h3><ul>")
        for l in removed:
            sections.append(f'<li>{l["title"]} — {l.get("location", "")} — byl {_format_price(l.get("price"))}</li>')
        sections.append("</ul>")

    return "\n".join(sections)


def _build_plain(area: str, new: list, changed: list, removed: list, url: str) -> str:
    lines = [f"Reality Monitor — {area}", f"Dashboard: {url}", ""]
    if new:
        lines.append(f"Nové ({len(new)}):")
        for l in new:
            lines.append(f"  • {l['title']} — {_format_price(l.get('price'))} — {l['url']}")
        lines.append("")
    if changed:
        lines.append(f"Změny cen ({len(changed)}):")
        for l in changed:
            lines.append(f"  • {l['title']} — {l['url']}")
        lines.append("")
    if removed:
        lines.append(f"Smazané ({len(removed)}):")
        for l in removed:
            lines.append(f"  • {l['title']}")
    return "\n".join(lines)
