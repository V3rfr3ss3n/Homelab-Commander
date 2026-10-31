"""Behavioral coverage for the offline public-documentation link gate."""

from pathlib import Path

from scripts.check_doc_links import check_links


def test_links_resolve_relative_wiki_reference_and_encoded_paths(
    tmp_path: Path,
) -> None:
    """Both documentation styles resolve only public files, without HTTP."""
    (tmp_path / "docs").mkdir()
    source = tmp_path / "docs/index.md"
    source.write_text(
        "[file](../target%20file.md#section)\n"
        '[file](<../target file.md> "Title")\n'
        "[[../target file|Label]]\n"
        "[[../release-0.2]]\n"
        "[guide]: ../target%20file.md\n"
        "[web](https://example.invalid/unreachable)\n"
        "[anchor](#section)\n"
    )
    target = tmp_path / "target file.md"
    target.write_text("# Target\n")
    release = tmp_path / "release-0.2.md"
    release.write_text("# Release\n")
    assert check_links(tmp_path, [source, target, release]) == []


def test_missing_ignored_and_escaping_targets_fail(tmp_path: Path) -> None:
    """Existing ignored files and files outside the repository are not public."""
    source = tmp_path / "index.md"
    source.write_text(
        "[missing](missing.md)\n[[missing-wiki]]\n"
        "[ignored](private.md)\n[escape](../outside.md)\n"
        "[ref]: missing-reference.md\n"
    )
    (tmp_path / "private.md").write_text("local only")
    errors = check_links(tmp_path, [source])
    assert len(errors) == 5
    assert all(error.startswith("index.md: missing public target ") for error in errors)


def test_code_examples_are_ignored_but_navigation_after_fences_is_checked(
    tmp_path: Path,
) -> None:
    """Code examples do not create false failures or hide later navigation."""
    source = tmp_path / "index.md"
    source.write_text(
        "`[inline](missing.md)`\n```markdown\n[example](missing.md)\n```\n"
        "~~~~\n[[example]]\n~~~\n~~~~\n[real](missing.md)\n"
    )
    assert check_links(tmp_path, [source]) == [
        "index.md: missing public target missing.md"
    ]
