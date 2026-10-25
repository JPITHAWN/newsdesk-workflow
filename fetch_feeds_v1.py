import httpx # For fetching RSS feeds on the internet
import feedparser # For parsing the data
import calendar # For having 24 hour article window
from datetime import datetime, timedelta, timezone # For having 24 hour article window
import hashlib                 # makes the sha256 fingerprint
from pathlib import Path       # easy file reading and writing

url = "https://feeds.bbci.co.uk/news/uk/rss.xml"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
} #I'm Chrome, but treat me as Mozilla, Safari and Firefox-compatible, so I get everyone's best pages

try:
    response = httpx.get(url, timeout=10, headers=headers) # fetch XML/RSS data

except httpx.HTTPError as e:
    print("Fetch failed:", e)
    raise SystemExit
else:
    print("Status:", response.status_code)
    if response.status_code != 200:
        print("Stopping.. bad status.")
        raise SystemExit

news_feed = feedparser.parse(response.content) #Parse data into feedparser format
print("Feed title:", news_feed.feed.get("title"))
print("Articles:", len(news_feed.entries))
print()

SEEN_FILE = Path("seen.txt")
SEEN_CAP = 1000
seen_list = SEEN_FILE.read_text().split() if SEEN_FILE.exists() else []
seen_set = set(seen_list)

cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

for entry in news_feed.entries:
    parsed_entry_date = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed_entry_date is None: # no date at all: skip it
        continue                      
    date_published = datetime.fromtimestamp(calendar.timegm(parsed_entry_date), tz=timezone.utc)
    if date_published < cutoff: # older than 24h: skip it
        continue

    link = entry.get("link")
    if not link:               # no link: skip it (avoids the empty-link bug)
        continue
    key = hashlib.sha256(link.encode()).hexdigest()[:16]
    if key in seen_set:        # already sent before: skip it
        continue

    seen_set.add(key)
    seen_list.append(key)
                      
    print(date_published.strftime("%d %b %H:%M"), entry.get("title"))
    print("  ", link)
seen_list = seen_list[-SEEN_CAP:]          # keep only the newest 5000
SEEN_FILE.write_text("\n".join(seen_list) + "\n")
