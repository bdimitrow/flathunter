"""Crawler for imot.bg search result pages."""
import hashlib
import re
from urllib.parse import urldefrag, urljoin, urlsplit

from flathunter.abstract_crawler import Crawler


class Imot(Crawler):
    """Extract listings from imot.bg's server-rendered search results."""

    BASE_URL = "https://www.imot.bg"
    URL_PATTERN = re.compile(r'^https?://(?:www\.)?imot\.bg(?:[/?#]|$)')

    @staticmethod
    def _text(element):
        return ' '.join(element.stripped_strings) if element else ''

    def extract_data(self, raw_data):
        """Parse listing cards, ignoring advertisements and duplicate cards."""
        entries = {}
        for item in raw_data.select('div.item[id^="ida"]'):
            link = item.select_one('a.title[href]')
            if link is None:
                continue
            url = urljoin(self.BASE_URL, str(link['href']))
            match = re.match(r'/obiava-([a-z0-9]+)-', urlsplit(url).path)
            if not self.URL_PATTERN.match(url) or not match:
                continue
            listing_id = match.group(1)
            title = ' '.join(str(text).strip() for text in
                             link.find_all(string=True, recursive=False)).strip()
            if not title:
                continue
            rooms = re.search(r'(\d+)\s*-\s*СТАЕН', title, re.IGNORECASE)
            size = re.search(r'([\d\s]+(?:[.,]\d+)?)\s*кв\.?\s*м',
                             self._text(item.select_one('.info')))
            price = self._text(item.select_one('.price > div'))
            # Existing price filters expect ungrouped numbers and decimal commas.
            price = re.sub(r'(?<=\d)\s+(?=\d)', '', price)
            price = re.sub(r'(?<=\d)\.(?=\d{1,2}(?:\D|$))', ',', price)
            image = item.select_one('img.pic')
            image_url = image.get('src', '') if image else ''
            entries[listing_id] = {
                # Namespaced, deterministic IDs fit the signed SQLite INTEGER column.
                'id': int(hashlib.sha256(('imot.bg:' + listing_id).encode()).hexdigest()[:15], 16),
                'url': urldefrag(url)[0],
                'title': title,
                'address': self._text(link.select_one('location')),
                'price': price,
                'size': re.sub(r'\s+', '', size.group(1)) + ' m²' if size else '',
                'rooms': rooms.group(1) if rooms else '',
                'image': urljoin(self.BASE_URL, str(image_url)) if image_url else '',
                'crawler': self.get_name(),
            }
        return list(entries.values())

    def get_results(self, search_url, max_pages=None):
        """Follow next-page links, retaining search filters and avoiding loops."""
        entries = {}
        visited = set()
        url = urldefrag(search_url)[0]
        while url and url not in visited and (max_pages is None or len(visited) < max_pages):
            visited.add(url)
            soup = self.get_page(url)
            for entry in self.extract_data(soup):
                entries[entry['id']] = entry
            next_link = soup.select_one('.pagination a.next[href]')
            url = urldefrag(urljoin(url, str(next_link['href'])))[0] if next_link else ''
            if url and not self.URL_PATTERN.match(url):
                break
        return list(entries.values())
