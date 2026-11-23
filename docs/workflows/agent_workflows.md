# CodePilot Agent Workflows

## Mastermind Feature 2 (M2): AI Bug Investigation Workflow

The AI Bug Investigation workflow investigates reported bugs by parsing multi-language stack traces, sanitizing secrets, performing longest-suffix file mapping, traversing the call path graph, formulating ranked root-cause hypotheses backed by cryptographic evidence references, and executing approved reproduction diagnostics in an isolated sandbox.

```mermaid
flowchart TD
    A["User / Client (POST /debug/investigations)"] --> B["Secret Redaction Engine (AUD-11)"]
    B --> C["Multi-Language Stack Trace Parser"]
    C --> D["Longest-Suffix Path Mapper & Ambiguity Detection"]
    D --> E["Call Path & Code Graph Tracer"]
    E --> F["Hypothesis Engine & Evidence Linker"]
    F --> G["Persist Investigation (hypotheses: UNCONFIRMED)"]
    G --> H["Client Response (201 Created / Report)"]
    H --> I["User Opt-In Approval (POST /debug/investigations/{id}/diagnostics)"]
    I --> J{"EXECUTE Gate: Consent Granted?"}
    J -- No --> K["403 Forbidden (Execution Blocked)"]
    J -- Yes --> L["Diagnostic Sandbox Runner (60s timeout, No Network)"]
    L --> M{"Bug Reproduced?"}
    M -- Yes --> N["reproduction_status: REPRODUCED<br/>Hypothesis Status: REPRODUCED"]
    M -- No --> O["reproduction_status: NOT_REPRODUCED<br/>Hypothesis Status: REFUTED / UNCONFIRMED"]
```

### Core Architecture Components

1. **Secret Redaction Engine (`ai_service/security_analysis/secret_detector.py`)**:
   - Scrubs API keys (OpenAI, Anthropic, GitHub, Google, AWS, Slack), JWTs, Bearer tokens, private keys, database connection strings, and sensitive environment variables before storage (`stack_trace_redacted`) or prompt dispatch (AUD-11 compliance).

2. **Multi-Language Stack Trace Parser (`ai_service/debugging/stack_trace_parser.py`)**:
   - Parses Python tracebacks, Node/V8 stack traces, Java stack traces, and Go panics.
   - Normalizes file paths (SEC-API-06, UT-05) and performs **longest-suffix matching** against snapshot repository files.
   - Ambiguous suffix matches are flagged and recorded as candidates rather than arbitrarily guessed.

3. **Call Path & Code Graph Tracer (`ai_service/debugging/call_path_tracer.py`)**:
   - Reconstructs end-to-end execution flow: Entrypoint -> Intermediate Callers -> Failure Site.
   - Extracts source code snippets with exact line bounds and calculates cryptographic SHA256 snippet hashes.

4. **Root-Cause Hypothesis Engine (`ai_service/debugging/hypothesis_engine.py`)**:
   - Generates ranked root cause hypotheses (Hit@1 and Hit@3 precision on AI-11 benchmark).
   - Links supporting and contradicting evidence references (`evidence_refs` with `owner_type='HYPOTHESIS'`).
   - Enforces the invariant: **status stays `UNCONFIRMED` until a reproduction diagnostic validates it**.

5. **Diagnostic Sandbox Runner & EXECUTE Gate (`sandbox/runner/diagnostic_sandbox.py`)**:
   - Enforces the **EXECUTE opt-in gate**: sandbox execution requires explicit user authorization.
   - Runs reproduction tests under strict limits: 60s hard timeout, 2GB memory cap, no network egress.
   - Updates `reproduction_status` and hypothesis status upon test completion.

---

## Mastermind Feature 3 (M3): Code Improvement Suggestions Workflow

The Code Improvement Suggestions workflow analyzes repository snapshots to discover actionable, evidence-backed improvements across Performance, Maintainability, Readability, Architecture, and Code Quality. It evaluates concrete refactorings with before/after diffs, explains trade-offs, computes multidimensional priority scores, enforces prompt-injection boundaries, supports 24-hour idempotent execution, provides optimistic-locking triage (accept/dismiss), and hands off approved suggestions directly to M4 AI-assisted code fixes.

```mermaid
flowchart TD
    A["User / Client (POST /improvements/analyze)"] --> B{"Idempotency-Key Header Present?"}
    B -- No --> C["422 Validation Failed (Missing Key)"]
    B -- Yes --> D{"Key Exists in Idempotency Store?"}
    D -- Same Hash --> E["Return Cached Report (201 Created / Idempotent-Replayed: true)"]
    D -- Diff Hash --> F["409 Conflict (IDEMPOTENCY_CONFLICT)"]
    D -- New Key --> G["Validate Pinned Snapshot Context (Invariant I1)"]
    G --> H["Retrieve Active Suppressions (Repository Scoped)"]
    H --> I["Refactoring Analyzer & Smell Detection"]
    I --> J["Cryptographic Evidence Extraction & Hash Verification (Invariant I5)"]
    J --> K["Secret Redaction (AUD-11) & Nonce-Delimited Prompt Defense (SEC-PI)"]
    K --> L["Suppressions Filter (Drop matching rule / path_glob)"]
    L --> M["Recommendation Ranker: Impact * Confidence / (Effort * Risk)"]
    M --> N["Deduplication (Collapse duplicate spans)"]
    N --> O["Persist Suggestions & Analysis Run in ImprovementRepository"]
    O --> P["Client Response (201 Created / ImprovementReportResponse)"]
    P --> Q["User Triage (PATCH /improvements/suggestions/{id})"]
    Q --> R{"Optimistic Lock: Version Match?"}
    R -- No --> S["409 Conflict (Concurrent Stale Edit)"]
    R -- Yes --> T["Update Status (ACCEPTED / DISMISSED) & Version++"]
    T --> U["Hand-Off to Fixes (POST /fixes with suggestion_id)"]
    U --> V["Synthesize Diff & Generate Reviewable Patch (M4 Pipeline)"]
```

### Core Architecture Components

1. **Refactoring Analyzer (`ai_service/improvements/refactoring_analyzer.py`)**:
   - Synthesizes before/after refactorings for quadratic loop string concatenation, linear searches on lists, high cyclomatic complexity, deeply nested conditionals, long functions, unclosed file descriptors, bare `except:` clauses, dead code, and boolean simplification.

2. **Recommendation Ranker (`ai_service/improvements/recommendation_ranker.py`)**:
   - Scores recommendations using multidimensional impact and confidence weights penalized by effort and risk factors:
     $$\text{PriorityScore} = \text{round}\left(\frac{\text{Impact} \times \text{Confidence}}{\text{Effort} \times \text{Risk}} \times 10, 2\right)$$
   - Sorts suggestions in descending order of priority score and deduplicates redundant overlapping spans.

3. **Suggestion Engine & Injection Defense (`ai_service/improvements/suggestion_engine.py`)**:
   - Enforces SEC-PI-01 through SEC-PI-08: wraps repository content in random nonce-delimited blocks (`<EVIDENCE_{nonce}>`), respects system prompt supremacy, sanitizes `@`-mentions, and scrubs secrets using `redact_secrets` (AUD-11).
   - Generates polymorphic `EvidenceRef` with SHA256 snippet hashes ensuring citation integrity (Invariant I5).
   - Evaluates active repository suppressions to respect human overrides.

4. **Improvement Repository (`backend/app/repositories/improvement_repository.py`)**:
   - Thread-safe repository managing suggestion records, reports, unified `analysis_runs` synchronization, and 24-hour idempotency replay state.
   - Enforces optimistic concurrency control (`version` integer) on suggestion edits to prevent lost updates.

5. **Fixes Hand-Off Integration (`backend/app/api/v1/fixes.py`)**:
   - Integrates M3 with M4: allows `POST /fixes` to take `suggestion_id`, auto-synthesizing the unified diff from the suggestion's before/after code blocks.


---

## Mastermind Feature 5 (M5): Unit Test Generation Workflow

The Unit Test Generation workflow synthesizes meaningful, non-vacuous unit tests for selected functions, classes, or modules by analyzing actual AST implementation logic, mapping repository test conventions via `TESTS` graph edges, isolating external dependencies with mock fixtures, verifying assertion quality (rejecting tautological/vacuous asserts), executing candidate tests under the hardened sandbox EXECUTE gate with two-phase dependency preparation, calculating before/after/delta coverage metrics, and seamlessly exporting test patches into M4 Patch Core.

```mermaid
flowchart TD
    A["User / Client (POST /tests/generate)"] --> B["Validate Pinned Snapshot Context (Invariant I1)"]
    B --> C["Test Discovery Service: Map TESTS Edges & Framework"]
    C --> D["AST Signature & Control Flow Analyzer"]
    D --> E["Test Synthesizer: Happy Paths, Edge Cases, Error Cases"]
    E --> F["Mock & Fixture Synthesizer (Isolate DB/Network)"]
    F --> G["Quality Check: Vacuous Assertion Detector (Master §14.3)"]
    G --> H["Persist Test Artifact & Analysis Run (TEST_GEN)"]
    H --> I["Client Response (201 Created / Report)"]
    I --> J["User Sandbox Execution (POST /tests/{run_id}/execute)"]
    J --> K{"EXECUTE Gate: Consent Granted?"}
    K -- No --> L["403 Forbidden (EXECUTE_OPT_IN_REQUIRED)"]
    K -- Yes --> M{"Two-Phase Install: install_scripts?"}
    M -- True --> N["Risk Flag: HIGH_RISK"]
    M -- False --> O["Standard Sandbox Profile (S1)"]
    N --> P["Sandboxed Test Execution (60s timeout, No Network, 2GB RAM)"]
    O --> P
    P --> Q["Secret Redaction Engine on Output (AUD-11)"]
    Q --> R["Coverage Analyzer: Compute Before/After/Delta Line Coverage"]
    R --> S["Update Artifact Validation Status (VALIDATED / FAILED)"]
    S --> T["Patch Export Hand-Off (POST /tests/{run_id}/export)"]
    T --> U["Unified Diff Creation & Binding to diff_sha256 in M4 Patch Core"]
```

### Core Architecture Components

1. **AST & Control Flow Analyzer (`ai_service/generation/test_generator.py`)**:
   - Parses target files with AST, extracting function/method signatures, parameter type annotations, return types, docstrings, branches, and raised exception types.
   - Infers boundary values (None, empty string/list/dict, 0, negative values) and custom target edge cases.

2. **Vacuous Assertion Quality Guard (`ai_service/generation/test_generator.py`)**:
   - Enforces Master Architecture Specification §14.3: analyzes generated test AST to prevent trivial or tautological asserts (`assert True`, `assert 1 == 1`, `assert x == x`) and confirms target functions are genuinely exercised.

3. **Test Discovery & Graph Mapping (`backend/app/modules/testing/test_discovery.py`)**:
   - Locates existing test files and frameworks (`pytest`, `unittest`, `jest`, `vitest`).
   - Maps `TESTS` graph edges between target symbols and existing test suites with confidence ratings (`HIGH`, `MEDIUM`, `LOW`).

4. **Sandboxed Test Runner & EXECUTE Gate (`backend/app/modules/testing/test_execution.py`)**:
   - Strictly enforces the **EXECUTE opt-in gate**: sandbox execution without `consent: {"execute": true}` returns `403 Forbidden` (`EXECUTE_OPT_IN_REQUIRED`).
   - Implements two-phase dependency preparation (Master §14.2): `install_scripts: true` marks the run as `HIGH_RISK`.
   - Isolates execution: 60s hard timeout, 2048 MB memory limit, zero network egress, and secret redaction (AUD-11) on stdout/stderr.

5. **Coverage Delta Analyzer (`backend/app/modules/testing/coverage_analyzer.py`)**:
   - Computes baseline statement coverage before tests and post-generation coverage, outputting `before`, `after`, and `delta` JSONB reports with newly covered lines.

6. **M4 Patch Core Integration (`backend/app/modules/testing/test_manager.py`)**:
   - `POST /tests/{run_id}/export` compiles the generated test suite into a unified diff bound to `diff_sha256`, registering it directly into `PatchManager` for code review, approval, and application.

---

## Mastermind Feature 7 (M7): Pull Request Reviews Workflow

The Pull Request Reviews workflow provides end-to-end automated analysis, blast radius calculation, and actionable inline review comment generation for incoming GitHub pull requests. It ingests GitHub webhooks, verifies HMAC-SHA256 signatures with dual-secret rotation, deduplicates deliveries, parses unified diffs, maps changed lines to AST symbols, conducts graph-based blast radius impact analysis, executes multi-scanner checks (bugs, code smells, zero-raw-secret detection), enforces strict line anchor verification (AI-16: comments without valid anchors on changed lines are discarded), supports human review triage (edit/discard), and enforces the Dangerous Operation Register publish gate with immutable audit logging.

```mermaid
flowchart TD
    A["GitHub Webhook (POST /github/webhooks)"] --> B{"HMAC-SHA256 Valid? (Dual-Secret)"}
    B -- No --> C["401 Unauthorized (WEBHOOK_SIGNATURE_INVALID)"]
    B -- Yes --> D{"Delivery ID Exists in Deliveries?"}
    D -- Duplicate --> E["200 OK (REPLAY Idempotent Ack)"]
    D -- New Delivery --> F["202 Accepted (Fast <500ms ack)"]
    F --> G["Parse PR & Event Routing (opened / synchronize / closed)"]
    G --> H["Client Review Request (POST /pull-requests/{id}/review-runs)"]
    H --> I{"Head SHA Matches PR? (Force-Push Guard)"}
    I -- No --> J["409 Conflict (PR_HEAD_CHANGED) & Invalidate Stale Runs"]
    I -- Yes --> K["Diff Hunk Parser & Added-Line Extraction"]
    K --> L["AST Symbol Mapping & Call Graph Impact Analysis"]
    L --> M["Multi-Scanner Execution: Bug, Smell, Secret Detection"]
    M --> N{"Line Anchor Guard (AI-16): Line in Changed Lines?"}
    N -- No --> O["Discard Finding (Prevent unanchored comment)"]
    N -- Yes --> P["Generate Grounded Review Comment (DRAFT + Cryptographic Evidence)"]
    P --> Q["Synthesize Executive Summary & Persist Review Run"]
    Q --> R["Draft Review Inspection (GET /pull-requests/{id}/reviews/{run_id})"]
    R --> S["Human Review Triage (PATCH .../comments/{comment_id}: EDITED / DISCARDED)"]
    S --> T["Publish Request (POST .../publish)"]
    T --> U{"Dangerous Operation Gate: Consent / Approval?"}
    U -- No --> V["403 Forbidden (PUBLISH_APPROVAL_REQUIRED)"]
    U -- Yes --> W["Skip DISCARDED Comments, Publish Active to GitHub"]
    W --> X["Record Immutable Audit Event (SEC-AUD-02) & Return 202"]
```

### Core Architecture Components

1. **GitHub Webhook Handler (`backend/app/modules/github/webhook_handler.py`)**:
   - Constant-time HMAC-SHA256 verification supporting primary and previous secrets for seamless 180-day rotation without downtime (`SEC-API-28`, `SEC-API-30`).
   - Conforms strictly to GitHub documentation test vector: secret `It's a Secret to Everybody`, body `Hello, World!` -> `sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17`.
   - Replay deduplication via `X-GitHub-Delivery` in `webhook_deliveries` returning `200 OK`.
   - Enforces a 26 MB body payload limit (`MAX_WEBHOOK_BODY_BYTES`).
   - Fork PR isolation: marks external forks read-only with zero access to internal repository secrets.

2. **PR Diff Analyzer (`backend/app/modules/pull_requests/diff_analyzer.py`)**:
   - Parses unified diff hunks, tracks additions and deletions, and computes exact 1-based modified line numbers in the head commit.
   - Maps modified lines directly to AST function and class symbols in the repository snapshot.

3. **Blast Radius & Impact Analyzer (`agentic/workflows/pull_request_review.py`)**:
   - Traverses the code graph in the head snapshot context (`CALLS`, `IMPORTS`, `DEPENDS_ON`, `TESTS`).
   - Identifies all dependent modules impacted by the changes and selects test suites that exercise modified code.

4. **Multi-Scanner Review Engine & AI-16 Line Anchor Verification**:
   - Coordinates AST bug detection (`BugDetector`), code quality smell detection (`CodeSmellDetector`), and secret scanning (`SecretScanner`).
   - Zero Raw Secrets Invariant (`I9` / `SEC-SECRET-01`): secrets are never logged or stored in plaintext; only SHA256 fingerprints are cited.
   - Line Anchor Verification (`AI-16` / `V6 Claim Support Check`): only findings that anchor directly to changed or added lines in the diff are retained as inline review comments; comments on unchanged code are discarded, guaranteeing 100% anchor validity.

5. **Comment Triage & Lifecycle (`backend/app/modules/pull_requests/review_manager.py`)**:
   - Generates comments in `DRAFT` status with cryptographic `FindingEvidence` and suggested code remediations.
   - Allows human reviewers to revise comment text (`EDITED`) or discard comments (`DISCARDED`) via `PATCH /pull-requests/{id}/reviews/{run_id}/comments/{comment_id}`.

6. **Dangerous Operation Register & Publisher (`backend/app/modules/pull_requests/publisher.py`)**:
   - Enforces the dangerous operation publication gate: publishing comments to GitHub requires explicit approval (`publish_approval_id`) or `OWNER` authorization.
   - Discarded comments are skipped; active comments are transitioned to `PUBLISHED` and assigned `github_comment_id`.
   - Writes immutable records to `pr_audit_events` with actor type, resource, action, and outcome metadata per `SEC-AUD-02` and `SEC-AUD-10`.

