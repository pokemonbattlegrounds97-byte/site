"""Refresh videos.json from the channel's public YouTube feed (no API key).

Keeps the newest full videos (Shorts left out; youtube.com/shorts/<id> answers 200 only for a Short), splits each title
at " — " into a title and a subtitle, and writes videos.json only when something changed. Run by
.github/workflows/videos.yml every few hours.
"""
import json, re, time, urllib.request, urllib.error, html, pathlib

CHANNEL = "UCKd1YNx4HJN78uEFab7eqZA"
KEEP = 6
OUT = pathlib.Path(__file__).resolve().parent.parent / "videos.json"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def is_short(vid):
    opener = urllib.request.build_opener(NoRedirect)
    try:
        return opener.open(urllib.request.Request(f"https://www.youtube.com/shorts/{vid}", method="HEAD", headers={"User-Agent": "Mozilla/5.0"}), timeout=20).status == 200
    except urllib.error.HTTPError:
        return False


def fetch_feed():
    """YouTube's feed endpoint now and then answers 500/404 for a while (it did on 2026-10-13): retry with a growing pause,
    and if it's still down, skip this run instead of failing the workflow - videos.json stays as it is till the next run."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}"
    for attempt, pause in enumerate((0, 20, 60, 120)):
        time.sleep(pause)
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode()
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"feed attempt {attempt + 1} failed: {e}")
    return None


def main():
    feed = fetch_feed()
    if feed is None:
        print("::warning::YouTube feed unavailable after 4 tries; leaving videos.json as it is")
        return
    vids = []
    for entry in re.findall(r"<entry>(.*?)</entry>", feed, re.S):
        vid = re.search(r"<yt:videoId>(.*?)</yt:videoId>", entry).group(1)
        title = html.unescape(re.search(r"<title>(.*?)</title>", entry).group(1)).strip()
        published = re.search(r"<published>(.*?)</published>", entry).group(1)[:10]
        if "#shorts" in title.lower() or is_short(vid):
            continue
        head, _, sub = title.partition(" — ")
        vids.append({"id": vid, "title": " ".join(w.capitalize() if w.isupper() and len(w) > 1 else w for w in head.split()), "sub": sub, "date": published})
        if len(vids) >= KEEP:
            break
    if not vids:
        raise SystemExit("feed gave no videos; leaving videos.json as it is")
    new = json.dumps(vids, ensure_ascii=False, indent=1) + "\n"
    if OUT.exists() and OUT.read_text() == new:
        print("no change")
        return
    OUT.write_text(new)
    print(f"updated: {len(vids)} videos, newest {vids[0]['title']}")


if __name__ == "__main__":
    main()
