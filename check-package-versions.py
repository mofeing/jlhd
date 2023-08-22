from git import Repo
from tempfile import mkdtemp
import tomlkit
import os.path
import semver
import argparse
import sys
import json

parser = argparse.ArgumentParser()
parser.add_argument(
    "-o", dest="output", default=sys.stdout, type=argparse.FileType("w")
)
args = parser.parse_args()

registry_repo = Repo.clone_from(
    "https://github.com/JuliaRegistries/General.git",
    mkdtemp(),
    multi_options=["--single-branch", "--depth=1"],
)

docsets_repo = Repo.clone_from(
    "https://github.com/Kapeli/Dash-User-Contributions.git",
    mkdtemp(),
    multi_options=["--single-branch", "--depth=1"],
)

with open(os.path.join(registry_repo.working_tree_dir, "Registry.toml"), "r") as fh:
    registry = tomlkit.load(fh)

with open("packages.toml", "r") as fh:
    pkgs = tomlkit.load(fh)

# filter non-existing packages and map library path in registry
paths = {}
for pkg, info in pkgs.items():
    try:
        paths[pkg] = registry["packages"][info["uuid"]]["path"]
    except tomlkit.exceptions.NonExistentKey:
        sys.stderr.write(f"{pkg}[{info['uuid']}] not found in General registry\n")

# keep outdated docset packages
# NOTE don't update `packages.toml` now
targets = {}
for name, path in paths.items():
    with open(
        os.path.join(registry_repo.working_tree_dir, path, "Versions.toml"), "r"
    ) as fh:
        last_version = max(map(semver.Version.parse, tomlkit.load(fh).keys()))

    docset_json = os.path.join(docsets_repo.working_tree_dir, "docsets", pkgs[name]["bundle_name"], "docset.json")
    if not os.path.exists(docset_json):
        targets[name] = last_version
        print(f"{name} => {last_version} [new package]")
        continue

    with open(docset_json, "r") as fh:
        last_docset_version = semver.Version.parse(json.load(fh)["version"])

    if last_docset_version < last_version:
        targets[name] = last_version
        print(f"{name} => {last_version} [old: {last_docset_version}]")

# format for GITHUB_OUTPUT
if len(targets) != 0:
    args.output.write("matrix=")
    json.dump(
        {
            "include": [
                {
                    "name": name,
                    "version": f"{version.major}.{version.minor}.{version.patch}",
                    **pkgs[name],
                }
                for name, version in targets.items()
            ]
        },
        args.output,
    )
