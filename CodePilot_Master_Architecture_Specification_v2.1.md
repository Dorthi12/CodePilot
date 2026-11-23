**CODEPILOT**

**THE KNOWLEDGE OF ATHENA**

**MASTER ARCHITECTURE, FEATURE & ENGINEERING SPECIFICATION**

Version 2.1 \| Audited against the slide requirements \| End-to-End Team Reference

21 specified capabilities • 3 requirement tiers • Shared repository knowledge layer  
Full-stack architecture • API contracts • Data model • AI workflows • Testing & deployment

*Prepared as an implementation blueprint for the CodePilot development team*

**Contents**

- [Document Control](#document-control)
- [Executive Summary](#executive-summary)
- [1. Scope, Assumptions and Non-Goals](#1-scope-assumptions-and-non-goals)
- [2. Design Principles](#2-design-principles)
- [3. Target System Architecture](#3-target-system-architecture)
- [4. Recommended Technology Stack](#4-recommended-technology-stack)
- [5. Repository Ingestion and Indexing Foundation](#5-repository-ingestion-and-indexing-foundation)
- [6. Parsing, Symbol Resolution and Knowledge Model](#6-parsing-symbol-resolution-and-knowledge-model)
- [7. Semantic Retrieval and RAG](#7-semantic-retrieval-and-rag)
- [8. Feature Specifications — BASIC](#8-feature-specifications--basic)
- [9. Feature Specifications — ADVANCED](#9-feature-specifications--advanced)
- [10. Feature Specifications — MASTERMIND](#10-feature-specifications--mastermind)
- [11. Shared API Design and Contracts](#11-shared-api-design-and-contracts)
- [12. Frontend Application Architecture](#12-frontend-application-architecture)
- [13. Multi-Agent Architecture and Tool Governance](#13-multi-agent-architecture-and-tool-governance)
- [14. Code Fix, Test Execution and Sandbox Design](#14-code-fix-test-execution-and-sandbox-design)
- [15. Security, Privacy and Governance](#15-security-privacy-and-governance)
- [16. Testing and Quality Assurance Strategy](#16-testing-and-quality-assurance-strategy)
- [17. Observability, Cost and Operations](#17-observability-cost-and-operations)
- [18. Deployment and Environment Design](#18-deployment-and-environment-design)
- [19. Suggested Repository / Monorepo Structure](#19-suggested-repository--monorepo-structure)
- [20. Implementation Roadmap and Team Work Allocation](#20-implementation-roadmap-and-team-work-allocation)
- [21. Feature-to-Foundation Dependency Matrix](#21-feature-to-foundation-dependency-matrix)
- [22. Risks, Trade-offs and Decisions to Record](#22-risks-trade-offs-and-decisions-to-record)
- [23. Demo Scenarios for Team Validation](#23-demo-scenarios-for-team-validation)
- [24. Final Product Definition](#24-final-product-definition)
- [Appendix A. Audit log (v2.0 to v2.1)](#appendix-a-audit-log-v20-to-v21)

# Document Control

| Field | Value |
| --- | --- |
| Document | CodePilot Master Architecture, Feature & Engineering Specification |
| Version | 2.1 |
| Revision history | 2.1: end-to-end audit against the 21 slide requirements; contracts, data model, API and roadmap corrected (see Appendix A). 2.0: initial problem-statement-aligned specification. |
| Baseline | Groove AI Master Architecture Schema v1.0 |
| Requirements source | CodePilot problem statement slides: Basic, Advanced and Mastermind |
| Audience | Frontend, backend, AI/ML, infrastructure, QA and project leads |
| Status | Proposed target architecture; implementation details are recommendations unless marked as existing v1.0 |
| Scope | All 21 stated requirements plus cross-cutting engineering foundations |

Interpretation rule: the three CodePilot tiers contain 7 requirements each. This specification preserves the problem statement's feature names and intent. Where the v1.0 schema already contains a related capability, it is marked as reusable or extendable; related functionality is not treated as proof that a new requirement is already complete.

## How to read this specification

- Existing v1.0 foundation: components already described in Groove AI v1.0 and suitable for reuse.
- Target implementation: the proposed design required to meet the CodePilot requirement completely.
- Recommended technology: a practical stack choice, not a claim that it is already installed or implemented.
- Acceptance criteria: observable behaviour that QA and reviewers can use to verify completion.
- Security and safety gates: mandatory controls for code execution, repository access, generated patches and third-party integrations.

# Executive Summary

CodePilot is an AI-powered codebase understanding and developer-assistance platform. A user connects a GitHub repository; CodePilot ingests and parses it; builds a structural knowledge graph; indexes code semantically; and exposes navigation, search, explanation, cross-file reasoning, debugging, documentation, code improvement, test generation, security analysis and pull-request review.

The core product principle is that repository answers must be grounded in the actual repository. CodePilot must not rely on a model's generic knowledge when the answer depends on a particular implementation. Responses should cite repository, branch/commit, file path and line range wherever possible.

## Product outcomes

- Understand the repository structure, modules, classes, functions, APIs and dependencies.
- Search code using identifiers, exact text and natural-language intent.
- Explain selected code and answer questions requiring evidence from multiple files.
- Visualize architecture, call relationships and execution paths.
- Investigate reported defects and show evidence-backed root-cause hypotheses.
- Propose code changes as reviewable patches rather than silently modifying the user's repository.
- Generate tests, inspect security risks and review pull requests with traceable findings.

## Tier structure

| Tier | Requirements | Product emphasis |
| --- | --- | --- |
| BASIC (7) | GitHub Integration; Repository Import; Codebase Explorer; Code Search; File-Level Summaries; AI Code Explanation; Repository Management | Connect, ingest, navigate, search and understand code. |
| ADVANCED (7) | Cross-File Relationships; Architecture Diagrams; Bug and Code Smell Detection; Module Dependency Analysis; Whole-Codebase Question Answering; Technical Documentation; Context-Aware Answers | Understand relationships and reason across repository context. |
| MASTERMIND (7) | Multi-Agent Code Analysis; AI Bug Investigation; Code Improvement Suggestions; AI-Assisted Code Fixes; Unit Test Generation; Security Vulnerability Detection; Pull Request Reviews | Investigate, recommend, generate and review engineering changes. |

## Requirements traceability matrix

Every requirement on the three slides maps to one feature section, one API group, persisted data, a UI route and acceptance criteria. "Audit result" lists what the v2.1 review had to fix; details are in Appendix A.

| ID | Slide | Requirement | Spec section | Primary endpoints | Audit result (v2.0 to v2.1) |
| --- | --- | --- | --- | --- | --- |
| B1 | Basic 1 | GitHub Integration | §8 B1, §15.2 | integrations/github/*, github/repositories, auth/* | Login/session endpoints and tiered GitHub permissions were missing (AUD-22, AUD-27). |
| B2 | Basic 2 | Repository Import | §8 B2, §5 | POST repositories, repositories/{id}/imports, jobs/* | No repository-registration or branch-list endpoint; lifecycle, uniqueness and incremental-index defects (AUD-02, 13, 14, 15). |
| B3 | Basic 3 | Codebase Explorer | §8 B3 | snapshots/{sid}/tree, files/content, symbols, references | File paths used as URL segments; no references endpoint (AUD-06, 20). |
| B4 | Basic 4 | Code Search | §8 B4 | POST search, symbols/search, files/search | Variables were not extracted, so they were not searchable (AUD-01). |
| B5 | Basic 5 | File-Level Summaries | §8 B5 | POST ai/file-summary, files/summary | Cache key ignored graph-derived content; table undefined (AUD-12, 18). |
| B6 | Basic 6 | AI Code Explanation | §8 B6 | POST ai/explain | Cache and trace tables undefined (AUD-12). |
| B7 | Basic 7 | Repository Management | §8 B7, §5.7 | repositories (list, get, patch, delete, refresh, snapshots), DELETE snapshots/{sid} | Staleness detection, retention and snapshot deletion unspecified (AUD-15, 28). |
| A1 | Advanced 1 | Cross-File Relationships | §9 A1 | snapshots/{sid}/graph/* | No path or impact APIs although other features depend on them (AUD-05). |
| A2 | Advanced 2 | Architecture Diagrams | §9 A2 | POST architecture/diagram, snapshots/{sid}/architecture/* | User edits and export had no endpoints (AUD-07). |
| A3 | Advanced 3 | Bug and Code Smell Detection | §9 A3 | POST analysis/code-quality, findings | No finding origin (static vs AI vs confirmed); no graph-based smell rule pack (AUD-03, 16). |
| A4 | Advanced 4 | Module Dependency Analysis | §9 A4, §6.1.2 | snapshots/{sid}/dependencies/* | Module never defined; no coupling formulas (AUD-04). |
| A5 | Advanced 5 | Whole-Codebase Question Answering | §9 A5 | POST chat, conversations | Streaming and feedback duplication (AUD-21, 24). |
| A6 | Advanced 6 | Technical Documentation | §9 A6 | docs/* | Depended on a Phase-3 patch service (AUD-30). |
| A7 | Advanced 7 | Context-Aware Answers | §9 A7 | context/resolve, ai/answer, sources | Relation to chat/explain endpoints unclear (AUD-25). |
| M1 | Mastermind 1 | Multi-Agent Code Analysis | §10 M1, §13 | agents/analysis-runs/* | WAITING_APPROVAL had no approve endpoint or transition table (AUD-08). |
| M2 | Mastermind 2 | AI Bug Investigation | §10 M2 | debug/investigations/* | Stack-trace formats and path mapping unspecified (AUD-11). |
| M3 | Mastermind 3 | Code Improvement Suggestions | §10 M3 | improvements/* | No hand-off to fixes; suggestion state undefined (AUD-09, 12). |
| M4 | Mastermind 4 | AI-Assisted Code Fixes | §10 M4, §14 | fixes/* | Edit/reject/revise/PR missing; approval not bound to diff; write permissions (AUD-09, 26, 27). |
| M5 | Mastermind 5 | Unit Test Generation | §10 M5, §14 | tests/* | Dependency install in sandbox could execute arbitrary code (AUD-26). |
| M6 | Mastermind 6 | Security Vulnerability Detection | §10 M6 | security/scans, findings | Duplicated findings API and run tables (AUD-16, 21). |
| M7 | Mastermind 7 | Pull Request Reviews | §10 M7 | github/webhooks, repositories/{id}/pull-requests, pull-requests/* | No PR list, comment edit or PR snapshot model (AUD-02, 10). |

# 1. Scope, Assumptions and Non-Goals

## 1.1 In scope

- GitHub-hosted public and private repositories, subject to user-authorized access.
- Initial language support: Python, JavaScript, TypeScript, Java and Go; additional grammars can be added incrementally.
- Static source analysis, repository graph construction, semantic retrieval and LLM-assisted reasoning.
- Optional GitHub App/OAuth integration for pull requests and repository metadata.
- Developer-in-the-loop code patches, test generation and review workflows.
- Web application with repository dashboard, explorer, graph canvas, code viewer and AI workspace.

## 1.2 Assumptions to validate with the team

- GitHub is the first source-control provider. GitLab/Bitbucket support is a later adapter, not assumed in the MVP.
- Repository ingestion initially indexes a selected branch and commit SHA. Multi-branch comparison is a later extension.
- CodePilot does not execute arbitrary repository code by default. Any dynamic execution must occur in an isolated, disposable sandbox.
- Generated code is never pushed, merged or committed without explicit user approval.
- LLM provider is abstracted behind an interface so the team can change providers without rewriting feature logic.
- Repository and user data are isolated by tenant/user and repository identifiers.

## 1.3 Non-goals for initial release

- Replacing an IDE, CI system, static-analysis platform or human code reviewer.
- Guaranteeing that every generated fix is correct or every vulnerability is detected.
- Executing untrusted code on the application host.
- Automatically merging pull requests or applying patches to the default branch.
- Claiming complete semantic understanding for languages or frameworks that are not supported by the parser.

# 2. Design Principles

1. Repository-grounded answers: every factual codebase claim should carry evidence or explicitly state that evidence is insufficient.
2. One canonical repository snapshot: every analysis is associated with repository ID, branch and immutable commit SHA.
3. Shared knowledge infrastructure: features reuse parser output, graph data, code chunks, embeddings and retrieval services.
4. Separation of concerns: ingestion, parsing, graph building, indexing, AI orchestration and UI are separate modules/services.
5. Human approval for changes: patches, generated tests and PR comments are proposals until reviewed.
6. Safe by default: least-privilege GitHub access, secret redaction, sandbox isolation, path validation and audit logs.
7. Incremental computation: changed files should trigger targeted reparsing and reindexing where dependency consistency permits.
8. Observable workflows: long-running jobs expose progress, status, errors, retryability and trace IDs.
9. Provider abstraction: LLM, embedding, GitHub and static-analysis tools are replaceable behind interfaces.
10. Measured quality: use retrieval, citation, test and security evaluation sets rather than relying on subjective demos.

# 3. Target System Architecture

## 3.1 Recommended logical architecture

| Layer | Components | Responsibilities |
| --- | --- | --- |
| Web client | React + TypeScript + Vite; Tailwind; React Flow; Monaco; Zustand; TanStack Query | Dashboard, repository explorer, graph visualizations, code viewer, chat, review UI and patch approval. |
| API gateway | FastAPI (recommended primary API) or existing Express gateway retained as a thin edge layer | Authentication integration, request validation, authorization, rate limiting, routing and API versioning. |
| Application services | Repository, ingestion, parser, graph, search, RAG, agent, patch, test, security and PR services | Business logic, orchestration, feature-specific APIs and shared domain contracts. |
| Background processing | Celery + Redis initially; Celery workers separated by queue | Clone, parse, embed, graph build, large analyses, agent runs, test generation and PR review. |
| Structural knowledge | Neo4j | Files, modules, classes, functions, imports, calls, API routes, ownership and impact relationships. |
| Relational metadata | PostgreSQL | Users, repositories, commits, files, jobs, permissions, findings, conversations, patches and audit records. |
| Semantic knowledge | FAISS index per repository snapshot (or pgvector if operational simplicity is preferred) | Code chunk embeddings and semantic nearest-neighbour retrieval. |
| Cache and queue | Redis | Task broker, job progress, short-lived cache, rate limits and distributed locks. |
| Repository storage | Encrypted object storage or restricted persistent volume | Source snapshots, patch artifacts, generated reports and test outputs; avoid public web serving. |
| AI providers | LLM adapter + embedding adapter | Provider-neutral chat/completion, structured output, embeddings and model telemetry. |

Architecture recommendation: v1.0 defines both Node.js/Express and FastAPI. For a student/team project, avoid duplicating business logic across both. Prefer FastAPI as the authoritative application API because parsing, graph operations, retrieval and agent orchestration are Python-heavy. If the current frontend or authentication gateway already depends on Express, keep Node as a narrow gateway only; do not implement the same repository logic twice.

## 3.2 End-to-end data flow

1. User signs in and authorizes CodePilot to access selected GitHub repositories.
2. User imports a repository and selects owner/repository, branch and optional commit.
3. API validates access, creates repository snapshot and ingestion job, then enqueues work.
4. Worker fetches/clones the selected commit into an isolated workspace and records immutable commit SHA.
5. Inventory stage classifies files, excludes generated/binary/vendor content and applies size limits.
6. Tree-sitter parses supported files into normalized entities and source spans.
7. Resolvers connect imports, symbols, calls, classes, routes, tests and configuration references.
8. PostgreSQL stores canonical metadata; Neo4j stores relationships; FAISS stores code embeddings and metadata mappings.
9. Quality checks verify parse coverage, graph integrity, index consistency and secret scan results.
10. Repository snapshot becomes READY only when required stages succeed; partial readiness is explicit.
11. User explores, searches, chats or runs analysis; services retrieve evidence from graph, vector index and raw source.
12. Mastermind features create analysis runs, findings and proposed patches; users inspect and approve outputs.

## 3.3 Architecture diagram (text form)

React Web App → API Gateway/FastAPI → Domain Services → (PostgreSQL, Neo4j, FAISS, Redis, Repository/Object Storage). Background jobs are dispatched through Redis/Celery to isolated workers. AI orchestration calls a provider adapter and consumes evidence from the retrieval service. GitHub App/OAuth is used for authorized repository and PR operations.

## 3.4 Service boundaries

| Service/module | Owns | Must not own |
| --- | --- | --- |
| Auth & identity | Users, sessions, GitHub authorization, roles | Repository parsing or LLM prompts |
| Repository service | Repo records, branch/commit selection, lifecycle, deletion | Graph traversal implementation |
| Ingestion worker | Clone/fetch, inventory, filtering, workspace cleanup | Frontend session state |
| Parsing service | Tree-sitter parsing and normalized symbol extraction | LLM answer generation |
| Graph service | Neo4j writes/queries and graph algorithms | Raw GitHub OAuth secrets |
| Indexing service | Chunking, embedding, FAISS index lifecycle | PR approval decisions |
| Retrieval/RAG service | Hybrid retrieval, reranking, citations and context packing | Direct source-code mutation |
| Agent orchestrator | Task plans, tool permissions, agent execution and run state | Unrestricted shell or network access |
| Patch Core and test service | Diff creation, preview, export, approvals (Patch Core, no execution); validation and sandboxed test execution via the Sandbox runner | Automatic merge/push |
| Security/PR service | Security findings, diff review and GitHub PR comments | Unapproved changes to remote branches |
| Context builder | Context envelope (active repo, snapshot, files, symbols, findings, diffs), authorization of every referenced entity, token budgeting | Answer generation or direct retrieval from stores it does not own |
| Architecture and dependency analysis | Component detection, module derivation, coupling metrics, cycles, diagram generation | LLM calls other than optional descriptive labels |
| Documentation service | Doc generation runs, signature validation against parser output, Markdown export | Direct file writes to the repository (goes through Patch Core) |
| Sandbox runner | Disposable containers for analyzers that load project config, test execution and patch validation | Network access, credentials, long-lived state |

# 4. Recommended Technology Stack

| Area | Recommended tool | Why / usage | Alternative / note |
| --- | --- | --- | --- |
| Frontend | React 18+ / TypeScript / Vite | Component UI, typed API models, fast development. | Keep React from v1.0. |
| Styling | Tailwind CSS | Consistent utility-based UI. | CSS modules acceptable. |
| Graph visualization | React Flow (@xyflow/react) | Interactive file/function/architecture/impact graphs. | Use Cytoscape.js if very large graph rendering becomes limiting. |
| Code editor | Monaco Editor | Syntax highlighting, line navigation, diff review and decorations. | Keep Monaco from v1.0. |
| Client state | Zustand | Active repo, selected file/node, graph filters and panel state. | Avoid duplicating server cache in Zustand. |
| Server state | TanStack Query | Caching, retries, query invalidation and loading states. | Use typed API client. |
| Backend | Python FastAPI + Pydantic | REST APIs, async I/O, validation and OpenAPI. | Express only as optional gateway. |
| ORM/migrations | SQLAlchemy 2 + Alembic | PostgreSQL persistence and versioned migrations. | Do not manually drift schema. |
| Graph DB | Neo4j + official Python driver | Structural relationship queries and path traversal. | Use APOC only where justified. |
| Relational DB | PostgreSQL | Transactional metadata, jobs, findings and audit trail. | Use JSONB for flexible metadata, not every field. |
| Vector search | FAISS | Local per-repository vector index as in v1.0. | pgvector can simplify deployment and transactions. |
| Embeddings | Sentence Transformers | Local embeddings for code chunks. | Select model based on evaluation; dimension must match index. |
| LLM orchestration | Provider adapter; LangChain or direct SDK | Prompting, structured output and retrieval chains. | Keep framework-specific code behind interfaces. |
| Agent orchestration | Explicit state machine / LangGraph (optional) | Controlled multi-step agent runs and checkpoints. | Do not start with unrestricted autonomous agents. |
| Parsing | Tree-sitter + language grammars | AST/CST extraction across supported languages. | Language-specific resolvers supplement grammar. |
| Static analysis | Semgrep, Ruff, Bandit, ESLint, CodeQL where available | Deterministic security and quality checks. | Tool availability/licensing must be verified. |
| Git integration | GitPython or subprocess git wrapper; GitHub App API | Clone, fetch, commit metadata, PR diffs and comments. | Never trust user-supplied clone arguments. |
| Queue | Celery + Redis | Long-running ingestion and analysis tasks. | RQ is a simpler alternative. |
| Realtime | WebSocket or SSE | Progress and streaming AI output. | SSE is sufficient for one-way token streaming. Job progress uses GET /jobs/{id}/events (SSE); chat streams over POST using fetch streaming because EventSource cannot POST. |
| Testing | pytest, httpx, Testcontainers, Playwright, Vitest | Unit, integration, API and browser tests. | Add contract tests for service boundaries. |
| Observability | OpenTelemetry, structured logs, Prometheus/Grafana | Trace ingestion and agent workflows. | Sentry for exception monitoring. |
| Deployment | Docker Compose for local; cloud containers for hosted | Repeatable developer environment. | Kubernetes only when scale/ops justify it. |

## 4.1 Model/provider abstraction

Define interfaces such as LLMProvider.generate(), LLMProvider.stream(), LLMProvider.generate_structured(), EmbeddingProvider.embed_documents() and EmbeddingProvider.embed_query(). Implement provider adapters for the selected hosted or local models. Feature code should depend on these interfaces, not a vendor-specific SDK.

## 4.2 Version and compatibility policy

- Pin exact package versions in lockfiles and Docker images after the team verifies compatibility.
- Do not copy v1.0's historical package versions blindly; validate current supported releases before implementation.
- Record embedding model name, revision, dimension and preprocessing version with every index.
- Record LLM provider/model, prompt version, tool versions and analysis configuration for reproducibility.

# 5. Repository Ingestion and Indexing Foundation

## 5.1 Repository lifecycle

Status applies to a snapshot. The repository record itself is ACTIVE, DELETING or DELETED.

| Status | Meaning | Allowed next states |
| --- | --- | --- |
| QUEUED | Import request accepted. | CLONING, FAILED, CANCELLED |
| CLONING | Fetching selected GitHub snapshot. | INVENTORYING, FAILED, CANCELLED |
| INVENTORYING | Classifying files and building inventory. | PARSING, PARTIAL, FAILED, CANCELLED |
| PARSING | Tree-sitter extraction and symbol resolution. | INDEXING, PARTIAL, FAILED, CANCELLED |
| INDEXING | Graph writes, embeddings and index persistence. | VALIDATING, PARTIAL, FAILED, CANCELLED |
| VALIDATING | Integrity checks and quality gates. | READY, PARTIAL, FAILED |
| READY | Required pipeline complete for the selected commit. | STALE, DELETING |
| PARTIAL | Some optional stages failed; snapshots.capabilities lists what works (see 5.6). | RETRYING, STALE, DELETING |
| RETRYING | Re-running failed idempotent stages of the same snapshot. | VALIDATING, PARTIAL, FAILED, CANCELLED |
| STALE | Usable but behind: the tracked remote branch advanced. Data stays readable. A refresh creates a new snapshot; it never mutates this one. | DELETING |
| FAILED | Non-recoverable or exhausted failure. | QUEUED (manual retry from the failed stage), DELETING |
| CANCELLED | User cancelled; partial artifacts cleaned up. | QUEUED (re-import), DELETING |
| DELETING | Cleanup from all stores and workspaces; retryable. | DELETED |
| DELETED | Tombstone row kept for audit. | (terminal) |

## 5.2 File classification

- Include source code, tests, build/config files, package manifests, lockfiles as metadata, documentation and supported infrastructure-as-code.
- Exclude .git internals, node_modules, virtual environments, compiled artifacts, large generated bundles, minified files, binaries and vendored dependencies by default.
- Do not silently exclude test files or configuration needed for understanding; classify them separately.
- Use .gitignore plus CodePilot policy rules; allow user overrides with warnings.
- Set configurable maximum repository size, file size, file count, archive size and parse time.

## 5.3 Ingestion worker stages

| Stage | Implementation | Output / failure handling |
| --- | --- | --- |
| Validate | Normalize GitHub URL; confirm owner/repo; authorize token; verify requested ref. | Reject unsupported host, inaccessible repo or invalid ref with actionable error. |
| Fetch snapshot | GitPython or safe git subprocess; shallow fetch where practical; checkout immutable commit SHA. | Repo workspace path, commit SHA, branch metadata. |
| Inventory | Walk repository with ignore policy; detect language and binary files; compute hashes/LOC/size. | repo_files rows and inventory manifest. |
| Parse | Tree-sitter grammar selection, AST/CST traversal, extraction visitors. | Normalized files, imports, functions, classes, calls, routes and diagnostics. |
| Resolve | Resolve relative imports, package aliases, symbol definitions and call targets. | Resolved and unresolved graph edges with confidence. |
| Persist graph | Batch Neo4j MERGE/UNWIND writes; enforce repo/snapshot scoping. | Graph snapshot and counts. |
| Chunk/embed | Function-aware chunking with fallback windows; batch embeddings; build FAISS index. | Vector index + metadata mapping. |
| Validate | Check index count, graph references, file existence, parse coverage and tenant isolation. | READY or PARTIAL status with quality report. |

## 5.4 Incremental re-indexing

A new commit always produces a new immutable snapshot. Existing snapshots are never edited in place, so a user can still read the older commit and every citation stays valid.

1. Compare repo_files content hashes with the previous READY snapshot of the same branch.
2. Copy forward symbols, chunks and embeddings of unchanged files by content_hash. Graph nodes are re-created under the new snapshot_id (node ids embed snapshot_id, see 6.4).
3. Reparse only new or changed files. Removed files are simply not carried forward.
4. Recompute import and call edges for changed files and for unchanged files that referenced them (reverse dependents taken from the previous graph).
5. Reuse vectors through embedding_cache keyed by (content_hash, embedding_model_version) and write a fresh per-snapshot FAISS index. Nothing is deleted from an existing index.
6. Invalidate cached summaries whose context_hash changed (see B5).
7. If resolution confidence is uncertain (changed manifests, tsconfig/path aliases, build configuration), run a full re-resolution pass.

Never mix chunks from different snapshots in one query context.

## 5.5 Snapshot identity

Every repository analysis record must include repo_id, snapshot_id, owner/repo, branch, commit_sha, ingestion_version, parser_version, embedding_model_version and created_at. All graph/vector lookups must be scoped to snapshot_id (or a rigorously enforced repo+commit key). This prevents stale evidence from being presented as current code.

A snapshot is identified by (repository_id, commit_sha, analysis_profile, ingestion_version). Re-importing with identical values returns the existing snapshot (idempotent). A changed parser version, embedding model or analysis profile creates a new snapshot row for the same commit. Snapshots also carry a kind: BRANCH, PR_BASE or PR_HEAD.

## 5.6 Capability flags

Snapshots store a capabilities map so a PARTIAL snapshot can still be used and the UI can enable only what works.

- explorer: tree and file content (needs inventory only).
- symbols: symbol list, symbol search, references (needs parse stage).
- lexical_search: exact and trigram search over symbols and chunk text.
- semantic_search: embedding index published and validated.
- graph: relationships, impact, architecture, dependency analysis (needs graph persisted).
- ai: summaries, explanation, chat (needs an LLM provider and at least one retrieval mode).
- analysis: per-language tool availability for quality, security and test runs.

## 5.7 Staleness, access re-verification and retention

- Staleness: repositories store tracked_branch, remote_head_sha and remote_checked_at. A GitHub push webhook updates them when the GitHub App is installed; otherwise the API checks lazily when the dashboard or repository page loads (rate-limited and cached). When remote_head_sha differs from the snapshot commit, the snapshot becomes STALE and the UI offers Refresh.
- Access re-verification: GitHub access is re-checked on refresh, before every PUBLISH action and on a schedule. Default policy when access is revoked: block refresh and publishing and suspend reads of private-repository snapshots until the user reconnects or deletes the repository (record in ADR-010).
- Retention: keep the latest N snapshots per repository/branch (default 3) plus any snapshot pinned or referenced by an open PR review or unexpired patch. A scheduled cleanup removes the rest from PostgreSQL, Neo4j, FAISS, object storage and caches.

# 6. Parsing, Symbol Resolution and Knowledge Model

## 6.1 Tree-sitter extraction

| Entity | Fields | Relationships / use |
| --- | --- | --- |
| File | id, snapshot_id, path, language, extension, LOC, size, hash | Contains symbols and routes; imports other files/modules. |
| Module | id, name, package, internal/external, path | Groups files and dependency units. |
| Class / Interface / Enum / Type alias | id, snapshot_id, kind, name, file_id, start/end line, modifiers, exported | Contains methods and fields; extends/implements other types. |
| Function / Method | id, qualified_name, file_id, start/end line, params, return_type, async, exported, complexity | Calls other functions; belongs to class/file. |
| Variable / Constant / Field | id, snapshot_id, file_id, qualified_name, kind (GLOBAL, CONSTANT, CLASS_FIELD, ENUM_MEMBER), declared_type?, exported, start/end line | CONTAINS from File/Class; REFERENCES from functions that read or write it. Required so variables are searchable (Basic 4). Local variables and parameters are not indexed as symbols; parameters stay in the function signature. |
| Import | source_file, target_specifier, resolved_target, line, resolution_status | IMPORTS edge; unresolved references retained. |
| CallSite | caller_id, callee_id?, line, call_kind, resolution_confidence | CALLS edge if resolved; unresolved call-site record otherwise. |
| API Endpoint | method, route, framework, handler, file, line | TRIGGERS handler; CONTAINS route in file. |
| Test | test_file, test_name, target_symbol?, framework, line | TESTS relationship to target where resolved. |
| Code Chunk | chunk_id, file, start/end line, text, language, symbol_id?, hash | Embeds into vector index; source citation anchor. |
| Finding | rule_id, category, severity, file, line, evidence, confidence | Associated with symbol/file/snapshot. |
| Patch | patch_id, base_sha, diff, status, validation_summary | References finding(s), changed files and tests. |

### 6.1.1 Symbol kinds

symbols.kind is one of: MODULE, CLASS, INTERFACE, ENUM, TYPE_ALIAS, FUNCTION, METHOD, VARIABLE, CONSTANT, FIELD, ENUM_MEMBER, API_ENDPOINT, TEST. The search filter, explorer outline and graph labels all use this list.

### 6.1.2 How a module is derived

| Language | Internal module is | Notes |
| --- | --- | --- |
| Python | Package directory (with __init__.py or namespace directory); top-level packages from pyproject/setup configuration | Configurable depth for sub-modules. |
| JavaScript / TypeScript | Nearest package.json; workspace packages are separate modules | Optional sub-modules by first-level source directory. |
| Java | Package from the package statement, grouped by Maven/Gradle module in multi-module builds |  |
| Go | Package directory; module root from go.mod |  |
| External | Dependency declared in a manifest (requirements/pyproject, package.json, pom/gradle, go.mod), or an import specifier that resolves to no internal module | Module kind EXTERNAL; declared=false flags imports missing from manifests. |

Granularity (depth) is part of the analysis profile. Aggregated DEPENDS_ON edges between modules store the number of underlying file-level edges.

## 6.2 Language coverage

| Language | Tree-sitter grammar | Initial extractors | Known limitations |
| --- | --- | --- | --- |
| Python | tree-sitter-python | imports, functions, classes, decorators, async, FastAPI/Flask routes | Dynamic imports, reflection and runtime monkey-patching. |
| JavaScript | tree-sitter-javascript | ES imports, require, functions, classes, Express routes | Dynamic property access and bundler aliases. |
| TypeScript | tree-sitter-typescript | types, interfaces, imports, functions, classes, decorators, routes | Type checker needed for reliable symbol resolution. |
| Java | tree-sitter-java | packages, imports, classes, methods, annotations, Spring routes | Full overload/type resolution requires symbol/classpath analysis. |
| Go | tree-sitter-go | packages, imports, functions, methods, interfaces, net/http routes | Interface dispatch may remain unresolved. |
| Later extensions | Rust, Ruby, C/C++ etc. | Grammar plus language-specific resolvers | Do not advertise full support until evaluated. |

## 6.3 Resolution confidence

- RESOLVED: exact symbol/file target found with deterministic rule.
- PROBABLE: inferred through imports, type context or naming but not guaranteed.
- UNRESOLVED: retain source location and raw target text; do not invent an edge.
- Every graph edge should store resolution_method and confidence so UI and agents can qualify conclusions.

## 6.4 Graph schema

| Node labels | Core properties |
| --- | --- |
| RepositorySnapshot | snapshot_id, repo_id, commit_sha, branch, status |
| File | id, snapshot_id, path, language, loc, complexity, hash |
| Module | id, snapshot_id, name, path, kind (INTERNAL or EXTERNAL), version, declared |
| Class | id, snapshot_id, kind (CLASS, INTERFACE, ENUM, TYPE_ALIAS), qualified_name, file_path, start_line, end_line |
| Variable | id, snapshot_id, qualified_name, kind, file_path, line, exported |
| Component | id, snapshot_id, name, layer, confidence (derived by A2) |
| Function | id, snapshot_id, qualified_name, file_path, start_line, end_line, complexity, async |
| APIEndpoint | id, snapshot_id, method, route, framework, file_path, line |
| TestCase | id, snapshot_id, name, file_path, framework, line |
| Finding | id, snapshot_id, rule_id, severity, category, status |

| Relationship | Direction | Properties |
| --- | --- | --- |
| CONTAINS | File to Function/Class/Variable/APIEndpoint/TestCase; Class to Function/Variable | line range, symbol kind |
| IMPORTS | File → File/Module | specifier, line, resolution status/confidence |
| CALLS | Function → Function | call-site line, call kind, resolution confidence |
| TRIGGERS | APIEndpoint → Function | handler/middleware |
| EXTENDS / IMPLEMENTS | Class → Class/Interface | type relation |
| TESTS | TestCase → Function/Class/File | mapping confidence |
| DEPENDS_ON | Module → Module | dependency kind |
| BELONGS_TO | File to Module; Module or File to Component | membership weight |
| REFERENCES | Function/Method to Variable | read or write, line, resolution confidence |
| AFFECTS | Finding to File/Function/Class/Variable | impact role. Patch impact is computed at validation time and stored in PostgreSQL (there is no Patch node). |

Node ids embed snapshot_id (for example a hash of snapshot_id, kind, path or qualified name and signature). A single-property uniqueness constraint on id and an index on snapshot_id are then sufficient, and every Cypher query must still filter by snapshot_id.

## 6.5 PostgreSQL canonical tables

| Table | Important columns / constraints |
| --- | --- |
| users | id UUID PK, github_login, email (nullable; GitHub emails can be private; unique when present), display_name, avatar_url, created_at, disabled_at |
| oauth_connections | id, user_id FK, provider, provider_user_id, installation_id?, encrypted_token_ref, permissions JSONB, expires_at, revoked_at; unique(provider, provider_user_id) |
| repositories | id, owner_user_id, provider, provider_repo_id, owner, name, canonical_url, visibility, default_branch, tracked_branch, remote_head_sha, remote_checked_at, access_verified_at, label, status (ACTIVE, DELETING, DELETED), created_at; unique(owner_user_id, provider, provider_repo_id) |
| repository_permissions | repository_id, user_id, role (OWNER, ADMIN, VIEWER), granted_by, created_at; PK(repository_id, user_id). Teams are deferred. |
| snapshots | id, repository_id, kind (BRANCH, PR_BASE, PR_HEAD), branch, ref, commit_sha, status, capabilities JSONB, analysis_profile, ingestion_version, parser_version, embedding_version, parse_coverage, file_count, pinned, created_at, indexed_at; unique(repository_id, commit_sha, analysis_profile, ingestion_version) |
| repo_files | id, snapshot_id FK, path, language, extension, category (SOURCE, TEST, CONFIG, DOC, MANIFEST, GENERATED), size_bytes, loc, content_hash, parse_status; unique(snapshot_id, path) |
| modules | id, snapshot_id, name, kind (INTERNAL, EXTERNAL), language, root_path, manifest_path, version, declared |
| symbols | id, snapshot_id, file_id, module_id, parent_symbol_id, kind (see 6.1.1), name, qualified_name, start_line, end_line, signature, exported, complexity, metadata JSONB |
| imports | id, snapshot_id, source_file_id, target_specifier, resolved_file_id, resolved_module_id, line, resolution_status, resolution_method, confidence |
| call_sites | id, snapshot_id, caller_symbol_id, callee_symbol_id?, raw_callee_text, line, call_kind, resolution_status, confidence. Unresolved calls live here, not in Neo4j. |
| api_endpoints | id, snapshot_id, file_id, handler_symbol_id?, method, route, framework, line |
| code_chunks | id, snapshot_id, file_id, symbol_id, chunk_type (CODE, FILE_SUMMARY, DOC, CONFIG), start_line, end_line, content_hash, text_ref, search_text (full-text/trigram), embedding_id |
| jobs | id, owner_id, snapshot_id?, run_id?, job_type, status, progress, stage, error_code, trace_id, idempotency_key, timestamps |
| conversations | id, owner_id, snapshot_id, title, created_at |
| messages | id, conversation_id, role, content, model, prompt_version, retrieval_trace_id, token_usage JSONB, created_at |
| analysis_runs | id, snapshot_id, run_type (QUALITY, SECURITY, AGENT_ANALYSIS, INVESTIGATION, IMPROVEMENT, DOCS, TEST_GEN, FIX, PR_REVIEW, ARCHITECTURE), status, job_id, parent_run_id, config JSONB, model_and_tool_versions JSONB, cost_estimate, created_by, started_at, completed_at |
| findings | id, snapshot_id, analysis_run_id, fingerprint, origin (STATIC_TOOL, GRAPH_RULE, AI_HYPOTHESIS, CONFIRMED), category, rule_id, tool, tool_version, severity, confidence, cwe, owasp, title, description, remediation, file_path, line_start, line_end, symbol_id, evidence JSONB, status (OPEN, ACKNOWLEDGED, FALSE_POSITIVE, ACCEPTED_RISK, FIXED); index(snapshot_id, fingerprint) |
| patches | id, snapshot_id, analysis_run_id, finding_id?, suggestion_id?, source_type (FIX, DOCS, TEST), base_commit_sha, unified_diff, diff_sha256, status (see 14.4), parent_patch_id, validation JSONB, created_by, approved_by |
| test_artifacts | id, analysis_run_id, file_path, content, framework, validation_status |
| pull_requests | id, repository_id, number, title, author_login, base_ref, head_ref, head_repo_full_name (forks), base_sha, head_sha, base_snapshot_id, head_snapshot_id, state, last_synced_at, latest_review_run_id; unique(repository_id, number) |
| audit_events | id, actor_id, action, resource_type, resource_id, metadata JSONB, created_at |

Use Alembic migrations, foreign keys, indexes on snapshot_id/path and owner/time fields, and PostgreSQL row-level security where appropriate. Encrypt provider tokens using a managed key service; do not store raw GitHub tokens in ordinary application tables.

Run tables are unified. Documentation, investigation, improvement, security, review and test-generation runs are analysis_runs rows distinguished by run_type; type-specific detail lives in the tables of 6.6. Every run has a job_id so progress, cancellation and retry behave the same everywhere.

## 6.6 Tables owned by feature sections

The v2.0 feature sections named more than 30 tables that were never defined. They are defined here (39 tables). Names used in v2.0 that are replaced: documentation_runs, investigation_runs, improvement_runs, security_scans, review_runs (now analysis_runs.run_type), embeddings_meta (now snapshot_artifacts) and user_feedback (now feedback). All tables carry snapshot_id or reach it through a foreign key, and all queries are scoped by it.

| Table | Key columns | Used by |
| --- | --- | --- |
| ingestion_diagnostics | id, snapshot_id, stage, severity, code, file_path?, message | B2 |
| snapshot_artifacts | id, snapshot_id, kind (INVENTORY_MANIFEST, QUALITY_REPORT, FAISS_INDEX, DIAGRAM_EXPORT), storage_uri, checksum, size_bytes, embedding_model, embedding_dim | B2, 7.2 |
| embedding_cache | content_hash, embedding_model_version, vector or storage_ref, created_at; PK(content_hash, embedding_model_version) | 5.4, 7.2 |
| file_summaries | id, snapshot_id, file_id, content_hash, context_hash, prompt_version, model, summary_json, created_at | B5, A5 |
| ai_cache | cache_key, feature, snapshot_id, content_hash, prompt_version, model, result_json, created_at | B6, A6 |
| retrieval_traces | id, snapshot_id, message_id or run_id, query, intent, candidates JSONB, selected JSONB, token_budget, timings JSONB | B6, A5, A7 |
| source_refs | id, snapshot_id, file_id, line_start, line_end, symbol_id, content_hash, snippet_hash | A5, A7 |
| context_sessions | id, owner_id, snapshot_id, envelope JSONB, created_at, expires_at | A7 |
| architecture_components | id, snapshot_id, name, layer, confidence, rationale, source (DETECTED or USER) | A2 |
| component_memberships | component_id, file_id or module_id, weight | A2 |
| diagram_configs | id, snapshot_id, diagram_type, grouping_strategy, filters JSONB, layout JSONB, created_by | A2 |
| rule_metadata | rule_id, tool, pack, category, default_severity, cwe, owasp, description | A3, M6 |
| suppressions | id, repository_id, fingerprint or rule_id + path glob, reason, created_by, expires_at | A3, M3, M6 |
| tool_execution_logs | id, run_id, tool, tool_version, status, duration_ms, coverage JSONB, stderr_redacted | A3, M6 |
| dependency_inventory | id, snapshot_id, module_id, ecosystem, package, version_spec, resolved_version, scope, manifest_path, advisory_ids JSONB | A4, M6 |
| dependency_metrics | snapshot_id, module_id, afferent, efferent, instability, scc_id, centrality, hotspot_score | A4 |
| generated_docs | id, run_id, scope, title, format, content_md, validation JSONB, status | A6 |
| agent_tasks | id, run_id, agent_role, status, input JSONB, output JSONB, started_at, ended_at, tokens | M1 |
| agent_messages | id, run_id, task_id, role, content, created_at | M1 |
| tool_calls | id, run_id, task_id, tool, permission_level, input JSONB, output_ref, status, duration_ms | M1, M2 |
| verification_results | id, run_id, finding_id, check (CITATION, DUPLICATE, SCHEMA), passed, detail | M1 |
| investigations | run_id PK, issue_description, stack_trace_redacted, parsed_frames JSONB, failing_test, entrypoint, reproduction_status | M2 |
| hypotheses | id, run_id, rank, summary, confidence, status (UNCONFIRMED, SUPPORTED, REPRODUCED, REFUTED) | M2 |
| evidence_refs | id, owner_type (FINDING, HYPOTHESIS, SUGGESTION, COMMENT), owner_id, source_ref_id, role (SUPPORTS or CONTRADICTS) | A3, M2, M3, M7 |
| diagnostic_steps | id, run_id, hypothesis_id, kind, command_ref, status, result_ref, approved_by | M2 |
| suggestions | id, run_id, category, title, problem, recommendation, benefit, effort, risk, affected_symbols JSONB, status (NEW, ACCEPTED, DISMISSED), feedback | M3 |
| patch_files | id, patch_id, path, change_type, additions, deletions | A6, M4, M5 |
| validation_runs | id, patch_id, kind (APPLY, SYNTAX, LINT, TEST, SECURITY, IMPACT), status, output_ref, tool_versions JSONB | M4, M5 |
| approvals | id, patch_id, scope (EXPORT or PUBLISH), diff_sha256, approver_id, created_at | A6, M4, M5 |
| test_runs | id, run_id, sandbox_image, status, started_at, ended_at, limits JSONB | M2, M5 |
| test_results | id, test_run_id, test_name, status, duration_ms, failure_ref | M2, M5 |
| coverage_reports | id, test_run_id, tool, before JSONB, after JSONB, delta JSONB | M5 |
| secret_findings | id, finding_id, secret_type, fingerprint (hash only), file_path, line. Never the raw value. | M6 |
| pr_files | id, pull_request_id, path, status, additions, deletions, hunks_ref | M7 |
| review_comments | id, run_id, pull_request_id, file_path, side, line, finding_id, body, severity, status (DRAFT, EDITED, DISCARDED, PUBLISHED), github_comment_id | M7 |
| usage_events | id, user_id, repository_id, run_id, provider, model, input_tokens, output_tokens, est_cost, created_at | 17.2 |
| feedback | id, user_id, target_type, target_id, rating, comment, created_at | A5, M3 |
| webhook_deliveries | delivery_id PK, event, repository_id, received_at, status | M7, 15 |
| idempotency_keys | key, user_id, endpoint, request_hash, response_ref, created_at | 11.1 |

# 7. Semantic Retrieval and RAG

## 7.1 Chunking strategy

Prefer syntax-aware chunks: one function/method/class or a coherent block, with file-level context metadata. Use overlapping line windows only as a fallback for oversized or unstructured files. The v1.0 40-line/5-line-overlap strategy is a reasonable baseline, but must be evaluated against function-aware chunking.

## 7.2 Embedding index contract

- Each vector maps to a stable chunk ID and metadata record: snapshot_id, file_path, start_line, end_line, symbol_id, language, content_hash and embedding model revision.
- Vector dimension must exactly match the selected embedding model output. v1.0 contains both 768-dimension and 384-dimension statements; the implementation must choose one verified model and use its actual output dimension consistently.
- Use one FAISS index per snapshot or a safely partitioned index with mandatory snapshot filters.
- Persist index metadata and build status; write to a temporary index then atomically publish after validation.
- Do not strip comments from the only stored source; preserve raw text for display and optionally normalize text for embedding.
- FAISS operational constraints: index files must sit on a volume shared by the api and worker containers (or be loaded from object storage). FAISS has no native metadata filtering, so language/directory filters use an allowed-ID set or post-filtering with over-fetch. Deletion support depends on the index type, so each snapshot gets an immutable index built from embedding_cache.
- If those constraints are unacceptable, choose pgvector in ADR-003. Chunk metadata, filters and snapshot scoping then become ordinary SQL and the shared-volume problem disappears.
- Embedding model choice is made in ADR-004 by evaluation; a general text model is not assumed to be best for code.

## 7.3 Hybrid retrieval

1. Parse query intent: exact symbol/file lookup, semantic question, dependency question, debugging, security or PR review.
2. Retrieve exact lexical matches using PostgreSQL full-text/trigram or a code search index.
3. Retrieve semantic chunks from FAISS.
4. Retrieve structural context from Neo4j: imports, callers/callees, definitions, related APIs and dependents.
5. Rerank candidate evidence using a cross-encoder or a lightweight relevance scorer; retain provenance.
6. Expand context around high-value chunks while respecting token budget and snapshot identity.
7. Send evidence to the LLM with instructions to cite sources and state uncertainty.
8. Validate citations against retrieved records before returning the answer.

## 7.4 RAG response contract

| Field | Meaning |
| --- | --- |
| answer | Natural-language response. |
| sources[] | snapshot_id, file_path, line_start, line_end, snippet, symbol_id, retrieval_method, score. |
| claims[] | Atomic claims linked to one or more source IDs. |
| limitations[] | Missing context, unresolved dynamic behavior, unsupported language or failed tools. |
| confidence | Calibrated qualitative/quantitative indicator; do not imply certainty from LLM self-rating. |
| trace_id | Correlates API, retrieval, model and tool logs. |

## 7.5 Prompt injection and untrusted code

Repository files, README text, comments, issue descriptions and PR descriptions are untrusted data. They must never be interpreted as system instructions. Delimit retrieved content, instruct the model to treat it as evidence only, prevent tools from following instructions found in code, and require policy checks before any tool action. Never expose secrets discovered in source files to the model unless the feature explicitly needs a redacted finding.

# 8. Feature Specifications — BASIC

The following seven features map directly to the Basic slide. Each is described as a complete implementation unit: purpose, UX, input, processing, data, API, output, failure cases, security and acceptance criteria.

## B1. GitHub Integration

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Allow a user to connect a GitHub identity and grant CodePilot scoped access to selected repositories. |
| v1.0 reuse / change | v1.0 describes JWT authentication, GitHub OAuth, PAT support and encrypted private-repository credentials. Reuse the concept, but prefer GitHub App installation tokens for repository-scoped access where practical. |
| User workflow | Sign in with GitHub (the sole identity provider in the initial release; see ADR-009) → GitHub authorization page → consent → callback → connected account screen → repository picker. Show granted permissions, installation/repository access and a disconnect action. Write permissions (review comments, branch creation) are requested only when the user enables those features (see 15.2). |
| Inputs | OAuth authorization code or GitHub App installation; requested repository permissions; selected repository IDs. Never ask users to paste a long-lived PAT as the default path. |
| Backend processing | Create state+PKCE values → redirect to GitHub → validate callback state → exchange code server-side → store encrypted token reference → fetch account/repository permissions → map provider identity to local user → expose authorized repository picker. |
| Frameworks and tools | GitHub App or OAuth App; FastAPI auth module; secure cookie/JWT session; PostgreSQL; KMS/secret manager; httpx GitHub API client. |
| API contract | GET /auth/me; POST /auth/logout; GET /integrations/github/start; GET /integrations/github/callback; GET /integrations/github/status; DELETE /integrations/github; GET /github/repositories; GET /github/repositories/{provider_repo_id}/branches |
| Data persistence | users; oauth_connections(provider, provider_user_id, installation_id, encrypted_token_ref, permissions, expires_at, revoked_at); repository_permissions; audit_events. |
| Output | Connected account profile, available repositories, permission status and token expiry/refresh state. |
| Failure handling | User denies access; callback state mismatch; expired code; insufficient repository permission; rate limit; revoked installation. Display actionable reconnect path. |
| Security | Least privilege; server-side token exchange; encrypted secrets; never send access tokens to browser; CSRF/state validation; token redaction in logs; revoke on disconnect. Permission tiers are defined in 15.2; read-only is the default. |
| Testing | OAuth happy path; invalid state; expired code; private repo permission; revoked token; user A cannot list user B's repos. |
| Acceptance criteria | A user can connect/disconnect GitHub and see only repositories they are authorized to access. Tokens never appear in frontend payloads or logs. Session login and logout work; the app never needs a pasted personal access token. |

## B2. Repository Import

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Import a selected repository snapshot for analysis and expose a reliable ingestion lifecycle. |
| v1.0 reuse / change | Directly extends v1.0 Repo Ingestion: GitPython clone, file filtering, PostgreSQL inventory, Celery jobs and progress events. |
| User workflow | Select repository, branch/ref and optional commit → click Import → progress stages → results summary with files/languages/LOC and readiness status. Public repositories can also be registered by github.com URL (host allowlist, no other providers). |
| Inputs | repository_id, branch/ref, optional commit_sha, inclusion/exclusion policy, analysis configuration. Plus an Idempotency-Key header. The repository must first exist as a repositories row (POST /repositories). |
| Backend processing | Authorize repo → resolve ref to immutable SHA → create snapshot/job → enqueue clone → fetch/checkout exact SHA → safe workspace → inventory/filter → parse → resolve graph → embed → validate → publish snapshot READY/PARTIAL. |
| Frameworks and tools | GitPython or safe git subprocess wrapper; FastAPI; Celery; Redis; Tree-sitter; PostgreSQL; Neo4j; FAISS; isolated filesystem/object storage. |
| API contract | POST /repositories; POST /repositories/{id}/imports; GET /jobs; GET /jobs/{job_id}; GET /jobs/{job_id}/events; POST /jobs/{job_id}/retry; POST /jobs/{job_id}/cancel |
| Data persistence | repositories, snapshots, repo_files, jobs, ingestion_diagnostics, snapshot_artifacts, embedding_cache. |
| Output | snapshot_id, commit_sha, status, progress, stage, file_count, language_stats, parse_coverage and warnings. |
| Failure handling | Private access denied; invalid branch; clone timeout; oversized repo; unsupported files; parser crash; Neo4j/FAISS outage. Retry only safe/idempotent stages. |
| Security | No shell interpolation; validate repository URL/provider ID; path traversal protection; resource quotas; workspace cleanup; network egress restrictions; secrets scanning and redaction. |
| Testing | Public/private repo; empty repo; monorepo; symlinks; huge file; branch moves during import; cancellation; retry; cleanup after failure. Idempotent re-import; same commit with new parser version; stale-state detection after a remote push. |
| Acceptance criteria | Imported snapshot is pinned to a commit SHA; progress is visible per stage; re-importing the same commit with the same ingestion/parser/embedding versions and profile returns the existing snapshot; a changed profile or tool version creates a new snapshot; partial failures are reported accurately with usable capabilities listed. |

## B3. Codebase Explorer

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Let developers navigate directories, source files, symbols and repository metadata. |
| v1.0 reuse / change | v1.0 Directory Tree, Code Viewer, Monaco and Graph↔Code Sync. |
| User workflow | Three-pane repository view: left file tree, center graph/overview, right Monaco code viewer. Search/filter tree; expand folders; click file/symbol; jump to definition/reference; show file metadata. |
| Inputs | snapshot_id, file path, symbol ID, optional line range and filters. File paths are always passed as a URL-encoded query parameter, never as path segments. |
| Backend processing | Fetch tree metadata from PostgreSQL → render lazy tree → file click loads authorized source snapshot → Monaco renders content → graph sync highlights corresponding File/Symbol node → metadata and findings load on demand. Definition/reference lookups read call_sites, imports and Neo4j CALLS/IMPORTS/REFERENCES edges. |
| Frameworks and tools | React, TypeScript, virtualized tree, Monaco Editor, Zustand, TanStack Query, FastAPI. |
| API contract | GET /snapshots/{sid}/tree?path=&depth=; GET /snapshots/{sid}/files/content?path=; GET /snapshots/{sid}/symbols?path=&kind=; GET /snapshots/{sid}/symbols/{symbol_id}; GET /snapshots/{sid}/symbols/{symbol_id}/references |
| Data persistence | repo_files, symbols, snapshots and graph node mappings. |
| Output | Tree nodes, source content, language, LOC, hash, parse state, symbol list and line spans. |
| Failure handling | Deleted file in newer snapshot; binary file; unsupported encoding; oversized file; stale selection. Offer text/metadata-only fallback. |
| Security | Authorize snapshot on every path; normalize and constrain path under snapshot root; prevent ../ traversal and symlink escape; avoid serving repository files from public static path. |
| Testing | Deep tree; large monorepo; Unicode paths; binary; invalid path; graph-to-code and code-to-graph sync; user isolation. |
| Acceptance criteria | A user can browse and open files from the exact imported commit, and graph/file selections stay synchronized. |

## B4. Code Search

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Search for functions, classes, variables, identifiers, text and concepts across an imported repository. |
| v1.0 reuse / change | v1.0 Semantic Code Search via Sentence Transformers + FAISS. Extend with exact lexical and symbol search. |
| User workflow | Search bar with modes: Exact text, Symbol, Natural language. Filters for language, directory, file type and result type. Results show snippet, file, lines, symbol and relevance. Result-type filter: file, function, class, variable/constant/field, endpoint, test. |
| Inputs | query, snapshot_id, search_mode, filters, top_k, pagination cursor. kind[] filter (symbol kinds from 6.1.1). |
| Backend processing | Classify query → exact/symbol search in PostgreSQL/search index and/or semantic query embedding → graph expansion if relationship terms → merge/deduplicate/rerank → return snippets and source refs. |
| Frameworks and tools | PostgreSQL full-text/trigram or Zoekt/OpenSearch if scale requires; FAISS; Sentence Transformers; Neo4j; FastAPI. |
| API contract | POST /search; GET /snapshots/{sid}/symbols/search?q=&kind=; GET /snapshots/{sid}/files/search?q= |
| Data persistence | code_chunks, embeddings_meta/vector IDs, symbols, repo_files and snapshot metadata. |
| Output | items[{file_path,line_start,line_end,snippet,symbol_id,match_type,score,source_ref}]. |
| Failure handling | No index; query too broad; unsupported language; stale index; empty results. Explain which search modes are available. |
| Security | Snapshot authorization; bounded top_k/query length; no arbitrary filesystem glob execution; redact secrets from snippets where policy requires. |
| Testing | Exact identifier; partial symbol; typo; natural-language concept; multi-language filters; duplicate chunk merge; snapshot isolation. Search for a module-level constant and a class field. |
| Acceptance criteria | Search returns relevant, navigable results with accurate line references and distinguishes exact matches from semantic matches. Variables, constants and class fields are searchable alongside functions and classes. |

## B5. File-Level Summaries

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Generate a concise, structured explanation of what a file is responsible for, how it works and what it depends on. |
| v1.0 reuse / change | v1.0 AI Explanation, Auto Docs and RAG can provide the model/retrieval foundation, but file summaries are a distinct feature. |
| User workflow | Summary tab on file open; sections: purpose, key responsibilities, important symbols, inputs/outputs, dependencies, side effects, risks and related files. Regenerate on commit change. |
| Inputs | snapshot_id, file_path, summary_depth (brief/detailed), optional focus. |
| Backend processing | Load file AST/symbol inventory → compute deterministic metadata live (symbols, imports, dependents from Neo4j) → retrieve related imports/callers/callees/config/tests → build structured evidence pack → LLM structured generation of the narrative parts → validate symbol and file references → cache the narrative by (content_hash, context_hash, prompt_version, model). context_hash covers the dependency context used in the evidence pack, so the cache invalidates when a dependent or dependency changes, not only when the file changes. |
| Frameworks and tools | FastAPI; Tree-sitter; Neo4j; RAG service; LLM structured outputs; PostgreSQL cache. |
| API contract | GET /snapshots/{sid}/files/summary?path=; POST /ai/file-summary |
| Data persistence | file_summaries(snapshot_id, file_id, content_hash, context_hash, prompt_version, model, summary_json, created_at). |
| Output | purpose, responsibilities[], key_symbols[], dependencies[], inbound_dependents[], side_effects[], uncertainties[], citations[]. |
| Retrieval linkage | Summaries are generated on demand (optionally pre-generated in the background for the most central files) and stored as retrievable chunks (chunk_type FILE_SUMMARY) for A5 and A7. Whole-codebase QA must still work when no summary exists. |
| Failure handling | No parsed AST; file too large; retrieval incomplete; LLM unavailable. Return a partial deterministic metadata summary when possible. |
| Security | Treat comments/docs as untrusted input; do not execute code; cite only retrieved source ranges. |
| Testing | Utility file; API controller; configuration file; empty file; generated file; stale cache after content change. |
| Acceptance criteria | Summary explains the selected file specifically, cites relevant lines and invalidates when the file content or its dependency context changes. |

## B6. AI Code Explanation

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Explain selected code in understandable language while preserving technical accuracy and repository context. |
| v1.0 reuse / change | Directly extends v1.0 RAG AI Explanation using selected lines, FAISS retrieval, LangChain/provider adapter and source references. |
| User workflow | Select code or function → Explain → choose beginner/technical/deep mode → view explanation, execution steps, parameters, return values, edge cases and related source links. |
| Inputs | snapshot_id, file_path, start_line, end_line or symbol_id, explanation_style, optional question. |
| Backend processing | Validate selection → parse enclosing symbol → retrieve relevant chunks and graph neighbours → prompt model with source evidence → generate structured explanation → validate citations → render with clickable source links. |
| Frameworks and tools | FastAPI; Tree-sitter; Neo4j; FAISS; embedding adapter; LLM provider; Monaco decorations. |
| API contract | POST /ai/explain |
| Data persistence | messages/AI runs, retrieval_traces, ai_cache (keyed by content_hash, selection, style, prompt_version, model). |
| Output | overview, step_by_step[], inputs, outputs, side_effects[], edge_cases[], related_symbols[], citations[], limitations[]. |
| Failure handling | Selection not found; unsupported syntax; context not retrieved; model timeout. Return evidence-only explanation or ask user to narrow selection. |
| Security | Prompt injection resistance; output escaping; no tool invocation required for ordinary explanation; redact credentials. |
| Testing | Simple function; async flow; exception handling; cross-file call; incomplete retrieval; citation validation. |
| Acceptance criteria | Explanation refers to actual selected code, uses repository-specific context and provides working file/line navigation. |

## B7. Repository Management

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Let users manage multiple imported repositories, snapshots, permissions and lifecycle. |
| v1.0 reuse / change | v1.0 repo list/get/delete/status endpoints and repository-scoped storage. |
| User workflow | Dashboard list with owner/name, branch, commit, import status, last indexed time, languages and actions: open, refresh, switch snapshot, rename label, remove. A "behind remote" badge appears when the tracked branch has advanced (STALE). |
| Inputs | repository ID, snapshot ID, selected branch, action, confirmation. |
| Backend processing | List only authorized repos → fetch status/metadata → open selected snapshot → refresh triggers import of new commit → deletion marks resource DELETING and cascades cleanup across PostgreSQL/Neo4j/FAISS/cache/storage. Staleness detection, access re-verification and snapshot retention follow 5.7. |
| Frameworks and tools | FastAPI; PostgreSQL; Neo4j; FAISS lifecycle manager; Redis; GitHub API. |
| API contract | GET /repositories; GET /repositories/{id}; PATCH /repositories/{id}; GET /repositories/{id}/snapshots; POST /repositories/{id}/refresh; DELETE /snapshots/{sid}; DELETE /repositories/{id} |
| Data persistence | repositories, repository_permissions, snapshots, jobs, audit_events. |
| Output | Repository metadata, snapshot list, current status, deletion/refresh job ID. |
| Failure handling | Permission revoked; snapshot currently in use; cleanup failure; repository deleted upstream. Support retryable cleanup and tombstone status. |
| Security | Owner/role check on every operation; deletion confirmation; audit trail; purge tokens and indexes; enforce retention policy. GitHub access is re-verified on refresh; retention and cleanup apply to every store. |
| Testing | Multiple repos; switching snapshots; refresh; permission revocation; delete during job; cleanup retry; tenant isolation. Retention cleanup keeps pinned snapshots; delete a single snapshot while another is READY. |
| Acceptance criteria | Users can reliably list, switch, refresh and delete only repositories they own or are authorized to manage. |

# 9. Feature Specifications — ADVANCED

## A1. Cross-File Relationships

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Identify and explain relationships among functions, classes, modules and files, including direct and transitive connections. |
| v1.0 reuse / change | v1.0 Neo4j file dependency graph, function call graph, Graph↔Code Sync and Call Trace. |
| User workflow | Select a symbol or file → Relationships panel shows imports, imported-by, calls, called-by, definitions, implementations, route handlers and related tests. Each edge is clickable. |
| Inputs | snapshot_id, node_type, node_id, relationship_types, direction, depth, filters. |
| Backend processing | Resolve selected node → execute bounded Cypher traversals → rank direct vs transitive links → attach source locations and edge confidence → return graph and explanation. Path tracing and impact (reverse reachability) use the same bounded traversal executor and are reused by A5, M2, M4 and M7. |
| Frameworks and tools | Neo4j; Cypher; Tree-sitter resolver; FastAPI; React Flow; PostgreSQL mapping. |
| API contract | GET /snapshots/{sid}/graph/nodes/{node_id}/relationships?types=&direction=&depth=&limit=; POST /snapshots/{sid}/graph/subgraph; GET /snapshots/{sid}/graph/paths?from=&to=&max_depth=; GET /snapshots/{sid}/graph/nodes/{node_id}/impact?depth= |
| Data persistence | Neo4j nodes/edges plus relational symbol source spans and unresolved reference records. |
| Output | nodes[], edges[], relationship_type, confidence, evidence_location, traversal_depth, truncation flag. |
| Failure handling | Ambiguous symbol name; graph too large; unresolved dynamic call; traversal timeout. Require node IDs and cap depth/returned nodes. |
| Security | Scope every query to snapshot; parameterized Cypher; query timeout and maximum depth; do not allow user-supplied raw Cypher. |
| Testing | Direct import; transitive dependency; overloaded symbol; unresolved dynamic call; cyclic graph; large graph limit. |
| Acceptance criteria | Users can navigate from a symbol to related files/functions and inspect why each relationship exists. |

## A2. Architecture Diagrams

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Generate visual representations of repository architecture and module interactions. |
| v1.0 reuse / change | v1.0 Architecture Detection, Dependency Graph, Execution Flow and React Flow. |
| User workflow | Architecture overview with detected components/layers; user can switch between package/module diagram, service map, dependency graph and API-to-data flow. Nodes open source files. |
| Inputs | snapshot_id, diagram_type, grouping_strategy, depth, filters. |
| Backend processing | Compute graph clusters and module boundaries → use folder/package/config metadata → optionally ask LLM to label components from evidence → render deterministic nodes/edges → allow user edits/exports. The service map reads docker-compose, Dockerfile and Kubernetes manifests when present; otherwise it uses folder/package boundaries. |
| Frameworks and tools | Neo4j; graph algorithms (NetworkX for offline clustering if useful); React Flow; Mermaid export; LLM only for descriptive labels. |
| API contract | POST /architecture/diagram; GET /snapshots/{sid}/architecture/components; GET /snapshots/{sid}/architecture/diagrams/{id}; PATCH /snapshots/{sid}/architecture/diagrams/{id}; GET /snapshots/{sid}/architecture/diagrams/{id}/export?format= |
| Data persistence | architecture_components, component_memberships, diagram_configs and graph snapshot. |
| Output | components[{id,name,layer,files,confidence}], edges[{source,target,kind}], layout, citations and detected_patterns. Export formats: Mermaid, SVG, JSON. |
| Failure handling | No meaningful graph; monolith with weak boundaries; unsupported framework. Label uncertain groupings rather than asserting an architecture style. |
| Security | Read-only analysis; source citation and snapshot isolation. |
| Testing | Layered app; monolith; microservice-style repo; circular imports; empty graph; user-defined grouping. |
| Acceptance criteria | Diagram is reproducible from graph data, explains grouping rationale and supports click-through to code. |

## A3. Bug and Code Smell Detection

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Identify suspicious code patterns, maintainability problems and likely defects; distinguish heuristic findings from confirmed bugs. |
| v1.0 reuse / change | v1.0 complexity metrics and LLM-assisted code smell heuristics. Extend with deterministic linters, type checks and static analysis. |
| User workflow | Run analysis on file or repository → findings list grouped by severity/category → inline Monaco annotations → evidence, confidence, impacted symbols and suggested investigation steps. |
| Inputs | snapshot_id, scope, rule_pack, severity_threshold, optional changed_files. |
| Backend processing | Run deterministic rules and language tools → normalize findings → deduplicate/suppress known false positives → enrich with graph context and relevant code → optional LLM explanation → persist findings and provenance. |
| Finding origin | Every finding has origin STATIC_TOOL, GRAPH_RULE, AI_HYPOTHESIS or CONFIRMED (reproduced or validated). The UI labels the origin and never counts an AI_HYPOTHESIS as a confirmed bug. |
| Built-in graph/metric rule pack | Long function, high cyclomatic complexity, many parameters, deep nesting, oversized class or file, duplicate code blocks (hash-based clone detection), unused symbols (no inbound references, excluding exported entry points), circular dependencies, god module (high fan-in and fan-out), public functions with no TESTS edge, TODO/FIXME markers. Thresholds are configurable per rule pack. These cover the maintainability and poor-practice part of the requirement; linters and Semgrep cover likely bugs. |
| Frameworks and tools | Semgrep; Ruff; Bandit; ESLint; TypeScript compiler; language-specific analyzers; Tree-sitter; Neo4j; LLM for explanation, not sole detection. |
| API contract | POST /analysis/code-quality; GET /analysis-runs/{run_id}; GET /findings?snapshot_id=&category=&severity=&status=&origin=; GET /findings/{id}; PATCH /findings/{id} |
| Data persistence | analysis_runs(run_type QUALITY), findings, rule_metadata, suppressions, tool_execution_logs. |
| Output | Finding with rule_id, title, severity, confidence, file/lines, evidence, remediation, tool, tool_version and status. |
| Failure handling | Tool unavailable; unsupported language; timeout; duplicate findings. Return partial analysis with tool coverage. |
| Security | Pin tool versions; treat findings as untrusted; no automatic fixes; avoid printing secrets in evidence; enforce sandbox for tools that execute project configuration. |
| Testing | Known vulnerable/smelly fixtures; false-positive fixtures; suppression; parser/tool timeout; SARIF import. Origin labelling in the UI; graph-rule fixtures (cycle, dead code, long function). |
| Acceptance criteria | Findings are reproducible, sourced to exact lines and identify detection method; UI clearly separates static finding, AI hypothesis and confirmed defect. |

## A4. Module Dependency Analysis

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Explain how modules depend on and communicate with one another, including coupling, cycles and dependency hotspots. |
| v1.0 reuse / change | v1.0 Neo4j IMPORTS graph and impact traversal. Extend with package manifests and external dependency metadata. |
| User workflow | Module dependency matrix and graph; show incoming/outgoing dependencies, cycles, centrality, high-coupling modules, external packages and dependency paths. |
| Inputs | snapshot_id, module/package filter, direction, depth, include_external. |
| Backend processing | Resolve imports to modules → aggregate file edges into module edges → identify cycles and strongly connected components → compute in/out degree and centrality → enrich with package manifest metadata. |
| Module definition | Modules are derived per language as defined in 6.1.2. |
| Metrics | Afferent coupling Ca (modules depending on this one), efferent coupling Ce (modules this one depends on), instability I = Ce / (Ca + Ce), defined as 0 when Ca + Ce = 0. Cycles are strongly connected components (Tarjan). Hotspots rank by Ca, Ce and a centrality measure (PageRank or betweenness, chosen in ADR). Dependency paths reuse GET graph/paths on Module nodes. |
| Frameworks and tools | Neo4j; NetworkX or graph algorithms; Tree-sitter; package manifest parsers; React Flow/Recharts. |
| API contract | GET /snapshots/{sid}/dependencies/modules; GET /snapshots/{sid}/dependencies/matrix; GET /snapshots/{sid}/dependencies/cycles; GET /snapshots/{sid}/dependencies/hotspots; GET /snapshots/{sid}/dependencies/external |
| Data persistence | modules, imports, Module nodes, DEPENDS_ON relationships, dependency_inventory (package manifests), dependency_metrics. |
| Output | modules[], edges[], cycles[], coupling_metrics, unresolved_dependencies and external_packages. |
| Failure handling | Unresolved aliases; generated code; missing manifest; dynamic imports. Report coverage and unresolved count. |
| Security | No package installation required for static dependency inventory; if metadata is fetched, restrict external network and validate package identifiers. |
| Testing | Circular dependencies; aliases; workspace monorepo; external dependency; dynamic import. |
| Acceptance criteria | Developers can identify direct/transitive dependencies, cycles and high-coupling modules with traceable file paths. |

## A5. Whole-Codebase Question Answering

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Answer questions requiring evidence from multiple files and multiple knowledge layers. |
| v1.0 reuse / change | v1.0 Codebase Chat using FAISS top-k, LangChain conversational retrieval and SSE. Extend to hybrid graph+vector retrieval. |
| User workflow | Repository chat supports questions such as 'Trace login from route to database', 'Where is authorization enforced?' and 'What breaks if this interface changes?'. Source chips open code. |
| Inputs | snapshot_id, conversation_id, question, chat_history, response_mode, optional selected_context. |
| Backend processing | Intent classify → lexical/vector retrieval → graph traversal → retrieve file summaries/docs/config/tests → rerank and deduplicate → construct evidence pack → LLM structured answer → citation validation → stream response. |
| Frameworks and tools | FastAPI; RAG service; FAISS; Neo4j; PostgreSQL; LangChain or LangGraph; SSE; LLM adapter. |
| API contract | POST /chat; GET /conversations?snapshot_id=; GET /conversations/{id}/messages; DELETE /conversations/{id} |
| Data persistence | conversations, messages, retrieval_traces, source_refs, feedback and prompt versions. |
| Output | answer, citations[], claims[], limitations[], suggested_followups[], trace_id. |
| Streaming | POST /chat streams over fetch (ReadableStream), not EventSource. Event types: token, source, claim, limitation, done, error. |
| Failure handling | No evidence; context overflow; model timeout; stale snapshot; ambiguous question. Ask clarifying question or say evidence is insufficient. |
| Security | Repository authorization on each request; prompt-injection defenses; rate limits; no cross-repository retrieval; redact credentials. |
| Testing | Multi-file data flow; cross-module auth; missing evidence; contradictory sources; history context; citation accuracy. |
| Acceptance criteria | Answers synthesize multiple files when needed and each repository-specific claim links to valid file/line evidence. |

## A6. Technical Documentation

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Generate and maintain documentation for modules, functions, classes, APIs, configuration and architecture. |
| v1.0 reuse / change | v1.0 Auto Documentation Generator for docstrings/JSDoc/Javadoc/GoDoc. Expand to Markdown and API/system docs. |
| User workflow | Generate docs for file/module/repository; preview changes; choose audience and format; edit output; export Markdown or propose a documentation patch. |
| Inputs | snapshot_id, scope, format, audience, include_examples, include_private_symbols. |
| Backend processing | Collect symbols and signatures → retrieve related implementation and tests → generate structured docs → validate symbols/parameters/routes against parser → render preview/diff → user approves export/patch. The documentation patch is created through Patch Core (diff creation, preview, export, approval; no code execution), which is built in Phase 2. |
| Frameworks and tools | Tree-sitter; RAG; LLM structured output; Markdown renderer; Monaco diff; patch service. |
| API contract | POST /docs/generate; GET /docs/{run_id}; POST /docs/{run_id}/export; POST /docs/{run_id}/patch |
| Data persistence | analysis_runs(run_type DOCS), generated_docs, ai_cache, patches, patch_files, approvals. |
| Output | Module overview, symbol docs, API reference, setup guide, architecture notes, source references and unresolved details. |
| Failure handling | Missing types; ambiguous behavior; no examples; model invents parameter. Validate signatures and mark inferred descriptions. |
| Security | Generated docs are drafts; no overwrite without approval; escape Markdown/HTML; avoid leaking secrets. |
| Testing | Function docs; API route docs; module docs; stale docs after code changes; signature mismatch. |
| Acceptance criteria | Documentation matches actual symbols and API signatures, contains source links and is previewed before modifying repository files. |

## A7. Context-Aware Answers

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Ensure generated explanations and recommendations are relevant to the active repository, selected code, graph state, branch and commit. |
| v1.0 reuse / change | v1.0 source chips and graph-code synchronization are a foundation, but context must be formalized as a shared service and contract. |
| User workflow | User asks from a selected file, symbol, graph node, finding or PR diff. UI displays active context chips (repo, commit, files, symbols) and lets user remove/add context. |
| Inputs | snapshot_id, active_file, selected_symbol, graph_selection, finding_id, diff_id, user_question. |
| Backend processing | Build context envelope → verify all references belong to authorized snapshot → retrieve local and graph evidence → rank based on active selection → answer with source mapping → validate every citation. |
| Frameworks and tools | Shared Context Builder; Neo4j; FAISS; PostgreSQL; FastAPI; LLM provider; React state. |
| API contract | POST /context/resolve; POST /ai/answer; GET /sources/{source_id} |
| Data persistence | context_sessions, retrieval_traces, source_refs and messages. |
| Output | Context envelope {snapshot_id, commit_sha, active_entities[], evidence[], exclusions[], token_budget}; answer with citations. |
| Relationship to other AI endpoints | The Context Builder is a shared service used by B6, A5, M2, M4 and M7. POST /context/resolve previews the envelope for UI chips, POST /ai/answer is a stateless single-turn answer, and POST /chat adds conversation history. Context entity types are extensible: file, symbol, graph node, finding, diff, patch. |
| Failure handling | Selection stale; file from another snapshot; insufficient context; conflicting context. Explain mismatch and refresh context. |
| Security | Enforce snapshot and repository ACL before retrieval; do not trust client-supplied file paths without server-side resolution. |
| Testing | Switch repository; switch commit; ask from graph selection; context removal; invalid source; cross-user attempt. |
| Acceptance criteria | Answer uses the active selection and commit, citations resolve to the same snapshot, and missing context is stated instead of guessed. |

# 10. Feature Specifications — MASTERMIND

## M1. Multi-Agent Code Analysis

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Coordinate specialized agents to analyze architecture, security, performance, testing and code quality using shared repository evidence. |
| v1.0 reuse / change | v1.0 shared RAG, graph and parser become shared tools. Multi-agent orchestration is new. |
| User workflow | User selects analysis scope and agents → sees plan → approves execution → watches agent progress → reviews consolidated report with per-agent findings and disagreements. |
| Plan approval rule | The plan is always shown. A plan with only READ and ANALYZE steps inside the budget starts automatically unless the user chose "require approval". A plan containing EXECUTE, WRITE or PUBLISH steps, or exceeding the cost threshold, enters WAITING_APPROVAL until POST /agents/analysis-runs/{id}/approve. |
| Inputs | snapshot_id, analysis_scope, agent_set, budget/time limits, policy profile. |
| Backend processing | Orchestrator creates run and plan → agents receive scoped tasks and evidence tools → each returns structured findings with citations → verifier deduplicates/checks evidence → aggregator ranks and reports consensus/conflicts → persist artifacts. |
| Frameworks and tools | LangGraph or explicit workflow state machine; FastAPI; Celery; shared retrieval tools; Pydantic structured schemas; LLM provider adapter; static analysis tools. |
| API contract | POST /agents/analysis-runs; GET /agents/analysis-runs/{id}; POST /agents/analysis-runs/{id}/approve; POST /agents/analysis-runs/{id}/cancel; GET /agents/analysis-runs/{id}/events; GET /agents/analysis-runs/{id}/report |
| Data persistence | analysis_runs(run_type AGENT_ANALYSIS), agent_tasks, agent_messages, tool_calls, findings, verification_results, usage_events. |
| Output | Plan, task graph, agent-specific reports, consolidated findings, evidence, confidence, disagreements and run metrics. |
| Failure handling | Agent timeout; provider rate limit; tool failure; conflicting findings; budget exhaustion. Partial report with failed-agent status. |
| Security | Agents have least-privilege tools; no unrestricted shell/network; per-run budget; bounded recursion; all tool calls audited; user approval for write-capable tools. |
| Testing | Single agent; parallel agents; timeout; disagreement; hallucinated citation; malicious repo instruction; cancellation; budget cap. |
| Acceptance criteria | At least two specialized agents can execute bounded tasks, share verified context, produce evidence-backed findings and generate one consolidated report. |

## M2. AI Bug Investigation

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Investigate a reported issue by tracing relevant code paths, reproducing where safe, and identifying evidence-backed root-cause hypotheses. |
| v1.0 reuse / change | v1.0 Call Trace, Execution Flow, Impact Analysis, Codebase Chat and code graph. |
| User workflow | User enters error description/stack trace/reproduction steps → system identifies relevant files and call paths → shows hypotheses, supporting evidence, missing evidence and suggested next diagnostics. |
| Inputs | snapshot_id, issue_description, stack_trace, failing_test, endpoint/function, environment metadata (redacted). |
| Stack trace support | Parsers for Python tracebacks, Node/V8 stack traces, Java stack traces and Go panics. Frames map to repository paths by longest-suffix match against repo_files; ambiguous matches are reported, not guessed. Stack traces and logs are secret-redacted before storage or prompting. |
| Backend processing | Parse issue and stack trace → map frames to symbols → retrieve related logs/tests/config → trace callers/callees and data flow → identify suspicious branches/error handling → run approved tests in sandbox if configured → rank hypotheses → produce investigation report. |
| Frameworks and tools | Neo4j traversal; RAG; Tree-sitter; language static analyzers; optional isolated test runner; LLM reasoning with structured output. |
| API contract | POST /debug/investigations; GET /debug/investigations/{id}; POST /debug/investigations/{id}/diagnostics |
| Data persistence | analysis_runs(run_type INVESTIGATION), investigations, hypotheses, evidence_refs, diagnostic_steps, test_runs, test_results and finding links. |
| Output | Problem summary, suspected root causes ranked, call path, relevant files/lines, reproduction status, evidence, confidence and next steps. |
| Failure handling | Stack trace cannot map; dynamic dispatch; no test environment; flaky test; unavailable dependency. Mark as unconfirmed hypothesis. |
| Security | Run only in disposable sandbox with no secrets by default; resource/network restrictions; scrub logs; no production environment access. |
| Testing | Known bug benchmark; stack trace mapping; multi-file root cause; no reproduction; false root cause; malicious test script. |
| Acceptance criteria | Investigation report traces actual source paths, distinguishes hypothesis from reproduced defect and never claims a fix without validation. |

## M3. Code Improvement Suggestions

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Recommend changes to quality, maintainability, performance and readability with explicit rationale and trade-offs. |
| v1.0 reuse / change | v1.0 Code Smell Detection and Complexity Metrics; extend to performance patterns and architectural recommendations. |
| User workflow | Findings/suggestion panel grouped by category and impact; each suggestion shows current code, proposed approach, rationale, risks and affected modules. |
| Inputs | snapshot_id, scope, improvement_categories, constraints, severity threshold. |
| Backend processing | Run static metrics and linters → identify hotspots → retrieve code/dependencies/tests → agent evaluates alternatives → rank by impact, confidence and effort → validate claims and display suggestions. |
| Frameworks and tools | Ruff/ESLint/Semgrep; graph metrics; RAG; agent orchestrator; LLM structured output. |
| API contract | POST /improvements/analyze; GET /improvements/{run_id}; PATCH /improvements/suggestions/{id} |
| Data persistence | analysis_runs(run_type IMPROVEMENT), suggestions, evidence_refs, suppressions. |
| Output | Category, problem, recommendation, expected benefit, complexity/effort, risk, affected symbols, evidence and validation needed. |
| Hand-off | A suggestion can start a patch through POST /fixes with suggestion_id. |
| Failure handling | Insufficient evidence; style preference conflicts; optimization not measurable. Mark as advisory and avoid fabricated performance gains. |
| Security | Read-only analysis; no automatic source mutation; sanitize output. |
| Testing | Known code smells; micro-optimization false claims; style conflict; low-context file; duplicate suggestions. |
| Acceptance criteria | Suggestions are actionable, evidence-backed, prioritized and explain trade-offs rather than presenting generic advice. |

## M4. AI-Assisted Code Fixes

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Generate a reviewable patch for a selected finding or bug, validate it and let the developer decide whether to apply it. |
| v1.0 reuse / change | v1.0 Monaco diff/preview pattern in documentation generation; graph impact and RAG evidence. Actual code-fix pipeline is new. |
| User workflow | Choose finding → Generate fix → inspect unified diff and explanation → run configured tests/lint/security checks → accept/reject/edit patch → optionally create branch/PR only after explicit approval. |
| Inputs | snapshot_id, finding_id or task description, target files, constraints, allowed tools, validation policy. Also suggestion_id. |
| Backend processing | Build fix context → plan minimal edit → generate unified diff → parse/apply to temporary worktree → syntax/type/lint/test checks in sandbox → analyze resulting graph/impact → produce validation report → user approval → export patch or create branch/PR. |
| Frameworks and tools | LLM code generation; unified diff library; GitPython; Tree-sitter; pytest/Jest/etc.; sandbox runner; Monaco diff editor; GitHub API. |
| API contract | POST /fixes; GET /fixes/{id}; PATCH /fixes/{id}; POST /fixes/{id}/revise; POST /fixes/{id}/validate; POST /fixes/{id}/approve; POST /fixes/{id}/reject; POST /fixes/{id}/export; POST /fixes/{id}/pull-request |
| Data persistence | analysis_runs(run_type FIX), patches, patch_files, validation_runs, test_results, approvals and audit_events. |
| Output | Patch diff, changed file list, rationale, test results, static analysis results, unresolved risks and approval status. |
| Failure handling | Patch does not apply; syntax invalid; tests fail; context stale; conflicting edits. Keep patch unapplied and provide diagnostics. |
| Security | Never auto-push/merge; run tests in isolated container; disable credentials/network by default; enforce file allowlist; inspect diff for secrets and dangerous changes. Approval is bound to diff_sha256 and a scope (EXPORT or PUBLISH); any edit changes the hash and clears validation and approval. Creating a branch or PR needs a separate PUBLISH approval and GitHub write permission (15.2). Merge permission is never requested. |
| Testing | Patch applies; patch conflict; test failure; malicious generated command; stale base SHA; approval audit. Edit after approval invalidates approval; PUBLISH without write permission fails safely. |
| Acceptance criteria | A fix is always presented as a diff, validated against a pinned base snapshot and only exported/applied after explicit user approval. |

## M5. Unit Test Generation

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Generate meaningful tests for selected functions/classes/modules using actual implementation and existing test conventions. |
| v1.0 reuse / change | v1.0 parser, function graph, file summaries, RAG and patch preview. Test generation itself is new. |
| User workflow | Select symbol → Generate tests → choose framework/style/coverage goal → preview test file → run in sandbox → inspect coverage and failures → approve/export. |
| Inputs | snapshot_id, symbol_id/file_path, framework, test_type, target_edge_cases, existing_test_paths. |
| Backend processing | Inspect signature/body/dependencies → retrieve existing tests and fixtures → infer expected behaviour from implementation/docs → generate tests → run in isolated workspace → collect failures/coverage → refine within bounded attempts → show diff. |
| Test-to-target mapping | TESTS edges derive from naming conventions, imports and call relationships with a confidence value. They locate existing tests and fixtures and support the coverage delta. |
| Frameworks and tools | pytest; Jest/Vitest; JUnit; Go testing; coverage.py/nyc/JaCoCo; Tree-sitter; LLM adapter; sandbox runner. |
| API contract | POST /tests/generate; GET /tests/{run_id}; POST /tests/{run_id}/execute; POST /tests/{run_id}/export |
| Data persistence | analysis_runs(run_type TEST_GEN), test_artifacts, test_runs, test_results, coverage_reports, patches. |
| Output | Test code, test cases covered, fixtures/mocks, execution results, coverage delta and assumptions. |
| Failure handling | Unclear expected behavior; external service dependency; flaky tests; missing runtime. Generate candidate tests but flag assumptions and skip execution if unsafe. |
| Security | Sandbox; no production credentials; no network by default; dependency install from allowlisted lockfile/cache; execution time/memory limits. Dependency preparation follows the two-phase rule in 14.2; install scripts are disabled by default. |
| Testing | Boundary cases; exceptions; async; mocks; generated test compiles; tests detect seeded bug; no test passes vacuously. |
| Acceptance criteria | Generated tests compile/run in supported sandbox, cover stated cases and are traceable to the selected function and base commit. |

## M6. Security Vulnerability Detection

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Identify potentially unsafe coding patterns and common security vulnerabilities, with evidence, severity and remediation guidance. |
| v1.0 reuse / change | v1.0 Code Smell Detection framework and graph; security-specific rules, scanners and triage are new. |
| User workflow | Run security scan → dashboard by severity/category → open finding to see code, taint/data flow, affected endpoint and fix guidance → mark false positive/accepted risk. |
| Inputs | snapshot_id, scan_profile, languages, include_dependencies, changed_files_only. |
| Backend processing | Run deterministic SAST and secret scanning → parse dependency manifests and known advisories where permitted → map findings to graph and entry points → perform data-flow/taint analysis where tool supports → AI triage and explain evidence → deduplicate and prioritize. |
| Frameworks and tools | Semgrep; CodeQL where licensed/available; Bandit; ESLint security plugins; Gitleaks; dependency audit tools; Neo4j; LLM for triage. |
| API contract | POST /security/scans; GET /security/scans/{id}; findings are read through GET /findings?category=SECURITY and PATCH /findings/{id} |
| Data persistence | analysis_runs(run_type SECURITY), findings, rule_metadata, dependency_inventory, secret_findings (redacted fingerprints only), suppressions. |
| Output | CWE/OWASP category where applicable, severity, confidence, affected file/line, evidence, source-to-sink path, remediation and tool provenance. |
| Failure handling | Scanner unavailable; unsupported language; dependency advisory feed unavailable; false positive. Show coverage gaps and tool status. |
| Security | Never expose secret values; store only redacted fingerprint/location; protect scanner outputs; isolate any dynamic analysis; do not claim absence of vulnerabilities from a partial scan. |
| Testing | Known vulnerable fixtures; secret fixture; safe code false-positive fixture; dependency advisory; scanner timeout; suppression and re-open. |
| Acceptance criteria | Security findings identify the rule/tool, evidence and remediation; scan report includes coverage and explicitly states what was not checked. |

## M7. Pull Request Reviews

| Specification field | Implementation detail |
| --- | --- |
| Purpose | Analyze proposed code changes, understand their impact on the base repository and generate actionable review comments. |
| v1.0 reuse / change | v1.0 repository graph, impact analysis, call trace, RAG, code smell and GitHub integration. PR diff ingestion and review workflow are new. |
| User workflow | User selects PR or receives authorized webhook → CodePilot loads base/head commits and diff → review plan → findings grouped by file/severity → suggested inline comments → human edits/approves posting. |
| Inputs | repository_id, pull_request_number, base_sha, head_sha, diff, review_profile. |
| Backend processing | Verify webhook signature/permissions → fetch immutable base/head snapshots and changed files → parse diff hunks → map changed lines to symbols → calculate affected dependents/call paths → run relevant quality/security checks → agent review → deduplicate and validate line anchors → create draft review → user approves posting. |
| PR snapshots | Base and head are indexed as lightweight snapshots (kind PR_BASE and PR_HEAD) scoped to changed files and their dependents, reusing the base branch snapshot when one exists. Fork PRs are fetched read-only and never receive secrets. |
| Frameworks and tools | GitHub App webhooks/API; GitPython; Neo4j; RAG; static analyzers; agent orchestrator; GitHub Checks/Review API. |
| API contract | POST /github/webhooks; GET /repositories/{id}/pull-requests; POST /pull-requests/{id}/review-runs; GET /pull-requests/{id}/reviews/{run_id}; PATCH /pull-requests/{id}/reviews/{run_id}/comments/{comment_id}; POST /pull-requests/{id}/reviews/{run_id}/publish |
| Data persistence | pull_requests, pr_files, analysis_runs(run_type PR_REVIEW), review_comments, findings, base/head snapshots and audit_events. |
| Output | Review summary, inline comments, severity, evidence, impacted modules, tests to run and approval state. |
| Failure handling | Diff too large; force-push changes head SHA; deleted line anchor; missing permissions; webhook replay. Re-fetch and invalidate stale run. |
| Security | Verify webhook HMAC; least-privilege GitHub App permissions; do not publish comments without approval; protect PR source from prompt injection; never check out untrusted PR code on privileged runner. Publishing needs GitHub write permission, requested only when the user enables it (15.2). |
| Testing | PR with bug; PR with no findings; changed line moved; force-push; webhook replay; private repo; approval before publish. Edit and discard a draft comment before publish; fork PR. |
| Acceptance criteria | Review is pinned to exact base/head SHAs, comments anchor to changed lines, findings cite repository evidence and publication requires user approval. |

# 11. Shared API Design and Contracts

## 11.1 API conventions

- Base path: /api/v1. Use JSON request/response except explicit SSE endpoints and binary patch exports.
- Authentication: secure session cookie or bearer token; enforce owner/repository permissions server-side.
- Every request accepts or derives snapshot_id and validates that it belongs to the requested repository.
- Long-running operations return 202 Accepted with job_id/run_id and a status endpoint.
- Use cursor pagination for large result sets; cap graph depth, node count, query length and response size.
- Return consistent errors: {error:{code,message,details,trace_id}}. Do not leak stack traces or secrets.
- Use idempotency keys for imports, webhook processing and patch approvals where retries could duplicate actions.
- Publish OpenAPI schema and generate typed frontend clients.
- Path convention: reads of snapshot-scoped data use /snapshots/{sid}/...; operations that start work or consume AI/compute are top-level resources with snapshot_id in the JSON body; run resources (analysis runs, patches, conversations, pull requests, findings, jobs) have globally unique ids and carry snapshot_id as an attribute. The server always validates that the snapshot belongs to the caller.
- File paths are never URL path segments; they are passed as a URL-encoded ?path= parameter.
- Findings and feedback are single resources (/findings, /feedback) shared by every feature. Cancel is uniform: POST /jobs/{id}/cancel.
- Long-running operations also expose GET /jobs/{id}/events (SSE). Streaming endpoints that need POST (chat) use fetch streaming.
- Webhook endpoints are unauthenticated by session and rely on HMAC signature verification plus delivery-id deduplication (webhook_deliveries).

## 11.2 Common API response envelope

| Field | Type | Purpose |
| --- | --- | --- |
| request_id | string | Unique request identifier. |
| data | object/array | Successful payload. |
| meta | object | Pagination, snapshot and timing metadata. |
| warnings | array | Partial coverage, unresolved symbols or tool warnings. |
| trace_id | string | Distributed trace correlation. |

## 11.3 Core endpoint catalogue

The catalogue is the single source of truth: each feature section's API contract row is generated from it. It lists 98 endpoints.

| Feature | Method + endpoint (prefix /api/v1) | Purpose |
| --- | --- | --- |
| B1 GitHub Integration | GET /auth/me | Current user, session and GitHub connection state. |
| B1 GitHub Integration | POST /auth/logout | End the session. |
| B1 GitHub Integration | GET /integrations/github/start | Begin GitHub authorization (state + PKCE). |
| B1 GitHub Integration | GET /integrations/github/callback | Validate state; exchange code server-side. |
| B1 GitHub Integration | GET /integrations/github/status | Connection, permission tier and token expiry. |
| B1 GitHub Integration | DELETE /integrations/github | Disconnect and revoke. |
| B1 GitHub Integration | GET /github/repositories | Authorized repository picker (paged, searchable). |
| B1 GitHub Integration | GET /github/repositories/{provider_repo_id}/branches | Branches/refs available for import. |
| B2 Repository Import | POST /repositories | Register a repository from the picker (provider_repo_id) or a public github.com URL. |
| B2 Repository Import | POST /repositories/{id}/imports | Start an import; returns 202 with snapshot_id and job_id. |
| B2 Repository Import | GET /jobs | List jobs (filter by repository_id, status, type). |
| B2 Repository Import | GET /jobs/{job_id} | Poll job/run state. |
| B2 Repository Import | GET /jobs/{job_id}/events | SSE stream of stage/progress events. |
| B2 Repository Import | POST /jobs/{job_id}/retry | Retry from the failed idempotent stage. |
| B2 Repository Import | POST /jobs/{job_id}/cancel | Cancel any job or analysis run. |
| B3 Codebase Explorer | GET /snapshots/{sid}/tree?path=&depth= | Lazy directory tree. |
| B3 Codebase Explorer | GET /snapshots/{sid}/files/content?path= | Source text and file metadata. |
| B3 Codebase Explorer | GET /snapshots/{sid}/symbols?path=&kind= | Symbols in a file. |
| B3 Codebase Explorer | GET /snapshots/{sid}/symbols/{symbol_id} | Symbol detail and span. |
| B3 Codebase Explorer | GET /snapshots/{sid}/symbols/{symbol_id}/references | Definition, callers, importers and variable references (jump to definition/reference). |
| B4 Code Search | POST /search | Exact, symbol, semantic and hybrid search (snapshot_id in body). |
| B4 Code Search | GET /snapshots/{sid}/symbols/search?q=&kind= | Symbol search/autocomplete (function, class, variable, constant, endpoint, test). |
| B4 Code Search | GET /snapshots/{sid}/files/search?q= | File-name/path search. |
| B5 File-Level Summaries | GET /snapshots/{sid}/files/summary?path= | Cached summary plus deterministic metadata. |
| B5 File-Level Summaries | POST /ai/file-summary | Generate or regenerate a file summary. |
| B6 AI Code Explanation | POST /ai/explain | Explain a selected range or symbol with citations. |
| B7 Repository Management | GET /repositories | List authorized repositories with status. |
| B7 Repository Management | GET /repositories/{id} | Repository detail. |
| B7 Repository Management | PATCH /repositories/{id} | Rename label, set tracked branch. |
| B7 Repository Management | GET /repositories/{id}/snapshots | List snapshots and select one. |
| B7 Repository Management | POST /repositories/{id}/refresh | Import the latest commit of the tracked branch as a new snapshot. |
| B7 Repository Management | DELETE /snapshots/{sid} | Delete one snapshot (cascade across all stores). |
| B7 Repository Management | DELETE /repositories/{id} | Delete repository and all snapshots (cascade). |
| A1 Cross-File Relationships | GET /snapshots/{sid}/graph/nodes/{node_id}/relationships?types=&direction=&depth=&limit= | Bounded relationship traversal. |
| A1 Cross-File Relationships | POST /snapshots/{sid}/graph/subgraph | Bounded subgraph for the graph canvas. |
| A1 Cross-File Relationships | GET /snapshots/{sid}/graph/paths?from=&to=&max_depth= | Bounded call/import paths between two nodes (call trace). |
| A1 Cross-File Relationships | GET /snapshots/{sid}/graph/nodes/{node_id}/impact?depth= | Reverse-reachability impact set. |
| A2 Architecture Diagrams | POST /architecture/diagram | Generate and persist an architecture diagram (snapshot_id in body). |
| A2 Architecture Diagrams | GET /snapshots/{sid}/architecture/components | Detected components and layers. |
| A2 Architecture Diagrams | GET /snapshots/{sid}/architecture/diagrams/{id} | Fetch a stored diagram. |
| A2 Architecture Diagrams | PATCH /snapshots/{sid}/architecture/diagrams/{id} | Apply user grouping/layout edits. |
| A2 Architecture Diagrams | GET /snapshots/{sid}/architecture/diagrams/{id}/export?format= | Export as mermaid, svg or json. |
| A3 Bug and Code Smell Detection | POST /analysis/code-quality | Start a bug/code-smell analysis run. |
| A3 Bug and Code Smell Detection | GET /analysis-runs/{run_id} | Run status, coverage and summary (all run types). |
| A3 Bug and Code Smell Detection | GET /findings?snapshot_id=&category=&severity=&status=&origin= | List findings (also used for security). |
| A3 Bug and Code Smell Detection | GET /findings/{id} | Finding detail with evidence. |
| A3 Bug and Code Smell Detection | PATCH /findings/{id} | Change status: acknowledge, false positive, accepted risk, reopen. |
| A4 Module Dependency Analysis | GET /snapshots/{sid}/dependencies/modules | Modules and aggregated edges. |
| A4 Module Dependency Analysis | GET /snapshots/{sid}/dependencies/matrix | Module dependency matrix. |
| A4 Module Dependency Analysis | GET /snapshots/{sid}/dependencies/cycles | Cycles (strongly connected components). |
| A4 Module Dependency Analysis | GET /snapshots/{sid}/dependencies/hotspots | High-coupling/high-centrality modules. |
| A4 Module Dependency Analysis | GET /snapshots/{sid}/dependencies/external | External packages from manifests and imports. |
| A5 Whole-Codebase Question Answering | POST /chat | Whole-codebase Q&A (streamed; creates a conversation on first message). |
| A5 Whole-Codebase Question Answering | GET /conversations?snapshot_id= | List conversations. |
| A5 Whole-Codebase Question Answering | GET /conversations/{id}/messages | Message history with citations. |
| A5 Whole-Codebase Question Answering | DELETE /conversations/{id} | Delete a conversation. |
| A6 Technical Documentation | POST /docs/generate | Start a documentation run. |
| A6 Technical Documentation | GET /docs/{run_id} | Preview generated docs and validation results. |
| A6 Technical Documentation | POST /docs/{run_id}/export | Export Markdown. |
| A6 Technical Documentation | POST /docs/{run_id}/patch | Create a documentation patch through Patch Core. |
| A7 Context-Aware Answers | POST /context/resolve | Build and preview the context envelope (UI chips). |
| A7 Context-Aware Answers | POST /ai/answer | Stateless single-turn answer over a context envelope. |
| A7 Context-Aware Answers | GET /sources/{source_id} | Resolve a citation to snapshot/file/lines/snippet. |
| M1 Multi-Agent Code Analysis | POST /agents/analysis-runs | Create a multi-agent run and plan. |
| M1 Multi-Agent Code Analysis | GET /agents/analysis-runs/{id} | Run state, plan, per-agent status. |
| M1 Multi-Agent Code Analysis | POST /agents/analysis-runs/{id}/approve | Approve plan or a gated EXECUTE/WRITE/PUBLISH step. |
| M1 Multi-Agent Code Analysis | POST /agents/analysis-runs/{id}/cancel | Cancel the run. |
| M1 Multi-Agent Code Analysis | GET /agents/analysis-runs/{id}/events | SSE agent progress. |
| M1 Multi-Agent Code Analysis | GET /agents/analysis-runs/{id}/report | Consolidated report with disagreements. |
| M2 AI Bug Investigation | POST /debug/investigations | Start an investigation from issue text, stack trace or failing test. |
| M2 AI Bug Investigation | GET /debug/investigations/{id} | Report: call path, ranked hypotheses, evidence. |
| M2 AI Bug Investigation | POST /debug/investigations/{id}/diagnostics | Request an approved diagnostic (for example a sandboxed test run). |
| M3 Code Improvement Suggestions | POST /improvements/analyze | Start an improvement analysis run. |
| M3 Code Improvement Suggestions | GET /improvements/{run_id} | Prioritized suggestions. |
| M3 Code Improvement Suggestions | PATCH /improvements/suggestions/{id} | Accept, dismiss or add feedback on a suggestion. |
| M4 AI-Assisted Code Fixes | POST /fixes | Generate a patch from finding_id, suggestion_id or a task description. |
| M4 AI-Assisted Code Fixes | GET /fixes/{id} | Patch, diff, rationale, validation and approval state. |
| M4 AI-Assisted Code Fixes | PATCH /fixes/{id} | User edits the diff (clears validation and approval). |
| M4 AI-Assisted Code Fixes | POST /fixes/{id}/revise | Ask the model for a revision with an instruction. |
| M4 AI-Assisted Code Fixes | POST /fixes/{id}/validate | Run apply, syntax, lint, test, security and impact checks. |
| M4 AI-Assisted Code Fixes | POST /fixes/{id}/approve | Approve export (bound to diff_sha256). |
| M4 AI-Assisted Code Fixes | POST /fixes/{id}/reject | Reject the patch. |
| M4 AI-Assisted Code Fixes | POST /fixes/{id}/export | Download unified diff. |
| M4 AI-Assisted Code Fixes | POST /fixes/{id}/pull-request | Create branch/PR; needs separate PUBLISH approval and write permission. |
| M5 Unit Test Generation | POST /tests/generate | Generate candidate tests. |
| M5 Unit Test Generation | GET /tests/{run_id} | Tests, assumptions, execution and coverage results. |
| M5 Unit Test Generation | POST /tests/{run_id}/execute | Run tests in the sandbox (explicit opt-in). |
| M5 Unit Test Generation | POST /tests/{run_id}/export | Export the test patch. |
| M6 Security Vulnerability Detection | POST /security/scans | Start a security scan run. |
| M6 Security Vulnerability Detection | GET /security/scans/{id} | Scan status, coverage and what was not checked. |
| M7 Pull Request Reviews | POST /github/webhooks | Receive GitHub events (HMAC verified, deduplicated). |
| M7 Pull Request Reviews | GET /repositories/{id}/pull-requests | List/sync pull requests. |
| M7 Pull Request Reviews | POST /pull-requests/{id}/review-runs | Start a PR review run pinned to base/head SHAs. |
| M7 Pull Request Reviews | GET /pull-requests/{id}/reviews/{run_id} | Draft review: summary, comments, impact. |
| M7 Pull Request Reviews | PATCH /pull-requests/{id}/reviews/{run_id}/comments/{comment_id} | Edit or discard a draft comment. |
| M7 Pull Request Reviews | POST /pull-requests/{id}/reviews/{run_id}/publish | Publish approved comments to GitHub (separate approval). |
| Cross-cutting | POST /feedback | Feedback on answers, findings or suggestions (target_type, target_id, rating). |
| Cross-cutting | GET /usage | Token/cost usage and remaining budgets. |

## 11.4 Example request/response contracts

Import request:

```json
POST /api/v1/repositories/{repository_id}/imports
{ "ref": "main", "analysis_profile": "standard" }
```

Accepted response:

```json
{ "data": { "snapshot_id": "uuid", "job_id": "uuid", "status": "QUEUED" }, "trace_id": "..." }
```

Search request (POST /api/v1/search):

```json
{ "snapshot_id": "uuid", "query": "where is refresh token validated?", "mode": "hybrid", "kind": ["function", "variable"], "filters": { "language": ["python"] }, "top_k": 10 }
```

Search result item:

```json
{ "file_path": "app/auth/service.py", "line_start": 42, "line_end": 67, "symbol": "refresh_access_token", "kind": "function", "match_type": "semantic", "score": 0.91, "source_id": "..." }
```

Finding contract:

```json
{ "id": "uuid", "snapshot_id": "uuid", "rule_id": "SEC-EXAMPLE-001", "origin": "STATIC_TOOL", "severity": "HIGH", "confidence": "MEDIUM",
  "title": "Untrusted input reaches SQL query", "location": { "file_path": "app/db.py", "line_start": 88, "line_end": 92 },
  "evidence": [], "tool": "semgrep", "tool_version": "pinned", "status": "OPEN" }
```

Error contract:

```json
{ "error": { "code": "SNAPSHOT_NOT_READY", "message": "Snapshot is PARTIAL; semantic_search is unavailable.", "details": {}, "trace_id": "..." } }
```

# 12. Frontend Application Architecture

## 12.1 Route structure

| Route | Page | Main components |
| --- | --- | --- |
| /login | Login | GitHub sign-in (sole identity provider), error states. |
| /dashboard | Repository dashboard | Repo list with status and behind-remote badge, import modal (picker, branch), recent jobs, onboarding. |
| /repo/:repoId | Repository overview | Snapshot list and switcher; opens the latest READY snapshot. |
| /repo/:repoId/:snapshotId | Repository workspace | Tree, graph canvas, Monaco, AI panel, summary, symbol references, metrics. |
| /repo/:repoId/:snapshotId/search | Search workspace | Search bar, mode and kind filters, result list, preview. |
| /repo/:repoId/:snapshotId/chat | Codebase chat | Conversation, context chips, citations, streaming. |
| /repo/:repoId/:snapshotId/architecture | Architecture | Diagram type switcher, components, edit grouping, export. |
| /repo/:repoId/:snapshotId/dependencies | Module dependencies | Matrix and graph, cycles, hotspots, external packages. |
| /repo/:repoId/:snapshotId/docs | Documentation | Run list, preview, export or documentation patch. |
| /repo/:repoId/:snapshotId/analysis | Analysis dashboard | Quality, security, agent run history; findings list with origin and status filters. |
| /repo/:repoId/:snapshotId/analysis/:runId | Run detail | Consolidated report, agent progress, plan approval, disagreements. |
| /repo/:repoId/:snapshotId/debug/:investigationId | Bug investigation | Call path, ranked hypotheses, evidence, diagnostics approval. |
| /repo/:repoId/:snapshotId/improvements | Improvement suggestions | Prioritized suggestions, accept/dismiss, create patch. |
| /repo/:repoId/:snapshotId/patches/:patchId | Patch review | Monaco diff, validation results, edit, approve, reject, export, create PR. |
| /repo/:repoId/:snapshotId/tests/:runId | Test generation | Generated tests, assumptions, execution results, coverage delta. |
| /repo/:repoId/:snapshotId/review/:prId | PR review | Diff viewer, draft comments (edit/discard), impacted graph, publish approval. |
| /settings/integrations | Integrations | GitHub connection, permission tier, disconnect. |
| /settings/usage | Usage and budgets | Token/cost usage and limits. |

## 12.2 Repository workspace layout

- Header: repository identity, branch, commit SHA, ingestion status, snapshot switcher.
- Left panel: directory tree, symbol outline, API routes, dependencies and findings filters.
- Center panel: graph canvas with modes for file dependency, function call, architecture, execution, impact and PR change scope.
- Right panel: Monaco code viewer, file summary, explanation, chat, docs, findings and patch diff tabs.
- Bottom drawer: job progress, test output, diagnostics and tool execution logs.
- Global search and command palette: navigate to file/symbol, ask a question or launch an analysis.

## 12.3 State management

Use Zustand for ephemeral UI state: selected repository/snapshot, selected file/node, graph mode, filters, active panel and open tabs. Use TanStack Query for server state: repository metadata, tree, graph, search, findings and job status. Do not store repository source code or GitHub tokens in persistent browser storage.

## 12.4 UI states

- Loading/skeleton, empty state, ready, partial readiness, stale snapshot, failed job, permission revoked, unsupported language, no evidence, streaming, cancellation and retry states.

# 13. Multi-Agent Architecture and Tool Governance

## 13.1 Agent roles

| Agent | Responsibilities | Allowed tools |
| --- | --- | --- |
| Planner/Orchestrator | Decompose user request, define plan and budgets, assign tasks. | Read repository metadata; launch approved specialist tasks. |
| Architecture Agent | Understand modules, boundaries, dependencies and patterns. | Graph queries, file summaries, semantic retrieval. |
| Debugging Agent | Trace stack traces, call paths, error handling and test evidence. | Graph trace, retrieval, static checks, sandbox tests only if approved. |
| Quality Agent | Detect code smells, maintainability and complexity issues. | Linters, metrics, code retrieval. |
| Security Agent | Analyze input validation, auth, secrets, injection and dependency risks. | SAST, secret scanner, dependency audit, graph context. |
| Performance Agent | Identify obvious hotspots, expensive loops/queries and bottlenecks. | Complexity metrics, static rules, profile artifacts if provided. |
| Testing Agent | Propose tests and validate coverage of changed logic. | Test generator, isolated runner, coverage tools. |
| Review Agent | Consolidate findings, remove duplicates and create review comments. | Read-only diff, findings and citation validator. |

## 13.2 Agent run state machine

| State | Meaning | Allowed next states |
| --- | --- | --- |
| CREATED | Run accepted and validated. | PLANNING, FAILED, CANCELLED |
| PLANNING | Plan and required context are prepared. | WAITING_APPROVAL, RUNNING, FAILED, CANCELLED |
| WAITING_APPROVAL | The plan or a gated EXECUTE/WRITE/PUBLISH step needs consent (POST /agents/analysis-runs/{id}/approve). | RUNNING, CANCELLED |
| RUNNING | Specialist tasks executing. | VERIFYING, WAITING_APPROVAL (a task needs a newly gated step), PARTIAL, FAILED, CANCELLED |
| VERIFYING | Citations, duplicates, schema and tool results checked. | COMPLETED, PARTIAL, FAILED, CANCELLED |
| COMPLETED | Report persisted. | (terminal) |
| PARTIAL | Some agents/tools failed; usable results available. | (terminal; a new run may retry failed agents) |
| FAILED | Run cannot continue. | (terminal) |
| CANCELLED | User or policy cancelled the run. | (terminal) |

## 13.3 Tool permission levels

| Level | Examples | Policy |
| --- | --- | --- |
| READ | Read snapshot files, query graph, retrieve chunks, inspect diff. | Default allowed after repo authorization. |
| ANALYZE | Run static analyzers, calculate metrics, create report. | Allowed under quotas; tools pinned and sandboxed if they execute code. |
| EXECUTE | Run tests, build, type-check or reproduction script. | Explicit opt-in; disposable container; strict limits; no secrets/network by default. |
| WRITE | Create patch artifact or modify temporary worktree. | Allowed only in isolated workspace; user approval required before export/apply. |
| PUBLISH | Create branch/PR or post review comments. | Separate explicit approval, scoped GitHub permission and audit event. |

## 13.4 Agent reliability rules

- Use structured JSON outputs validated with Pydantic schemas.
- Require evidence IDs for every finding and factual claim.
- Cap steps, tool calls, retries, wall-clock time, context tokens and estimated cost.
- Do not let agents recursively spawn agents without orchestrator approval.
- Store agent plans, tool inputs/outputs, model versions and prompt versions for auditability.
- Use a verifier step to check source locations and detect unsupported claims.
- Agent disagreement must be represented, not silently averaged away.

# 14. Code Fix, Test Execution and Sandbox Design

## 14.1 Patch lifecycle

1. Create patch request against immutable base commit SHA.
2. Gather source, tests, dependency context and related findings.
3. Generate a unified diff limited to allowed files.
4. Apply diff to a disposable worktree; reject path traversal, binary edits and unexpected file additions.
5. Run syntax parse and formatter/linter checks.
6. Run selected tests in isolated container if user enabled execution.
7. Run static security scan on resulting diff.
8. Compute changed symbols and graph impact.
9. Present diff and validation results; user can edit, approve, reject or request revision.
10. On explicit approval, export patch or create a branch/PR through GitHub integration.

## 14.2 Sandbox requirements

- One disposable container/workspace per run; no host Docker socket mounted.
- Non-root user, read-only base image, restricted writable work directory and resource quotas.
- Default no network; if dependency retrieval is necessary, use allowlisted proxy/cache.
- No production secrets, GitHub token or user credentials inside test container.
- CPU, memory, process count, disk, file count and execution time limits.
- Capture stdout/stderr with secret redaction; terminate runaway processes.
- Destroy container and temporary workspace after completion; retain only approved artifacts.
- Two-phase dependency preparation. Phase 1 (prepare) runs without repository secrets through an allowlisted package proxy, installs only from lockfiles with integrity hashes and disables install-time scripts where the ecosystem supports it (for example npm --ignore-scripts, pip with --require-hashes and --only-binary=:all:). Phase 2 (execute) runs the tests with no network. A project that needs install scripts requires explicit user approval and the run is marked HIGH-RISK.
- Per-language sandbox images (Python, Node, Java, Go) are built from pinned base images, contain no credentials and are rebuilt on a schedule.
- Static analyzers that load project-controlled configuration (for example ESLint configs, TypeScript plugins, build scripts) run in the sandbox or with project configuration loading disabled.

## 14.3 Test generation quality

A generated test is not considered valid merely because it passes. The workflow should verify that it exercises the intended behaviour, asserts meaningful outcomes, covers edge cases, avoids vacuous assertions and follows repository conventions. Where possible, mutation testing or seeded-fault evaluation can assess whether tests detect incorrect behaviour.

## 14.4 Patch statuses

DRAFT → VALIDATING → VALIDATED or VALIDATION_FAILED → APPROVED → EXPORTED or PUBLISHED. REJECTED is available from any non-terminal state. Any edit creates a new diff_sha256, returns the patch to DRAFT and clears validation and approvals. If the base snapshot becomes STALE the patch is flagged STALE and the user is offered a rebase/regenerate. Approvals are scoped (EXPORT or PUBLISH) and bound to the exact diff hash; PUBLISH needs its own approval and an audit event.

# 15. Security, Privacy and Governance

| Control area | Required implementation |
| --- | --- |
| Authentication | Secure session cookies or short-lived access tokens; CSRF protection where cookies are used; MFA delegated to identity provider if available. |
| Authorization | Repository-level ACL checks on every API; owner/team roles; no trust in client-supplied repo_id. |
| GitHub credentials | GitHub App installation tokens preferred; encrypt token material using KMS; rotate/revoke; never log tokens. Permission tiers are defined in 15.2. |
| Tenant isolation | snapshot_id + repository ownership checks in PostgreSQL, Neo4j and vector search; automated cross-tenant tests. |
| Path security | Normalize paths, resolve symlinks safely, enforce workspace root, reject traversal and unsafe archive entries. |
| Secrets | Scan source for secrets; redact values in findings, prompts, logs and UI; avoid storing raw secret contents. |
| Prompt injection | Treat repository content and PR descriptions as untrusted data; isolate instructions from evidence; tool allowlists. |
| Code execution | No execution by default; isolated sandbox for tests; no host credentials; quotas and egress restrictions. |
| Patch governance | Diff-only proposals; immutable base SHA; tests; human approval; audit all exports and GitHub writes. |
| Webhooks | Verify HMAC signature, deduplicate delivery IDs, validate repository installation and event permissions. |
| Data retention | Document deletion, retention and backup policy; remove graph/vector/source artifacts when repository is deleted. |
| Auditability | Record actor, resource, action, timestamp, approval, model/tool version and trace ID. |

## 15.1 Threat model to review

- Malicious repository contains prompt injection in README/comments/tests.
- Untrusted PR changes CI scripts to exfiltrate secrets.
- Path traversal or symlink escape reads files outside clone workspace.
- Cross-user repository or vector-index leakage.
- Compromised GitHub token or overly broad OAuth scope.
- Agent tool abuse, infinite loops, budget exhaustion or shell command injection.
- LLM hallucinated code citation or false security claim.
- Denial of service through huge repositories, graph traversal or expensive repeated prompts.

## 15.2 GitHub App permission tiers

| Tier | Repository permissions | Enabled when |
| --- | --- | --- |
| Read (default) | Metadata: read; Contents: read; Pull requests: read | Always. Covers import, exploration, analysis and reading PR diffs. |
| Review publishing | Pull requests: write | The user enables publishing review comments for that repository. |
| Branch and PR creation | Contents: write; Pull requests: write | The user enables creating a branch/PR from an approved patch. Merge is never requested. |

Subscribed webhook events: push and pull_request. Changing permissions requires re-authorization by the installation owner, and the UI must explain this. Every write goes through a PUBLISH approval and an audit event.

# 16. Testing and Quality Assurance Strategy

## 16.1 Test pyramid

| Level | What to test | Tools / examples |
| --- | --- | --- |
| Unit | Parser visitors, path normalization, chunking, scoring, schemas, prompt output validators. | pytest, Vitest, Pydantic validation. |
| Integration | PostgreSQL migrations, Neo4j writes/queries, FAISS ID mapping, Redis queue, GitHub adapter. | Testcontainers, mocked provider clients. |
| Contract | OpenAPI request/response, event payloads, job state transitions. | Schemathesis or custom contract tests. |
| End-to-end | Connect GitHub → import repo → search → explain → graph → fix preview → approve/export. | Playwright. |
| Security | Tenant isolation, SSRF/path traversal, prompt injection, secret redaction, sandbox escape tests. | OWASP test cases, dependency scanners. |
| AI evaluation | Retrieval relevance, citation precision, grounded answer correctness, false positive rate, patch acceptance. | Golden datasets and human review. |
| Performance | Import throughput, graph traversal latency, search latency, concurrent jobs and memory. | Locust/k6, Prometheus. |

## 16.2 Suggested acceptance targets (initial targets, to be measured)

| Metric | Initial target | Notes |
| --- | --- | --- |
| Repository import | Progress updates for every stage; retryable failures visible. | Runtime depends on repository size. |
| Search latency | P95 under 3 seconds for warm indexed queries. | Set benchmark repository and hardware first. |
| Graph navigation | P95 under 2 seconds for bounded subgraph query. | Use node/depth caps and indexes. |
| Chat first token | P95 under 5 seconds for typical question. | Provider/network dependent; measure separately. |
| Citation validity | At least 98% of returned citations resolve to correct snapshot/file/lines in evaluation set. | Citation validity is not the same as answer correctness. |
| Cross-file QA | Evaluate against curated multi-file question set; report accuracy and evidence recall. | Do not claim a universal accuracy figure. |
| Patch validation | 100% of exported patches pass diff integrity checks; test pass status always shown. | Not every generated patch must pass tests. |
| Security scan | Report scanner coverage and tool failures for every run. | No scan can prove absence of vulnerabilities. |

## 16.3 AI evaluation dataset

- Create 5–10 representative repositories with different sizes and supported languages.
- Prepare questions whose answers require one file, multiple files, graph traversal, API tracing and dependency reasoning.
- Create ground-truth source spans for each expected answer.
- Include negative questions where repository evidence is absent; expected behaviour is explicit uncertainty.
- Create seeded bug, code smell and vulnerable-code fixtures with known findings.
- Evaluate generated patches against hidden tests and human review.
- Track retrieval recall@k, citation precision, groundedness, answer correctness, false-positive rate and latency.

# 17. Observability, Cost and Operations

## 17.1 Telemetry

- Structured logs include request_id, trace_id, user_id (non-sensitive internal ID), repo_id, snapshot_id, job_id and stage.
- OpenTelemetry traces connect API request → queue task → parser → graph/vector operations → LLM calls.
- Metrics: queue depth, job duration, parse coverage, files/second, embedding throughput, graph query latency, retrieval latency, token usage, provider errors and patch validation outcomes.
- Never log source code or secrets by default. Add explicit redaction and sampling policies.

## 17.2 Cost controls

- Use deterministic static analysis before LLM calls; invoke models only for relevant findings.
- Cache file summaries and explanations by content hash, snapshot and prompt version.
- Use smaller models for classification/reranking and stronger models for difficult reasoning.
- Limit retrieved chunks and context expansion; summarize large files structurally.
- Enforce per-user/per-repository token and run budgets.
- Expose run cost estimates and actual usage to project administrators.

# 18. Deployment and Environment Design

## 18.1 Local development topology

| Container/service | Purpose | Typical local port / note |
| --- | --- | --- |
| web | Vite React frontend | 5173 |
| api | FastAPI application | 8000 |
| worker | Celery worker | No public port |
| scheduler (optional) | Periodic cleanup/re-index tasks | No public port |
| postgres | Relational metadata | 5432 |
| neo4j | Graph database | 7474 HTTP, 7687 Bolt |
| redis | Queue/cache | 6379 |
| object storage (optional) | S3-compatible local storage | Use internal network only |
| sandbox runner | Disposable test execution workers | No public API |

## 18.2 Environment variables

| Variable | Service | Purpose / handling |
| --- | --- | --- |
| DATABASE_URL | API/worker | PostgreSQL DSN; secret manager. |
| NEO4J_URI / USER / PASSWORD | API/worker | Neo4j connection; secret manager. |
| REDIS_URL | API/worker | Queue/cache DSN. |
| GITHUB_APP_ID / PRIVATE_KEY | GitHub adapter | App credentials; never commit. |
| GITHUB_WEBHOOK_SECRET | API | Webhook signature validation. |
| LLM_PROVIDER / LLM_API_KEY | AI service | Provider selection and secret key. |
| EMBEDDING_MODEL / EMBEDDING_DIM | Indexer/API | Must match persisted index metadata. |
| FAISS_INDEX_DIR | Indexer/worker | Persistent index storage. |
| REPOSITORY_WORKSPACE_DIR | Ingestion/worker | Restricted temporary source workspace. |
| SESSION_SECRET | API | Session cookie signing (one session mechanism, no parallel JWT); rotate and keep out of source control. |
| OTEL_EXPORTER_ENDPOINT | All services | Telemetry collector. |
| GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET | API | GitHub App user authorization (server-side only). |
| TOKEN_ENCRYPTION_KEY_ID | API/worker | Reference to the managed key that encrypts oauth_connections tokens; the key itself is never stored in the database. |
| APP_BASE_URL / CORS_ALLOWED_ORIGINS | API | OAuth redirect validation and strict CORS. |
| LLM_MODEL / RERANKER_MODEL | AI service | Pinned names recorded with every run. |
| OBJECT_STORAGE_URL / BUCKET / credentials | API/worker | Snapshot artifacts, patches, reports. |
| SANDBOX_RUNTIME / SANDBOX_IMAGE_PREFIX / SANDBOX_LIMITS | Sandbox runner | Runtime, images and CPU/memory/time quotas. |
| MAX_REPO_SIZE_MB / MAX_FILE_SIZE_KB / MAX_FILES / PARSE_TIMEOUT_S | Ingestion | Quotas from 5.2. |
| RUN_TOKEN_BUDGET_DEFAULT / USER_DAILY_TOKEN_BUDGET | API/agents | Cost controls from 17.2. |
| SNAPSHOT_RETENTION_COUNT | Scheduler | Retention from 5.7. |

## 18.3 Deployment stages

1. Local development with Docker Compose and seeded sample repositories.
2. Shared development environment with isolated test GitHub App and non-production data.
3. Staging with realistic repository sizes, observability, security tests and backup/restore validation.
4. Production deployment with managed PostgreSQL/Redis/Neo4j or hardened self-hosted services, encrypted storage, secrets manager and restricted network access.
5. Release process: migrations → deploy API/workers → smoke test ingestion/search/permissions → enable feature flag → monitor.

# 19. Suggested Repository / Monorepo Structure

```text
codepilot/
  apps/
    web/                  # React + TypeScript frontend
    api/                  # FastAPI application and API routers
    worker/               # Celery tasks and worker entrypoints
  packages/
    contracts/            # OpenAPI-generated TS/Python contracts
    ui/                   # Shared frontend components
  services/
    auth/
    github/
    repository/
    ingestion/
    parsing/
    symbol_resolution/
    graph/
    indexing/
    retrieval/
    rag/
    context/              # Context Builder (A7)
    architecture/         # components, diagrams (A2)
    dependency_analysis/  # modules, metrics, cycles (A4)
    documentation/        # doc runs (A6)
    agents/
    debugging/
    quality/
    improvements/         # suggestions (M3)
    security/
    patching/             # Patch Core + validation
    testing/
    sandbox/              # sandbox runner and images
    pull_requests/
  core/
    config/
    logging/
    telemetry/
    permissions/
    errors/
    providers/
  migrations/
  infra/
    docker/
    compose/
    scripts/
  tests/
    unit/
    integration/
    contract/
    e2e/
    fixtures/
  docs/
    architecture/
    api/
    decisions/
  .env.example
  docker-compose.yml
  README.md
```

# 20. Implementation Roadmap and Team Work Allocation

## 20.1 Recommended implementation phases

| Phase | Deliverables | Exit gate |
| --- | --- | --- |
| 0. Engineering setup | Repo structure, CI, Docker Compose, DB migrations, auth skeleton, API contracts, logging. | Every teammate can run the stack; migrations and tests pass. |
| 1. Basic foundation | GitHub integration, import lifecycle, tree/code viewer, search (including variables), summaries, explanation, repo management. | Basic 7 demonstrated end-to-end on sample repositories. |
| 2. Advanced intelligence | Cross-file graph with path and impact queries, architecture diagrams, bug/smell analysis (findings schema, run model, sandbox-lite), module dependency, whole-codebase QA, docs with Patch Core, context engine. | Advanced 7 have source-grounded outputs and graph/code navigation. |
| 3. Mastermind analysis | Agent orchestrator, debugging, suggestions, patch validation and sandbox execution, test generation, security scan, PR review and publishing. | Mastermind 7 work with approvals, evidence and audit logs. |
| 4. Hardening | Evaluation, performance, security, deployment, docs, observability and demo scenarios. | Release checklist passes; limitations and supported languages documented. |

## 20.2 Parallel team ownership (suggested)

| Workstream | Primary ownership | Deliverables |
| --- | --- | --- |
| Frontend | Frontend developers | Dashboard, explorer, Monaco, graph, chat, findings, patch diff, PR review UI. |
| Backend/platform | Backend developers | FastAPI, auth, repository lifecycle, API contracts, jobs, permissions, persistence. |
| Parsing/graph | Parser/graph developers | Tree-sitter extractors, resolvers, Neo4j schema, graph queries, impact analysis. |
| AI/RAG | AI developers | Embedding pipeline, hybrid retrieval, citations, summaries, explanation, chat, agent orchestration. |
| Mastermind tools | AI/backend developers | Bug investigation, patch service, test runner, security tool adapters, PR review. |
| DevOps/QA | Infrastructure/QA | Docker, CI, test environments, observability, sandbox, evaluation datasets and regression suites. |

## 20.3 Dependency order

- Auth and repository authorization before any repository data access.
- Snapshot identity and ingestion lifecycle before parser/indexing features.
- Parser and normalized schema (including variables and modules) before graph, search and cross-file reasoning.
- Graph + vector index + source mapping before whole-codebase chat and context-aware answers.
- Findings schema, unified run model and sandbox-lite before bug and code smell detection (A3).
- Patch Core (diff creation, preview, export, approvals; no execution) before documentation patches (A6).
- Sandbox execution runner and patch validation before code fixes (M4) and test generation (M5).
- GitHub App tiers, webhooks and diff mapping before PR review publication.

## 20.4 Definition of Done for every feature

- Requirements and user workflow documented.
- API request/response schemas validated and OpenAPI updated.
- Database migrations and indexes included.
- Authorization, input validation, quotas and error handling implemented.
- Unit and integration tests pass.
- Frontend loading, empty, partial, error and success states implemented.
- Observability and audit events added where appropriate.
- Acceptance criteria demonstrated on at least one representative repository.
- Known limitations and unsupported cases documented.

## 20.5 Cut line if time is limited

Build vertical slices in this order and mark the rest as stretch. A feature counts as complete only when its own acceptance criteria are met; do not present a reduced version as the full requirement.

1. Core spine: B1, B2, B3, B4 (symbol + lexical first), B7, B6, B5.
2. Grounded reasoning: A7 and A5 (context envelope, hybrid retrieval, citation validation), A1, then basic A2 and A4 and deterministic-only A3 (Semgrep/Ruff plus the graph rule pack), A6 with Markdown export.
3. Analysis: M6 (Semgrep + secret scanning), M3, M2 without execution, M7 draft review without publishing, M1 with at least two agents (this satisfies its acceptance criterion).
4. Controlled change: M4 diff generation with preview and approval, M5 candidate tests, then sandbox execution, validation and PR publishing.

# 21. Feature-to-Foundation Dependency Matrix

| Feature group | Required foundations | Downstream consumers |
| --- | --- | --- |
| GitHub Integration / Repo Import | Auth, GitHub adapter, job queue, snapshot store | All 19 remaining features |
| Explorer / Search / Summaries / Explain | Parser, file inventory, symbol map, source storage, embeddings | Chat, context engine, debugging, docs, agents |
| Cross-file / Architecture / Module dependencies | Resolved imports/calls, Neo4j graph, source spans | Impact, debugging, agent analysis, PR review |
| Code quality / Security | Static tool adapters, finding schema, rule metadata, run model, sandbox-lite for config-loading tools | Suggestions, bug investigation, PR review, fixes |
| Patch Core | Diff builder, patches/patch_files tables, preview, export, approvals | Documentation patches (A6), fixes (M4), test export (M5) |
| Whole-codebase QA / Context answers | Hybrid retrieval, graph traversal, citation validator | All AI features and agent tools |
| Multi-agent analysis | Shared tools, budgets, run state machine, structured outputs | Bug investigation, improvement, security and review |
| Code fixes / Test generation | Patch lifecycle, isolated worktree, sandbox, validation | PR review and developer approval |
| Pull request reviews | GitHub App, webhook verification, diff parser, base/head snapshots | Findings, graph impact, agents, inline comments |

# 22. Risks, Trade-offs and Decisions to Record

| Risk / decision | Why it matters | Recommended mitigation |
| --- | --- | --- |
| Dual Node + Python backend | Duplicates auth, validation and business logic. | Use FastAPI as core API; keep Node only if an existing gateway need is real. |
| FAISS dimension mismatch in v1.0 | The v1.0 overview says 768 while detailed configuration says 384 for MiniLM-L6-v2. | Choose a model and assert dimension at index build/load; version index metadata. |
| Tree-sitter call resolution limits | Static syntax alone cannot resolve every dynamic call or overloaded symbol. | Store confidence and unresolved references; add language-specific resolver/type checker. |
| Graph explosion | Large repositories create huge graphs and expensive traversals. | Pagination, subgraph queries, depth caps, precomputed summaries and caching. |
| LLM hallucination | Model may invent relationships or vulnerabilities. | Evidence-only prompts, structured output, citation validation and deterministic scanners. |
| Agent complexity | Multi-agent workflows can become expensive and hard to debug. | Start with bounded sequential/parallel tasks and explicit state machine; add autonomy gradually. |
| Unsafe test execution | Untrusted code can compromise infrastructure. | Disposable sandbox, no secrets, no network by default and resource quotas. |
| Stale snapshots | Answers can cite old code after branch moves. | Pin every run to commit SHA and show snapshot in UI. |
| False security confidence | No scanner can prove code is secure. | Report tool coverage, limitations and unresolved categories. |
| Scope creep | 21 features are a large engineering project. | Deliver tier-by-tier with measurable acceptance gates. |
| Snapshot storage growth | Every snapshot duplicates metadata, graph and vector data. | Retention count, copy-forward of unchanged files, scheduled cleanup, per-user quotas (5.7). |
| Install-time code execution | npm/pip install scripts run arbitrary code even when tests are sandboxed. | Two-phase preparation, scripts disabled, hash-pinned lockfiles, explicit HIGH-RISK opt-in (14.2). |
| GitHub permission escalation | Write scopes enlarge the blast radius of a bug or prompt injection. | Tiered permissions, per-repository opt-in, no merge permission, PUBLISH approvals (15.2). |
| FAISS operational limits | Shared volume, no native filtering, deletion depends on index type. | Immutable per-snapshot indexes built from embedding_cache, or pgvector (ADR-003). |

## 22.1 Architecture Decision Records to create

- ADR-001: FastAPI-only core API vs Node gateway + FastAPI.
- ADR-002: GitHub App vs OAuth App and exact permissions.
- ADR-003: FAISS vs pgvector and index persistence strategy.
- ADR-004: Embedding model, dimension, chunking and reranking evaluation.
- ADR-005: Snapshot model and incremental indexing consistency.
- ADR-006: Agent orchestration framework and tool permission model.
- ADR-007: Sandbox runtime and network policy.
- ADR-008: Security scanning toolchain and license/availability review.
- ADR-009: GitHub-only sign-in vs additional identity providers; session cookie vs token.
- ADR-010: Snapshot retention, copy-forward indexing and policy when GitHub access is revoked.

# 23. Demo Scenarios for Team Validation

| Demo | User action | Expected result |
| --- | --- | --- |
| Import and explore | Connect GitHub, import a Python/TypeScript repository, open a file. | Commit-pinned snapshot, tree, code viewer and graph node sync. |
| Find authentication | Search 'where is refresh token validated?' | Exact/semantic hits with file and line references. |
| Understand cross-file flow | Ask 'trace request from API route to database write'. | Multi-file answer with API→handler→service→repository path. |
| Architecture overview | Open architecture diagram. | Components/layers and dependency edges with clickable source nodes. |
| Investigate bug | Paste stack trace from seeded bug fixture. | Mapped stack frames, call path, root-cause hypotheses and evidence. |
| Generate fix | Select finding and request a patch. | Diff preview, validation output and explicit approval gate. |
| Generate tests | Select a function with edge cases. | Candidate tests, execution status and coverage report. |
| Security scan | Run scan on vulnerable fixture repository. | Findings with rule IDs, severity, evidence and remediation. |
| Review PR | Open seeded PR with intentional defect. | Diff-aware findings and inline comments requiring approval to publish. |

# 24. Final Product Definition

CodePilot is complete when it can transform an authorized GitHub repository snapshot into a navigable structural and semantic knowledge base, answer repository-specific questions with verifiable evidence, and support controlled engineering workflows for analysis, debugging, improvement, fixes, testing, security and pull-request review.

The Basic tier establishes access and comprehension. The Advanced tier establishes relationship-aware repository intelligence. The Mastermind tier turns that intelligence into controlled developer assistance. These tiers should be built on one shared parsing, graph, retrieval, source-provenance and permission foundation.

## Release principle

Do not measure success by the number of buttons or agents. Measure it by whether a developer can ask a real question about a real repository, receive an accurate answer with valid source references, understand uncertainty, and safely review any proposed code change.

## Source baseline and scope note

This v2.1 specification (v2.0 audited and corrected; see Appendix A) is based on the Groove AI Master Architecture Schema v1.0 and the CodePilot Basic, Advanced and Mastermind problem-statement slides supplied in the conversation. Existing v1.0 elements are reused where relevant; additional workflows, data models, APIs, security controls, test strategies and technology recommendations are proposed engineering expansions to satisfy the CodePilot requirements. The document does not assert that the proposed features have already been implemented.

# Appendix A. Audit log (v2.0 to v2.1)

Method: each of the 21 slide requirements was traced to a feature section, API, persisted data, UI route, acceptance criteria and upstream foundations. Cross-references were then checked for undefined names, contradictions and dependency-order errors. Result: all 21 requirement names and intents were already present in v2.0; the defects were in the supporting contracts.

Findings: 1 Critical, 7 High, 19 Medium, 8 Low (35 total).

| ID | Severity | Area | Finding in v2.0 | Resolution in v2.1 | Where |
| --- | --- | --- | --- | --- | --- |
| AUD-01 | High | B4 | Slide requires searching variables, but v2.0 extracted no variable, constant or field entities, so they could not be indexed or searched. | Variable/Constant/Field entity, symbol kinds, graph label, REFERENCES edge, kind filter in search. | 6.1, 6.1.1, 6.4, B4 |
| AUD-02 | High | B2, B7, M7 | Import needed a repository_id but nothing created repository rows; no branch-list endpoint for ref selection; no PR list endpoint for M7. | POST /repositories, GET /github/repositories/{id}/branches, GET /repositories/{id}/pull-requests; repositories columns added. | B2, M7, 6.5, 11.3 |
| AUD-03 | High | A3 | Acceptance requires the UI to separate static findings, AI hypotheses and confirmed defects, but findings had no origin field; graph-based smells had no rule list. | findings.origin enum, built-in graph/metric rule pack. | A3, 6.5 |
| AUD-04 | Medium | A4 | "Module" was never defined, so DEPENDS_ON aggregation was ambiguous; no coupling formulas. | Per-language module derivation; Ca, Ce, instability, SCC cycles, centrality. | 6.1.2, A4 |
| AUD-05 | Medium | A1, A5, M2, M4, M7 | Impact analysis and path tracing are relied on by five features but had no API. | GET graph/paths and graph/nodes/{id}/impact. | A1, 11.3 |
| AUD-06 | Medium | B3 | Workflow promised jump to definition/reference; no references endpoint. | GET symbols/{id}/references. | B3 |
| AUD-07 | Medium | A2 | Workflow allowed user edits and exports; no endpoints. | PATCH diagram, export endpoint (mermaid, svg, json). | A2 |
| AUD-08 | Medium | M1 | WAITING_APPROVAL state existed with no approve endpoint; workflow always approves the plan but the state table only gated write/execute steps; no transition table. | Approval rule, approve endpoint, full transition table. | M1, 13.2 |
| AUD-09 | Medium | M3, M4 | Workflow included edit, reject, revise and create branch/PR; API only had create, validate, approve and export; approval was not bound to the diff. | PATCH, revise, reject, pull-request endpoints; approvals bound to diff_sha256; patch status model; suggestion hand-off. | M4, 14.4, 6.5 |
| AUD-10 | Medium | M7 | Comments are editable before publish but there was no edit endpoint; no way to store PR base/head snapshots; fork PRs not covered. | Comment PATCH, snapshots.kind PR_BASE/PR_HEAD, lightweight PR snapshots, fork handling. | M7, 5.5, 6.5 |
| AUD-11 | Medium | M2 | Stack-trace formats and frame-to-file mapping were unspecified; stack traces may contain secrets. | Supported formats, suffix mapping, redaction before storage and prompting. | M2 |
| AUD-12 | Critical | Data model | More than 30 tables named in feature sections (for example file_summaries, retrieval_traces, agent_tasks, review_comments) were never defined in 6.5; call_sites, modules and api_endpoints were also missing although entities and graph edges required them. | 3 core tables added and 39 feature-owned tables defined in 6.6; run tables unified under analysis_runs.run_type. | 6.5, 6.6 |
| AUD-13 | High | Data model | unique(repository_id, commit_sha) blocks re-indexing the same commit with a new parser, embedding model or profile, and contradicts "explicitly versioned" duplicate imports. | Unique key (repository_id, commit_sha, analysis_profile, ingestion_version). | 5.5, 6.5, B2 |
| AUD-14 | High | Ingestion | Incremental re-indexing deleted entities from the previous snapshot, contradicting immutable snapshots and making cited evidence unstable; FAISS in-place deletion is index-type dependent. | Copy-forward into a new snapshot, embedding_cache, fresh per-snapshot index. | 5.4, 7.2 |
| AUD-15 | Medium | Lifecycle | CANCELLED, RETRYING and DELETED were referenced but not defined; STALE both meant behind-remote and re-queueable, mutating a snapshot. | Full state table; STALE is readable and a refresh creates a new snapshot. | 5.1 |
| AUD-16 | Medium | Data model | findings lacked snapshot_id, fingerprint, tool, symbol; security scans and quality runs used different run tables; duplicate findings endpoints. | Columns added; analysis_runs.run_type; single /findings resource. | 6.5, A3, M6 |
| AUD-17 | Medium | Data model | repositories lacked provider_repo_id, visibility, default branch; users.email required although GitHub emails may be private; repository_permissions mentioned team_id with no teams. | Columns fixed; email nullable; teams deferred. | 6.5 |
| AUD-18 | Medium | B5 | Summary cache keyed by file content hash, but output includes graph-derived dependents, so it went stale when other files changed. | Deterministic parts computed live; narrative cache keyed with context_hash. | B5 |
| AUD-19 | Low | Graph | AFFECTS referenced a Patch node that does not exist; no File to Module link; no stated id scheme guaranteeing uniqueness across snapshots. | BELONGS_TO added; AFFECTS limited to Finding; snapshot-scoped ids. | 6.4 |
| AUD-20 | High | API | Inconsistent path styles (/snapshots/{sid}, /graph/{sid}, /dependencies/{sid}, bare /nodes/{id}); file paths used as URL segments, which breaks on slashes. | One path convention; ?path= query parameter; catalogue regenerated. | 11.1, 11.3 |
| AUD-21 | Medium | API | Two findings APIs and several feedback endpoints; cancel only existed for snapshots. | Single /findings, /feedback, uniform job cancel. | 11.3 |
| AUD-22 | Medium | Auth | Login page and "Email/login" had no endpoints; JWT and session secrets both listed. | GitHub-only sign-in decision, /auth/me and /auth/logout, single session mechanism. | B1, 12.1, 18.2 |
| AUD-23 | Medium | API | No progress stream or job list although the dashboard shows recent jobs and principles require observable workflows. | GET /jobs and GET /jobs/{id}/events (SSE). | B2, 11.1 |
| AUD-24 | Low | API | Chat is POST with SSE; EventSource cannot POST. | Fetch streaming and event types documented. | A5, 4 |
| AUD-25 | Low | A7 | POST /ai/answer, POST /chat and POST /ai/explain overlapped with no stated relationship. | Context Builder defined as shared service. | A7, 3.4 |
| AUD-26 | High | Sandbox | Tests run in a sandbox, but installing dependencies executes arbitrary install scripts; "allowlisted lockfile/cache" was not enough. | Two-phase prepare/execute, scripts disabled, hashes, HIGH-RISK opt-in. | 14.2, M5 |
| AUD-27 | Medium | Security | Least privilege conflicted with M4 and M7, which write to GitHub. | Three permission tiers, opt-in, no merge permission. | 15.2 |
| AUD-28 | Medium | B7 | Staleness detection, access re-verification after revocation and snapshot retention were unspecified. | Webhook or lazy check, default suspend-on-revoke policy, retention count. | 5.7 |
| AUD-29 | Medium | Ops | Missing environment variables (token encryption key, GitHub client credentials, CORS, sandbox, quotas). | Rows added. | 18.2 |
| AUD-30 | Medium | Roadmap | Advanced features needed the patch service (A6) and sandboxed analyzers (A3) that the roadmap placed in Phase 3. | Patch Core and sandbox-lite moved to Phase 2. | 20.1, 20.3, 21 |
| AUD-31 | Low | Docs | "All 20 remaining features": 21 minus the two foundation features is 19. | Corrected. | 21 |
| AUD-32 | Low | Retrieval | FAISS operational constraints (shared volume, filtering, deletion) not stated. | Constraints stated; pgvector fallback. | 7.2, 22 |
| AUD-33 | Low | Frontend | No routes for architecture, dependencies, docs, investigation, improvements, patch review, tests. | Routes added. | 12.1 |
| AUD-34 | Low | Repo layout | No service folders for context, architecture, dependency analysis, documentation, improvements, sandbox. | Folders added. | 19 |
| AUD-35 | Low | Planning | No guidance for building a coherent subset under time pressure. | Cut line added (a recommendation, not a defect). | 20.5 |

## Decisions introduced by this revision

These are recommendations; change them if the team disagrees and record the outcome as an ADR.

- GitHub is the only sign-in method in the initial release, and sessions use one cookie mechanism (ADR-009).
- Snapshots are immutable; a new commit copies forward unchanged data into a new snapshot (ADR-010).
- When GitHub access is revoked, reads of private snapshots are suspended until reconnect or delete (ADR-010).
- FAISS is kept as the baseline vector store with immutable per-snapshot indexes; pgvector remains the fallback (ADR-003).
- All runs share analysis_runs with a run_type; findings and feedback are single resources.
- Agent plans auto-start only for READ/ANALYZE-only plans within budget.

## Not verified

Tool, library and GitHub permission names were taken from the original specification and general knowledge and were not checked against current releases. Package and tool versions must still be validated and pinned as 4.2 already requires.
