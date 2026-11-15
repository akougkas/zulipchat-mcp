"""Preflight package exports before replacing any destination files."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable, Mapping
from pathlib import Path

Merger = Callable[[str, str], str]


def write_package(
    output_dir: str | Path,
    documents: Mapping[str, str],
    *,
    force: bool = False,
    mergers: Mapping[str, Merger] | None = None,
) -> list[dict[str, str]]:
    """Validate all conflicts and boundaries before writing; reject symlinks.

    Each replacement is atomic. A filesystem failure during writing can still
    leave a partially written package, so this is not a multi-file transaction.

    A replaced file keeps its mode, and new files get the usual default mode.
    A merged file is the host's own configuration, re-serialized without its
    comments, so it is first copied beside itself as `<name>.bak-<time>`.
    """
    root = Path(output_dir).absolute()
    plans: list[tuple[Path, str, str]] = []
    for relative, incoming in documents.items():
        fragment = Path(relative)
        if fragment.is_absolute() or ".." in fragment.parts:
            raise ValueError(
                f"Package path must stay inside the output directory: {relative}"
            )
        path = root / fragment
        for component in (path, *path.parents):
            if component.is_symlink():
                raise ValueError(f"Refusing to export through a symlink: {component}")
        content = incoming
        action = "written"
        if path.exists():
            if not path.is_file():
                raise ValueError(f"Export destination is not a regular file: {path}")
            current = path.read_text(encoding="utf-8")
            merger = (mergers or {}).get(relative)
            if merger:
                content = merger(current, incoming)
                action = "merged"
            elif current != incoming and not force:
                raise FileExistsError(
                    f"{path} already exists; use --force to replace it"
                )
            if content == current:
                action = "unchanged"
        plans.append((path, content, action))

    umask = os.umask(0)
    os.umask(umask)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    results = []
    for path, content, action in plans:
        result = {"path": str(path), "action": action}
        if action != "unchanged":
            # The plan was checked earlier; a link swapped in since is refused.
            for component in (path, *path.parents):
                if component.is_symlink():
                    raise ValueError(
                        f"Refusing to export through a symlink: {component}"
                    )
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = 0o666 & ~umask
            if path.exists():
                mode = path.stat().st_mode & 0o777
            if action == "merged":
                backup = path.with_name(f"{path.name}.bak-{stamp}")
                backup.write_bytes(path.read_bytes())
                os.chmod(backup, mode)
                result["backup"] = str(backup)
            descriptor, temporary = tempfile.mkstemp(
                prefix=f".{path.name}.", dir=path.parent
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                    handle.write(content)
                os.chmod(temporary, mode)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        results.append(result)
    return results
