# agent-skills

A small library of Claude Code agent skills plus `manage-skills.py`, an interactive
picker that decides which of them are switched on.

## Idea

Skills live here, organized into collections. Only a chosen subset should be visible
to an agent at any time. Rather than moving directories around, the tool maintains
`active/` as a symlink farm: one symlink per enabled skill, pointing back at the real
skill directory.

Your agent then only needs one link — from its own skills directory to `active/`.

```
skills/                          # source of truth (committed)
  superpowers-6fd4507/
    writing-plans/
    writing-skills/
  mine-swift/
  flutter-0d624f3/
  ...

active/                          # generated, gitignored
  writing-plans   -> ~/.agent-skills/skills/superpowers-6fd4507/writing-plans
  writing-skills  -> ~/.agent-skills/skills/superpowers-6fd4507/writing-skills

~/.claude/skills -> ~/.agent-skills/active      # you make this link once
```

Layout is exactly two levels: `skills/<collection>/<skill>/`. A collection is just a
grouping folder; the skill directory is what gets linked. Directories starting with `.`
are skipped, and a collection with no skill subdirectories is not shown.

## Setup

```sh
git clone <this repo> ~/.agent-skills     # path matters, see Configuration
cd ~/.agent-skills
ln -s ~/.agent-skills/active ~/.claude/skills   # or wherever your agent reads skills
```

## Usage

```sh
./manage-skills.py
```

A full-screen picker opens with collections collapsed. Checkboxes are pre-checked from
whatever is currently linked in `active/`, so the tool always starts from the real state
on disk.

| Key | Action |
| --- | --- |
| `↑` / `↓` | move cursor |
| `→` | expand collection |
| `←` | collapse collection (from a skill row, jumps back to its collection) |
| `space` | toggle skill, or toggle the whole collection |
| `a` | select all |
| `n` | select none |
| `enter` | confirm and write symlinks |
| `q` / `Ctrl-C` | quit without changing anything |

A collection shows `[x]` when all its skills are on, `[~]` when some are, `[ ]` when none.

On confirm the tool **removes every symlink** in each target directory, then creates one
symlink per selected skill. Real files or directories sitting in `active/` are left
untouched — only symlinks are deleted — so `active/` is fully derived state and safe to
throw away. Quitting with `q` writes nothing.

If two collections contain a skill with the same directory name, only the first wins;
the tool prints a `!` conflict line naming both collections and skips the second.

## Configuration

Both paths are constants at the top of `manage-skills.py`:

```python
SOURCE_DIR = Path.home() / ".agent-skills/skills"

TARGET_DIRS = [
    Path.home() / ".agent-skills/active",
]
```

`SOURCE_DIR` is hardcoded to `~/.agent-skills/skills`, which is why the clone location
matters — edit it if you keep the repo elsewhere. `TARGET_DIRS` is a list: add more
entries to fan the same selection out to several agent configurations at once (each is
created with `mkdir -p` if missing, and each is cleared of symlinks on every run).

Symlinks are written as absolute, resolved paths, so `active/` is machine-specific and
gitignored. After cloning on a new machine, or any time it looks stale, just re-run
`./manage-skills.py`.

## Requirements

Python 3.10+ (uses `list | None` type syntax) and a POSIX terminal — the picker uses
`termios`/`tty` raw mode and ANSI escapes, so it needs a real TTY and does not run on
Windows or through a pipe.
