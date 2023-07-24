import scrapy
from urllib.parse import urljoin, urlparse
from os.path import relpath, splitext
from pathlib import Path
from scrapy.linkextractors import LinkExtractor

class DocumenterSpider(scrapy.Spider):
    name = "documenter"
    start_urls = []
    target_path = ""
    
    def parse(self, response, **kwargs):
        filename = urlparse(response.url).path.removeprefix("/")

        # if html but url is a folder, suffix "index.html"
        ext = splitext(filename)[-1]
        if ext == '':
            filename = urljoin(filename, "index.html")
            ext = ".html"

        url_root = urlparse(self.start_urls[0]).path.removeprefix("/")
        filename = relpath(filename, url_root)

        filename: Path = self.target_path.joinpath(filename)
        
        # if file exists, it doesn't need more processing
        # TODO skip on parsing
        if filename.exists():
            return

        filename.parent.mkdir(parents=True, exist_ok=True)
        with open(filename, 'wb') as file:
            file.write(response.body)

        if ext != ".html":
            return

        # fetch images
        # TODO replace url for local version in html
        for src in response.css("img::attr(src)"):
            src = src.get()
            url = urljoin(self.start_urls[0], src)
            yield scrapy.Request(url)

        # fetch scripts
        # TODO replace url for local version in html
        for src in response.css("script::attr(src)"):
            src = src.get()

            # skip vendored scripts
            # TODO make local copy of vendored scripts
            # TODO manage 'versions.js'
            if urlparse(src).scheme != '':
                continue

            url = urljoin(self.start_urls[0], src)
            yield scrapy.Request(url)

        # fetch css
        # TODO replace url for local version in html
        for href in response.css("link::attr(href)"):
            href = href.get()

            # skip vendored styles
            # TODO make local copy of vendored styles
            if urlparse(href).scheme != '':
                continue

            url = urljoin(self.start_urls[0], href)
            yield scrapy.Request(url)

        # fetch html
        link_extractor = LinkExtractor(allow=[self.start_urls[0]
                                              .replace(':', '\:')
                                              .replace('/', '\/')
                                              .replace('.', '\.')
                                              ])
        for link in link_extractor.extract_links(response):
            # page-wide link
            if urlparse(link.url).fragment != '':
                continue

            yield scrapy.Request(link.url)
