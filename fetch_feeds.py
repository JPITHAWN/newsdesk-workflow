
import httpx # used for fetching the rss data
import feedparser # used for parsing the data

# used for ensuring loopback window
import calendar
from datetime import datetime, timedelta, timezone

from pathlib import Path # used for managing seen_file
import hashlib # used for hashing
from concurrent.futures import ThreadPoolExecutor # used for threading

# Configurations
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_WORKERS = 10
REDIRECT = True
SEEN_FILE = Path(__file__).parent / "seen.txt"
SEEN_CAP = 5000


FEEDS = [
    {"name": "BBC UK",      "url": "https://feeds.bbci.co.uk/news/uk/rss.xml",  "lookback_hours": 24},
    {"name": "Guardian UK", "url": "https://www.theguardian.com/uk-news/rss",   "lookback_hours": 24},
    {"name": "Rappler PH",  "url": "https://www.rappler.com/philippines/feed/", "lookback_hours": 30},
]

# Functions

def fetch_rss_feed(client: httpx.Client, feed: dict) -> tuple[list[dict], str | None]: # fetches the news feed
    """Return (articles, error). Never raises."""
    try:
        response = client.get(feed["url"]) # fetch RSS/XML data
    except httpx.HTTPError as e:
        return [], f"fetch failed: {e}" # returns empty list, error statement if failed

    if response.status_code != 200: # returns bad status if status code is not 200
        return [], f"bad status {response.status_code}"

    parsed = feedparser.parse(response.content) # parses raw xml data
    if parsed.bozo and not parsed.entries: # returns invalid if xml is broken AND no articles are present
        return [], "not a valid feed"

    cutoff = datetime.now(timezone.utc) - timedelta(hours=feed["lookback_hours"]) # gets cutoff date from timestamp
    articles = [] # initialises empty article list

    for entry in parsed.entries: # for every article in feed
        date = entry.get("published_parsed") or entry.get("updated_parsed") # gets article date
        link = entry.get("link") # gets link
        if date is None or not link: # skips if missing date or missing link
            continue

        published = datetime.fromtimestamp(calendar.timegm(date), tz=timezone.utc) # reformat date 
        if published < cutoff: # skip if published date is before cutoff date
            continue

        articles.append({
            "title": entry.get("title", "(no title)"),
            "link": link,
            "published": published,
            "source": feed["name"],
        }) # appends info to article

    return articles, None # returns article and None if no problems occurred

def link_key(link: str) -> str: #converts article url into a base-16 16 character string
    return hashlib.sha256(link.encode()).hexdigest()[:16]


def load_seen() -> list[str]: # loads the seen.txt file
    if SEEN_FILE.exists():
        return SEEN_FILE.read_text(encoding="utf-8").split()
    return []


def save_seen(seen_list: list[str]) -> None: # saves the seen.txt file
    SEEN_FILE.write_text("\n".join(seen_list[-SEEN_CAP:]) + "\n", encoding="utf-8")


def main() -> None:
    seen_list = load_seen()
    seen_set = set(seen_list)
    failed = []

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=REDIRECT,
    ) as client, ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = pool.map(lambda feed: fetch_rss_feed(client, feed), FEEDS) # For every feed in feeds, run fetch_rss_feeds

        # FEEDS has feed
        # results has both articles and error
        for feed, (articles, error) in zip(FEEDS, results): #zip iterates through two lists at the same time
            if error: # if error is not empty, print error and continues
                print(f"[FAILED] {feed['name']}: {error}")
                failed.append(feed["name"])
                continue

            print(f"\n== {feed['name']} ({feed['lookback_hours']}h) ==")
            for article in articles: # for every article in articles
                key = link_key(article["link"]) # hashes the url as 16 character string
                if key in seen_set: #if it is in set, do not append in the seen_list
                    continue
                seen_set.add(key)
                seen_list.append(key)

                print(article["published"].strftime("%d %b %H:%M"), article["title"])
                print("  ", article["link"])

    if failed: # prints failed feeds
        print("\nFeeds failed:", ", ".join(failed))

    save_seen(seen_list) # saves new list


if __name__ == "__main__":
    main()
