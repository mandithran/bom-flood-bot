import feedparser
import requests
from atproto import Client
import os
import logging

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
    """Load the list of previously posted warnings."""
    if os.path.exists(POSTED_WARNINGS_FILE):
        with open(POSTED_WARNINGS_FILE, "r") as file:
            return set(file.read().splitlines())  # Read warnings as a set (fast lookups)
    return set()

def save_posted_warning(warning_id):
    """Save a new warning ID to the posted warnings file."""
    with open(POSTED_WARNINGS_FILE, "a") as file:
        file.write(f"{warning_id}\n")

def log_warning(title):
    """Log all found warnings (new or old) to warnings_log.txt."""
    with open(WARNINGS_LOG_FILE, "a") as file:
        file.write(f"{title}\n")

def fetch_flood_warnings():
    """Fetch flood warnings from multiple BoM RSS feeds, only keeping those with 'Flood Warning' in the title."""
    warnings = []
    posted_warnings = load_posted_warnings()
    
    for feed_url in RSS_FEEDS:
        print(f"🔍 Checking RSS feed: {feed_url}")
        logging.info(f"Checking feed: {feed_url}")

        try:
            response = requests.get(feed_url, headers=HEADERS)

            if response.status_code != 200:
                print(f"⚠️ Failed to fetch feed {feed_url}. Status Code: {response.status_code}")
                logging.warning(f"Failed to fetch feed {feed_url}. Status Code: {response.status_code}")
                continue  # Skip to the next feed

            feed = feedparser.parse(response.content)

            if not feed.entries:
                print(f"⚠️ No data found in {feed_url}")
                logging.warning(f"No data found in {feed_url}")
                continue  # Skip to the next feed

            for entry in feed.entries:
                title = entry.title.strip()
                link = entry.link

                # Log every warning (new or duplicate)
                log_warning(title)

                # ✅ Only collect new warnings that contain "Flood Warning"
                if "Flood Warning" in title and title not in posted_warnings:
                    message = f"🚨 {title} has been issued. \nMore info: {link}"
                    warnings.append((title, message))
                    logging.info(f"New flood warning detected: {title}")
                    print(f"✅ New flood warning found: {title}")
                else:
                    logging.debug(f"Skipping duplicate or non-flood warning: {title}")
                    print(f"⏭️ Skipping: {title}")

        except requests.RequestException as e:
            print(f"❌ Error fetching {feed_url}: {e}")
            logging.error(f"Error fetching {feed_url}: {e}")

    if not warnings:
        logging.info("No new flood warnings found.")
        print("🚫 No new flood warnings found.")

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

def check_and_post_warnings():
    """Fetch and post new flood warnings to BlueSky."""
    logging.info("Fetching flood warnings...")
    print("🚀 Starting flood warning check...")
    
    warnings = fetch_flood_warnings()
    
    if warnings:
        for warning_id, message in warnings:
            post_to_bluesky(message)
            save_posted_warning(warning_id)  # ✅ Save posted warning to prevent reposting
    else:
        logging.info("No new flood warnings found.")
        print("✅ No new flood warnings to post.")

    logging.info("Bot execution completed.")
    print("🏁 Bot execution completed.")

if __name__ == "__main__":
    check_and_post_warnings()