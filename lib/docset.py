from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import sqlite3 as sql
import os.path
from lib.spider import DocumenterSpider
from scrapy.crawler import CrawlerProcess
import shutil
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse


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
        dash_index_file_path = f"<key>dashIndexFilePath</key>\n<string>{self.index}</string>\n" if self.index is not None else ""
        dash_docset_fallback_url = f"<key>DashDocSetFallbackURL</key>\n<string>{self.fallback_url}</string>\n" if self.fallback_url is not None else ""
        dash_docset_play_url = f"<key>DashDocSetPlayURL</key>\n<string>{self.playground}</key>\n" if self.playground is not None else ""
        is_javascript_enabled = "<key>isJavaScriptEnabled</key>\n<true/>\n" if self.allow_js else ""
        dash_docset_default_fts_enabled = "<key>DashDocSetDefaultFTSEnabled</key>\n<true/>\n" if self.fts else ""
        dash_docset_fts_not_supported = "<key>DashDocSetFTSNotSupported</key>\n<true/>\n" if self.fts_forbidden else ""
        return '<?xml version="1.0" encoding="UTF-8"?>\n' \
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n' \
                '<plist version="1.0">\n' \
                '<dict>\n' \
                '<key>CFBundleIdentifier</key>\n' \
                f'<string>{self.bundle_id}</string>\n' \
                '<key>CFBundleName</key>\n' \
                f'<string>{self.bundle_name}</string>\n' \
                '<key>DocSetPlatformFamily</key>\n' \
                f'<string>{self.platform_family}</string>\n' \
                '<key>isDashDocset</key>\n' \
                '<true/>\n' \
                f"{dash_index_file_path}" \
                f"{dash_docset_fallback_url}" \
                f"{dash_docset_play_url}" \
                f"{is_javascript_enabled}" \
                f"{dash_docset_default_fts_enabled}" \
                f"{dash_docset_fts_not_supported}" \
                "</dict>\n" \
                "</plist>\n"
                

    @property
    def root(self):
        return Path(f"{self.bundle_name}.docset")

    def render(self):
        shutil.rmtree(self.root, ignore_errors=True)

        print("Generating Info.plist...")
        plist = self.root / "Contents" / "Info.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)

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
        cursor.execute(
            "CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT)"
        )
        cursor.execute("CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path)")

        for root, _, filenames in os.walk(content):
            filenames = list(
                filter(lambda x: os.path.splitext(x)[-1] == ".html", filenames)
            )

            for filename in filenames:
                with open(
                    Path(root) / filename, "r+", encoding="utf8", errors="ignore"
                ) as fh:
                    soup = BeautifulSoup(fh, features="lxml")

                    # fix links
                    # NOTE if deployed with folder organization, "index.html" is not appended to links
                    for tag in soup.find_all("a", href=True):
                        scheme, netloc, path, params, query, fragment = urlparse(
                            tag["href"]
                        )
                        folder, file = os.path.split(path)

                        if not file:
                            file = "index.html"
                            tag["href"] = urlunparse(
                                (
                                    scheme,
                                    netloc,
                                    os.path.join(folder, file),
                                    params,
                                    query,
                                    fragment,
                                )
                            )

                    print(f"{os.path.join(root,filename)}:")

                    # register types, functions, methods, ...
                    for tag in soup.find_all(class_="docstring"):
                        binding = tag.find(class_="docstring-binding")
                        name = binding.find("code").string.replace("'", "''")
                        href = binding["href"]
                        path = os.path.join(
                            os.path.relpath(root, start=content), filename, href
                        ).replace("'", "''")
                        type = tag.find(class_="docstring-category").string
                        print(f"\t{name} => {type} @ {path}")
                        cursor.execute(
                            f"INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES ('{name}', '{type}', '{path}')"
                        )

                    # register sections
                    for tag in soup.select("h1 > .docs-heading-anchor"):
                        name = tag.parent.text.replace("'", "''")
                        href = tag["href"]
                        path = os.path.join(
                            os.path.relpath(root, start=content), filename, href
                        ).replace("'", "''")
                        type = "Section"
                        print(f"\t{name} => {type} @ {path}")
                        cursor.execute(
                            f"INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES ('{name}', '{type}', '{path}')"
                        )

                    fh.write(str(soup))
                    con.commit()
