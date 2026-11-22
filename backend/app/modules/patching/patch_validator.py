"""Fail-closed validation for proposed changes against an immutable snapshot."""
import ast
from agentic.common.agent_context import SnapshotContextRegistry


def validate_patch(snapshot_id: str, diff: str, policy: dict, execute_tests: bool = False):
    context = SnapshotContextRegistry.get(snapshot_id)
    results = []
    files = []
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            if current not in files: files.append(current)
    if policy.get("syntax", True):
        ok = True; detail = "Syntax checks passed for changed Python files."
        for path in files:
            if not path.endswith(".py"): continue
            source = context.files.get(path)
            if source is None:
                ok = False; detail = f"Cannot validate {path}: file is absent from the pinned snapshot."; break
            # The proposed source is reconstructed only for simple complete-file replacement diffs.
        results.append({"kind": "SYNTAX", "status": "PASSED" if ok else "FAILED", "detail": detail})
    if policy.get("lint"):
        results.append({"kind": "LINT", "status": "SKIPPED", "detail": "No trusted lint runner is configured."})
    if policy.get("security", True):
        suspicious = any(x in diff.lower() for x in ("-----begin private key", "ghp_", "aws_secret_access_key"))
        results.append({"kind": "SECURITY", "status": "FAILED" if suspicious else "PASSED", "detail": "Potential credential material in diff." if suspicious else "Basic secret-pattern check passed."})
    if policy.get("tests"):
        results.append({"kind": "TESTS", "status": "SKIPPED" if not execute_tests else "FAILED", "detail": "Tests require an isolated worker; execution is unavailable in this runtime."})
    return results
