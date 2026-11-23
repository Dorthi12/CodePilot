"""
Tests for Feature 2 Context Resolution and Feature 1 Integration:
- Cross-file symbol retrieval via Feature 1 search
- Missing context detection
- Resolving code via coordinates (file_path + start_line/end_line)
- Resolving code via symbol_id
"""

import unittest

from AIservices.core.parser import index_repository
from AIservices.features.code_explanation import (
    ExplanationRequest,
    explain_code,
)


class TestExplanationContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = {
            "services/auth_service.py": """
import hashlib
from utils.token import generate_secure_token

class AuthService:
    def login(self, username: str) -> str:
        token = generate_secure_token(username)
        return token
""",
            "utils/token.py": """
import uuid

def generate_secure_token(seed: str) -> str:
    \"\"\"Generate secure token using uuid.\"\"\"
    return f"{seed}-{uuid.uuid4()}"
""",
            "client/api.py": """
def fetch_external_data():
    res = unknown_external_service_call()
    return res
""",
        }
        cls.index = index_repository("ctx-repo", "snap-c1", cls.files)

    def test_cross_file_symbol_resolution_via_feature1(self):
        # The snippet in auth_service calls generate_secure_token which is defined in utils/token.py
        snippet = """def login(self, username: str) -> str:
    token = generate_secure_token(username)
    return token"""

        req = ExplanationRequest(
            repo_id="ctx-repo",
            snapshot_id="snap-c1",
            code=snippet,
            file_path="services/auth_service.py",
            start_line=5,
            end_line=7,
        )
        resp = explain_code(req, self.index)

        # Feature 1 search should find generate_secure_token definition in utils/token.py
        rel_names = [r.name for r in resp.related_symbols]
        self.assertIn("generate_secure_token", rel_names)
        self.assertTrue(any(r.file_path == "utils/token.py" for r in resp.related_symbols))

        # Citations should include the related symbol
        cite_paths = [c.file_path for c in resp.citations]
        self.assertIn("utils/token.py", cite_paths)

    def test_missing_context_detection(self):
        # The snippet calls unknown_external_service_call which is not defined in the repository
        snippet = """def fetch_external_data():
    res = unknown_external_service_call()
    return res"""

        req = ExplanationRequest(
            repo_id="ctx-repo",
            snapshot_id="snap-c1",
            code=snippet,
            file_path="client/api.py",
        )
        resp = explain_code(req, self.index)

        # Missing context should be clearly reported in limitations
        self.assertGreater(len(resp.limitations), 0)
        self.assertTrue(any("unknown_external_service_call" in l for l in resp.limitations))

    def test_resolve_code_from_file_path_and_line_range(self):
        # Supply file_path and lines without explicit code parameter
        req = ExplanationRequest(
            repo_id="ctx-repo",
            snapshot_id="snap-c1",
            file_path="utils/token.py",
            start_line=4,
            end_line=6,
        )
        resp = explain_code(req, self.index)
        self.assertIn("generate_secure_token", resp.selected_code)
        self.assertEqual(resp.file_path, "utils/token.py")

    def test_resolve_code_from_symbol_id(self):
        # Locate symbol_id from index
        target_sym = next(s for s in self.index.symbols if s.name == "generate_secure_token")
        self.assertIsNotNone(target_sym)

        req = ExplanationRequest(
            repo_id="ctx-repo",
            snapshot_id="snap-c1",
            symbol_id=target_sym.symbol_id,
        )
        resp = explain_code(req, self.index)
        self.assertIn("generate_secure_token", resp.selected_code)
        self.assertEqual(resp.file_path, target_sym.file_path)


if __name__ == "__main__":
    unittest.main()
