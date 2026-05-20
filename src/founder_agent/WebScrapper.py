import requests
from bs4 import BeautifulSoup
import os
import logging

# Setup logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(levelname)s - %(message)s'
)


# Website base URL and articles page
base_url = "https://www.paulgraham.com/"
articles_page = base_url + "articles.html"

# Subfolder to save articles
output_dir = "paulgraham_articles"
os.makedirs(output_dir, exist_ok=True)

def sanitize_filename(name):
	return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

def main():
	logging.info(f"Fetching articles list from {articles_page}")
	response = requests.get(articles_page)
	response.raise_for_status()
	logging.info("Parsing HTML content for article links")
	soup = BeautifulSoup(response.text, "html.parser")
	# Find all article links
	links = soup.find_all("a", href=True)
	logging.info(f"Found {len(links)} links. Filtering article links...")
	count = 0
	for link in links:
		href = link["href"]
		logging.info(f"Link found: {href}")
		# Only download links that are relative and end with .html
		if href.endswith(".html") and not href.startswith("http"):
			# Exclude some known non-article pages
			exclude = ["index.html", "faq.html", "bio.html", "books.html", "rss.html", "arc.html", "bel.html", "lisp.html", "antispam.html", "kedrosky.html", "raq.html", "quo.html"]
			if any(href.endswith(ex) for ex in exclude):
				continue
			article_url = base_url + href
			logging.info(f"Downloading article: {article_url}")
			try:
				article_resp = requests.get(article_url)
				article_resp.raise_for_status()
				# Use the link text or href as filename
				title = link.text.strip() or href.split("/")[-1].replace(".html","")
				filename = sanitize_filename(title) + ".html"
				filepath = os.path.join(output_dir, filename)
				logging.info(f"Saving to {filepath}")
				with open(filepath, "w", encoding="utf-8") as f:
					f.write(article_resp.text)
				logging.info(f"Downloaded: {filename}")
				count += 1
			except Exception as e:
				logging.error(f"Failed to download {article_url}: {e}")
	logging.info(f"Completed. Total articles downloaded: {count}")

if __name__ == "__main__":
	main()
