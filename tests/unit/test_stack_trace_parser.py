"""Unit tests for multi-language stack trace parser (AUD-11)."""

import pytest
from shared.types.investigation import StackTraceLanguage
from ai_service.debugging.stack_trace_parser import StackTraceParser


@pytest.fixture
def parser() -> StackTraceParser:
    return StackTraceParser()


def test_parse_python_traceback(parser: StackTraceParser) -> None:
    trace = """Traceback (most recent call last):
  File "app/api/routes.py", line 18, in refresh
    res = auth_service.refresh_access_token(...)
  File "app/auth/service.py", line 48, in refresh_access_token
    token = validate_token(t)
  File "app/auth/service.py", line 31, in validate_token
    raise AuthError("token expired")
AuthError: token expired"""

    repo_files = ["app/api/routes.py", "app/auth/service.py"]
    parsed = parser.parse(trace, repo_files=repo_files)

    assert parsed.language == StackTraceLanguage.PYTHON
    assert parsed.error_class == "AuthError"
    assert parsed.error_message == "token expired"
    assert len(parsed.frames) == 3

    assert parsed.frames[0].mapped_file_path == "app/api/routes.py"
    assert parsed.frames[0].line == 18
    assert parsed.frames[0].function_name == "refresh"
    assert parsed.frames[0].is_mapped is True

    assert parsed.frames[1].mapped_file_path == "app/auth/service.py"
    assert parsed.frames[1].line == 48
    assert parsed.frames[1].function_name == "refresh_access_token"

    assert parsed.frames[2].mapped_file_path == "app/auth/service.py"
    assert parsed.frames[2].line == 31
    assert parsed.frames[2].function_name == "validate_token"


def test_parse_node_v8_stack_trace(parser: StackTraceParser) -> None:
    trace = """TypeError: Cannot read properties of undefined (reading 'token')
    at AuthService.validateToken (/usr/src/app/src/auth/service.ts:42:15)
    at /usr/src/app/src/controllers/auth.controller.js:25:9
    at async /usr/src/app/src/server.js:80:12"""

    repo_files = [
        "src/auth/service.ts",
        "src/controllers/auth.controller.js",
        "src/server.js",
    ]
    parsed = parser.parse(trace, repo_files=repo_files)

    assert parsed.language == StackTraceLanguage.NODE
    assert parsed.error_class == "TypeError"
    assert "reading 'token'" in parsed.error_message
    assert len(parsed.frames) == 3

    assert parsed.frames[0].mapped_file_path == "src/auth/service.ts"
    assert parsed.frames[0].line == 42
    assert parsed.frames[0].column == 15
    assert parsed.frames[0].function_name == "AuthService.validateToken"

    assert parsed.frames[1].mapped_file_path == "src/controllers/auth.controller.js"
    assert parsed.frames[1].line == 25


def test_parse_java_stack_trace(parser: StackTraceParser) -> None:
    trace = """java.lang.NullPointerException: Token is null
    at com.codepilot.service.AuthService.refreshToken(AuthService.java:65)
    at com.codepilot.controller.AuthController.handleRefresh(AuthController.java:30)"""

    repo_files = [
        "src/main/java/com/codepilot/service/AuthService.java",
        "src/main/java/com/codepilot/controller/AuthController.java",
    ]
    parsed = parser.parse(trace, repo_files=repo_files)

    assert parsed.language == StackTraceLanguage.JAVA
    assert parsed.error_class == "java.lang.NullPointerException"
    assert parsed.error_message == "Token is null"
    assert len(parsed.frames) == 2

    assert parsed.frames[0].mapped_file_path == "src/main/java/com/codepilot/service/AuthService.java"
    assert parsed.frames[0].line == 65
    assert parsed.frames[0].function_name == "com.codepilot.service.AuthService.refreshToken"


def test_parse_go_panic_trace(parser: StackTraceParser) -> None:
    trace = """panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: code=0x1 addr=0x0 pc=0x10a2b4]
goroutine 1 [running]:
main.validateToken(0x0, 0x0)
\t/go/src/app/auth.go:35 +0x26
main.refreshToken(0x102)
\t/go/src/app/main.go:50 +0x42"""

    repo_files = ["app/auth.go", "app/main.go"]
    parsed = parser.parse(trace, repo_files=repo_files)

    assert parsed.language == StackTraceLanguage.GO
    assert parsed.error_class == "panic"
    assert "runtime error" in parsed.error_message
    assert len(parsed.frames) == 2

    assert parsed.frames[0].mapped_file_path == "app/auth.go"
    assert parsed.frames[0].line == 35
    assert parsed.frames[0].function_name == "main.validateToken"


def test_secret_redacted_inside_trace(parser: StackTraceParser) -> None:
    trace = """Traceback (most recent call last):
  File "app/auth.py", line 12, in login
    token = "sk-1234567890abcdef1234567890"
ValueError: Invalid API key sk-1234567890abcdef1234567890"""

    parsed = parser.parse(trace, repo_files=["app/auth.py"])
    assert "sk-1234567890abcdef" not in parsed.redacted_trace
    assert "[REDACTED]" in parsed.redacted_trace
