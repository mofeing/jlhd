from git import Repo
from tempfile import mkdtemp
import tomlkit
import os.path
import semver
import argparse
import sys
import json

parser = argparse.ArgumentParser()
parser.add_argument("-o", dest="output", default=sys.stdout, type=argparse.FileType("w"))
args = parser.parse_args()

registry_repo = Repo.clone_from("https://github.com/JuliaRegistries/General.git", mkdtemp(), multi_options=["--single-branch", "--depth=1"])

with open(os.path.join(registry_repo.working_tree_dir, "Registry.toml"), "r") as fh:
    registry = tomlkit.load(fh)

with open("packages.toml", "r") as fh:
    pkgs = tomlkit.load(fh)

# filter non-existing packages and map library path in registry
paths = {}
for pkg, info in pkgs.items():
    try:
        paths[pkg] = registry['packages'][info['uuid']]['path']
    except tomlkit.exceptions.NonExistentKey:
        print(f"{pkg}[{info['uuid']}] not found in General registry")

# keep outdated docset packages
# NOTE don't update `packages.toml` now
targets = {}
for name, path in paths.items():
    with open(os.path.join(registry_repo.working_tree_dir, path, "Versions.toml"), "r") as fh:
        last_version = max(map(semver.Version.parse, tomlkit.load(fh).keys()))

    last_docset_version = max(map(semver.Version.parse, pkgs[name]['builds']), default=semver.Version(0))

    if last_docset_version < last_version:
        targets[name] = last_version
        print(f"{name} => {last_version}")

# format for GITHUB_OUTPUT
if len(targets) != 0:
    args.output.write("matrix=")
    json.dump({'include': [{
        'name': name,
        'version': f"{version.major}.{version.minor}.{version.patch}",
        **pkgs[name],
     } for name, version in targets.items()]}, args.output)
