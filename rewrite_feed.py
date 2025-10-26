#!/usr/bin/env python3
import requests, html
from xml.etree import ElementTree as ET

SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE = "https://www.dropbox.com/scl/fi/fxvd9icshki3uzn61vm1o/CELESTIAL-WITH-STEVE-KELLEY-front.jpg?rlkey=jquwu0g9mu8mwu6ggalu6eusw&raw=1"

ITUNES_NS  = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)

def to_html_paragraphs(text: str) -> str:
    """
    Convert plain text with newlines into simple HTML Apple renders nicely:
    - Double newlines -> new paragraph
    - Single newlines -> <br/>
    """
    if text is None:
        return ""
    # Escape any accidental HTML, then apply breaks
    esc = html.escape(text)
    # Normalize Windows CRLF
    esc = esc.replace("\r\n", "\n").replace("\r", "\n")
    # Paragraphs first (double newline)
    parts = [p for p in esc.split("\n\n")]
    parts = [p.replace("\n", "<br/>") for p in parts]
    return "<p>" + "</p><p>".join(parts) + "</p>"

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

    # ---- items: add <content:encoded> with HTML formatting ----
    content_tag = "{" + CONTENT_NS + "}encoded"
    for item in channel.findall("./item"):
        # grab plain description
        desc_el = item.find("description")
        desc_text = desc_el.text if desc_el is not None else ""

        # build HTML version
        html_body = to_html_paragraphs(desc_text)

        # replace or add <content:encoded> (wrapped in CDATA by ElementTree-safe trick)
        # ElementTree can’t emit CDATA easily; Apple is fine with normal text containing HTML.
        # So we set text to the HTML string directly.
        existing = item.find(content_tag)
        if existing is None:
            existing = ET.SubElement(item, content_tag)
        existing.text = html_body

        # Optional: keep a concise itunes:summary (plain text, no HTML)
        itunes_summary = item.find("{" + ITUNES_NS + "}summary")
        if itunes_summary is None:
            itunes_summary = ET.SubElement(item, "{" + ITUNES_NS + "}summary")
        itunes_summary.text = desc_text  # unchanged, plain text

    # Write out
    with open("feed.xml", "wb") as f:
        f.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))

if __name__ == "__main__":
    main()
