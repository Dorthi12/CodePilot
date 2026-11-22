"""Agent types and enumerations matching CodePilot Master Specification."""

from enum import Enum


class AgentRole(str, Enum):
    ORCHESTRATOR = "ORCHESTRATOR"
    ARCHITECTURE = "ARCHITECTURE"
    SECURITY = "SECURITY"
    CODE_QUALITY = "CODE_QUALITY"
    PERFORMANCE = "PERFORMANCE"
    TESTING = "TESTING"
    REVIEW = "REVIEW"


class RunStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ToolPermissionLevel(str, Enum):
    READ = "READ"
    ANALYZE = "ANALYZE"
    EXECUTE = "EXECUTE"
    WRITE = "WRITE"
    PUBLISH = "PUBLISH"


class FindingOrigin(str, Enum):
    STATIC_TOOL = "STATIC_TOOL"
    GRAPH_RULE = "GRAPH_RULE"
    AI_HYPOTHESIS = "AI_HYPOTHESIS"
    CONFIRMED = "CONFIRMED"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    FIXED = "FIXED"


class VerificationCheck(str, Enum):
    CITATION = "CITATION"
    DUPLICATE = "DUPLICATE"
    SCHEMA = "SCHEMA"
