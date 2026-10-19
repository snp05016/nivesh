#!/usr/bin/env python3
"""Fail when a Swift file declares nothing that any other Swift file references.

Usage: find_unreferenced_swift.py <swift-root> [<swift-root> ...]

Every file under the given roots is scanned. A file's symbols are its non-private
top-level (column 0) struct/class/enum/protocol/actor/typealias/func/let/var names
plus the non-private members declared directly inside its top-level extensions
(so a `.myModifier()` helper keeps its file alive). The file is dead when none of
those names appears as an identifier in any other live file (comments stripped).
Dead files are removed and the check repeats, so a chain of types used only by
other dead code is reported too. Files with no symbols are skipped, as are @main
entry points and ALLOWLIST entries.

ponytail: file-level only; a dead type inside a live file is not caught. Swap in
Periphery if that matters.
"""
import re
import sys
from pathlib import Path

# File names (not paths) that are intentionally unreferenced. Only shrink this list:
# a new dead file should be deleted or wired up, not added here.
ALLOWLIST = {
    "PortfolioToolsCard.swift",  # host of the calculators, not mounted until WIP-03
    # Unreferenced when this check landed (audit ARCH-20); other audit items decide
    # whether each is wired up or deleted.
    "AppSoundManager.swift",
    "PremiumUpsellBanner.swift",
    "StockTapActionSheetModifier.swift",
    "UniversalSearchViewModel.swift",
    "UniversalSearchView.swift",
    "StockCorporateActionsView.swift",
    "StockFinancialsView.swift",
}

_ATTRS = r"(?:@\w+(?:\([^)]*\))?\s+)*"
_MODS = r"(?:(?:public|internal|open|final|indirect|nonisolated|static|class|override|mutating)\s+)*"
_NAME = r"\s+`?([A-Za-z_]\w*)"
DECL = re.compile(
    r"^" + _ATTRS + _MODS + r"(?:struct|class|enum|protocol|actor|typealias|func|let|var)" + _NAME,
    re.M,
)
MEMBER = re.compile(r"^\s+" + _ATTRS + _MODS + r"(?:func|var|let|case|struct|class|enum|typealias)" + _NAME)
EXTENSION = re.compile(r"^" + _ATTRS + r"(?:(?:public|internal|fileprivate|private)\s+)?extension\b")
IDENT = re.compile(r"[A-Za-z_]\w*")


def strip_comments(src: str, blank_strings: bool = False) -> str:
    """Remove // and (nested) /* */ comments; optionally blank string contents."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if src.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif src.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            out.append(" ")
        elif src[i] == '"' or src.startswith('#"', i):
            hashes = 0
            while src[i] == "#":
                hashes, i = hashes + 1, i + 1
            quote = '"""' if src.startswith('"""', i) else '"'
            end = quote + "#" * hashes
            j = i + len(quote)
            while j < n and not src.startswith(end, j):
                j += 2 if (src[j] == "\\" and not hashes) else 1
            j = min(n, j + len(end))
            lit = src[i - hashes:j]
            out.append(re.sub(r"[^\n]", " ", lit) if blank_strings else lit)
            i = j
        else:
            out.append(src[i])
            i += 1
    return "".join(out)


def symbols_of(src: str) -> set:
    """Non-private top-level names plus non-private members of top-level extensions."""
    names = set(DECL.findall(src))
    depth, in_ext = 0, False
    for line in strip_comments(src, blank_strings=True).splitlines():
        if depth == 0:
            in_ext = bool(EXTENSION.match(line))
        elif depth == 1 and in_ext:
            m = MEMBER.match(line)
            if m:
                names.add(m.group(1))
        depth += line.count("{") - line.count("}")
    return names


def find_dead(files: dict) -> list:
    """files: path -> comment-stripped source. Returns dead paths, sorted."""
    symbols = {p: symbols_of(s) for p, s in files.items()}
    idents = {p: set(IDENT.findall(s)) for p, s in files.items()}
    candidates = {
        p for p, syms in symbols.items()
        if syms and p.name not in ALLOWLIST and not re.search(r"^@main\b", files[p], re.M)
    }
    live, dead = set(files), set()
    changed = True
    while changed:
        changed = False
        for p in sorted(candidates - dead):
            used = set().union(*(idents[q] for q in live if q != p)) if len(live) > 1 else set()
            if not symbols[p] & used:
                dead.add(p)
                live.discard(p)
                changed = True
    return sorted(dead)


def _self_check() -> None:
    a = 'struct Used {}\nlet url = "https://x" // Ghost\n'
    b = "struct Ghost {}\n/* Used */ final class Chain { let u = Used() }\n"
    c = "@MainActor\nstruct OnlyChain { let c = Chain() }\n"
    d = "@main\nstruct App { let u = Used().stamped() }\n"
    e = ('private struct Stamp {}\nextension View {\n    func stamped() -> some View {\n'
         '        let s = "{"\n        return self\n    }\n    private func hidden() {}\n}\n')
    files = {Path(k + ".swift"): v for k, v in zip("abcde", (a, b, c, d, e))}
    files = {p: strip_comments(s) for p, s in files.items()}
    assert "https://x" in files[Path("a.swift")]
    assert "Ghost" not in files[Path("a.swift")]
    assert symbols_of(files[Path("e.swift")]) == {"stamped"}, symbols_of(files[Path("e.swift")])
    assert find_dead(files) == [Path("b.swift"), Path("c.swift")], find_dead(files)


def main(roots: list) -> int:
    _self_check()
    paths = sorted(p for r in roots for p in Path(r).rglob("*.swift"))
    if not paths:
        print(f"no Swift files under {roots}", file=sys.stderr)
        return 2
    files = {p: strip_comments(p.read_text(encoding="utf-8")) for p in paths}
    dead = find_dead(files)
    for p in dead:
        print(f"{p}: no top-level symbol referenced elsewhere ({', '.join(sorted(symbols_of(files[p])))})")
    if dead:
        print(f"\n{len(dead)} unreferenced Swift file(s). Delete them, wire them up, "
              f"or add them to ALLOWLIST in {Path(__file__).name}.", file=sys.stderr)
        return 1
    print(f"OK: {len(paths)} Swift files, none unreferenced.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
