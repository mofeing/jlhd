import scrapy
from urllib.parse import urljoin, urlparse, urlunparse
import os.path
from os.path import relpath, splitext
from pathlib import Path
from scrapy.linkextractors import LinkExtractor
import re
from bs4 import BeautifulSoup


class DocumenterSpider(scrapy.Spider):
    name = "documenter"
    start_urls = []
    target_path = ""

    def parse(self, response, external: bool = False, **kwargs):
        filename = urlparse(response.url).path.removeprefix("/")

        # if html but url is a folder, suffix "index.html"
        ext = splitext(filename)[-1]
        if ext == "":
            filename = urljoin(filename, "index.html")
            ext = ".html"

        url_root = urlparse(self.start_urls[0]).path.removeprefix("/")
        filename = relpath(filename, url_root)

        # do not go up to upper directories
        filename = re.sub("\.\.\/", "", filename)
        if external:
            filename = os.path.join("__dash_external", filename.lstrip('/'))

        filename: Path = self.target_path.joinpath(filename)

        # if file exists, it doesn't need more processing
        # TODO skip on parsing
        if filename.exists():
            return
        
        filename.parent.mkdir(parents=True, exist_ok=True)

        # if css, js or image, fetch and exit
        if ext != ".html":
            print(f"[ARTIFACT] {filename}")
            with open(filename, "wb") as file:
                file.write(response.body)
            return

        # if html, fetch, parse links and relink to local files
        soup = BeautifulSoup(response.body, features='lxml')

        # fetch images
        for src in response.css("img::attr(src)"):
            # skip external images
            if urlparse(src.get()).scheme == "https":
                continue
            yield response.follow(src.get(), callback=None)

        for tag in soup.select("img[src]"):
            if urlparse(tag['src']).scheme == "https":
                continue

        # fetch scripts
        for src in response.css("script::attr(src)"):
            src = src.get()

            # make local copy of vendored scripts
            # TODO manage 'versions.js'
            isexternal = urlparse(src).scheme != ""

            # url = urljoin(self.start_urls[0], src)
            yield response.follow(src, callback=None, cb_kwargs = dict(external = isexternal))

        for tag in soup.select("script[src]"):
            print(f"\033[0;31m[SCRIPT DETECTED]\n\told: {tag['src']}\033[0;00m")

            if urlparse(tag['src']).scheme == "https":
                tag['src'] = os.path.join("__dash_external", urlparse(tag['src']).path.lstrip('/'))

            print(f"\033[0;33m\tnew: {tag['src']}\033[0;00m")

        # fetch css
        for href in response.css("link::attr(href)"):
            href = href.get()

            # make local copy of vendored styles
            isexternal = urlparse(href).scheme != ""

            yield response.follow(href, callback=None, cb_kwargs = dict(external = isexternal))

        for tag in soup.select("link[href]"):
            print(f"\033[0;31m[LINK DETECTED]\n\told: {tag['href']}\033[0;00m")

            if urlparse(tag['href']).scheme == "https":
                tag['href'] = os.path.join("__dash_external", urlparse(tag['href']).path.lstrip('/'))

            print(f"\033[0;33m\tnew: {tag['href']}\033[0;00m")
            

        # fetch html
        link_extractor = LinkExtractor(
            allow=[
                self.start_urls[0]
                .replace(":", "\:")
                .replace("/", "\/")
                .replace(".", "\.")
            ]
        )
        for link in link_extractor.extract_links(response):
            # page-wide link
            if urlparse(link.url).fragment != "":
                continue

            yield response.follow(link.url, callback=self.parse)

        for tag in soup.select("a[href]"):
            scheme, netloc, path, params, query, fragment = urlparse(tag['href'])

            if scheme == "" and netloc == "" and path == "" and query == "":
                print(f"[DEBUG] local link = {tag['href']}")
                continue

            if netloc != "" and netloc != urlparse(self.start_urls[0]).netloc:
                print(f"[DISCARDED] {tag['href']}")
                continue


            _, ext = splitext(path)
            if len(path) != 0 and ext != ".html":
                path = os.path.join(path, "index.html")
                print(f"\033[0;32m[DEBUG] path={path} \033[0;00m")

            tag['href'] = urlunparse(('', '', path, params, query, fragment))

        with open(filename, "wb") as file:
            file.write(soup.prettify('utf8'))