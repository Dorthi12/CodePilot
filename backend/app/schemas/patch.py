"""M4 patch API contracts and validation schemas."""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class ValidationPolicy(BaseModel):
    syntax: bool = True
    lint: bool = False
    tests: bool = False
    security: bool = True


class FixCreateRequest(BaseModel):
    snapshot_id: str
    finding_id: Optional[str] = None
    suggestion_id: Optional[str] = None
    task: Optional[str] = Field(default=None, max_length=4000)
    target_files: List[str] = Field(default_factory=list, max_length=20)
    constraints: List[str] = Field(default_factory=list, max_length=30)
    validation_policy: ValidationPolicy = Field(default_factory=ValidationPolicy)
    unified_diff: Optional[str] = Field(default=None, max_length=2_000_000)

    @model_validator(mode="after")
    def exactly_one_source(self):
        if sum(bool(v) for v in (self.finding_id, self.suggestion_id, self.task)) != 1:
            raise ValueError("Provide exactly one of finding_id, suggestion_id, or task")
        return self


class FixEditRequest(BaseModel):
    unified_diff: str = Field(min_length=1, max_length=2_000_000)
    rationale: Optional[str] = Field(default=None, max_length=8000)


class FixReviseRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)


class FixValidateRequest(BaseModel):
    consent_execute_tests: bool = False


class FixApproveRequest(BaseModel):
    scope: Literal["EXPORT", "PUBLISH"] = "EXPORT"
    diff_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class FixRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class FixPullRequestCreate(BaseModel):
    publish_approval_id: str
    branch_name: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    body: Optional[str] = Field(default="", max_length=10000)
