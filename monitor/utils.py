import hashlib
import re
from bs4 import BeautifulSoup, Comment


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
