"""
Tests for language detection, symbol extraction, and repository indexing.
"""

import unittest

from AIservices.core.language_utils import detect_language, is_supported
from AIservices.core.models import SupportedLanguage, SymbolKind
from AIservices.core.parser import extract_symbols, index_repository


class TestLanguageUtils(unittest.TestCase):
    def test_detect_language(self):
        self.assertEqual(detect_language("main.py"), SupportedLanguage.PYTHON)
        self.assertEqual(detect_language("src/index.js"), SupportedLanguage.JAVASCRIPT)
        self.assertEqual(detect_language("src/component.tsx"), SupportedLanguage.TYPESCRIPT)
        self.assertEqual(detect_language("service/Order.java"), SupportedLanguage.JAVA)
        self.assertEqual(detect_language("pkg/queue.go"), SupportedLanguage.GO)
        self.assertEqual(detect_language("README.md"), SupportedLanguage.UNKNOWN)
        self.assertEqual(detect_language("config.json"), SupportedLanguage.UNKNOWN)

    def test_is_supported(self):
        self.assertTrue(is_supported("app.py"))
        self.assertTrue(is_supported("app.ts"))
        self.assertTrue(is_supported("Main.java"))
        self.assertFalse(is_supported("data.csv"))
        self.assertFalse(is_supported("image.png"))


class TestParserExtraction(unittest.TestCase):
    def test_extract_python_symbols(self):
        code = """import os
import sys
from typing import Optional

SECRET_KEY = "12345"
timeout = 30

class AuthService:
    def __init__(self):
        pass

    def authenticate_user(self, username: str) -> bool:
        return True

def standalone_helper():
    pass
"""
        symbols, warnings = extract_symbols(code, "services/auth.py", "repo1", "snap1")
        self.assertGreater(len(symbols), 0)

        names = {s.name: s for s in symbols}
        self.assertIn("AuthService", names)
        self.assertEqual(names["AuthService"].kind, SymbolKind.CLASS)

        self.assertIn("authenticate_user", names)
        self.assertEqual(names["authenticate_user"].kind, SymbolKind.FUNCTION)

        self.assertIn("standalone_helper", names)
        self.assertEqual(names["standalone_helper"].kind, SymbolKind.FUNCTION)

        # Check location fields
        for s in symbols:
            self.assertGreaterEqual(s.start_line, 1)
            self.assertGreaterEqual(s.end_line, s.start_line)
            self.assertTrue(s.file_path == "services/auth.py")
            self.assertTrue(len(s.snippet) > 0)
            self.assertTrue(len(s.symbol_id) > 0)

    def test_extract_typescript_symbols(self):
        code = """import { Client } from 'lib';

export interface UserProfile {
    id: string;
    name: string;
}

export type Status = 'active' | 'inactive';

export class ProfileManager {
    updateProfile(id: string): void {}
}

export function getProfile(id: string): UserProfile {
    return { id, name: 'test' };
}

export const defaultUser = { id: '1' };
"""
        symbols, warnings = extract_symbols(code, "src/profile.ts", "repo1", "snap1")
        self.assertGreater(len(symbols), 0)

        names = {s.name: s for s in symbols}
        self.assertIn("UserProfile", names)
        self.assertIn("Status", names)
        self.assertIn("ProfileManager", names)
        self.assertIn("getProfile", names)

    def test_extract_java_symbols(self):
        code = """package com.example;

import java.util.List;

public class PaymentProcessor {
    public void processPayment(double amount) {
        System.out.println(amount);
    }
}
"""
        symbols, warnings = extract_symbols(code, "src/PaymentProcessor.java", "repo1", "snap1")
        self.assertGreater(len(symbols), 0)
        names = {s.name: s for s in symbols}
        self.assertIn("PaymentProcessor", names)
        self.assertEqual(names["PaymentProcessor"].kind, SymbolKind.CLASS)

    def test_extract_go_symbols(self):
        code = """package worker

import "fmt"

type WorkerQueue struct {
    id string
}

func RunWorker(id string) error {
    return nil
}
"""
        symbols, warnings = extract_symbols(code, "worker.go", "repo1", "snap1")
        self.assertGreater(len(symbols), 0)
        names = {s.name: s for s in symbols}
        self.assertIn("WorkerQueue", names)
        self.assertIn("RunWorker", names)

    def test_empty_or_whitespace_file(self):
        symbols, warnings = extract_symbols("   \n\n  \t ", "empty.py", "repo1", "snap1")
        self.assertEqual(symbols, [])
        self.assertEqual(warnings, [])

    def test_unsupported_file_warning(self):
        symbols, warnings = extract_symbols("Hello world text file", "notes.txt", "repo1", "snap1")
        self.assertEqual(symbols, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn("Unsupported file type", warnings[0])

    def test_deterministic_symbol_id(self):
        code = "def calculate_sum(a, b):\n    return a + b\n"
        s1, _ = extract_symbols(code, "math.py", "repo1", "snap1")
        s2, _ = extract_symbols(code, "math.py", "repo1", "snap1")
        self.assertEqual(len(s1), len(s2))
        self.assertEqual(s1[0].symbol_id, s2[0].symbol_id)

    def test_index_repository_multi_file(self):
        files = {
            "app/auth.py": "def login(): pass\ndef logout(): pass",
            "app/models.ts": "export interface Token { value: string; }",
            "docs/README.md": "# Documentation file",
        }
        index = index_repository("test-repo", "v1.0", files)
        self.assertEqual(index.repo_id, "test-repo")
        self.assertEqual(index.snapshot_id, "v1.0")
        self.assertGreaterEqual(len(index.symbols), 3)
        self.assertTrue(any("Skipped unsupported file" in w for w in index.warnings))


if __name__ == "__main__":
    unittest.main()
