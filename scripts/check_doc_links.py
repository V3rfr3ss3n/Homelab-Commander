"""Check local Markdown file links without network requests or ignored files."""

import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote, urlsplit

INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)")
REFERENCE_LINK = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*(?:<([^>]+)>|(\S+))", re.MULTILINE)
WIKI_LINK = re.compile(r"\[\[([^\]\n]+)\]\]")
CODE = re.compile(r"(`+).*?\1")


def destinations(content: str) -> Iterable[tuple[str, bool]]:
    """Read inline, reference-definition and relative Obsidian destinations.

    Fenced blocks and inline code are examples, not navigation. Fragment and
    query validation is outside this file-existence check.
    """
    lines: list[str] = []
    fence = ""
    for line in content.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            value = marker[1]
            if not fence:
                fence = value
            elif value[0] == fence[0] and len(value) >= len(fence):
                fence = ""
            continue
        if not fence:
            lines.append(CODE.sub("", line))
    text = "\n".join(lines)
    for pattern in (INLINE_LINK, REFERENCE_LINK):
        for match in pattern.finditer(text):
            yield match[1] or match[2], False
    for match in WIKI_LINK.finditer(text):
        yield match[1].split("|", 1)[0], True


def check_links(root: Path, files: Iterable[Path]) -> list[str]:
    """Report links outside the public file set, including repository escapes."""
    root = root.resolve()
    public_files = {(root / file).resolve() for file in files}
    errors: list[str] = []
    for source in sorted(public_files):
        if source.suffix.lower() != ".md" or not source.is_file():
            continue
        for destination, wiki in destinations(source.read_text(encoding="utf-8")):
            url = urlsplit(destination)
            if url.scheme or url.netloc or not url.path:
                continue
            path = unquote(url.path)
            target = (
                root / path.lstrip("/")
                if path.startswith("/")
                else source.parent / path
            )
            if wiki and not target.is_file():
                target = target.with_name(target.name + ".md")
            target = target.resolve()
            if (
                not target.is_relative_to(root)
                or target not in public_files
                or not target.is_file()
            ):
                errors.append(
                    f"{source.relative_to(root)}: missing public target {destination}"
                )
    return errors


def main() -> int:
    """Check tracked and non-ignored new files from the repository root."""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    files = [Path(name.decode("utf-8")) for name in result.stdout.split(b"\0") if name]
    errors = check_links(root, files)
    for error in errors:
        print(error)
    print(f"Documentation links: {len(errors)} error(s)")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
