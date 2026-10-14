"""Offline regression tests for imot.bg markup and pagination."""
from pathlib import Path

from bs4 import BeautifulSoup
import pytest

from flathunter.config import YamlConfig
from flathunter.crawler.imot import Imot
from flathunter.filter import ExposeHelper


URL = 'https://www.imot.bg/obiavi/naemi/grad-sofiya'
HTML = Path(__file__).with_name('fixtures').joinpath('imot-search.html').read_bytes()


def test_live_markup_and_encoding(requests_mock):
    requests_mock.get(URL, content=HTML)
    crawler = Imot(YamlConfig())
    entry, = crawler.crawl(URL)
    assert entry['title'] == 'Дава под наем 2-СТАЕН'
    assert entry['address'] == 'град София, Манастирски ливади'
    assert entry['price'] == '700 €'
    assert entry['size'] == '92 m²'
    assert entry['rooms'] == '2'
    assert entry['image'].endswith('2c179059770301825_kg.jpg')
    assert entry['image'].startswith('https://')
    assert 0 < entry['id'] < 2**63
    assert entry['id'] == crawler.crawl(URL)[0]['id']


def test_missing_fields_and_price_normalization():
    soup = BeautifulSoup(HTML, 'lxml')
    soup.select_one('.price > div').string = '1\xa0250.50 €'
    for node in soup.select('location, .info, img.pic'):
        node.decompose()
    entry, = Imot(YamlConfig()).extract_data(soup)
    assert ExposeHelper.get_price(entry) == 1250.5
    assert entry['address'] == entry['size'] == entry['image'] == ''
    soup.select_one('a.title').decompose()
    assert Imot(YamlConfig()).extract_data(soup) == []


@pytest.mark.parametrize('limit, count', [(None, 2), (1, 1), (2, 2), (0, 0)])
def test_pagination_and_duplicates(requests_mock, limit, count):
    next_url = URL + '/p-2?sort=1'
    first = HTML + f'<div class="pagination"><a class="next" href="{next_url}">Next</a></div>'.encode()
    second = HTML + HTML.replace(b'2c179059770301825', b'2c179117330988999')
    # A repeated next URL must not cause an infinite crawl.
    second += f'<div class="pagination"><a class="next" href="{next_url}">Next</a></div>'.encode()
    requests_mock.get(URL, content=first)
    requests_mock.get(next_url, content=second)
    entries = Imot(YamlConfig()).crawl(URL, max_pages=limit)
    assert len(entries) == count
    assert requests_mock.call_count == count


def test_external_pagination_and_unrelated_urls(requests_mock):
    requests_mock.get(URL, content=HTML + b'<div class="pagination"><a class="next" href="https://other.example/">Next</a></div>')
    crawler = Imot(YamlConfig())
    assert len(crawler.crawl(URL)) == 1
    assert crawler.crawl('https://www.imot.bg.other.example/') == []
    assert requests_mock.call_count == 1


def test_empty_results():
    assert Imot(YamlConfig()).extract_data(BeautifulSoup('<html></html>', 'lxml')) == []


def test_registered_crawler():
    config = YamlConfig()
    config.init_searchers()
    assert any(isinstance(crawler, Imot) for crawler in config.searchers())
