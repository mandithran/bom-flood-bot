import feedparser
import requests
from atproto import Client
import os
import logging
from datetime import datetime, timezone

# Setup logging
LOG_FILE = "debug.log"
WARNINGS_LOG_FILE = "warnings_log.txt"
POSTED_WARNINGS_FILE = "posted_warnings.txt"

logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.DEBUG
)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
console_handler.setFormatter(console_formatter)
logging.getLogger().addHandler(console_handler)

logging.info("Starting flood warning bot execution.")

# Ensure posted warnings file exists
if not os.path.exists(POSTED_WARNINGS_FILE):
    open(POSTED_WARNINGS_FILE, "a").close()  # ✅ Create empty file if it doesn't exist

# BoM Flood Warnings RSS Feeds
RSS_FEEDS = [
    "http://www.bom.gov.au/fwo/IDZ00060.warnings_wa.xml",  # Western Australia
    "http://www.bom.gov.au/fwo/IDZ00057.warnings_sa.xml",  # South Australia
    "http://www.bom.gov.au/fwo/IDZ00058.warnings_tas.xml",  # Tasmania
    "http://www.bom.gov.au/fwo/IDZ00055.warnings_nt.xml",  # Northern Territory
    "http://www.bom.gov.au/fwo/IDZ00054.warnings_nsw.xml",  # New South Wales
    "http://www.bom.gov.au/fwo/IDZ00059.warnings_vic.xml",  # Victoria
    "http://www.bom.gov.au/fwo/IDZ00056.warnings_qld.xml",  # Queensland
]

# User-Agent header to bypass 403 errors
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}

def load_posted_warnings():
    """Load previously posted warnings (title + pubDate) from file."""
    with open(POSTED_WARNINGS_FILE, "r") as file:
        return set(file.read().splitlines())  # Read warnings as a set
    return set()

def save_posted_warning(warning_id):
    """Save a new warning ID (title + pubDate) to prevent duplicate posting."""
    with open(POSTED_WARNINGS_FILE, "a") as file:
        file.write(f"{warning_id}\n")  # Store as "title|pubDate"

def log_warning(title, pub_date):
    """Log all found warnings (new or old) to warnings_log.txt."""
    with open(WARNINGS_LOG_FILE, "a") as file:
        file.write(f"{pub_date} | {title}\n")

def parse_pub_date(entry):
    """Convert RSS pubDate to a standard datetime object."""
    try:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()  # Convert to UTC ISO string
    except AttributeError:
        return "Unknown Date"  # If pubDate is missing, use a placeholder

def fetch_flood_warnings(use_local_file=False, local_file="sample_rss.xml"):
    """Fetch flood warnings from RSS feeds, or use a local XML file for testing."""
    warnings = []
    posted_warnings = load_posted_warnings()

    if use_local_file:
        print(f"📂 Loading warnings from local file: {local_file}")
        logging.info(f"Loading warnings from local file: {local_file}")
        try:
            with open(local_file, "r", encoding="utf-8") as file:
                feed_content = file.read()
        except FileNotFoundError:
            print(f"❌ Local file '{local_file}' not found.")
            logging.error(f"Local file '{local_file}' not found.")
            return []
        except Exception as e:
            print(f"❌ Error reading local file: {e}")
            logging.error(f"Error reading local file: {e}")
            return []
    else:
        # Normal live-fetching mode
        for feed_url in RSS_FEEDS:
            print(f"🔍 Checking RSS feed: {feed_url}")
            logging.info(f"Checking feed: {feed_url}")

            try:
                response = requests.get(feed_url, headers=HEADERS)
                if response.status_code != 200:
                    print(f"⚠️ Failed to fetch feed {feed_url}. Status Code: {response.status_code}")
                    logging.warning(f"Failed to fetch feed {feed_url}. Status Code: {response.status_code}")
                    continue
                feed_content = response.content
            except requests.RequestException as e:
                print(f"❌ Error fetching {feed_url}: {e}")
                logging.error(f"Error fetching {feed_url}: {e}")
                continue

    # Parse the feed (either from a file or from live data)
    feed = feedparser.parse(feed_content)

    if not feed.entries:
        print("⚠️ No data found in feed.")
        logging.warning("No data found in feed.")
        return []

    for entry in feed.entries:
        title = entry.title.strip()
        link = entry.link
        pub_date = parse_pub_date(entry)  # Extract pubDate

        log_warning(title, pub_date)

        # Generate unique ID including pubDate
        warning_id = f"{title}|{pub_date}"

        # ✅ Only collect new warnings that contain "Flood Warning" and have not been posted before
        if "Flood Warning" in title and warning_id not in posted_warnings:
            message = f"🚨 {title} (Issued: {pub_date})\nMore info: {link}"
            warnings.append((warning_id, message))
            logging.info(f"New flood warning detected: {title} ({pub_date})")
            print(f"✅ New flood warning found: {title} ({pub_date})")
        else:
            logging.debug(f"Skipping duplicate or previously posted warning: {title} ({pub_date})")
            print(f"⏭️ Skipping: {title} ({pub_date})")

    return warnings

def post_to_bluesky(message):
    """Post a message to BlueSky using the atproto package."""
    username = os.getenv("BLUESKY_USERNAME")
    password = os.getenv("BLUESKY_PASSWORD")

    if not username or not password:
        logging.error("❌ Error: Missing BlueSky credentials.")
        print("❌ Error: Missing BlueSky credentials.")
        return

    try:
        client = Client()
        client.login(username, password)
        client.send_post(text=message)
        logging.info(f"✅ Successfully posted to BlueSky: {message}")
        print(f"✅ Posted to BlueSky: {message}")
    except Exception as e:
        logging.error(f"❌ Failed to post to BlueSky: {str(e)}")
        print(f"❌ Failed to post to BlueSky: {str(e)}")

if __name__ == "__main__":
    use_local_file = True # ✅ Set to True for local file testing, False for live fetch

    print("🚀 Starting flood warning check...")
    warnings = fetch_flood_warnings(use_local_file=use_local_file)

    if warnings:
        for warning_id, message in warnings:
            if use_local_file:
                print(f"📝 [TEST MODE] Would post: {message}")  # ✅ Only print in test mode
                save_posted_warning(warning_id)  # ✅ Save warning ID (title + pubDate)
            else:
                post_to_bluesky(message)  # ✅ Post to BlueSky in live mode
                save_posted_warning(warning_id)  # ✅ Save warning ID (title + pubDate)
    else:
        print("✅ No new flood warnings found.")

    print("🏁 Bot execution completed.")
