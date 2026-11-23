import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, computed_field


class RepositoryImportRequest(BaseModel):
    url: str = Field(..., description="GitHub repository URL (e.g. https://github.com/owner/repo) or owner/repo format", min_length=3)
    branch: Optional[str] = Field(None, description="Branch to track and analyze, defaults to default_branch")


class RepositoryResponse(BaseModel):
    id: uuid.UUID
    owner_user_id: uuid.UUID
    provider: str
    provider_repo_id: str
    owner: str
    name: str
    canonical_url: str
    visibility: str
    default_branch: str
    tracked_branch: str
    description: Optional[str] = None
    language: Optional[str] = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    size_kb: int = 0
    status: str
    analysis_status: str
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    model_config = ConfigDict(from_attributes=True)


class RepositoryImportEventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    repository_id: Optional[uuid.UUID] = None
    provider: str
    provider_repo_id: Optional[str] = None
    repo_name: str
    source_url: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GitHubRepoPickerItem(BaseModel):
    id: int
    name: str
    full_name: str
    owner: str
    owner_avatar_url: Optional[str] = None
    html_url: str
    description: Optional[str] = None
    private: bool
    visibility: str
    language: Optional[str] = None
    default_branch: str = "main"
    stargazers_count: int = 0
    forks_count: int = 0
    updated_at: str
    is_imported: bool = False


class GitHubRepoListResponse(BaseModel):
    repositories: List[GitHubRepoPickerItem]
    page: int
    per_page: int
    has_more: bool = False
