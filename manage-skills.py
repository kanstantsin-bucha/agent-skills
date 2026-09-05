#!/usr/bin/env python3
"""Manage skill symlinks for Claude Code agent skill directories."""

import os
import sys
from pathlib import Path

# --- Configuration ---
SOURCE_DIR = Path.home() / ".agent-skills/skills"

# Target directories where skill symlinks will be placed.
# Add more entries here for additional agent configurations.
TARGET_DIRS = [
    Path.home() / ".agent-skills/active",
]
# ---------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"


def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"


def get_groups(source_dir: Path) -> list[tuple[str, list[tuple[str, Path]]]]:
    """Return [(collection_name, [(skill_name, skill_path), ...]), ...]."""
    groups = []
    for collection in sorted(source_dir.iterdir()):
        if not collection.is_dir() or collection.name.startswith("."):
            continue
        children = [
            (skill.name, skill)
            for skill in sorted(collection.iterdir())
            if skill.is_dir() and not skill.name.startswith(".")
        ]
        if children:
            groups.append((collection.name, children))
    return groups


def get_active_skill_names(target_dirs: list[Path]) -> set[str]:
    """Return names of skill dirs currently symlinked in any target dir."""
    active = set()
    for target in target_dirs:
        if target.exists():
            for item in target.iterdir():
                if item.is_symlink():
                    active.add(item.name)
    return active


def remove_symlinks(target_dirs: list[Path]) -> int:
    removed = 0
    for target in target_dirs:
        if not target.exists():
            continue
        for item in target.iterdir():
            if item.is_symlink():
                item.unlink()
                print(f"  {color('−', RED)} {item.name}")
                removed += 1
    return removed


def create_symlinks(selected: list[Path], target_dirs: list[Path]) -> int:
    created = 0
    for target in target_dirs:
        target.mkdir(parents=True, exist_ok=True)
        seen_names: dict[str, Path] = {}
        for skill_path in selected:
            name = skill_path.name
            if name in seen_names:
                print(
                    f"  {color('!', YELLOW)} Conflict: '{name}' from "
                    f"{skill_path.parent.name} and {seen_names[name].parent.name} — "
                    f"keeping first"
                )
                continue
            seen_names[name] = skill_path
            link = target / name
            if link.is_symlink():
                link.unlink()
            link.symlink_to(skill_path.resolve())
            print(f"  {color('+', GREEN)} {name}")
            created += 1
    return created


def interactive_select(
    groups: list[tuple[str, list[tuple[str, Path]]]], active: set[str]
) -> list[Path] | None:
    """Hierarchical checkbox selection: collapsible groups + indented skill rows."""
    all_paths = [p for _, children in groups for _, p in children]
    selected: dict[Path, bool] = {p: p.name in active for p in all_paths}
    expanded: set[str] = set()  # collection names currently open

    cursor = 0
    scroll_offset = 0
    HEADER_LINES = 4
    FOOTER_LINES = 2

    def build_items() -> list[tuple]:
        # ("group", collection, child_paths) | ("skill", name, path, collection)
        items: list[tuple] = []
        for collection, children in groups:
            child_paths = [p for _, p in children]
            items.append(("group", collection, child_paths))
            if collection in expanded:
                for name, path in children:
                    items.append(("skill", name, path, collection))
        return items

    def group_state(child_paths: list[Path]) -> str:
        states = [selected[p] for p in child_paths]
        if all(states):
            return "all"
        if any(states):
            return "partial"
        return "none"

    def println(s: str = "") -> None:
        sys.stdout.write(s + "\r\n")

    def render(items: list[tuple]) -> None:
        nonlocal scroll_offset
        try:
            term_height = os.get_terminal_size().lines
        except OSError:
            term_height = 24
        visible = max(1, term_height - HEADER_LINES - FOOTER_LINES)

        if cursor < scroll_offset:
            scroll_offset = cursor
        elif cursor >= scroll_offset + visible:
            scroll_offset = cursor - visible + 1

        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        println(color(BOLD + "Select skills to enable", BOLD))
        println(
            color(
                "  ↑/↓ move   space toggle   → expand   ← collapse   a all   n none   enter confirm   q quit",
                DIM,
            )
        )
        println()

        for i in range(scroll_offset, min(scroll_offset + visible, len(items))):
            item = items[i]
            is_cursor = i == cursor
            arrow = color("▶ ", CYAN) if is_cursor else "  "

            if item[0] == "group":
                _, collection, child_paths = item
                state = group_state(child_paths)
                check = (
                    color("[x]", GREEN)
                    if state == "all"
                    else (
                        color("[~]", YELLOW)
                        if state == "partial"
                        else color("[ ]", DIM)
                    )
                )
                fold = color("▾ ", DIM) if collection in expanded else color("▸ ", DIM)
                label = (
                    color(collection, BOLD)
                    if is_cursor
                    else color(collection, BOLD + DIM)
                )
                println(f"{arrow}{check} {fold}{label}")
            else:
                _, name, path, _ = item
                check = color("[x]", GREEN) if selected[path] else color("[ ]", DIM)
                label = color(name, BOLD) if is_cursor else name
                println(f"  {arrow}{check}   {label}")

        enabled = sum(v for v in selected.values())
        total = len(selected)
        println()
        scroll_hint = f"  ({scroll_offset + 1}–{min(scroll_offset + visible, len(items))} of {len(items)})  "
        println(color(f"{scroll_hint}{enabled}/{total} skills selected", DIM))
        sys.stdout.flush()

    def toggle(items: list[tuple], i: int) -> None:
        item = items[i]
        if item[0] == "group":
            new_val = group_state(item[2]) != "all"
            for p in item[2]:
                selected[p] = new_val
        else:
            selected[item[2]] = not selected[item[2]]

    import termios
    import tty

    items = build_items()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            render(items)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(2)
                if ch2 == "[A":  # up
                    cursor = (cursor - 1) % len(items)
                elif ch2 == "[B":  # down
                    cursor = (cursor + 1) % len(items)
                elif ch2 == "[C":  # right → expand group
                    item = items[cursor]
                    if item[0] == "group" and item[1] not in expanded:
                        expanded.add(item[1])
                        items = build_items()
                elif ch2 == "[D":  # left ← collapse
                    item = items[cursor]
                    if item[0] == "group" and item[1] in expanded:
                        expanded.discard(item[1])
                        items = build_items()
                    elif item[0] == "skill":
                        col = item[3]
                        expanded.discard(col)
                        items = build_items()
                        for j, it in enumerate(items):
                            if it[0] == "group" and it[1] == col:
                                cursor = j
                                break
            elif ch == " ":
                toggle(items, cursor)
            elif ch in ("a", "A"):
                for p in selected:
                    selected[p] = True
            elif ch in ("n", "N"):
                for p in selected:
                    selected[p] = False
            elif ch in ("\r", "\n"):
                return [p for p, v in selected.items() if v]
            elif ch in ("q", "Q", "\x03"):
                return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    if not SOURCE_DIR.exists():
        print(f"Source directory not found: {SOURCE_DIR}")
        sys.exit(1)

    groups = get_groups(SOURCE_DIR)
    if not groups:
        print("No skills found in source directory.")
        sys.exit(1)

    active = get_active_skill_names(TARGET_DIRS)
    result = interactive_select(groups, active)

    os.system("clear")

    if result is None:
        print("Cancelled.")
        return

    targets_display = ", ".join(str(t) for t in TARGET_DIRS)
    print(color(f"\nTargets: {targets_display}\n", DIM))

    print("Removing existing symlinks...")
    removed = remove_symlinks(TARGET_DIRS)
    if removed == 0:
        print(color("  (none)", DIM))

    print(f"\nCreating {len(result)} symlinks...")
    created = create_symlinks(result, TARGET_DIRS)

    print(color(f"\n✓ Done — {created} skills enabled.", GREEN))


if __name__ == "__main__":
    main()
