import hashlib
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup, Comment


def format_datetime_br(iso_string):
    """Converte ISO string (UTC) para formato brasileiro com timezone BR (UTC-3)."""
    if not iso_string:
        return "-"
    try:
        # Parse ISO string (ex: "2024-06-01T10:30:45Z")
        dt_utc = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        # Converter para timezone Brasil (UTC-3)
        tz_br = timezone(timedelta(hours=-3))
        dt_br = dt_utc.astimezone(tz_br)
        # Formatar: DD/MM/YYYY HH:MM:SS
        return dt_br.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return iso_string


def clean_html_content(html_text, selector=None):
    soup = BeautifulSoup(html_text, "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "header", "footer", "svg", "canvas", "meta", "link", "form", "input", "button", "aside"]):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    if selector:
        selected = soup.select(selector)
        if selected:
            nodes = selected
        else:
            nodes = [soup.body or soup]
    else:
        nodes = [soup.body or soup]

    parts = [node.get_text(" ", strip=True) for node in nodes]
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compute_hash(value):
    text = value or ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
