#!/usr/bin/env python3
import requests
from xml.etree import ElementTree as ET

SOURCE_FEED = "https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss"
NEW_IMAGE = "https://www.dropbox.com/scl/fi/fxvd9icshki3uzn61vm1o/CELESTIAL-WITH-STEVE-KELLEY-front.jpg?rlkey=jquwu0g9mu8mwu6ggalu6eusw&raw=1"

def main():
    r = requests.get(SOURCE_FEED, timeout=30)
    r.raise_for_status()
    xml = r.content

    ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
    ET.register_namespace("itunes", ITUNES_NS)
    itunes_tag = "{" + ITUNES_NS + "}" + "image"

    root = ET.fromstring(xml)

    # Find channel element robustly
    channel = None
    for child in root.iter():
        if child.tag.endswith("channel"):
            channel = child
            break
    if channel is None:
        raise RuntimeError("Could not find <channel> in source feed.")

    # Remove existing itunes:image elements
    for elem in list(channel):
        tag = elem.tag
        if tag == itunes_tag or (tag.endswith("image") and "itunes" in tag):
            channel.remove(elem)

    # Insert new itunes:image at top of channel
    itunes_image = ET.Element(itunes_tag)
    itunes_image.set("href", NEW_IMAGE)
    channel.insert(0, itunes_image)

    out = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with open("feed.xml", "wb") as f:
        f.write(out)

if __name__ == "__main__":
    main()
