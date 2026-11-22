"""
Tests for Feature 2: AI Code Explanation Engine across languages and question types.
"""

import unittest

from AIservices.core.parser import index_repository
from AIservices.features.code_explanation import (
    ExplanationRequest,
    ExplanationStyle,
    explain_code,
)


class TestExplanationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = {
            "services/auth.py": """
import hashlib

SECRET_KEY = "vault-key"

def hash_password(password: str) -> str:
    \"\"\"Hash password with sha256.\"\"\"
    if not password:
        raise ValueError("Password cannot be empty")
    return hashlib.sha256(password.encode()).hexdigest()
""",
            "models/user.ts": """
export interface User {
    id: string;
    email: string;
}

export class UserManager {
    private users: User[] = [];

    public addUser(user: User): boolean {
        if (!user.email.includes("@")) {
            return false;
        }
        this.users.push(user);
        return true;
    }
}
""",
            "algo/search.py": """
def binary_search(arr: list[int], target: int) -> int:
    left = 0
    right = len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
""",
            "service/Order.java": """
package com.shop;

public class OrderService {
    public double calculateDiscount(double total, int memberLevel) {
        if (total < 0) {
            throw new IllegalArgumentException("Negative total");
        }
        if (memberLevel >= 2) {
            return total * 0.15;
        }
        return 0.0;
    }
}
""",
            "worker/queue.go": """
package worker

import "fmt"

func ProcessQueue(items []string) error {
    for i, item := range items {
        if item == "" {
            continue
        }
        fmt.Println(i, item)
    }
    return nil
}
""",
        }
        cls.index = index_repository("explain-repo", "snap-v1", cls.files)

    def test_explain_python_function(self):
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code="""def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")
    return hashlib.sha256(password.encode()).hexdigest()""",
            explanation_style=ExplanationStyle.TECHNICAL,
        )
        resp = explain_code(req, self.index)
        self.assertEqual(resp.repo_id, "explain-repo")
        self.assertEqual(resp.language, "python")
        self.assertIn("hash_password", resp.overview)
        self.assertGreater(len(resp.step_by_step), 0)
        self.assertIsNotNone(resp.inputs)
        self.assertIsNotNone(resp.outputs)
        self.assertIn("raw_explanation", resp.model_dump())
        self.assertIn("Overview", resp.raw_explanation)

    def test_explain_typescript_class_and_method(self):
        code = """export class UserManager {
    private users: User[] = [];

    public addUser(user: User): boolean {
        if (!user.email.includes("@")) {
            return false;
        }
        this.users.push(user);
        return true;
    }
}"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            file_path="models/user.ts",
            explanation_style=ExplanationStyle.TECHNICAL,
        )
        resp = explain_code(req, self.index)
        self.assertEqual(resp.language, "typescript")
        self.assertIn("UserManager", resp.overview)
        self.assertTrue(any("addUser" in s or "UserManager" in s for s in resp.important_symbols))

    def test_explain_java_method(self):
        code = """public double calculateDiscount(double total, int memberLevel) {
    if (total < 0) {
        throw new IllegalArgumentException("Negative total");
    }
    if (memberLevel >= 2) {
        return total * 0.15;
    }
    return 0.0;
}"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            file_path="service/Order.java",
        )
        resp = explain_code(req, self.index)
        self.assertEqual(resp.language, "java")
        self.assertIn("calculateDiscount", resp.overview)
        self.assertIn("total", resp.inputs)

    def test_explain_go_loop(self):
        code = """func ProcessQueue(items []string) error {
    for i, item := range items {
        if item == "" {
            continue
        }
        fmt.Println(i, item)
    }
    return nil
}"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            file_path="worker/queue.go",
        )
        resp = explain_code(req, self.index)
        self.assertEqual(resp.language, "go")
        self.assertIn("ProcessQueue", resp.overview)

    def test_question_line_by_line(self):
        code = """def add(a, b):
    result = a + b
    return result"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            question="Explain this code line by line.",
        )
        resp = explain_code(req, self.index)
        self.assertIn("line-by-line", resp.overview.lower())
        self.assertGreaterEqual(len(resp.step_by_step), 2)

    def test_question_why_condition_used(self):
        code = """def validate_age(age):
    if age < 0:
        raise ValueError("Invalid age")
    return True"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            question="Why is this condition used?",
        )
        resp = explain_code(req, self.index)
        self.assertIn("condition", resp.overview.lower())
        self.assertTrue("guard" in resp.overview.lower() or "validation" in resp.overview.lower())

    def test_question_algorithm_explanation(self):
        code = """def binary_search(arr, target):
    left = 0
    right = len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            question="Explain the algorithm used here.",
        )
        resp = explain_code(req, self.index)
        self.assertIn("algorithm", resp.overview.lower())

    def test_question_edge_cases_and_bugs(self):
        code = """def divide(a, b):
    return a / b"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            question="Are there any potential bugs or edge cases?",
        )
        resp = explain_code(req, self.index)
        self.assertGreater(len(resp.edge_cases), 0)
        self.assertTrue(any("zero" in ec.lower() for ec in resp.edge_cases))

    def test_beginner_explanation_style(self):
        code = """def square(n):
    return n * n"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            explanation_style=ExplanationStyle.BEGINNER,
        )
        resp = explain_code(req, self.index)
        self.assertEqual(resp.explanation_style, "beginner")
        self.assertIn("simple terms", resp.overview.lower())

    def test_deep_explanation_style(self):
        code = """def square(n):
    return n * n"""
        req = ExplanationRequest(
            repo_id="explain-repo",
            snapshot_id="snap-v1",
            code=code,
            explanation_style=ExplanationStyle.DEEP,
        )
        resp = explain_code(req, self.index)
        self.assertEqual(resp.explanation_style, "deep")
        self.assertIn("core component", resp.overview.lower())


if __name__ == "__main__":
    unittest.main()
