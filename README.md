# Celestial Feed Mirror (Auto-updating)

Mirrors your SoundCloud RSS and overrides the show artwork so Apple Podcasts shows your **Celestial** logo, while SoundCloud stays clean.

- Source feed: `https://feeds.soundcloud.com/users/soundcloud:users:100329/sounds.rss`
- Artwork: `https://www.dropbox.com/scl/fi/fxvd9icshki3uzn61vm1o/CELESTIAL-WITH-STEVE-KELLEY-front.jpg?rlkey=jquwu0g9mu8mwu6ggalu6eusw&raw=1`

## Setup
1. Create a new GitHub repo (e.g. `celestial-feed`).
2. Upload `rewrite_feed.py`, `requirements.txt`, and `.github/workflows/update-feed.yml`.
3. In **Settings → Pages**, set **Build and deployment = GitHub Actions**.
4. Go to **Actions**, run **Update podcast feed** manually once.
5. Your feed will be at `https://<your-username>.github.io/<your-repo>/feed.xml`

In Apple Podcasts Connect, set the RSS feed URL to the GitHub Pages link above. The workflow refreshes every 6 hours (and whenever you run it), so new SoundCloud episodes **auto-appear**.
