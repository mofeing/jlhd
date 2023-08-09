import argparse
import tomlkit as toml

parser = argparse.ArgumentParser()
parser.add_argument("package")
parser.add_argument("version")
args = parser.parse_args()

with open("packages.toml", "r") as fh:
    pkgs = toml.load(fh)

pkgs[args.package]["builds"].append(args.version)

with open("packages.toml", "w") as fh:
    toml.dump(pkgs, fh)
