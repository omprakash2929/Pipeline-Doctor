"""Rule-based CI/CD failure log parser."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

MAX_LOG_CHARS = 2_000_000  # 2 MB limit
MAX_LOG_LINES = 5_000


@dataclass
class ErrorRule:
    category: str
    severity: str
    patterns: List[re.Pattern]
    root_cause: str
    fix: str
    confidence: float = 0.9


RULES: List[ErrorRule] = [
    ErrorRule(
        category="dependency_error",
        severity="high",
        patterns=[
            re.compile(r"npm ERR!", re.IGNORECASE),
            re.compile(r"No matching distribution", re.IGNORECASE),
            re.compile(r"ModuleNotFoundError", re.IGNORECASE),
            re.compile(r"Could not find a version that satisfies the requirement", re.IGNORECASE),
            re.compile(r"Cannot find module", re.IGNORECASE),
        ],
        root_cause="Missing or incompatible dependency package.",
        fix="Check package manifest (e.g. package.json, requirements.txt), verify package names and versions, and ensure registry connectivity.",
        confidence=0.95,
    ),
    ErrorRule(
        category="permission_error",
        severity="high",
        patterns=[
            re.compile(r"permission denied", re.IGNORECASE),
            re.compile(r"\bEACCES\b", re.IGNORECASE),
            re.compile(r"Operation not permitted", re.IGNORECASE),
        ],
        root_cause="File or directory operation rejected due to insufficient permissions.",
        fix="Adjust file system permissions using chmod/chown or verify runner process privileges.",
        confidence=0.95,
    ),
    ErrorRule(
        category="docker_build_error",
        severity="high",
        patterns=[
            re.compile(r"failed to build", re.IGNORECASE),
            re.compile(r"returned a non-zero code", re.IGNORECASE),
            re.compile(r"executor failed running", re.IGNORECASE),
            re.compile(r"ERROR:\s*failed to solve", re.IGNORECASE),
        ],
        root_cause="Docker container image build step failed.",
        fix="Inspect Dockerfile instructions leading up to failure, verify build arguments and base image availability, and test building locally.",
        confidence=0.90,
    ),
    ErrorRule(
        category="network_error",
        severity="medium",
        patterns=[
            re.compile(r"connection refused", re.IGNORECASE),
            re.compile(r"\bETIMEDOUT\b", re.IGNORECASE),
            re.compile(r"could not resolve host", re.IGNORECASE),
            re.compile(r"\bENOTFOUND\b", re.IGNORECASE),
            re.compile(r"Temporary failure in name resolution", re.IGNORECASE),
        ],
        root_cause="Network connection failed due to host resolution, timeout, or refused connection.",
        fix="Verify network connectivity, DNS settings, target service availability, and consider configuring retry mechanisms.",
        confidence=0.90,
    ),
    ErrorRule(
        category="test_failure",
        severity="medium",
        patterns=[
            re.compile(r"FAILED tests?", re.IGNORECASE),
            re.compile(r"AssertionError", re.IGNORECASE),
            re.compile(r"tests? failed", re.IGNORECASE),
            re.compile(r"===+\s*FAILURES\s*===+", re.IGNORECASE),
            re.compile(r"\bFAIL:\s+", re.IGNORECASE),
        ],
        root_cause="One or more automated tests failed during execution.",
        fix="Inspect failing test outputs and stack traces to resolve code regressions or update obsolete test assertions.",
        confidence=0.95,
    ),
    ErrorRule(
        category="out_of_memory",
        severity="critical",
        patterns=[
            re.compile(r"\bOOMKilled\b", re.IGNORECASE),
            re.compile(r"heap out of memory", re.IGNORECASE),
            re.compile(r"exit(?:ed)?\s+(?:with\s+)?code\s*[:=]?\s*137", re.IGNORECASE),
            re.compile(r"code\s*[:=]?\s*137\b", re.IGNORECASE),
            re.compile(r"died with signal 9\b", re.IGNORECASE),
        ],
        root_cause="Process was killed due to exceeding system or container memory limits (OOM).",
        fix="Increase container memory allocation, raise heap limits, or optimize memory usage and job concurrency.",
        confidence=0.95,
    ),
]


def detect_error(logs: str) -> Dict[str, Any]:
    """Detect root cause error category and details from pipeline logs using rule patterns.

    Args:
        logs: Pipeline execution log string.

    Returns:
        dict with keys: category, severity, root_cause, fix, evidence, confidence.
    """
    if not isinstance(logs, str) or not logs.strip():
        return {
            "category": "unknown",
            "severity": "low",
            "root_cause": "Empty or missing log content.",
            "fix": "Ensure pipeline logs are properly captured and provided.",
            "evidence": [],
            "confidence": 0.0,
        }

    # Handle very large logs safely by keeping the tail where failures occur
    if len(logs) > MAX_LOG_CHARS:
        logs = logs[-MAX_LOG_CHARS:]

    lines = logs.splitlines()
    if len(lines) > MAX_LOG_LINES:
        lines = lines[-MAX_LOG_LINES:]

    best_rule: ErrorRule | None = None
    best_hits = 0
    best_evidence: List[str] = []

    for rule in RULES:
        rule_hits = 0
        rule_evidence: List[str] = []

        for line in lines:
            line_has_match = False
            for pattern in rule.patterns:
                matches = pattern.findall(line)
                if matches:
                    rule_hits += len(matches)
                    line_has_match = True

            if line_has_match:
                cleaned_line = line.strip()
                if cleaned_line and cleaned_line not in rule_evidence and len(rule_evidence) < 5:
                    rule_evidence.append(cleaned_line)

        if rule_hits > best_hits:
            best_hits = rule_hits
            best_rule = rule
            best_evidence = rule_evidence

    if best_rule is not None and best_hits > 0:
        return {
            "category": best_rule.category,
            "severity": best_rule.severity,
            "root_cause": best_rule.root_cause,
            "fix": best_rule.fix,
            "evidence": best_evidence[:5],
            "confidence": best_rule.confidence,
        }

    return {
        "category": "unknown",
        "severity": "low",
        "root_cause": "Unable to determine root cause from known error patterns.",
        "fix": "Review full pipeline logs or submit for AI diagnosis.",
        "evidence": [],
        "confidence": 0.0,
    }
