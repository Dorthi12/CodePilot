# Sandbox Security Architecture

## Diagnostic Execution & Sandboxing Controls (M2 / M5)

In CodePilot, running untrusted or dynamic code (e.g. reproducing a reported bug or executing candidate tests) is strictly isolated within ephemeral sandbox environments.

### 1. EXECUTE Opt-In Gate
- In accordance with Master Architecture Specification §13.3 and §14.2, and API Specification §1.5, **no code or test execution may occur without explicit human consent**.
- Endpoints requiring EXECUTE opt-in:
  - `POST /debug/investigations/{id}/diagnostics`
  - `POST /tests/{run_id}/execute`
  - `POST /fixes/{id}/validate` (test step)
- Invoking execution without `consent: {"execute": true}` returns `403 Forbidden` with error code `EXECUTE_OPT_IN_REQUIRED`.

### 2. Hardened Sandbox Environment Limits
- **Network Isolation:** No network egress (`network: "NONE"`).
- **Execution Timeout:** 60-second hard timeout per job.
- **Compute Constraints:** 2 vCPUs, 2048 MB RAM cap.
- **Filesystem Isolation:** Ephemeral, read-only root mount with temporary scratch workspace.
- **Zero Production Access:** No access to production databases, secrets, or internal service meshes.
