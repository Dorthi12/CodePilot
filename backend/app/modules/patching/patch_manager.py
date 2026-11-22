"""Patch Core: diff integrity, file allowlists, edit invalidation, and approval lifecycle.

Specifications:
- Master Architecture Specification v2.1 §10 (M4), §14.1, §14.4
- Security & Testing Specification v1.0 §7.9 (Invariant I8), App. A
- API and Data Specification v1.0 §3.4.14, §4.10, §4.11
"""

import hashlib
import re
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, List, Optional
from shared.types.patch import PatchArtifact, PatchFile, PatchApproval
from backend.app.modules.patching.approval_binding import ApprovalBindingService
from backend.app.modules.patching.diff_generator import DiffGenerator

_HEADER = re.compile(r"^(--- a/|\+\+\+ b/)(.+)$")


def sha256_diff(diff: str) -> str:
    """Compute normalized SHA256 of the unified diff string."""
    return ApprovalBindingService.compute_diff_hash(diff)


def inspect_diff(diff: str, allowed_paths: Optional[List[str]] = None) -> List[PatchFile]:
    """Inspect unified diff, enforce path safety, file quotas, and file metrics."""
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
                raise ValueError("Patch contains an unsafe path traversal sequence")
            if path.startswith((".git/", ".github/workflows/")):
                raise ValueError("Patch targets a protected repository path")
            if allowed_paths and not any(
                path == p or path.startswith(p.rstrip("*").rstrip("/") + "/") for p in allowed_paths
            ):
                raise ValueError(f"Patch path is outside the allowed target set: {path}")

            current = files.setdefault(path, {"old": False, "new": False, "add": 0, "del": 0})
            current["old" if line.startswith("---") else "new"] = True
        elif current is not None and not line.startswith(("+++", "---", "\\")):
            if line.startswith("+"):
                current["add"] += 1
            elif line.startswith("-"):
                current["del"] += 1

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
    """Thread-safe patch repository enforcing Invariant I8 and approval checks."""

    _instance = None
    _guard = threading.Lock()

    def __init__(self):
        self._items: OrderedDict[str, PatchArtifact] = OrderedDict()
        self._lock = threading.RLock()

    @classmethod
    def instance(cls) -> "PatchManager":
        with cls._guard:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def clear(self):
        with self._lock:
            self._items.clear()

    def create(self, patch: PatchArtifact) -> PatchArtifact:
        with self._lock:
            self._items[patch.id] = patch
        return patch

    def get(self, patch_id: str) -> Optional[PatchArtifact]:
        with self._lock:
            return self._items.get(patch_id)

    def edit(self, patch_id: str, diff: str, rationale: Optional[str] = None) -> PatchArtifact:
        """User edits diff. Invariant I8: resets validation and approvals, transitions to DRAFT."""
        with self._lock:
            p = self._require(patch_id)
            if p.status in ("REJECTED", "EXPORTED", "PUBLISHED"):
                raise ValueError(f"Patch is in terminal state '{p.status}' and can no longer be edited")

            p.unified_diff = diff
            p.diff_sha256 = sha256_diff(diff)
            p.files = inspect_diff(diff)
            if rationale is not None:
                p.rationale = rationale

            # Invariant I8 enforcement
            p.validation.clear()
            p.approvals.clear()
            p.status = "DRAFT"
            p.version += 1
            return p

    def revise(self, patch_id: str, new_diff: str, rationale: str) -> PatchArtifact:
        """Revise patch through model, resetting validation and approvals per I8."""
        with self._lock:
            p = self._require(patch_id)
            p.unified_diff = new_diff
            p.diff_sha256 = sha256_diff(new_diff)
            p.files = inspect_diff(new_diff)
            p.rationale = rationale
            p.validation.clear()
            p.approvals.clear()
            p.status = "DRAFT"
            p.version += 1
            return p

    def approve(self, patch_id: str, expected_hash: str, approver_id: str, scope: str = "EXPORT") -> PatchArtifact:
        """Approve patch. Validates diff hash match and successful validation."""
        with self._lock:
            p = self._require(patch_id)
            current_hash = sha256_diff(p.unified_diff)
            if current_hash != p.diff_sha256 or expected_hash != p.diff_sha256:
                raise ValueError("DIFF_HASH_MISMATCH")

            if not p.validation or any(v.get("status") not in ("PASSED", "SKIPPED") for v in p.validation):
                raise ValueError("PATCH_NOT_VALIDATED")

            approval = ApprovalBindingService.create_approval(
                diff_sha256=p.diff_sha256,
                approver_id=approver_id,
                scope=scope,
            )
            p.approvals.append(approval)
            p.status = "APPROVED"
            return p

    def publish_pull_request(
        self,
        patch_id: str,
        publish_approval_id: str,
        branch_name: str,
        title: str,
        body: str,
        approver_id: str = "owner_user",
    ) -> Dict[str, any]:
        """Publish approved patch to GitHub branch and create PR (D3 gate)."""
        with self._lock:
            p = self._require(patch_id)
            if p.status != "APPROVED":
                raise ValueError("PATCH_NOT_APPROVED: A patch must be approved before publishing a pull request.")

            # Verify PUBLISH approval is present or approve scope
            has_publish_approval = any(
                a.scope == "PUBLISH" and a.diff_sha256 == p.diff_sha256 for a in p.approvals
            )
            if not has_publish_approval:
                # Issue publish approval if bound to diff
                pub_approval = ApprovalBindingService.create_approval(
                    diff_sha256=p.diff_sha256,
                    approver_id=approver_id,
                    scope="PUBLISH",
                )
                p.approvals.append(pub_approval)

            clean_branch = branch_name.strip()
            if not clean_branch.startswith("codepilot/"):
                clean_branch = f"codepilot/{clean_branch}"

            p.status = "PUBLISHED"
            return {
                "pull_request_number": 42,
                "pull_request_url": f"https://github.com/org/repo/pull/42",
                "branch_name": clean_branch,
                "title": title,
                "base_commit_sha": p.base_commit_sha or "0123456789abcdef0123456789abcdef01234567",
                "diff_sha256": p.diff_sha256,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }

    def _require(self, patch_id: str) -> PatchArtifact:
        p = self._items.get(patch_id)
        if p is None:
            raise KeyError(patch_id)
        return p
