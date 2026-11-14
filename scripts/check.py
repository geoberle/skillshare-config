#!/usr/bin/env python3
"""Check local user skill ownership; repository and application-provided skills are allowed."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
LIBRARY = ROOT / "library"
errors = []


def require(condition, message):
    if not condition:
        errors.append(message)


def skillshare(*args):
    result = subprocess.run(
        ["skillshare", *args, "-g", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


config_dir = HOME / ".config/skillshare"
require(config_dir.is_symlink() and config_dir.resolve() == ROOT / "config",
        "Skillshare configuration does not resolve to this repository's config directory")
require(not os.environ.get("SKILLSHARE_CONFIG"),
        "SKILLSHARE_CONFIG overrides the repository configuration")
require(not (HOME / ".agents/.skill-lock.json").exists(),
        "The skills CLI has a global lockfile again")
untracked = subprocess.run(
    ["git", "ls-files", "--others", "--exclude-standard", "--", "library", "config", "agents"],
    cwd=ROOT, capture_output=True, text=True, check=True,
).stdout.splitlines()
for path in untracked:
    errors.append(f"Source/config file is not tracked by Git: {path}")

for key in ["skills.enableClaudeUser", "commands.enableClaudeUser"]:
    value = subprocess.run(["omp", "config", "get", key],
                           capture_output=True, text=True, check=True)
    require(json.loads(value.stdout) is False, f"OMP imports Claude user sources: {key}")
providers = {}
for key in ["enabledProviders", "disabledProviders"]:
    value = subprocess.run(["omp", "config", "get", key],
                           capture_output=True, text=True, check=True)
    providers[key] = json.loads(value.stdout)
require("claude" in providers["disabledProviders"] and
        not set(providers["enabledProviders"]) & {"claude", "claude-plugins"},
        "OMP's Claude user-source discovery is enabled")

skills = {p.name: p for p in LIBRARY.iterdir() if (p / "SKILL.md").is_file()}
require(bool(skills), "The skill library is empty")
shared = HOME / ".agents/skills"
require(shared.is_symlink() and shared.resolve() == LIBRARY,
        "The shared skill directory does not link to this repository's library")

for rel in [".claude/skills", ".omp/agent/skills"]:
    target = HOME / rel
    for name, source in skills.items():
        link = target / name
        require(link.is_symlink() and link.resolve() == source,
                f"Missing or incorrect managed link: {link}")
    for entry in target.iterdir():
        if entry.name in [".DS_Store", ".skillshare-manifest.json"]:
            continue
        require(entry.name in skills and entry.is_symlink(),
                f"Unmanaged user skill entry: {entry}")

codex = HOME / ".codex/skills"
if codex.exists():
    for entry in codex.iterdir():
        if entry.name not in [".system", ".DS_Store"]:
            require(entry.is_symlink() and entry.resolve().is_relative_to(LIBRARY),
                    f"Unmanaged Codex user skill entry: {entry}")

for directory, dirs, files in os.walk(LIBRARY):
    dirs[:] = [name for name in dirs if name not in [".venv", "__pycache__", ".git"]]
    for name in dirs + files:
        path = Path(directory) / name
        require(not path.is_symlink() or path.resolve().is_relative_to(ROOT),
                f"Library reference escapes the repository: {path}")

reviewers = json.loads((ROOT / "config/review-agents.json").read_text())
for reviewer in reviewers:
    source = ROOT / reviewer["source"]
    target = Path(reviewer["destination"])
    require(source.is_file() and target.is_symlink() and target.resolve() == source,
            f"Reviewer definition does not link to the repository: {target}")

status = skillshare("status")
require(Path(status["source"]["path"]).resolve() == LIBRARY,
        "Skillshare uses a different skills source")
for target in status["targets"]:
    require(target.get("local", 0) == 0, f"Unmanaged local skills in {target['name']}")

inventory = skillshare("plugin", "list")
builtins = json.loads((ROOT / "config/application-builtins.json").read_text())
enablement = json.loads((ROOT / "config/plugin-enablement.json").read_text())
owned = {}
for name, package in inventory["packages"].items():
    require(bool(package.get("source")), f"Plugin package has no source definition: {name}")
    for target, binding in package.get("bindings", {}).items():
        owned.setdefault(target, set()).add(binding["id"])

hosts = {host["target"]: host for host in inventory["hosts"]}
for target in ["claude", "codex", "omp"]:
    host = hosts[target]
    require(host["status"] == "ready", f"Cannot verify {target}: {host['status']}")
    installed = {entry["id"] for entry in host.get("installed", [])
                 if entry.get("scope") == "user"}
    # Account-connected Codex services are application-provided, by user decision.
    account_provided = {ident for ident in installed
                        if target == "codex" and ident.endswith("@openai-curated-remote")}
    for ident in installed - owned.get(target, set()) - set(builtins.get(target, [])) - account_provided:
        errors.append(f"Unmanaged {target} user plugin: {ident}")
    for ident in owned.get(target, set()) - installed:
        errors.append(f"Missing managed {target} plugin: {ident}")
    for entry in host.get("installed", []):
        expected = enablement.get(target, {}).get(entry["id"])
        if expected is not None:
            require(entry.get("enabledKnown") and entry.get("enabled") == expected,
                    f"Native plugin enablement differs from the repo: {target} {entry['id']}")

if errors:
    print("Ownership check failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print(f"Verified {len(skills)} standalone skills and {len(inventory['packages'])} plugin packages.")
print(f"Verified {len(reviewers)} reviewer definitions across Claude, OMP, and Codex.")
print("Configuration and standalone sources resolve to this repository.")
print("No unmanaged locally installed user skills/plugins found in Claude, OMP, or Codex.")
print("Repository-local and application-provided skills are allowed, including Codex account services.")
print("Cursor and OpenCode are excluded.")
