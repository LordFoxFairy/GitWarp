from __future__ import annotations

from typing import Any


def build_finding(
    code: str,
    severity: str,
    message: str,
    *,
    item: dict[str, Any] | None = None,
    path: str | None = None,
    branch: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "path": path if path is not None else (item or {}).get("path"),
        "branch": branch if branch is not None else (item or {}).get("branch"),
        "agent_id": agent_id if agent_id is not None else (item or {}).get("agent_id"),
    }


def summarize_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    by_severity: dict[str, int] = {}
    by_code: dict[str, int] = {}
    for finding in findings:
        by_severity[finding["severity"]] = by_severity.get(finding["severity"], 0) + 1
        by_code[finding["code"]] = by_code.get(finding["code"], 0) + 1
    return {"total": len(findings), "by_severity": by_severity, "by_code": by_code}


def doctor_check(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    finding = {"code": code, "severity": severity, "message": message}
    if details:
        finding["details"] = details
    return finding
