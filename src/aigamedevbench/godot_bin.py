from __future__ import annotations

import re
import shutil

# An MSYS/Git-Bash path like /d/Godot/godot/bin/godot names drive D: but Windows'
# shutil.which cannot resolve it (and won't append .exe). Match a single-letter
# first segment so /usr/bin/... (a real POSIX path) is left alone.
_MSYS_DRIVE_RE = re.compile(r"^/([A-Za-z])(/.*)$")


def _msys_to_native(binary: str) -> str | None:
    """Convert an MSYS drive path (/d/foo) to native form (d:/foo), else None."""
    m = _MSYS_DRIVE_RE.match(binary)
    if m is None:
        return None
    return f"{m.group(1)}:{m.group(2)}"


def resolve_godot_binary(binary: str) -> str | None:
    """Resolve a Godot binary to a runnable path, or None if not found.

    Tries shutil.which directly (covers bare PATH names and native paths), then
    retries with an MSYS /d/... path rewritten to native d:/... form. On Windows
    a Git-Bash-style path slips past which() unresolved, so without this retry the
    harness silently skips its import/L0 godot passes and the runtime verifier
    later fails with a misleading 'import cache incomplete'.
    """
    hit = shutil.which(binary)
    if hit is not None:
        return hit
    native = _msys_to_native(binary)
    if native is not None:
        return shutil.which(native)
    return None
