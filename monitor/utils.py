import hashlib
import re
import difflib
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup, Comment


def normalize_text(text):
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text.strip())
    return cleaned


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


def section_label(element):
    if element.name and element.name.startswith("h"):
        label = normalize_text(element.get_text(" ", strip=True))
        return label or element.name
    if element.has_attr("id"):
        return f"{element.name}#{element['id']}"
    if element.has_attr("class"):
        classes = ".".join([cls for cls in element.get("class", []) if cls])
        return f"{element.name}.{classes}" if classes else element.name
    return element.name or "section"


def section_identifier(element, index=0):
    if element.has_attr("id"):
        return f"{element.name}#{element['id']}"
    if element.has_attr("class"):
        classes = ".".join([cls for cls in element.get("class", []) if cls])
        if classes:
            return f"{element.name}.{classes}"
    position = 0
    for prev in element.find_previous_siblings(element.name):
        position += 1
    return f"{element.name}[{position}]"


def extract_section_diff(old_text, new_text):
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    diff_lines = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=0))
    return diff_lines


def segment_html_sections(html_text, selector=None):
    soup = BeautifulSoup(html_text, "html.parser")

    for tag in soup(["script", "style", "noscript", "iframe", "header", "footer", "svg", "canvas", "meta", "link", "form", "input", "button", "aside"]):
        tag.decompose()

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    if selector:
        selected = soup.select(selector)
        if selected:
            roots = selected
        else:
            roots = [soup.body or soup]
    else:
        roots = [soup.body or soup]

    relevant_tags = ["h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol", "li", "p", "article", "section", "div"]
    sections = []
    seen_ids = set()

    for root in roots:
        candidates = []
        if root.name in relevant_tags and root is not soup.body:
            candidates = [root]
        else:
            candidates = [child for child in root.find_all(relevant_tags, recursive=False)]
            if not candidates and root is not soup.body:
                candidates = [root]

        for index, element in enumerate(candidates):
            content = normalize_text(element.get_text(" ", strip=True))
            if not content:
                continue
            section_id = section_identifier(element, index)
            if section_id in seen_ids:
                section_id = f"{section_id}_{index}"
            seen_ids.add(section_id)
            sections.append({
                "id": section_id,
                "label": section_label(element),
                "content": content,
            })

    if not sections and roots:
        fallback = normalize_text(roots[0].get_text(" ", strip=True))
        if fallback:
            sections.append({"id": "body", "label": "body", "content": fallback})

    return sections


def compare_sections(old_sections, new_sections):
    old_map = {section["id"]: section for section in old_sections}
    new_map = {section["id"]: section for section in new_sections}

    modified = []
    added = []
    removed = []

    for section_id, section in new_map.items():
        if section_id not in old_map:
            added.append({"id": section_id, "label": section["label"], "content": section["content"]})
        else:
            old_content = old_map[section_id]["content"]
            if section["content"] != old_content:
                modified.append({
                    "id": section_id,
                    "label": section["label"],
                    "old_content": old_content,
                    "new_content": section["content"],
                    "diff": extract_section_diff(old_content, section["content"]),
                })

    for section_id, section in old_map.items():
        if section_id not in new_map:
            removed.append({"id": section_id, "label": section["label"], "content": section["content"]})

    return {
        "alterado": bool(modified or added or removed),
        "secoes_modificadas": modified,
        "itens_adicionados": added,
        "itens_removidos": removed,
    }
