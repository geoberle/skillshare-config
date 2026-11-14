# Personal skills

This repository is the source for user-installed skills and reviewer agents in
Claude Code, OMP, and Codex. Skillshare reads its active configuration here and
manages delivery to those applications.

Repository-local skills are allowed. Application-built-in skills and Codex's
account-delivered services remain application-provided. Cursor and OpenCode are
outside this setup.

## Layout

| Path | Purpose |
| --- | --- |
| `config/config.yaml` | Active Skillshare sources, targets, plugins, and extras |
| `config/marketplaces.json` | Native marketplace sources and branch selections |
| `config/plugin-enablement.json` | Expected native plugin enabled states |
| `config/application-builtins.json` | Application-supplied native plugin identities |
| `config/review-agents.json` | Reviewer source files and installation destinations |
| `library/` | Standalone skills, resources, and upstream metadata |
| `agents/` | Steve and David reviewer definitions |
| `scripts/check.py` | Ownership and configuration checks |

`~/.config/skillshare` links to `config/`, so Skillshare's own writes update this
checkout. `~/.agents/skills` links to `library/`. Claude and OMP have individual
Skillshare-managed links into the library; Codex discovers the shared directory
directly. Complete plugins remain in native application stores, with their
sources and bindings declared here.

## Check

```sh
python3 /Users/goberlec/personal/skills/scripts/check.py
```

Requires Python 3.9+, Skillshare, and OMP. Checks configuration and skill links,
reviewer links, Git tracking, native plugin ownership and enablement, and OMP's
isolation from Claude user sources. Codex's `openai-curated-remote` account
services are recognized as application-provided. Repository-local skills are
not scanned.

## Skills

Edit personal skills in `library/`. Install or update upstream skills with an
explicit global scope, then sync:

```sh
skillshare install owner/repository --skill skill-name -g --dry-run
skillshare install owner/repository --skill skill-name -g
skillshare sync -g

skillshare install skill-name --update -g --dry-run
skillshare install skill-name --update -g
skillshare sync -g
```

Upstream provenance is stored in `library/.metadata.json`. Add new source files
to Git before running the ownership check.

## Plugins

```sh
skillshare plugin list -g
skillshare plugin check NAME -g --json
skillshare plugin update NAME --target claude -g --dry-run --json
```

Apply reviewed mutations using their returned `--revision`. Imported Claude and
Codex plugins use their native marketplaces. Plugin sync selection differs from
native enablement; keep `config/plugin-enablement.json` consistent with intended
native changes. Plugins are excluded from `skillshare sync --all`; use
`skillshare sync plugins -g` separately after reviewing its preview.

Skillshare blocks in-place OMP plugin upgrades. Close relevant sessions and back
up configuration/registries, then preview scoped removal with
`skillshare plugin remove NAME --target omp -g --dry-run --json`. Apply the
reviewed removal and re-add from the recorded source using
`skillshare plugin add URL --plugin NAME --name NAME --target omp -g`, also
previewing first. Preserve any recorded `--source-ref`. This retains shared
cache and other applications' bindings. Standalone skill updates do not use
OMP's plugin lifecycle.

OMP's Claude user-source imports stay disabled. Its native marketplace loader,
internally named `claude-plugins`, remains available for OMP's own installations.

## Reviewers

The two reviewers use matching instructions with application-specific settings:

| Source | Delivery |
| --- | --- |
| `agents/claude/*.md` | Native agent sync to `~/.claude/agents/` |
| `agents/omp/*.md` | Extras links to `~/.omp/agent/agents/` |
| `agents/codex/*.toml` | Extras links to `~/.codex/agents/` |

Update all three bodies when changing shared review guidance, then run:

```sh
skillshare sync agents -g
skillshare sync extras -g
```

## Git and recovery

Use ordinary Git at the repository root to version configuration and content
together. Skillshare's built-in `push`/`pull` operates on its configured source
scope rather than this whole-repository workflow.

On a new machine, install Skillshare and the applications, clone the repo,
review absolute paths in `config/`, and link `~/.config/skillshare` to `config/`.
Preserve existing destinations before replacing links. Sync skills, agents, and
extras separately. Restore native marketplaces from `config/marketplaces.json`
before reinstalling imported plugins; review plugin sync before applying it.
Native authentication is not stored here.

Recovery backups are stored outside the repository at:

```
~/.local/state/skillshare/backups/setup-20261026/
```

Restore with the relevant applications closed and preserve current state first.
Application caches, credentials, Python environments, and runtime logs do not
belong in this repository.
