#!/usr/bin/env python3
import re, html, requests
from xml.etree import ElementTree as ET

SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE = "https://djstevekelley.github.io/celestial-feed/Celestial_Podcast_Cover_3000x3000.jpg"

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)
ET.register_namespace("atom", ATOM_NS)

# ----------- helpers -----------
def clean_lines(block: str):
    """Split text block into non-empty lines and drop separator lines."""
    lines = []
    for ln in block.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if re.fullmatch(r"[-_]{3,}", ln):
            continue
        lines.append(ln)
    return lines


def paragraphs_from_text(text: str):
    """Split text into paragraphs by blank lines."""
    paras = []
    current = []
    for ln in text.splitlines():
        if not ln.strip():
            if current:
                paras.append(" ".join(current))
                current = []
        else:
            current.append(ln.strip())
    if current:
        paras.append(" ".join(current))
    return paras


def format_description(desc: str):
    """Apply HTML formatting to the tracklist description."""
    desc = html.unescape(desc)
    parts = []
    lines = clean_lines(desc)
    in_tracklist = False
    for ln in lines:
        if "tracklist" in ln.lower():
            parts.append("<b>Tracklist:</b><br/>")
            in_tracklist = True
            continue
        if in_tracklist:
            if not ln.strip() or "available on" in ln.lower():
                in_tracklist = False
                parts.append("<br/>")
            else:
                parts.append(f"• {ln}<br/>")
                continue
        parts.append(f"{ln}<br/>")

    formatted = "".join(parts)
    formatted = re.sub(r"<br/>{2,}", "<br/>", formatted)
    return formatted


# ----------- main -----------
def main():
    r = requests.get(SOURCE_FEED, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    # find <channel>
    channel = None
    for child in root.iter():
        if child.tag.endswith("channel"):
            channel = child
            break
    if channel is None:
        raise RuntimeError("Could not find <channel> in source feed.")

    # --- Standards additions: Atom self-link + iTunes explicit flag ---
    FEED_URL = "https://djstevekelley.github.io/celestial-feed/feed.xml"

    # 1) Ensure <atom:link rel="self" .../> exists
    atom_self = None
    for el in channel.findall(f"{{{ATOM_NS}}}link"):
        if el.get("rel") == "self":
            atom_self = el
            break

    if atom_self is None:
        atom_self = ET.Element(f"{{{ATOM_NS}}}link", {
            "href": FEED_URL,
            "rel": "self",
            "type": "application/rss+xml",
        })
        channel.insert(0, atom_self)
    else:
        atom_self.set("href", FEED_URL)
        atom_self.set("rel", "self")
        atom_self.set("type", "application/rss+xml")

    # 2) Ensure <itunes:explicit>no</itunes:explicit> exists
    explicit_el = channel.find("{" + ITUNES_NS + "}explicit")
    if explicit_el is None:
        explicit_el = ET.Element("{" + ITUNES_NS + "}explicit")
        channel.append(explicit_el)
    explicit_el.text = "no"

    # replace/insert itunes:image
    itunes_tag = "{" + ITUNES_NS + "}image"
    for elem in list(channel):
        if elem.tag == itunes_tag or (elem.tag.endswith("image") and "itunes" in elem.tag):
            channel.remove(elem)
    img = ET.Element(itunes_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # rewrite descriptions
    for item in channel.findall("item"):
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            formatted = format_description(desc_el.text)
            desc_el.text = formatted

    # output XML
    tree = ET.ElementTree(root)
    tree.write("feed.xml", encoding="utf-8", xml_declaration=True)


if __name__ == "__main__":
    main()
