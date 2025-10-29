#!/usr/bin/env python3
import re, html, requests, sys
from xml.etree import ElementTree as ET

# ----------- config -----------
SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE   = "https://djstevekelley.github.io/celestial-feed/Celestial_Podcast_Cover_3000x3000.jpg"
FEED_URL    = "https://djstevekelley.github.io/celestial-feed/feed.xml"

ITUNES_NS   = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS  = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS     = "http://www.w3.org/2005/Atom"
PODCAST_NS  = "https://podcastindex.org/namespace/1.0"
XMLNS       = "http://www.w3.org/2000/xmlns/"  # for explicit xmlns:* setting

ET.register_namespace("itunes",   ITUNES_NS)
ET.register_namespace("content",  CONTENT_NS)
ET.register_namespace("atom",     ATOM_NS)
ET.register_namespace("podcast",  PODCAST_NS)

# ----------- helpers -----------
def clean_lines(block: str):
    lines = []
    for ln in block.splitlines():
        ln = ln.strip()
        if not ln:             # skip blank
            continue
        if re.fullmatch(r"[-_]{3,}", ln):  # skip separators
            continue
        lines.append(ln)
    return lines

def paragraphs_from_text(text: str):
    paras, current = [], []
    for ln in text.splitlines():
        if not ln.strip():
            if current:
                paras.append(" ".join(current)); current = []
        else:
            current.append(ln.strip())
    if current:
        paras.append(" ".join(current))
    return paras

def format_description(desc: str):
    desc = html.unescape(desc)
    parts = []
    lines = clean_lines(desc)
    in_tracklist = False

    for ln in lines:
        low = ln.lower()

        if "tracklist" in low and not in_tracklist:
            parts.append("<b>Tracklist:</b><br/>")
            in_tracklist = True
            continue

        if low.startswith("available to stream"):
            parts.append("<br/>")

        if in_tracklist:
            if not ln.strip() or low.startswith("available to stream"):
                in_tracklist = False
            else:
                parts.append(f"• {ln}<br/>")
                continue

        parts.append(f"{ln}<br/>")

    formatted = "".join(parts)
    formatted = re.sub(r"(?:<br/>){3,}", "<br/><br/>", formatted)
    return formatted

# ----------- main -----------
def main():
    r = requests.get(SOURCE_FEED, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)

    # Make sure the root has explicit xmlns declarations (belt & braces)
    root.set(f"{{{XMLNS}}}itunes", ITUNES_NS)
    root.set(f"{{{XMLNS}}}atom", ATOM_NS)
    root.set(f"{{{XMLNS}}}podcast", PODCAST_NS)

    # find <channel>
    channel = None
    for child in root.iter():
        if child.tag.endswith("channel"):
            channel = child
            break
    if channel is None:
        raise RuntimeError("Could not find <channel> in source feed.")

    # --- Atom self-link ---
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

    # --- itunes:explicit (force single, channel-level) ---
    # Remove any existing channel-level itunes:explicit
    for el in list(channel):
        if el.tag == f"{{{ITUNES_NS}}}explicit":
            channel.remove(el)
    # Add one clean tag near the top
    explicit_el = ET.Element(f"{{{ITUNES_NS}}}explicit")
    explicit_el.text = "no"       # use "yes" if you ever need to
    channel.insert(1, explicit_el)

    # --- Podcasting 2.0 minimal marker (keeps validator green for namespace) ---
    if channel.find(f"{{{PODCAST_NS}}}locked") is None:
        podcast_locked = ET.Element(f"{{{PODCAST_NS}}}locked")
        podcast_locked.text = "no"
        channel.insert(2, podcast_locked)

    # --- itunes:image (channel-level) ---
    itunes_image_tag = f"{{{ITUNES_NS}}}image"
    for el in list(channel):
        if el.tag == itunes_image_tag or (el.tag.endswith("image") and "itunes" in el.tag):
            channel.remove(el)
    img = ET.Element(itunes_image_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # --- Rewrite each item description ---
    for item in channel.findall("item"):
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            desc_el.text = format_description(desc_el.text)

    # Safety check: ensure itunes:explicit exists in channel before writing
    if channel.find(f"{{{ITUNES_NS}}}explicit") is None:
        print("ERROR: itunes:explicit not present in channel before write", file=sys.stderr)
        sys.exit(1)

    # Write output feed.xml
    tree = ET.ElementTree(root)
    tree.write("feed.xml", encoding="UTF-8", xml_declaration=True)

if __name__ == "__main__":
    main()
