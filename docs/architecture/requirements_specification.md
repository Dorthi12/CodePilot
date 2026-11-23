# CodePilot – Complete System Requirements Specification (SRS)

**Project:** CodePilot – The Knowledge of Athena  
**Document:** System Requirements Specification (SRS)  
**Version:** 1.0  
**Status:** Approved Engineering Baseline  
**Architecture:** Modular Monolith + Independently Scalable Workers  

---

## 1. Executive Summary & Purpose

CodePilot is an enterprise-grade AI software intelligence platform designed to ingest, understand, explore, reason about, and autonomously improve complex codebases. It bridges deterministic AST/graph analysis with multi-agent intelligence and grounded semantic retrieval (RAG).

### 1.1 Core System Invariants
1. **Rule R1 (Data Authority):** PostgreSQL is the single source of truth. Nothing is ever written to Neo4j (graph) or FAISS (vector index) that is not already committed in PostgreSQL under the exact same `snapshot_id`.
2. **Snapshot Invariant:** Every index, search query, graph edge, file tree, and AI answer is pinned to an immutable snapshot defined by `(repository_id, commit_sha, analysis_profile, ingestion_version)`.
3. **Publish Gate:** A snapshot is completely invisible to feature APIs until verified and published atomically. Incomplete or drifting snapshots are blocked from publication.
4. **Three-Property Rule (Prompt Injection):** No agent execution step may combine (1) reading untrusted code, (2) accessing privileged credentials, and (3) possessing an external action or exfiltration channel.
5. **Human Approval Gate:** No code modification, git branch write, PR review publication, or unsafe code execution may occur without explicit, cryptographically-bound human authorization.

---

## 2. Functional Requirements (FR-01 to FR-21)

### Tier 1: Basic Capabilities (B1 – B7)

#### FR-01: GitHub Integration (B1)
- **FR-01.1:** System shall authenticate users via GitHub OAuth (user identity) and GitHub App (repository permissions).
- **FR-01.2:** System shall support 4 permission tiers: Tier 0 (Read Metadata), Tier 1 (Read Code), Tier 2 (Write Branches/PRs), Tier 3 (Admin & Webhooks).
- **FR-01.3:** System shall verify HMAC signatures on incoming GitHub webhooks (`push`, `pull_request`, `installation`) and process events idempotently.

#### FR-02: Repository Import & Ingestion (B2)
- **FR-02.1:** System shall clone or archive-fetch repositories at a specific commit SHA without executing repository hooks.
- **FR-02.2:** System shall enforce ingestion limits: exclude binaries, vendor directories, files exceeding 1 MB, and repositories exceeding 500,000 LOC without elevated quota.
- **FR-02.3:** System shall execute a multi-stage background ingestion pipeline: `FETCH` $\to$ `INVENTORY` $\to$ `PARSE` $\to$ `RESOLVE` $\to$ `CHUNK` $\to$ parallel(`GRAPH_BUILD`, `EMBED`) $\to$ `VERIFY` $\to$ `PUBLISH`.

#### FR-03: Codebase Explorer (B3)
- **FR-03.1:** System shall provide a paged, interactive directory file tree populated purely from PostgreSQL metadata.
- **FR-03.2:** System shall display source code in Monaco Editor with syntax highlighting, line numbers, and symbol markers.
- **FR-03.3:** System shall render an AST symbol panel outlining classes, methods, functions, and interfaces for the active file.

#### FR-04: Code Search (B4)
- **FR-04.1:** System shall support exact lexical search (trigram & BM25), AST symbol identifier search, and dense semantic search (FAISS).
- **FR-04.2:** System shall merge results using Reciprocal Rank Fusion (RRF) and score candidates with a cross-encoder reranker.

#### FR-05: File-Level Summaries (B5)
- **FR-05.1:** System shall generate concise, structured file summaries detailing architectural role, primary exports, dependencies, and responsibilities.
- **FR-05.2:** Summaries shall be deterministically cached in `embedding_cache` by `content_hash` to eliminate redundant LLM invocations.

#### FR-06: AI Code Explanation (B6)
- **FR-06.1:** System shall explain functions, classes, or code blocks in plain, technically rigorous developer prose.
- **FR-06.2:** All explanations must explicitly cite exact line spans from the pinned snapshot.

#### FR-07: Repository Management (B7)
- **FR-07.1:** System shall allow users to switch active branches, trigger incremental re-indexing, pin snapshots to prevent deletion, and review ingestion health.

---

### Tier 2: Advanced Capabilities (A1 – A7)

#### FR-08: Cross-File Relationships (A1)
- **FR-08.1:** System shall construct and query a Neo4j property graph capturing `CALLS`, `IMPORTS`, `EXTENDS`, and `REFERENCES` relationships.
- **FR-08.2:** Each edge shall maintain an extraction confidence flag (`RESOLVED`, `PROBABLE`, `UNRESOLVED`).

#### FR-09: Architecture Diagrams (A2)
- **FR-09.1:** System shall automatically infer software components and layer boundaries from directory structures and cross-module edges.
- **FR-09.2:** System shall render interactive diagrams via React Flow and support lossless export to SVG and Mermaid formats.

#### FR-10: Bug & Code Smell Detection (A3)
- **FR-10.1:** System shall execute deterministic static analyzers (Tree-sitter AST queries) supplemented by targeted LLM inspection.
- **FR-10.2:** Findings shall be classified by category (bug, smell, security), severity (low, medium, high, critical), and file span.

#### FR-11: Module Dependency Analysis (A4)
- **FR-11.1:** System shall compute afferent/efferent coupling metrics, instability scores, and detect circular dependencies ($A \to B \to C \to A$).

#### FR-12: Whole-Codebase Question Answering (A5)
- **FR-12.1:** System shall answer repository-wide architecture, logic, and implementation queries using hybrid RAG.
- **FR-12.2:** System shall explicitly abstain (`abstain: true`) if insufficient repository evidence is retrieved rather than hallucinating.

#### FR-13: Technical Documentation Generation (A6)
- **FR-13.1:** System shall synthesize comprehensive system overviews, module design docs, and OpenAPI endpoint specifications directly from code structures.

#### FR-14: Context-Aware Answers & Citation Validation (A7)
- **FR-14.1:** System shall maintain multi-turn conversational context, resolving ambiguous follow-ups against active repository entities.
- **FR-14.2:** System shall enforce the **V1–V6 Citation Validation Pipeline**: verify citations exist in snapshot, line spans are valid, hashes match stored source, and claimed symbols overlap cited lines.

---

### Tier 3: Mastermind Capabilities (M1 – M7)

#### FR-15: Multi-Agent Code Analysis (M1)
- **FR-15.1:** System shall orchestrate specialized autonomous agents (Architecture, Code Quality, Security, Performance) working concurrently with partitioned evidence.

#### FR-16: AI Bug Investigation (M2)
- **FR-16.1:** System shall investigate reported bugs by ingesting stack traces, formulating hypotheses, executing graph path traversals, and validating root causes.

#### FR-17: Code Improvement Suggestions (M3)
- **FR-17.1:** System shall identify refactoring opportunities, dead code, algorithmic bottlenecks, and provide before/after code diffs with explanatory rationales.

#### FR-18: AI-Assisted Code Fixes (M4)
- **FR-18.1:** System shall generate unified diff patches to resolve verified bugs or security vulnerabilities.
- **FR-18.2:** Patches must be validated in the isolated sandbox (syntax verification and test execution).
- **FR-18.3:** Applying a patch to a git branch requires explicit human approval bound to the patch `diff_hash`.

#### FR-19: Unit Test Generation (M5)
- **FR-19.1:** System shall synthesize test cases covering happy paths, edge cases, and regression triggers for targeted symbols.
- **FR-19.2:** Generated tests must be executed in the sandbox to verify they compile, execute, and pass without side effects.

#### FR-20: Security Vulnerability Detection (M6)
- **FR-20.1:** System shall scan for OWASP Top 10 vulnerabilities, leaked secrets/credentials, and vulnerable open-source dependencies (CVE audit).

#### FR-21: Pull Request Reviews (M7)
- **FR-21.1:** System shall analyze incoming GitHub PR diffs, evaluate architectural blast radius, assess risk, and generate draft review comments.
- **FR-21.2:** Publishing comments to GitHub requires human authorization.

---

## 3. Non-Functional Requirements (NFR-01 to NFR-10)

| ID | Category | Requirement Specification | Measurement Metric / Target |
|---|---|---|---|
| **NFR-01** | **Scalability** | Support 1,000 peak concurrent active users executing ~5 requests/min. | Total platform throughput $\ge 250$ req/s without degradation. |
| **NFR-02** | **Latency** | Maintain strict interactive latency budgets across user-facing paths. | Explorer tree: $<300\text{ ms}$; Hybrid search: $<800\text{ ms}$; Chat TTFT: $<2.5\text{ s}$. |
| **NFR-03** | **Consistency** | Cross-store integrity across PostgreSQL, Neo4j, FAISS, and Object Storage. | $100\%$ published snapshots must pass pre-publish verification checks. |
| **NFR-04** | **AI Accuracy** | Zero-tolerance for ungrounded claims; evidence citations strictly validated. | Citation validity $\ge 99\%$; Contradiction rate $<2\%$; Hallucination floor $<3\%$. |
| **NFR-05** | **Security & RBAC** | Strict tenant isolation in all stores; 7 human roles + 8 agent tool profiles. | 0 cross-tenant data leakage; zero unauthenticated API access. |
| **NFR-06** | **Sandbox Isolation** | Untrusted code executes in hardened, ephemeral containers. | gVisor/Firecracker, no network egress, 2 vCPU / 2 GB RAM / 60s hard timeout. |
| **NFR-07** | **Injection Defense** | Protect against malicious repositories, prompt injection, and indirect attacks. | Strict delimiter parsing, system prompt supremacy, zero agent combines 3 properties. |
| **NFR-08** | **Observability** | Full RED/USE metrics, distributed tracing across queues and LLMs, audit logging. | OpenTelemetry trace propagation; HMAC tamper-evident chained audit trail. |
| **NFR-09** | **Cost & Overload** | Token budgets per feature; graceful brownout shedding during overload. | Enforced token quotas; L0–L3 brownout protection preserves core explorer. |
| **NFR-10** | **Reliability** | Fault-tolerant worker recovery, transactional outbox, idempotent jobs. | API Availability $\ge 99.9\%$; zero duplicate jobs on worker crash. |

---

## 4. Security & Governance Architecture

### 4.1 RBAC Roles Matrix
1. **Anonymous:** Public metadata only.
2. **Authenticated User:** Personal profile, public repositories.
3. **Repo Reader:** Explorer, hybrid search, code summaries, code explanation, Q&A.
4. **Repo Contributor:** Request bug investigations, generate tests, generate draft fixes.
5. **Repo Maintainer:** Approve and apply patches, approve PR review publication, manage webhooks.
6. **Tenant Admin:** Manage tenant quotas, user roles, security policies, KMS keys.
7. **System Admin:** Platform infrastructure, worker autoscaling, global kill-switches.

### 4.2 Dangerous Operation Register
Any high-risk operation (`apply_patch`, `push_branch`, `publish_pr_review`, `execute_arbitrary_code`) requires:
- Approval record created in `approvals` table with unique `approval_id`.
- Cryptographic binding to `diff_hash` = $\text{SHA256}(\text{unified\_diff})$.
- Expiration window (default 24 hours).
- Automatic revocation if target commit moves.

---

## 5. Technology Stack & Verification Matrix

- **Frontend:** React 18, TypeScript, Vite, Monaco Editor, React Flow (`@xyflow/react`), Tailwind CSS, Zustand, TanStack Query.
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2 (asyncpg), Alembic, Celery, Redis.
- **AI Service:** Provider Abstraction (OpenAI, Anthropic, Gemini), Sentence-Transformers, FAISS-CPU, Rank-BM25, Tiktoken.
- **Agentic Engine:** Celery/Redis task dispatcher, NetworkX DAG scheduler, Docker SDK runner, Unidiff.
- **Databases:** PostgreSQL 16 (source of truth), Neo4j 5 (graph), FAISS (vector), Redis 7 (cache & locks).
- **Evaluation Benchmark:** `CodePilot-Bench` automated evaluation harness.
