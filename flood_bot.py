import feedparser
import requests
from atproto import Client, client_utils
import os
import logging
from datetime import datetime, timezone
import re

ENABLE_POSTING = True  # ✅ Change this to True when you're ready to post again

# Setup logging
LOG_FILE = "debug.log"
WARNINGS_LOG_FILE = "warnings_log.txt"
POSTED_WARNINGS_FILE = "./posted_warnings.txt"

logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO  # 👈 Only logs INFO, WARNING, ERROR, CRITICAL
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
    logging.info((f"Posted_warnings.txt not found in cache. Creating empty posted_warnings.txt file"))

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
    """Load previously posted warnings (title + pubDate) from file, ensuring the file exists."""
    if not os.path.exists(POSTED_WARNINGS_FILE):
        print("📁 Creating missing posted_warnings.txt")
        open(POSTED_WARNINGS_FILE, "a").close()
        return set()

    with open(POSTED_WARNINGS_FILE, "r") as file:
        posted_warnings = set(file.read().splitlines())

    print(f"📜 Previously posted warnings ({len(posted_warnings)}): {posted_warnings}")  # ✅ Debug print
    logging.info(f"Loaded {len(posted_warnings)} previously posted warnings")
    return posted_warnings

def save_posted_warning(warning_id):
    """Save a new warning ID (title + pubDate) to prevent duplicate posting."""
    with open(POSTED_WARNINGS_FILE, "a") as file:
        file.write(f"{warning_id}\n")
        file.flush()  # ✅ Force immediate write
        os.fsync(file.fileno())  # ✅ Ensure changes are physically saved
    print(f"💾 Saved posted warning: {warning_id}")
    logging.info(f"Saved posted warning: {warning_id}")

    # ✅ Force GitHub to recognize the file has changed
    os.system(f"echo 'Updated at {datetime.now()}' >> {POSTED_WARNINGS_FILE}")


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

def clean_title(title):
    """Remove the timestamp prefix (formatted as 'MM/DD:HH:mm TZ') but keep the full warning title."""
    return re.sub(r"^\d{2}/\d{2}:\d{2} [A-Z]{3} ", "", title)  # ✅ Strip timestamp only
    return match.group(1) if match else title  # Return cleaned title or original if not found

def fetch_flood_warnings(use_local_file=False, local_file="sample_rss.xml"):
    """Fetch flood warnings from all BoM RSS feeds or use a local test file."""
    warnings = []
    posted_warnings = load_posted_warnings()

    if use_local_file:
        print(f"📂 Loading warnings from local file: {local_file}")
        logging.info(f"Loading warnings from local file: {local_file}")

        try:
            with open(local_file, "r", encoding="utf-8") as file:
                feed_content = file.read()
            feeds = [feedparser.parse(feed_content)]  # ✅ Parse local file as a single feed
        except FileNotFoundError:
            print(f"❌ Local file '{local_file}' not found.")
            logging.error(f"Local file '{local_file}' not found.")
            return []
        except Exception as e:
            print(f"❌ Error reading local file: {e}")
            logging.error(f"Error reading local file: {e}")
            return []
    else:
        # ✅ Log that it's fetching from live feeds
        print("🌐 Fetching live flood warnings from BoM feeds...")
        logging.info("Fetching live flood warnings from BoM feeds...")

        feeds = []  # ✅ Store all parsed feeds
        for feed_url in RSS_FEEDS:
            print(f"🔍 Checking RSS feed: {feed_url}")
            logging.info(f"Checking feed: {feed_url}")

            try:
                response = requests.get(feed_url, headers=HEADERS)
                if response.status_code != 200:
                    print(f"⚠️ Failed to fetch feed {feed_url}. Status Code: {response.status_code}")
                    logging.warning(f"Failed to fetch feed {feed_url}. Status Code: {response.status_code}")
                    continue  # ✅ Skip and continue to the next feed

                feeds.append(feedparser.parse(response.content))  # ✅ Store all feeds

            except requests.RequestException as e:
                print(f"❌ Error fetching {feed_url}: {e}")
                logging.error(f"Error fetching {feed_url}: {e}")

    if not feeds:
        print("⚠️ All feed fetch attempts failed! No warnings available.")
        logging.error("All feed fetch attempts failed! No warnings available.")
        return []

    # ✅ Process all collected feeds
    for feed in feeds:
        if not feed.entries:
            print("⚠️ No data found in feed.")
            logging.warning("No data found in feed.")
            continue  # ✅ Skip empty feeds

        for entry in feed.entries:
            title = entry.title.strip()
            link = entry.link
            pub_date = parse_pub_date(entry)

            log_warning(title, pub_date)

            warning_id = f"{title}|{pub_date}"

            if any(keyword in title for keyword in ["Flood Warning", "Flood Watch"]) and warning_id not in posted_warnings:
                clean_warning_title = clean_title(title)

                # ✅ Format the BlueSky post using TextBuilder
                bluesky_message = client_utils.TextBuilder().text(f"🚨 {clean_warning_title} has been issued.\nMore info:\n").link(str(link), link)
                plain_text_message = f"🚨 {clean_warning_title} has been issued.\nMore info:\n{link}"

                warnings.append((warning_id, bluesky_message, plain_text_message))
                logging.info(f"New flood warning detected: {title} ({pub_date})")
                print(f"✅ New flood alert found: {title} ({pub_date})")

            else:
                logging.debug(f"Skipping duplicate or previously posted warning: {title} ({pub_date})")
                print(f"⏭️ Skipping: {title} ({pub_date})")

    return warnings


def post_to_bluesky(bluesky_message, plain_text_message):
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
        client.send_post(text=bluesky_message)
        logging.info(f"✅ Successfully posted to BlueSky: {plain_text_message}")
        print(f"✅ Posted to BlueSky: {plain_text_message}")
    except Exception as e:
        logging.error(f"❌ Failed to post to BlueSky: {str(e)}")
        print(f"❌ Failed to post to BlueSky: {str(e)}")

# Check if running inside GitHub Actions
IS_CI = os.getenv("CI") == "true"

if __name__ == "__main__":
    use_local_file = False  # ✅ Default to live mode

    # ✅ Only use test file if running manually (not in CI)
    if os.getenv("CI") is None:
        use_local_file = True

    print(f"🚀 Starting flood warning check (Test Mode: {use_local_file})...")

    warnings = fetch_flood_warnings(use_local_file=use_local_file)

    if warnings:
        for warning_id, bluesky_message, plain_text_message in warnings:
            if use_local_file:
                print(f"📝 [TEST MODE] Would post:\n{plain_text_message}")  # ✅ Print plain text for testing
                save_posted_warning(warning_id)
            else:
                if ENABLE_POSTING:
                    post_to_bluesky(bluesky_message, plain_text_message)  # ✅ Post in live mode to BlueSky
                print(f"💾 Saving posted warning: {warning_id}")
                save_posted_warning(warning_id)

        with open(POSTED_WARNINGS_FILE, "r") as file:
            posted_warnings = set(file.read().splitlines())

            print(f"📜 Updated posted warnings ({len(posted_warnings)}): {posted_warnings}")  # ✅ Debug print
            logging.info(f"Updated posted warnings {len(posted_warnings)} previously posted warnings")

    else:
        print("✅ No new flood warnings found.")

    print("🏁 Bot execution completed.")

