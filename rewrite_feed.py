#!/usr/bin/env python3
import re, html, requests
from xml.etree import ElementTree as ET

# --- configuration ---
SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE   = "https://djstevekelley.github.io/celestial-feed/Celestial_Podcast_Cover_3000x3000.jpg"

ITUNES_NS   = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS  = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS     = "http://www.w3.org/2005/Atom"
PODCAST_NS  = "https://podcastindex.org/namespace/1.0"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)
ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("podcast", PODCAST_NS)


# --- helpers ---
def clean_lines(block: str):
    lines = []
    for ln in block.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if re.fullmatch(r"[-_]{3,}", ln):
            continue
        lines.append(ln)
    return lines


def format_description(desc: str):
    desc = html.unescape(desc)
    lines = clean_lines(desc)
    formatted = []
    in_tracklist = False

    for ln in lines:
        low = ln.lower()
        if "tracklist" in low and not in_tracklist:
            formatted.append("<b>Tracklist:</b><br/>")
            in_tracklist = True
            continue

        if low.startswith("available to stream"):
            formatted.append("<br/>")

        if in_tracklist:
            if not ln.strip() or low.startswith("available to stream"):
                in_tracklist = False
            else:
                formatted.append(f"• {ln}<br/>")
                continue

        formatted.append(f"{ln}<br/>")

    formatted = "".join(formatted)
    formatted = re.sub(r"(?:<br/>){3,}", "<br/><br/>", formatted)
    return formatted


# --- main ---
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

    # --- replace itunes:image ---
    itunes_tag = "{" + ITUNES_NS + "}image"
    for elem in list(channel):
        if elem.tag == itunes_tag or (elem.tag.endswith("image") and "itunes" in elem.tag):
            channel.remove(elem)
    img = ET.Element(itunes_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # --- add <itunes:explicit>no</itunes:explicit> if missing ---
    explicit_tag = "{" + ITUNES_NS + "}explicit"
    if not any(el.tag == explicit_tag for el in channel):
        explicit_el = ET.Element(explicit_tag)
        explicit_el.text = "no"
        channel.insert(1, explicit_el)

    # --- reformat episode descriptions ---
    for item in channel.findall("item"):
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            desc_el.text = format_description(desc_el.text)

    ET.ElementTree(root).write("feed.xml", encoding="UTF-8", xml_declaration=True)


if __name__ == "__main__":
    main()
