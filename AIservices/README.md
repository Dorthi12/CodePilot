# CodePilot AIservices

Microservice backend implementing AI capabilities for CodePilot.

## Implemented Features
1. **Feature 1: Basic Code Search**: Multi-language symbol extraction, indexing, and ranked/filtered code search.
2. **Feature 2: AI Code Explanation**: Context-aware, structured explanations answering developer questions with repository citations and dependency grounding.

---

## Architecture & Modular Design

The service is self-contained within `AIservices/` and decoupled from the main Node.js backend and frontend.

```
AIservices/
├── api/                             # HTTP REST API layer
│   ├── __init__.py
│   ├── index_store.py               # In-memory repository index store
│   ├── routes.py                    # FastAPI endpoints (/health, /index, /search, /explain, /indexes)
│   └── schemas.py                   # HTTP request/response Pydantic models
├── core/                            # Shared base domain logic
│   ├── __init__.py
│   ├── language_utils.py            # Language detection & file extension mapping
│   ├── models.py                    # Shared domain models (CodeSymbol, RepoIndex, SearchRequest, etc.)
│   └── parser.py                    # Tree-sitter extractor with resilient multi-language fallback
├── features/                        # Dedicated modules for each AI feature
│   ├── __init__.py
│   ├── code_search/                 # Feature 1: Basic Code Search
│   │   ├── __init__.py
│   │   └── search_engine.py         # Multi-mode ranking engine (exact, symbol, fuzzy)
│   └── code_explanation/            # Feature 2: AI Code Explanation
│       ├── __init__.py
│       ├── context_resolver.py      # Cross-file symbol retrieval & missing context detection
│       ├── explanation_engine.py    # Core explanation orchestrator & response formatter
│       ├── llm_provider.py          # Gemini/OpenAI integration + deep offline static analyzer
│       └── models.py                # ExplanationRequest, ExplanationResponse, CitationItem
├── fixtures/                        # Realistic multi-language test fixtures
│   ├── __init__.py
│   └── sample_repo/                 # Python, TypeScript, Java, and Go sample code
├── tests/                           # Comprehensive test suite (67 unit & integration tests)
│   ├── __init__.py
│   ├── run_tests.py                 # Unified test runner
│   ├── test_api.py                  # API route endpoint tests (Feature 1)
│   ├── test_edge_cases.py           # Edge cases & index store CRUD (Feature 1)
│   ├── test_explanation_api.py      # REST API tests for /explain & /ai/explain (Feature 2)
│   ├── test_explanation_context.py  # Cross-file retrieval & Feature 1 integration (Feature 2)
│   ├── test_explanation_edge_cases.py# Provider failure fallback & input validation (Feature 2)
│   ├── test_explanation_engine.py   # Multi-language & question types tests (Feature 2)
│   ├── test_filters.py              # Filtering by kind, language, path prefix (Feature 1)
│   ├── test_parser.py               # Language detection, symbol extraction, indexing (Feature 1)
│   └── test_search_engine.py        # Scoring, ranking, deduplication, citations (Feature 1)
├── main.py                          # FastAPI application entry point with CORS enabled
├── requirements.txt                 # Dependencies
└── README.md                        # Documentation & Node.js backend integration guide
```

---

## Feature 2: AI Code Explanation

### Capabilities
- **Accepts Code or Coordinates**: Allows passing selected code directly, or coordinates (`file_path` + `start_line` / `end_line`), or `symbol_id`.
- **Answers Specific Developer Questions**:
  - *"What does this function do?"*
  - *"Explain this code line by line."*
  - *"Why is this condition used?"*
  - *"What is the purpose of this class?"*
  - *"Explain the algorithm used here."*
  - *"What will happen if this input is provided?"*
  - *"Are there any potential bugs or edge cases?"*
- **Feature 1 Integration**: Automatically scans the snippet for referenced symbols (functions, classes, interfaces) and invokes Feature 1 code search to retrieve their definitions from other files across the repository.
- **Missing Context & Limitations**: If a referenced function or dependency cannot be found in the repository index, the service clearly flags it under `limitations` instead of hallucinating.
- **Multi-Language Support**: Explains code in Python, JavaScript, TypeScript, Java, and Go.
- **Audience Styles**: Supports `beginner`, `technical`, and `deep`.
- **Offline & Fault-Tolerant**: Works with Google Gemini / OpenAI when API keys are configured, and includes a built-in static analysis engine that acts as an immediate zero-network fallback during outages or offline test runs.

---

## Getting Started

### Prerequisites
- Python 3.10+
- Dependencies installed:
```bash
pip install -r AIservices/requirements.txt
```

### Running the Service
```bash
python AIservices/main.py
```
Or with Uvicorn:
```bash
uvicorn AIservices.main:app --host 127.0.0.1 --port 8001 --reload
```
- API Base URL: `http://127.0.0.1:8001`
- Interactive OpenAPI Docs: `http://127.0.0.1:8001/docs`

---

## Running Tests

Run the complete test suite (both Feature 1 and Feature 2):
```bash
python AIservices/tests/run_tests.py
```
Or via `unittest`:
```bash
python -m unittest discover -s AIservices/tests
```

**Test results: 67 passed, 0 failures, 0 errors.**

---

## Node.js Backend Integration Guide

### 1. Indexing a Repository Snapshot (`POST /index`)
```http
POST http://127.0.0.1:8001/index
Content-Type: application/json

{
  "repo_id": "octocat-repo",
  "snapshot_id": "commit-abc123",
  "files": {
    "src/auth.py": "def login(): pass",
    "src/user.ts": "export interface User { id: string; }"
  }
}
```

### 2. Searching Code Symbols (`POST /search`)
```http
POST http://127.0.0.1:8001/search
Content-Type: application/json

{
  "repo_id": "octocat-repo",
  "snapshot_id": "commit-abc123",
  "query": "login",
  "top_k": 10
}
```

### 3. Explaining Code (`POST /explain` or `POST /ai/explain`)
```http
POST http://127.0.0.1:8001/explain
Content-Type: application/json

{
  "repo_id": "octocat-repo",
  "snapshot_id": "commit-abc123",
  "file_path": "src/auth.py",
  "start_line": 1,
  "end_line": 10,
  "question": "What does this function do and are there potential bugs?",
  "explanation_style": "technical"
}
```

**Response (`200 OK`):**
```json
{
  "repo_id": "octocat-repo",
  "snapshot_id": "commit-abc123",
  "file_path": "src/auth.py",
  "language": "python",
  "selected_code": "def login(): pass",
  "question": "What does this function do and are there potential bugs?",
  "explanation_style": "technical",
  "overview": "`login()` defines an authentication function in the python codebase...",
  "step_by_step": [
    "Step 1: Declares the function signature and defines input parameters.",
    "Step 2: Evaluates the expression..."
  ],
  "inputs": "No parameters required.",
  "outputs": "No explicit return statement found.",
  "important_symbols": ["Function: login"],
  "side_effects": ["Pure calculation or in-memory transformation with no external I/O side effects detected."],
  "edge_cases": ["Validate boundary inputs (empty collections, unexpected data types, zero values)."],
  "related_symbols": [
    {
      "name": "generate_token",
      "kind": "FUNCTION",
      "file_path": "src/token.py",
      "start_line": 5,
      "end_line": 9,
      "snippet": "def generate_token(): ...",
      "relevance_reason": "Referenced symbol 'generate_token' defined in src/token.py"
    }
  ],
  "citations": [
    {
      "source_id": "octocat-repo:src/auth.py:1-10",
      "file_path": "src/auth.py",
      "start_line": 1,
      "end_line": 10,
      "snippet": "def login(): pass"
    }
  ],
  "limitations": [],
  "raw_explanation": "### Overview\n..."
}
```

### 4. Node.js Client Example
```typescript
import axios from 'axios';

const AI_SERVICES_URL = process.env.AI_SERVICES_URL || 'http://127.0.0.1:8001';

export async function explainCode(params: {
  repoId: string;
  snapshotId: string;
  code?: string;
  filePath?: string;
  startLine?: number;
  endLine?: number;
  symbolId?: string;
  question?: string;
  style?: 'beginner' | 'technical' | 'deep';
}) {
  const response = await axios.post(`${AI_SERVICES_URL}/explain`, {
    repo_id: params.repoId,
    snapshot_id: params.snapshotId,
    code: params.code,
    file_path: params.filePath,
    start_line: params.startLine,
    end_line: params.endLine,
    symbol_id: params.symbolId,
    question: params.question,
    explanation_style: params.style || 'technical',
  });
  return response.data;
}
```
