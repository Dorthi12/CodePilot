"""
Test runner script for AIservices.
Discovers and executes all unit and integration tests.
Can be run via:
    python AIservices/tests/run_tests.py
    python -m unittest discover -s AIservices/tests
"""

import sys
import unittest
from pathlib import Path

# Ensure root of project is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def run_all_tests():
    test_dir = Path(__file__).resolve().parent
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(test_dir), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
