"""Unit tests for Static Application Security Testing (SAST) and Taint Analysis (M6).

Specifications:
- Master Architecture Specification v2.1 §10 (M6), §11.3
- Security and Testing Specification v1.0 §8.9 (AI-10)
- OWASP Top 10: SQLi (CWE-89), Cmd Injection (CWE-78), Path Traversal (CWE-22),
  Deserialization (CWE-502), SSRF (CWE-918), Weak Crypto (CWE-327), XXE (CWE-611).
"""

import pytest
from ai_service.security_analysis.vulnerability_analyzer import SASTVulnerabilityAnalyzer
from shared.types.agent import FindingSeverity


@pytest.fixture
def analyzer() -> SASTVulnerabilityAnalyzer:
    return SASTVulnerabilityAnalyzer()


def test_sql_injection_detection_and_taint_path(analyzer: SASTVulnerabilityAnalyzer):
    """Detect SQL injection when user input is concatenated/interpolated into cursor.execute."""
    code = """def get_user_profile(request, db_conn):
    user_id = request.args.get("id")
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    cursor = db_conn.cursor()
    cursor.execute(query)
    return cursor.fetchone()
"""
    findings, warnings = analyzer.analyze_file("app/db/users.py", code, "snap-1", "run-1")
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "SEC-SAST-SQL-INJECTION"
    assert f.cwe == "CWE-89"
    assert f.owasp == "A03:2021-Injection"
    assert f.severity == FindingSeverity.CRITICAL
    assert "source_to_sink_path" in f.metadata
    assert len(f.metadata["source_to_sink_path"]) >= 2
    assert "remediation" in f.model_dump() and f.remediation is not None


def test_safe_sql_parameterized_query_not_flagged(analyzer: SASTVulnerabilityAnalyzer):
    """Clean code control: Parameterized queries must not trigger false positives."""
    code = """def get_user_profile_safe(request, db_conn):
    user_id = request.args.get("id")
    cursor = db_conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone()
"""
    findings, _ = analyzer.analyze_file("app/db/users.py", code, "snap-1", "run-1")
    assert len(findings) == 0


def test_command_injection_detection(analyzer: SASTVulnerabilityAnalyzer):
    """Detect OS command injection when unvalidated variables are passed to system or subprocess."""
    code = """import os
import subprocess

def ping_host(user_input):
    cmd = "ping -c 1 " + user_input
    os.system(cmd)
    subprocess.run(f"nslookup {user_input}", shell=True)
"""
    findings, _ = analyzer.analyze_file("app/net/tools.py", code, "snap-1", "run-1")
    assert len(findings) >= 2
    rules = [f.rule_id for f in findings]
    assert rules.count("SEC-SAST-COMMAND-INJECTION") >= 2
    for f in findings:
        assert f.cwe == "CWE-78"
        assert f.severity == FindingSeverity.CRITICAL


def test_safe_subprocess_call_not_flagged(analyzer: SASTVulnerabilityAnalyzer):
    """Clean code control: Tokenized subprocess.run without shell=True is safe."""
    code = """import subprocess

def safe_ping(host):
    subprocess.run(["ping", "-c", "1", host], shell=False)
"""
    findings, _ = analyzer.analyze_file("app/net/tools.py", code, "snap-1", "run-1")
    assert len(findings) == 0


def test_path_traversal_detection(analyzer: SASTVulnerabilityAnalyzer):
    """Detect arbitrary file read / path traversal via open() with unvalidated paths."""
    code = """def read_report(req):
    filename = req.params["file"]
    full_path = f"/data/reports/{filename}"
    with open(full_path, "r") as f:
        return f.read()
"""
    findings, _ = analyzer.analyze_file("app/views/reports.py", code, "snap-1", "run-1")
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "SEC-SAST-PATH-TRAVERSAL"
    assert f.cwe == "CWE-22"
    assert f.severity == FindingSeverity.HIGH


def test_insecure_deserialization_pickle_and_yaml(analyzer: SASTVulnerabilityAnalyzer):
    """Detect insecure deserialization using pickle.loads and unsafe yaml.load."""
    code = """import pickle
import yaml

def load_payload(data):
    obj1 = pickle.loads(data)
    obj2 = yaml.load(data)
    return obj1, obj2
"""
    findings, _ = analyzer.analyze_file("app/parser.py", code, "snap-1", "run-1")
    assert len(findings) == 2
    for f in findings:
        assert f.rule_id == "SEC-SAST-INSECURE-DESERIALIZATION"
        assert f.cwe == "CWE-502"
        assert f.severity == FindingSeverity.CRITICAL


def test_safe_yaml_safe_load_not_flagged(analyzer: SASTVulnerabilityAnalyzer):
    """Clean code control: yaml.load with SafeLoader is not flagged."""
    code = """import yaml

def parse_config(data):
    return yaml.load(data, Loader=yaml.SafeLoader)
"""
    findings, _ = analyzer.analyze_file("app/parser.py", code, "snap-1", "run-1")
    assert len(findings) == 0


def test_weak_cryptography_md5_sha1(analyzer: SASTVulnerabilityAnalyzer):
    """Detect usage of obsolete hashlib algorithms (MD5 / SHA1)."""
    code = """import hashlib

def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()

def sign_data(data):
    return hashlib.sha1(data.encode()).hexdigest()
"""
    findings, _ = analyzer.analyze_file("app/crypto.py", code, "snap-1", "run-1")
    assert len(findings) == 2
    for f in findings:
        assert f.rule_id == "SEC-SAST-WEAK-CRYPTOGRAPHY"
        assert f.cwe == "CWE-327"
        assert f.severity == FindingSeverity.MEDIUM


def test_ssrf_detection(analyzer: SASTVulnerabilityAnalyzer):
    """Detect SSRF vulnerability with unvalidated HTTP requests."""
    code = """import requests

def fetch_webhook(query_params):
    target = query_params.get("url")
    return requests.get(target).text
"""
    findings, _ = analyzer.analyze_file("app/webhooks.py", code, "snap-1", "run-1")
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "SEC-SAST-SSRF"
    assert f.cwe == "CWE-918"
    assert f.severity == FindingSeverity.HIGH


def test_xxe_detection(analyzer: SASTVulnerabilityAnalyzer):
    """Detect XML entity expansion / XXE risk with standard ElementTree parsers."""
    code = """from xml.etree import ElementTree

def parse_xml_payload(xml_data):
    return ElementTree.fromstring(xml_data)
"""
    findings, _ = analyzer.analyze_file("app/xml_util.py", code, "snap-1", "run-1")
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "SEC-SAST-XXE-INJECTION"
    assert f.cwe == "CWE-611"
