import argparse
from lib.docset import Docset

parser = argparse.ArgumentParser(
    prog="jlhd",
    description="Fetch Documenter.jl websites and pack them into DocSet",
)
parser.add_argument("bundle_id")
parser.add_argument("bundle_name")
parser.add_argument("platform_family")
parser.add_argument("url")

parser.add_argument("--allow_js", action="store_true")
parser.add_argument("--playground")
parser.add_argument("--fallback_url")
parser.add_argument("--version", default=None)

args = parser.parse_args()
bundle_id = args.bundle_id
bundle_name = args.bundle_name
platform_family = args.platform_family
url = args.url.format(version="v" + args.version)

fallback_url = args.fallback_url if hasattr(args, 'fallback_url') else url

docset = Docset(
    bundle_id,
    bundle_name,
    platform_family,
    url,
    index="index.html",
    allow_js=args.allow_js,
    playground=args.playground,
    fallback_url=fallback_url,
)

docset.render()
