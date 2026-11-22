"""Patch Core: diff integrity, file allowlists, edit invalidation and approval lifecycle."""
import hashlib
import re
import threading
from collections import OrderedDict
from typing import Dict, List
from shared.types.patch import PatchArtifact, PatchFile

_HEADER = re.compile(r"^(--- a/|\+\+\+ b/)(.+)$")


def sha256_diff(diff: str) -> str:
    return hashlib.sha256(diff.encode("utf-8")).hexdigest()


def inspect_diff(diff: str, allowed_paths: List[str] | None = None) -> List[PatchFile]:
    if not diff or "\x00" in diff or len(diff) > 2_000_000:
        raise ValueError("Diff is empty, malformed, or exceeds the 2 MB limit")
    files: Dict[str, dict] = {}
    current = None
    for line in diff.splitlines():
        if line.startswith(("--- ", "+++ ")):
            m = _HEADER.match(line)
            if not m:
                continue
            path = m.group(2).strip()
            if path == "/dev/null":
                continue
            path = path.replace("\\", "/")
            if path.startswith("/") or any(p in (".", "..") for p in path.split("/")) or ":" in path:
                raise ValueError("Patch contains an unsafe path")
            if path.startswith((".git/", ".github/workflows/")):
                raise ValueError("Patch targets a protected repository path")
            if allowed_paths and not any(path == p or path.startswith(p.rstrip("*").rstrip("/") + "/") for p in allowed_paths):
                raise ValueError(f"Patch path is outside the allowed target set: {path}")
            current = files.setdefault(path, {"old": False, "new": False, "add": 0, "del": 0})
            current["old" if line.startswith("---") else "new"] = True
        elif current is not None and not line.startswith(("+++", "---", "\\")):
            if line.startswith("+"): current["add"] += 1
            elif line.startswith("-"): current["del"] += 1
    if not files:
        raise ValueError("Diff contains no file changes")
    if len(files) > 20:
        raise ValueError("A fix may change at most 20 files")
    out = []
    for path, data in files.items():
        change = "ADDED" if not data["old"] else "DELETED" if not data["new"] else "MODIFIED"
        out.append(PatchFile(path=path, change_type=change, additions=data["add"], deletions=data["del"]))
    return out


class PatchManager:
    _instance = None
    _guard = threading.Lock()

    def __init__(self):
        self._items: OrderedDict[str, PatchArtifact] = OrderedDict()
        self._lock = threading.RLock()

    @classmethod
    def instance(cls):
        with cls._guard:
            if cls._instance is None: cls._instance = cls()
            return cls._instance

    def create(self, patch: PatchArtifact) -> PatchArtifact:
        with self._lock: self._items[patch.id] = patch
        return patch

    def get(self, patch_id: str):
        with self._lock: return self._items.get(patch_id)

    def edit(self, patch_id: str, diff: str, rationale: str | None = None):
        with self._lock:
            p = self._require(patch_id)
            if p.status in ("REJECTED", "EXPORTED"): raise ValueError("Patch is no longer editable")
            p.unified_diff = diff; p.diff_sha256 = sha256_diff(diff); p.files = inspect_diff(diff)
            if rationale is not None: p.rationale = rationale
            p.validation.clear(); p.approvals.clear(); p.status = "DRAFT"; p.version += 1
            return p

    def approve(self, patch_id: str, expected_hash: str, approver_id: str):
        with self._lock:
            p = self._require(patch_id)
            if sha256_diff(p.unified_diff) != p.diff_sha256 or expected_hash != p.diff_sha256:
                raise ValueError("DIFF_HASH_MISMATCH")
            if not p.validation or any(v.get("status") not in ("PASSED", "SKIPPED") for v in p.validation):
                raise ValueError("PATCH_NOT_VALIDATED")
            from shared.types.patch import PatchApproval
            a = PatchApproval(diff_sha256=p.diff_sha256, approver_id=approver_id)
            p.approvals = [a]; p.status = "APPROVED"; return p

    def _require(self, patch_id):
        p = self._items.get(patch_id)
        if p is None: raise KeyError(patch_id)
        return p
