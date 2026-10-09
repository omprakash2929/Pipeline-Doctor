"""LLM client integration for Bedrock and Mock fallbacks."""

from abc import ABC, abstractmethod
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Pipeline Doctor, an expert DevOps troubleshooting assistant. "
    "Analyze the CI/CD failure logs. Do not invent information; base every claim on the logs."
)


def truncate_logs(logs: str, max_lines: int = 200, max_chars: int = 12000) -> str:
    """Truncate logs keeping the last lines and at most max_chars."""
    if not isinstance(logs, str) or not logs:
        return ""
    if len(logs) > max_chars:
        logs = logs[-max_chars:]
    lines = logs.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines)


def build_prompt(logs: str, language: str = "english") -> str:
    """Build user prompt with schema and language instructions."""
    if language.lower() == "hinglish":
        language_inst = (
            "Write all explanations (summary, likely_root_cause, recommended_fix, prevention) in simple Hinglish "
            "(Hindi written in Roman script mixed with English technical terms). "
            "JSON keys and category must remain in English."
        )
    else:
        language_inst = "Write all explanations in clear English."

    return (
        f"Analyze the following CI/CD failure logs and diagnose the problem.\n"
        f"{language_inst}\n\n"
        "Return ONLY a JSON object (no markdown, no extra commentary) with the following structure:\n"
        "{\n"
        '  "summary": "Brief 1-sentence summary of the failure",\n'
        '  "category": "One of: dependency_error, permission_error, docker_build_error, network_error, test_failure, out_of_memory, unknown",\n'
        '  "severity": "One of: low, medium, high, critical",\n'
        '  "likely_root_cause": "Detailed explanation of what failed and why",\n'
        '  "evidence": ["Exact matching log line 1", "Exact matching log line 2"],\n'
        '  "recommended_fix": ["Step 1 to fix the issue", "Step 2 to fix the issue"],\n'
        '  "prevention": ["Best practice step to prevent this in future"],\n'
        '  "confidence": 0.85\n'
        "}\n\n"
        f"Logs:\n{logs}"
    )


def parse_llm_json(raw_text: str) -> Dict[str, Any]:
    """Safely extract, parse, validate, and normalize JSON from LLM output."""
    fallback_result = {
        "summary": "Automatic LLM analysis could not determine the cause.",
        "category": "unknown",
        "severity": "low",
        "likely_root_cause": "Automatic AI analysis failed or returned invalid response.",
        "evidence": [],
        "recommended_fix": ["Inspect the pipeline logs manually for error details."],
        "prevention": [],
        "confidence": 0.0,
    }

    if not isinstance(raw_text, str) or not raw_text.strip():
        logger.warning("LLM returned empty output")
        return fallback_result

    cleaned = raw_text.strip()
    # Strip markdown code blocks ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # Extract outermost JSON object if surrounded by extra commentary
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)

    try:
        data = json.loads(cleaned)
    except Exception as exc:
        logger.error("Failed to parse JSON from LLM output: %s", exc)
        return fallback_result

    if not isinstance(data, dict):
        logger.error("LLM JSON root is not an object: %s", type(data))
        return fallback_result

    # Normalize fields
    valid_categories = {
        "dependency_error",
        "permission_error",
        "docker_build_error",
        "network_error",
        "test_failure",
        "out_of_memory",
        "unknown",
    }
    raw_cat = str(data.get("category", "unknown")).lower()
    category = raw_cat if raw_cat in valid_categories else "unknown"

    valid_severities = {"low", "medium", "high", "critical"}
    raw_sev = str(data.get("severity", "medium")).lower()
    severity = raw_sev if raw_sev in valid_severities else "medium"

    raw_conf = data.get("confidence", 0.0)
    try:
        confidence = float(raw_conf)
        confidence = max(0.0, min(1.0, confidence))
    except (ValueError, TypeError):
        confidence = 0.0

    raw_evidence = data.get("evidence", [])
    if isinstance(raw_evidence, list):
        evidence = [str(line).strip() for line in raw_evidence if line][:5]
    elif isinstance(raw_evidence, str) and raw_evidence.strip():
        evidence = [raw_evidence.strip()]
    else:
        evidence = []

    raw_fix = data.get("recommended_fix", [])
    if isinstance(raw_fix, list):
        recommended_fix = [str(s).strip() for s in raw_fix if s]
    elif isinstance(raw_fix, str) and raw_fix.strip():
        recommended_fix = [raw_fix.strip()]
    else:
        recommended_fix = ["Inspect pipeline logs manually."]

    raw_prev = data.get("prevention", [])
    if isinstance(raw_prev, list):
        prevention = [str(p).strip() for p in raw_prev if p]
    elif isinstance(raw_prev, str) and raw_prev.strip():
        prevention = [raw_prev.strip()]
    else:
        prevention = []

    return {
        "summary": str(data.get("summary", "Analysis completed.")),
        "category": category,
        "severity": severity,
        "likely_root_cause": str(data.get("likely_root_cause", "Root cause identified in logs.")),
        "evidence": evidence,
        "recommended_fix": recommended_fix,
        "prevention": prevention,
        "confidence": confidence,
    }


class LLMClient(ABC):
    """Abstract interface for LLM failure analyzers."""

    @abstractmethod
    def analyze(self, logs: str, language: str = "english") -> Dict[str, Any]:
        """Analyze pipeline logs and return a structured diagnosis dictionary."""
        pass


class MockLLMClient(LLMClient):
    """Deterministic mock LLM client for local development and testing."""

    def analyze(self, logs: str, language: str = "english") -> Dict[str, Any]:
        truncated = truncate_logs(logs)
        sample_line = "exit code 1"
        for line in truncated.splitlines():
            if line.strip():
                sample_line = line.strip()
                break

        if language.lower() == "hinglish":
            return {
                "summary": "CI/CD pipeline execution ke dauran build fail ho gaya.",
                "category": "unknown",
                "severity": "high",
                "likely_root_cause": "Pipeline step me configuration syntax error ya environment variable missing lag raha hai.",
                "evidence": [sample_line],
                "recommended_fix": [
                    "Pipeline environment variables aur configuration files ko check karein",
                    "Command syntax aur build parameters ko verify karein",
                ],
                "prevention": [
                    "Pipeline pre-flight checks me environment variable validation add karein",
                    "CI configuration files ke liye schema linter use karein",
                ],
                "confidence": 0.85,
            }

        return {
            "summary": "CI/CD build failure during execution step.",
            "category": "unknown",
            "severity": "high",
            "likely_root_cause": "Configuration syntax error or missing environment variable in pipeline step.",
            "evidence": [sample_line],
            "recommended_fix": [
                "Check pipeline environment variables and configuration files",
                "Verify command syntax and build parameters",
            ],
            "prevention": [
                "Add environment variable validation to pipeline pre-flight checks",
                "Use schema linters for CI configuration files",
            ],
            "confidence": 0.85,
        }


class BedrockLLMClient(LLMClient):
    """Amazon Bedrock LLM client using boto3 and the Converse API."""

    def __init__(self, model_id: Optional[str] = None, region: Optional[str] = None) -> None:
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    def analyze(self, logs: str, language: str = "english") -> Dict[str, Any]:
        truncated = truncate_logs(logs)
        prompt = build_prompt(truncated, language=language)

        try:
            response = self.client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                system=[{"text": SYSTEM_PROMPT}],
                inferenceConfig={"temperature": 0.2, "maxTokens": 1000},
            )
            output_text = response["output"]["message"]["content"][0]["text"]
            return parse_llm_json(output_text)
        except (BotoCoreError, ClientError, Exception) as exc:
            logger.error("Amazon Bedrock Converse call failed: %s", exc)
            return parse_llm_json("")


def get_llm_client() -> LLMClient:
    """Factory choosing LLMClient implementation based on LLM_BACKEND env var."""
    backend = os.getenv("LLM_BACKEND", "mock").lower()
    if backend == "mock":
        return MockLLMClient()
    elif backend == "bedrock":
        return BedrockLLMClient()
    else:
        raise ValueError(f"Unknown LLM_BACKEND: {backend}")
