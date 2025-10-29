#!/usr/bin/env python3
import re, html, requests
from xml.etree import ElementTree as ET

SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE = "https://djstevekelley.github.io/celestial-feed/Celestial_Podcast_Cover_3000x3000.jpg"



ITUNES_NS  = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ET.register_namespace("itunes", ITUNES_NS)
ET.register_namespace("content", CONTENT_NS)

# ---------- helpers ----------
def clean_lines(block: str):
    """Split text block into non-empty lines and drop separator lines like ----."""
    lines = []
    for ln in block.splitlines():
        ln = ln.strip()
        if not ln:
            continue
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
    Neat episode HTML:
      - Intro paragraph(s)
      - blank line, then Tracklist as <ul><li>…</li></ul> (if present)
      - blank line, then 'Available…'
      - blank line, then 'Website…'
    """
    if not desc_text:
        return ""

    src = desc_text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # find "Tracklist"
    m = re.search(r"\btrack\s*list\b|\btracklist\b", src, flags=re.I)
    if m:
        intro = src[:m.start()].strip()
        after = src[m.end():].strip()
    else:
        intro, after = src, ""

    # detect 'Available…' and 'Website…'
    available_re = re.compile(r"^available\b.*", flags=re.I | re.M)
    website_re   = re.compile(r"^website\b.*|https?://\S+", flags=re.I | re.M)

    available_line = None
    website_line = None

    m_av = available_re.search(after)
    if m_av:
        available_line = m_av.group(0).strip()
        after = (after[:m_av.start()] + after[m_av.end():]).strip()

    m_web = website_re.search(after)
    if m_web:
        website_line = m_web.group(0).strip()
        after = (after[:m_web.start()] + after[m_web.end():]).strip()

    # remaining lines -> track items
    after_clean = re.sub(r"^\s*[-–—_]{3,}\s*", "", after.strip(), flags=re.M)
    track_items = clean_lines(after_clean) if m else []

    html_parts = []

    if intro:
        html_parts.append(paragraphs_from_text(intro))

    if track_items:
        html_parts.append("<p></p>")
        html_parts.append("<p><strong>Tracklist:</strong></p>")
        html_parts.append("<ul>")
        for item in track_items:
            html_parts.append(f"<li>{html.escape(item)}</li>")
        html_parts.append("</ul>")

    if available_line:
        html_parts.append("<p></p>")
        html_parts.append(f"<p>{html.escape(available_line)}</p>")

    if website_line:
        html_parts.append("<p></p>")
        if re.fullmatch(r"https?://\S+", website_line, flags=re.I):
            html_parts.append(
                f'<p>Website: <a href="{html.escape(website_line)}">{html.escape(website_line)}</a></p>'
            )
        else:
            linked = re.sub(
                r"(https?://\S+)",
                lambda m: f'<a href="{html.escape(m.group(1))}">{html.escape(m.group(1))}</a>',
                html.escape(website_line),
            )
            html_parts.append(f"<p>{linked}</p>")

    return "".join(html_parts)

# ---------- main ----------
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
    itunes_tag = "{" + ITUNES_NS + "}image"
    for elem in list(channel):
        if elem.tag == itunes_tag or (elem.tag.endswith("image") and "itunes" in elem.tag):
            channel.remove(elem)
    img = ET.Element(itunes_tag)
    img.set("href", NEW_IMAGE)
    channel.insert(0, img)

    # ---- SHOW-LEVEL description & summary (channel/description + itunes:summary)
    new_show_description = (
        "Celestial with Steve Kelley showcases the best in Deep House and Progressive House every week — "
        "blending groove, melody, and emotion through carefully curated sets.\n\n"
        "Hosted by UK DJ and producer Steve Kelley, the show reflects the sound of his label Celestial Recording, "
        "alongside standout releases from imprints like Sublease Music, Bondage Music and many more. Expect an immersive journey "
        "through underground cuts, timeless house grooves, and exclusive previews from across the scene.\n\n"
        "With nearly two decades of experience behind the decks and in the studio, Steve’s sound has earned recognition "
        "from industry legends including Steve Bug and Nick Warren, as well as collaborations with Native Instruments "
        "for Traktor Pro. His sets have taken him across the globe — from the UK and Ibiza to Germany, Sweden, and Italy — "
        "and Celestial continues to connect listeners worldwide through authentic, emotive electronic music.\n\n"
        "Releases on: Sublease Music | Bondage Music | Celestial Recordings\n\n"
        "Stay connected:\n"
        "djstevekelley.com\n"
        "Instagram: @celestial.recordings\n"
        "Available on Apple Podcasts, SoundCloud, Mixcloud, and Spotify."
    )
    ch_desc = channel.find("description")
    if ch_desc is None:
        ch_desc = ET.SubElement(channel, "description")
    ch_desc.text = new_show_description

    itunes_summary_tag = "{" + ITUNES_NS + "}summary"
    ch_sum = channel.find(itunes_summary_tag)
    if ch_sum is None:
        ch_sum = ET.SubElement(channel, itunes_summary_tag)
    ch_sum.text = new_show_description

    # ---- EPISODE formatting: content:encoded + keep itunes:summary (plain)
    content_tag = "{" + CONTENT_NS + "}encoded"
    for item in channel.findall("./item"):
        desc_el = item.find("description")
        desc_text = (desc_el.text or "").strip() if desc_el is not None else ""
        if not desc_text:
            its_sum = item.find("{" + ITUNES_NS + "}summary")
            if its_sum is not None and its_sum.text:
                desc_text = its_sum.text.strip()

        html_body = build_html(desc_text)

        existing = item.find(content_tag)
        if existing is None:
            existing = ET.SubElement(item, content_tag)
        existing.text = html_body

        its_sum = item.find("{" + ITUNES_NS + "}summary")
        if its_sum is None:
            its_sum = ET.SubElement(item, "{" + ITUNES_NS + "}summary")
        its_sum.text = desc_text or ""

    with open("feed.xml", "wb") as f:
        f.write(ET.tostring(root, encoding="utf-8", xml_declaration=True))

if __name__ == "__main__":
    main()
