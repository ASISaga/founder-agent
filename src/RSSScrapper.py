import requests
import os
import logging
import xml.etree.ElementTree as ET

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


rss_file = "feed.rss"
output_dir = "paulgraham_rss_articles"
os.makedirs(output_dir, exist_ok=True)

def sanitize_filename(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

def main():
    logging.info(f"Reading RSS feed from local file: {rss_file}")
    with open(rss_file, "r", encoding="utf-8") as f:
        rss_content = f.read()
    root = ET.fromstring(rss_content)
    items = root.findall(".//item")
    logging.info(f"Found {len(items)} items in RSS feed.")
    count = 0
    for item in items:
        title = item.findtext("title") or "untitled"
        link = item.findtext("link")
        logging.info(f"Downloading: {title} ({link})")
        try:
            article_resp = requests.get(link)
            article_resp.raise_for_status()
            filename = sanitize_filename(title) + ".html"
            filepath = os.path.join(output_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(article_resp.text)
            logging.info(f"Saved: {filename}")
            count += 1
        except Exception as e:
            logging.error(f"Failed to download {link}: {e}")
    logging.info(f"Completed. Total articles downloaded: {count}")

if __name__ == "__main__":
    main()
