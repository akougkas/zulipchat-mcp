"""Dependency-light access to the immutable skills shipped inside the wheel."""

from importlib.resources import files


def skill_files() -> dict[str, str]:
    """Load only bundled documents; never scan user directories."""
    root = files("zulipchat_mcp").joinpath("skills")
    return {
        f"{entry.name}/SKILL.md": entry.joinpath("SKILL.md").read_text(encoding="utf-8")
        for entry in sorted(root.iterdir(), key=lambda item: item.name)
        if entry.is_dir() and entry.joinpath("SKILL.md").is_file()
    }
