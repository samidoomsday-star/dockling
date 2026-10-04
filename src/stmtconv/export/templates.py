"""Shared factual text templates, with bounded explicit placeholders."""

from pathlib import Path

from stmtconv.errors import StmtconvError


def render(name: str, values: dict[str, object]) -> str:
    bundled = Path(__file__).resolve().parents[1] / "_templates"
    local = Path.cwd() / "templates"
    directory = (
        local
        if (local / name).is_file()
        else bundled
        if bundled.is_dir()
        else Path(__file__).resolve().parents[3] / "templates"
    )
    try:
        return (directory / name).read_text(encoding="utf-8").format_map(values)
    except (OSError, ValueError, KeyError) as exc:
        raise StmtconvError(
            "TEMPLATE_INVALID", "A required text template is missing or invalid."
        ) from exc
