#!/usr/bin/env python3
import re, html, requests
from xml.etree import ElementTree as ET

# --- CONFIG ---
SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE   = "https://djstevekelley.github.io/celestial-feed/Celestial_Podcast_Cover_3000x3000.jpg"

# --- NAMESPACES ---
ITUNES_NS   = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS  = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS     = "http://www.w3.org/2005/Atom"
PODCAST_NS  = "https://podcastindex.org/namespace/1.0"

ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)
ET.register_namespace("atom", ATOM_NS)
ET.register_namespace("podcast", PODCAST_NS)


# --- HELPERS (minimal; leave episodes alone) ---
def clean_lines(block: str):
    out = []
    for ln in block.splitlines():
        ln = ln.strip()
        if not ln or re.fullmatch(r"[-_]{3,}", ln):
            continue
        out.append(ln)
    return out


# --- MAIN ---
def main():
    # fetch source feed
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

    # --- ensure itunes:image (channel artwork) ---
    itunes_image_tag = "{" + ITUNES_NS + "}image"
    for elem in list(channel):
        if elem.tag == itunes_image_tag or (elem.tag.endswith("image") and "itunes" in elem.tag):
            channel.remove(elem)
    img = ET.Element(itunes_image_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # --- ensure itunes:explicit at channel level ---
    explicit_tag = "{" + ITUNES_NS + "}explicit"
    if not any(el.tag == explicit_tag for el in channel):
        explicit_el = ET.Element(explicit_tag)
        explicit_el.text = "no"
        channel.insert(1, explicit_el)

    # --- ensure podcast namespace is actually USED so xmlns:podcast is emitted ---
    # harmless tag recommended by PodcastIndex; value "no" is fine for public feeds
    podcast_locked_tag = "{" + PODCAST_NS + "}locked"
    if not any(el.tag == podcast_locked_tag for el in channel):
        locked_el = ET.Element(podcast_locked_tag)
        locked_el.text = "no"
        # place after explicit
        channel.insert(2, locked_el)

    # write feed.xml
    try:
        # pretty print for py3.9+
        ET.indent(root)
    except Exception:
        pass
    with open("feed.xml", "wb") as f:
        f.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))


if __name__ == "__main__":
    main()
