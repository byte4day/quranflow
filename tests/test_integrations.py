from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_skill_is_discoverable_with_valid_required_frontmatter() -> None:
    skill = ROOT / ".agents/skills/play-quran/SKILL.md"
    parts = skill.read_text(encoding="utf-8").split("---", 2)
    assert len(parts) == 3 and not parts[0].strip()
    frontmatter = dict(line.split(":", 1) for line in parts[1].splitlines() if ":" in line)
    assert frontmatter["name"].strip() == "play-quran"
    assert frontmatter["description"].strip()
    assert (skill.parent / "scripts/play_quran.py").is_file()


def test_cursor_adapter_and_install_entrypoints_are_packaged() -> None:
    assert (ROOT / ".cursor/commands/play-quran.md").is_file()
    for filename in ("install.sh", "uninstall.sh"):
        script = ROOT / filename
        assert script.is_file()
        assert script.stat().st_mode & 0o111
