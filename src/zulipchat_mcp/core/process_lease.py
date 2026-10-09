"""Local OS ownership for a persisted event producer, released on process exit."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import TracebackType


class ProcessLease:
    """Hold one exclusive advisory lock; never delete or replace its inode."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fd: int | None = None

    def __enter__(self) -> ProcessLease:
        if self.path.is_symlink():
            raise ValueError("Event producer lock must not be a symlink")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            os.chmod(self.path, 0o600)
            if sys.platform == "win32":
                import msvcrt

                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"\0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(fd)
            raise RuntimeError(
                "INBOX_ALREADY_OWNED: another local process owns this mention "
                "inbox; connect hosts to the existing MCP server"
            ) from error
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
