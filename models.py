from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Priority(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass
class Story:
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    due_date: str = ""
    priority: str = Priority.MEDIUM
    assignee: str = ""
    status: str = ""
    labels: List[str] = field(default_factory=list)
    comment: str = ""
    jira_key: Optional[str] = None
    include: bool = True

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "due_date": self.due_date,
            "priority": self.priority,
            "assignee": self.assignee,
            "status": self.status,
            "labels": self.labels,
            "comment": self.comment,
            "jira_key": self.jira_key,
            "include": self.include,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Story:
        return cls(
            title=d.get("title", ""),
            description=d.get("description", ""),
            acceptance_criteria=d.get("acceptance_criteria", ""),
            due_date=d.get("due_date", ""),
            priority=d.get("priority", Priority.MEDIUM),
            assignee=d.get("assignee", ""),
            status=d.get("status", ""),
            labels=d.get("labels", []),
            comment=d.get("comment", ""),
            jira_key=d.get("jira_key"),
            include=d.get("include", True),
        )


@dataclass
class Epic:
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    due_date: str = ""
    priority: str = Priority.MEDIUM
    assignee: str = ""
    status: str = ""
    labels: List[str] = field(default_factory=list)
    comment: str = ""
    stories: List[Story] = field(default_factory=list)
    include: bool = True
    initiative_id: Optional[str] = None
    project_key: Optional[str] = None
    jira_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
            "due_date": self.due_date,
            "priority": self.priority,
            "assignee": self.assignee,
            "status": self.status,
            "labels": self.labels,
            "comment": self.comment,
            "stories": [s.to_dict() for s in self.stories],
            "include": self.include,
            "initiative_id": self.initiative_id,
            "project_key": self.project_key,
            "jira_key": self.jira_key,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Epic:
        stories = [Story.from_dict(s) for s in d.get("stories", [])]
        return cls(
            title=d.get("title", ""),
            description=d.get("description", ""),
            acceptance_criteria=d.get("acceptance_criteria", ""),
            due_date=d.get("due_date", ""),
            priority=d.get("priority", Priority.MEDIUM),
            assignee=d.get("assignee", ""),
            status=d.get("status", ""),
            labels=d.get("labels", []),
            comment=d.get("comment", ""),
            stories=stories,
            include=d.get("include", True),
            initiative_id=d.get("initiative_id"),
            project_key=d.get("project_key"),
            jira_key=d.get("jira_key"),
        )


@dataclass
class JiraConfig:
    base_url: str = ""
    username: str = ""
    api_token: str = ""
    project_key: str = ""
    ac_field_id: str = "customfield_11401"  # override via Settings if different in your Jira
    proxy_url: str = ""
    org_id: str = ""
    labels: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "base_url": self.base_url,
            "username": self.username,
            "api_token": self.api_token,
            "project_key": self.project_key,
            "ac_field_id": self.ac_field_id,
            "proxy_url": self.proxy_url,
            "org_id": self.org_id,
            "labels": self.labels,
        }

    @classmethod
    def from_dict(cls, d: dict) -> JiraConfig:
        raw_labels = d.get("labels", [])
        if isinstance(raw_labels, str):
            # Graceful handling if stored as comma-separated string
            raw_labels = [l.strip() for l in raw_labels.split(",") if l.strip()]
        return cls(
            base_url=d.get("base_url", "").rstrip("/"),
            username=d.get("username", ""),
            api_token=d.get("api_token", ""),
            project_key=d.get("project_key", ""),
            ac_field_id=d.get("ac_field_id", "customfield_11401"),
            proxy_url=d.get("proxy_url", ""),
            org_id=d.get("org_id", ""),
            labels=raw_labels,
        )

    def is_configured(self) -> bool:
        return bool(self.base_url and self.username and self.api_token and self.project_key)


@dataclass
class UploadResult:
    title: str
    issue_type: str
    success: bool
    jira_key: Optional[str] = None
    error_message: Optional[str] = None
    jira_url: Optional[str] = None
