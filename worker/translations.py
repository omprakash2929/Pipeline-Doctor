"""Hinglish translations for rule-based pipeline error diagnoses."""

from typing import Dict, Tuple

HINGLISH_TRANSLATIONS: Dict[str, Tuple[str, str]] = {
    "dependency_error": (
        "Missing ya incompatible dependency package ki dikkat hai.",
        "Package manifest (package.json, requirements.txt) check karein, version aur name verify karein, aur registry connectivity check karein.",
    ),
    "permission_error": (
        "File ya directory access permissions ki kami ki wajah se operation reject ho gaya.",
        "chmod/chown se file permissions adjust karein ya runner process ke access rights check karein.",
    ),
    "docker_build_error": (
        "Docker container image build step instruction fail ho gaya.",
        "Dockerfile me failing instruction check karein, base image aur build arguments verify karein, aur locally build karke test karein.",
    ),
    "network_error": (
        "Network connection timeout, refusal ya DNS resolution failure ki wajah se request fail ho gayi.",
        "Network connectivity, DNS settings, target service status check karein aur retry mechanism configure karein.",
    ),
    "test_failure": (
        "Ek ya zyada automated test assertions execution ke dauran fail ho gaye.",
        "Failing test output aur stack trace inspect karein, code me regression fix karein ya test assertions update karein.",
    ),
    "out_of_memory": (
        "System ya container memory limit exceed hone ki wajah se process kill (OOM) ho gaya.",
        "Container runner memory limit badhayein, heap limit raise karein ya memory usage aur parallel workers optimize karein.",
    ),
    "unknown": (
        "Known error patterns se root cause identify nahi ho paya.",
        "Full pipeline logs check karein ya AI diagnosis try karein.",
    ),
}


def get_hinglish_diagnosis(category: str, english_root_cause: str, english_fix: str) -> Tuple[str, str]:
    """Return Hinglish (root_cause, fix) for a category or fallback to English."""
    if category in HINGLISH_TRANSLATIONS:
        return HINGLISH_TRANSLATIONS[category]
    return english_root_cause, english_fix
