#!/usr/bin/env python3
import re, html, time, requests
from xml.etree import ElementTree as ET

# ----------- config -----------
SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE   = "https://djstevekelley.github.io/celestial-feed/Celestial_Podcast_Cover_3000x3000.jpg"
FEED_URL    = "https://djstevekelley.github.io/celestial-feed/feed.xml"

ITUNES_NS   = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS  = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS     = "http://www.w3.org/2005/Atom"
PODCAST_NS  = "https://podcastindex.org/namespace/1.0"

ET.register_namespace("itunes",   ITUNES_NS)
ET.register_namespace("content",  CONTENT_NS)
ET.register_namespace("atom",     ATOM_NS)
ET.register_namespace("podcast",  PODCAST_NS)

# SoundCloud sometimes blocks GitHub runners unless we look like a normal browser.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://soundcloud.com/",
}

# ----------- helpers -----------
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
    """Light HTML formatting for tracklist + spacing around 'Available to stream'."""
    desc = html.unescape(desc)
    parts = []
    lines = clean_lines(desc)
    in_tracklist = False

    for ln in lines:
        low = ln.lower()

        # Start tracklist
        if "tracklist" in low and not in_tracklist:
            parts.append("<b>Tracklist:</b><br/>")
            in_tracklist = True
            continue

        # Add a blank line before the availability sentence
        if low.startswith("available to stream"):
            parts.append("<br/>")

        # While inside tracklist, bullet each line until it ends
        if in_tracklist:
            if (not ln.strip()) or low.startswith("available to stream"):
                in_tracklist = False
            else:
                parts.append(f"• {ln}<br/>")
                continue

        parts.append(f"{ln}<br/>")

    formatted = "".join(parts)
    formatted = re.sub(r"(?:<br/>){3,}", "<br/><br/>", formatted)
    return formatted

def fetch_soundcloud_feed() -> bytes:
    """
    Fetch the SoundCloud RSS with retries + cache-busting.
    GitHub Actions can get 403 occasionally; retries often succeed.
    """
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    # Try a few variants (plain + cache bust)
    urls = [
        SOURCE_FEED,
        f"{SOURCE_FEED}?_={int(time.time())}",
        f"{SOURCE_FEED}&_={int(time.time())}" if "?" in SOURCE_FEED else f"{SOURCE_FEED}?_={int(time.time())}",
    ]

    last_err = None
    for attempt in range(1, 6):  # 5 attempts total
        for url in urls:
            try:
                resp = session.get(url, timeout=45, allow_redirects=True)
                # If SoundCloud blocks, we’ll retry
                if resp.status_code == 403:
                    last_err = RuntimeError(f"403 Forbidden fetching {url}")
                    continue
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                last_err = e
                continue

        # Backoff before next round
        time.sleep(min(10, 2 * attempt))

    raise RuntimeError(f"Failed to fetch SoundCloud feed after retries. Last error: {last_err}")

# ----------- main -----------
def main():
    xml_bytes = fetch_soundcloud_feed()
    root = ET.fromstring(xml_bytes)

    # find <channel>
    channel = None
    for child in root.iter():
        if child.tag.endswith("channel"):
            channel = child
            break
    if channel is None:
        raise RuntimeError("Could not find <channel> in source feed.")

    # 1) Ensure single channel-level <atom:link rel="self" .../>
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

    # 2) Force a single channel-level <itunes:explicit>
    # Apple support said True/False — use "false" for safest compatibility.
    for el in list(channel):
        if el.tag == f"{{{ITUNES_NS}}}explicit":
            channel.remove(el)
    explicit_el = ET.Element(f"{{{ITUNES_NS}}}explicit")
    explicit_el.text = "false"
    channel.insert(1, explicit_el)

    # 3) Podcasting 2.0 tag (validator green; harmless)
    podcast_locked = channel.find(f"{{{PODCAST_NS}}}locked")
    if podcast_locked is None:
        podcast_locked = ET.Element(f"{{{PODCAST_NS}}}locked")
        podcast_locked.text = "no"
        channel.insert(2, podcast_locked)

    # 4) replace/insert itunes:image at channel level
    itunes_image_tag = f"{{{ITUNES_NS}}}image"
    for el in list(channel):
        if el.tag == itunes_image_tag or (el.tag.endswith("image") and "itunes" in el.tag):
            channel.remove(el)
    img = ET.Element(itunes_image_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # 5) Rewrite each item description (neat formatting)
    for item in channel.findall("item"):
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            desc_el.text = format_description(desc_el.text)

    # Write output feed.xml
    tree = ET.ElementTree(root)
    tree.write("feed.xml", encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    main()
