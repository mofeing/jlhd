from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sqlite3 as sql
import os.path
from jlhd.spider import DocumenterSpider
from scrapy.crawler import CrawlerProcess
import shutil
from bs4 import BeautifulSoup

@dataclass
class Docset:
    bundle_id: str
    bundle_name: str
    platform_family: str
    url: str

    # dash
    icon: Optional[str] = None
    icon_retina: Optional[str] = None
    index: Optional[str] = None
    fallback_url: Optional[str] = None
    playground: Optional[str] = None
    allow_js: bool = False
    fts: bool = False
    fts_forbidden: bool = False


    @property
    def plist(self) -> str:
        return f'''
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
            <plist version="1.0">
            <dict>
            <key>CFBundleIdentifier</key>
            <string>{self.bundle_id}</string>
            <key>CFBundleName</key>
            <string>{self.bundle_name}</string>
            <key>DocSetPlatformFamily</key>
            <string>{self.platform_family}</string>
            <key>isDashDocset</key>
            <true/>
            {"""<key>dashIndexFilePath</key>
            <string>{self.index}</string>
            """ if self.index is not None else ""}
            {"""<key>DashDocSetFallbackURL</key>
            <string>{self.fallback_url}</string>""" if self.fallback_url is not None else ""}
            {"""<key>DashDocSetPlayURL</key>
            <string>{self.playground}</key>""" if self.playground is not None else ""}
            {"""<key>isJavaScriptEnabled</key>
            <true/>""" if self.allow_js else ""}
            {"""<key>DashDocSetDefaultFTSEnabled</key>
            <true/>""" if self.fts else ""}
            {"""<key>DashDocSetFTSNotSupported</key>
            <true/>""" if self.fts_forbidden else ""}
            </dict>
            </plist>
            '''
    
    @property
    def root(self):
        return Path(f"{self.bundle_name}.docset")

    def render(self):
        shutil.rmtree(self.root, ignore_errors=True)

        print("Generating Info.plist...")
        plist = self.root / "Contents" / "Info.plist"
        plist.parent.mkdir(parents = True, exist_ok=True)

        with open(plist, "w") as fh:
            fh.write(self.plist)

        # crawl website
        print("Crawling website...")
        content = self.root / "Contents" / "Resources" / "Documents"
        content.mkdir(parents=True, exist_ok=True)

        DocumenterSpider.target_path = content
        DocumenterSpider.start_urls = [self.url]

        crawler = CrawlerProcess()
        crawler.crawl(DocumenterSpider)
        crawler.start()
        crawler.stop()

        # TODO walk through html files
        print("Populating SQLite index...")
        db = self.root / "Contents" / "Resources" / "docSet.dsidx"
        con = sql.connect(db)
        cursor = con.cursor()
        cursor.execute("CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT)")
        cursor.execute("CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path)")

        for root, _, filenames in os.walk(content):
            filenames = list(filter(lambda x: os.path.splitext(x)[-1] == ".html", filenames))

            for filename in filenames:
                with open(Path(root) / filename, "r") as fh:
                    soup = BeautifulSoup(fh, features="lxml")

                    print(f"{os.path.join(root,filename)}:")

                    # register types, functions, methods, ...
                    for tag in soup.find_all(class_="docstring"):
                        binding = tag.find(class_="docstring-binding")
                        name = binding.find("code").string
                        href = binding['href']
                        path = os.path.join(os.path.relpath(root, start=content), filename, href)
                        type = tag.find(class_="docstring-category").string
                        print(f"\t{name} => {type} @ {path}")
                        cursor.execute(f"INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES ('{name}', '{type}', '{path}')")

                    # register sections
                    for tag in soup.select("h1 > .docs-heading-anchor"):
                        name = tag.parent['id']
                        href = tag['href']
                        path = os.path.join(os.path.relpath(root, start=content), filename, href)
                        type = "Section"
                        print(f"\t{name} => {type} @ {path}")
                        cursor.execute(f"INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES ('{name}', '{type}', '{path}')")

                    con.commit()

