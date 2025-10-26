#!/usr/bin/env python3
import re, html, requests
from xml.etree import ElementTree as ET

SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE   = "https://www.dropbox.com/scl/fi/fxvd9icshki3uzn61vm1o/CELESTIAL-WITH-STEVE-KELLEY-front.jpg?rlkey=jquwu0g9mu8mwu6ggalu6eusw&raw=1"

ITUNES_NS  = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)

def clean_lines(block: str):
    """Split text block into non-empty, de-dashed lines."""
    lines = []
    for ln in block.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        # skip separators like ----, ————
        if re.fullmatch(r"[-–—_]{3,}", ln):
            continue
        lines.append(ln)
    return lines

def paragraphs_from_text(text: str):
    """Turn plain text into <p>…</p> with <br/> for single newlines."""
    if not text:
        return ""
    esc = html.escape(text).replace("\r\n", "\n").replace("\r", "\n")
    paras = [p for p in esc.split("\n\n")]
    paras = [p.replace("\n", "<br/>") for p in paras]
    return "".join(f"<p>{p}</p>" for p in paras if p)

def build_html(desc_text: str) -> str:
    """
    Make neat HTML:
    - Intro paragraph(s)
    - blank line
    - Tracklist as <ul><li>…</li></ul> when present
    - blank line
    - 'Available to stream…' paragraph
    - blank line
    - 'Website: …' paragraph
    """
    if not desc_text:
        return ""

    src = desc_text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # Identify major sections
    # We look for a "Tracklist" marker (case-insensitive).
    tracklist_match = re.search(r"\btrack\s*list\b|\btracklist\b", src, flags=re.I)
    if tracklist_match:
        intro = src[:tracklist_match.start()].strip()
        after = src[tracklist_match.end():].strip()
    else:
        intro, after = src, ""

    # From the remaining text, try to isolate "Available…" and "Website…" lines (if present)
    # We split off any trailing marketing/info lines to keep lists clean.
    available_re = re.compile(r"^available\b.*", flags=re.I | re.M)
    website_re   = re.compile(r"^website\b.*|https?://\S+", flags=re.I | re.M)

    available_line = None
    website_line = None

    m_av = available_re.search(after)
    if m_av:
        available_line = m_av.group(0).strip()
        # remove it from 'after'
        after = (after[:m_av.start()] + after[m_av.end():]).strip()

    m_web = website_re.search(after)
    if m_web:
        website_line = m_web.group(0).strip()
        after = (after[:m_web.start()] + after[m_web.end():]).strip()

    # Build Tracklist items from what's left in 'after'
    # Remove any leading separators
    after_clean = re.sub(r"^\s*[-–—_]{3,}\s*", "", after.strip(), flags=re.M)
    track_items = clean_lines(after_clean) if tracklist_match else []

    # --- Assemble HTML ---
    html_parts = []

    # Intro paragraphs
    if intro:
        html_parts.append(paragraphs_from_text(intro))

    # Blank line (space) before Tracklist if we have one
    if track_items:
        html_parts.append("<p></p>")  # visual spacer
        html_parts.append("<p><strong>Tracklist:</strong></p>")
        html_parts.append("<ul>")
        for item in track_items:
            html_parts.append(f"<li>{html.escape(item)}</li>")
        html_parts.append("</ul>")

    # Blank line, then Available…
    if available_line:
        html_parts.append("<p></p>")
        html_parts.append(f"<p>{html.escape(available_line)}</p>")

    # Blank line, then Website…
    if website_line:
        html_parts.append("<p></p>")
        # If it's a URL only, link it; otherwise preserve text
        if re.fullmatch(r"https?://\S+", website_line, flags=re.I):
            html_parts.append(f'<p>Website: <a href="{html.escape(website_line)}">{html.escape(website_line)}</a></p>')
        else:
            # Try to link any URL within the line
            linked = re.sub(
                r"(https?://\S+)",
                lambda m: f'<a href="{html.escape(m.group(1))}">{html.escape(m.group(1))}</a>',
                html.escape(website_line),
            )
            html_parts.append(f"<p>{linked}</p>")

    return "".join(html_parts)

def main():
    r = requests.get(SOURCE_FEED, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    # ---- channel ----
    channel = None
    for child in root.iter():
        if child.tag.endswith("channel"):
            channel = child
            break
    if channel is None:
        raise RuntimeError("Could not find <channel> in source feed.")

    # Replace/insert <itunes:image>
    itunes_tag = "{" + ITUNES_NS + "}image"
    for elem in list(channel):
        if elem.tag == itunes_tag or (elem.tag.endswith("image") and "itunes" in elem.tag):
            channel.remove(elem)
    img = ET.Element(itunes_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # For each item: add/replace <content:encoded> with our HTML; keep itunes:summary as plain text
    content_tag = "{" + CONTENT_NS + "}encoded"
    for item in channel.findall("./item"):
        # Prefer description; fallback to itunes:summary if needed
        desc_el = item.find("description")
        desc_text = (desc_el.text or "").strip() if desc_el is not None else ""
        if not desc_text:
            its_sum = item.find("{" + ITUNES_NS + "}summary")
            if its_sum is not None and its_sum.text:
                desc_text = its_sum.text.strip()

        html_body = build_html(desc_text)

        # content:encoded (HTML)
        existing = item.find(content_tag)
        if existing is None:
            existing = ET.SubElement(item, content_tag)
        existing.text = html_body  # ElementTree will include it as text; HTML is fine.

        # itunes:summary (plain)
        its_sum = item.find("{" + ITUNES_NS + "}summary")
        if its_sum is None:
            its_sum = ET.SubElement(item, "{" + ITUNES_NS + "}summary")
        its_sum.text = desc_text or ""

    # Write out
    with open("feed.xml", "wb") as f:
        f.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))

if __name__ == "__main__":
    main()
