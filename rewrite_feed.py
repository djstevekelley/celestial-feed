#!/usr/bin/env python3
import re, html, requests
from xml.etree import ElementTree as ET

# --- CONFIG ---
SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE = "https://djstevekelley.github.io/celestial-feed/Celestial_Podcast_Cover_3000x3000.jpg"

# --- NAMESPACES ---
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS = "http://www.w3.org/2005/Atom"
PODCAST_NS = "https://podcastindex.org/namespace/1.0"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)
ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("podcast", PODCAST_NS)


# --- HELPERS ---
def clean_lines(block: str):
    lines = []
    for ln in block.splitlines():
        ln = ln.strip()
        if not ln or re.fullmatch(r"[-_]{3,}", ln):
            continue
        lines.append(ln)
    return lines


def paragraphs_from_text(text: str):
    lines = clean_lines(text)
    parts, para = [], []
    for ln in lines:
        if not ln:
            if para:
                parts.append("<p>" + " ".join(para) + "</p>")
                para = []
        else:
            para.append(html.escape(ln))
    if para:
        parts.append("<p>" + " ".join(para) + "</p>")
    return "\n".join(parts)


# --- MAIN ---
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

    # replace/insert itunes:image
    itunes_tag = "{%s}image" % ITUNES_NS
    for elem in list(channel):
        if elem.tag == itunes_tag or (elem.tag.endswith("image") and "itunes" in elem.tag):
            channel.remove(elem)
    img = ET.Element(itunes_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # ensure itunes:explicit exists
    explicit_tag = "{%s}explicit" % ITUNES_NS
    found_explicit = any(elem.tag == explicit_tag for elem in channel)
    if not found_explicit:
        explicit = ET.Element(explicit_tag)
        explicit.text = "no"
        channel.insert(1, explicit)

    # ensure podcast namespace tag presence
    root.set("xmlns:podcast", PODCAST_NS)

    # write output XML
    ET.indent(root)
    with open("feed.xml", "wb") as f:
        f.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))


if __name__ == "__main__":
    main()
