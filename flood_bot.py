import feedparser
from atproto import Client
import os
import logging

# Setup logging to a file (debug.log) and console
LOG_FILE = "debug.log"
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

# List of BoM Flood Warnings RSS Feeds
RSS_FEEDS = [
    "http://www.bom.gov.au/fwo/IDZ00060.warnings_wa.xml",  # Western Australia
    "http://www.bom.gov.au/fwo/IDZ00057.warnings_sa.xml",  # South Australia
    "http://www.bom.gov.au/fwo/IDZ00058.warnings_tas.xml",  # Tasmania
    "http://www.bom.gov.au/fwo/IDZ00055.warnings_nt.xml",  # Northern Territory
    "http://www.bom.gov.au/fwo/IDZ00054.warnings_nsw.xml",  # New South Wales
    "http://www.bom.gov.au/fwo/IDZ00059.warnings_vic.xml",  # Victoria
    "http://www.bom.gov.au/fwo/IDZ00056.warnings_qld.xml",  # Queensland
]

def fetch_flood_warnings():
    """Fetch flood warnings from multiple BoM RSS feeds, only keeping those with 'Flood Warning' in the title."""
    warnings = []
    
    for feed_url in RSS_FEEDS:
        logging.info(f"Checking feed: {feed_url}")
        feed = feedparser.parse(feed_url)
        
        for entry in feed.entries:
            title = entry.title
            link = entry.link

            # ✅ Only collect warnings that contain "Flood Warning" in the title
            if "Flood Warning" in title:
                message = f"🚨 {title} has been issued. \nMore info: {link}"
                warnings.append(message)
                logging.info(f"Found flood warning: {title}")
            else:
                logging.debug(f"Skipping non-flood warning: {title}")  # Debug log for skipped entries

    if not warnings:
        logging.info("No flood warnings found.")

    return warnings


def post_to_bluesky(message):
    """Post a message to BlueSky using the atproto package."""
    username = os.getenv("BLUESKY_USERNAME")
    password = os.getenv("BLUESKY_PASSWORD")

    if not username or not password:
        logging.error("❌ Error: Missing BlueSky credentials.")
        return

    try:
        client = Client()
        client.login(username, password)
        client.send_post(text=message)
        logging.info(f"✅ Successfully posted to BlueSky: {message}")
    except Exception as e:
        logging.error(f"❌ Failed to post to BlueSky: {str(e)}")


def check_and_post_warnings():
    """Fetch and post new flood warnings to BlueSky."""
    logging.info("Fetching flood warnings...")
    warnings = fetch_flood_warnings()
    
    if warnings:
        for warning in warnings:
            post_to_bluesky(warning)
    else:
        logging.info("No new flood warnings found.")

    logging.info("Bot execution completed.")


if __name__ == "__main__":
    check_and_post_warnings()
