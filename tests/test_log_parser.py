"""Tests for worker.log_parser module."""

import pytest
from models.schemas import Diagnosis
from worker.log_parser import detect_error


def test_dependency_error_npm():
    logs = """
    > myapp@1.0.0 build
    > tsc && vite build
    npm ERR! code 1
    npm ERR! path /app
    npm ERR! command failed
    npm ERR! A complete log can be found in: /root/.npm/_logs/2026-10-06-debug.log
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "dependency_error"
    assert res["severity"] == "high"
    assert len(res["evidence"]) > 0
    assert any("npm ERR!" in line for line in res["evidence"])
    assert res["confidence"] > 0.0


def test_dependency_error_pip_no_matching_distribution():
    logs = """
    Collecting unknown-pkg==9.9.9
      ERROR: Could not find a version that satisfies the requirement unknown-pkg==9.9.9
      ERROR: No matching distribution found for unknown-pkg==9.9.9
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "dependency_error"
    assert res["severity"] == "high"
    assert any("No matching distribution" in line for line in res["evidence"])


def test_dependency_error_modulenotfound():
    logs = """
    Traceback (most recent call last):
      File "/app/main.py", line 4, in <module>
        import requests
    ModuleNotFoundError: No module named 'requests'
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "dependency_error"
    assert any("ModuleNotFoundError" in line for line in res["evidence"])


def test_permission_error_denied():
    logs = """
    mkdir: cannot create directory '/var/log/app': Permission denied
    chmod: changing permissions of '/var/log/app': Operation not permitted
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "permission_error"
    assert res["severity"] == "high"
    assert any("Permission denied" in line for line in res["evidence"])


def test_permission_error_eacces():
    logs = """
    [Error: EACCES: permission denied, open '/etc/ssl/certs/custom.pem'] {
      errno: -13,
      code: 'EACCES',
      syscall: 'open',
      path: '/etc/ssl/certs/custom.pem'
    }
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "permission_error"
    assert any("EACCES" in line for line in res["evidence"])


def test_docker_build_error_non_zero_code():
    logs = """
    Step 5/8 : RUN pip install -r requirements.txt
     ---> Running in 9a8b7c6d5e
    The command '/bin/sh -c pip install -r requirements.txt' returned a non-zero code: 1
    Failed to build image
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "docker_build_error"
    assert res["severity"] == "high"
    assert any("returned a non-zero code" in line or "failed to build" in line.lower() for line in res["evidence"])


def test_network_error_connection_refused():
    logs = """
    2026-10-06T12:00:01Z [error] connect ECONNREFUSED 127.0.0.1:5432
    requests.exceptions.ConnectionError: HTTPConnectionPool: Connection refused
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "network_error"
    assert res["severity"] == "medium"
    assert any("Connection refused" in line for line in res["evidence"])


def test_network_error_etimedout():
    logs = """
    Fetching remote repository https://internal.git.corp/repo.git
    fatal: unable to access 'https://internal.git.corp/repo.git': ETIMEDOUT
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "network_error"
    assert any("ETIMEDOUT" in line for line in res["evidence"])


def test_network_error_cannot_resolve_host():
    logs = """
    curl: (6) Could not resolve host: api.staging.internal
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "network_error"
    assert any("Could not resolve host" in line for line in res["evidence"])


def test_test_failure_assertion():
    logs = """
    ============================= test session starts ==============================
    tests/test_auth.py:25: in test_token_expiration
        assert token.is_valid() is True
    E   AssertionError: assert False is True
    =========================== short test summary info ============================
    FAILED tests/test_auth.py::test_token_expiration - AssertionError: assert False is True
    1 failed, 12 passed in 1.42s
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "test_failure"
    assert res["severity"] == "medium"
    assert any("AssertionError" in line or "FAILED tests" in line for line in res["evidence"])


def test_test_failure_phrase():
    logs = """
    Running unit test suite...
    Execution finished: 4 tests failed out of 20
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "test_failure"


def test_out_of_memory_oomkilled():
    logs = """
    Pod container worker was terminated: OOMKilled
    Memory limit of 512Mi exceeded
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "out_of_memory"
    assert res["severity"] == "critical"
    assert any("OOMKilled" in line for line in res["evidence"])


def test_out_of_memory_heap():
    logs = """
    <--- Last few GCs --->
    [1:0x55f9a] 15000 ms: Mark-sweep (reduce) 1395.2 (1434.1) MB, 520.1 / 0.0 ms
    <--- JS stacktrace --->
    FATAL ERROR: Ineffective mark-compacts near heap limit Allocation failed - JavaScript heap out of memory
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "out_of_memory"
    assert any("heap out of memory" in line for line in res["evidence"])


def test_out_of_memory_exit_code_137():
    logs = """
    Running step: compile model weights
    Command exited with code 137
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "out_of_memory"
    assert any("137" in line for line in res["evidence"])


def test_unknown_case():
    logs = """
    Job started on runner-01
    Setting up environment
    Compilation finished with exit code 0
    Pipeline completed successfully
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "unknown"
    assert res["confidence"] == 0.0
    assert res["evidence"] == []


def test_empty_log_case():
    for empty_input in ["", "   \n\t   ", None]:
        res = detect_error(empty_input)
        Diagnosis(**res)
        assert res["category"] == "unknown"
        assert res["confidence"] == 0.0
        assert res["evidence"] == []


def test_multi_match_picks_rule_with_most_hits():
    # 1 occurrence of permission denied, but 3 occurrences of npm ERR!
    logs = """
    chmod: permission denied for file.txt
    npm ERR! code 1
    npm ERR! syscall spawn
    npm ERR! Failed at build script
    """
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "dependency_error"
    assert len(res["evidence"]) <= 5


def test_evidence_capped_at_five_lines():
    logs = "\n".join([f"npm ERR! line {i}" for i in range(20)])
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "dependency_error"
    assert len(res["evidence"]) == 5


def test_large_log_handling():
    # 15,000 lines of noise with an out-of-memory error at the end
    noise = ["Regular log output processing item..." for _ in range(12000)]
    noise.append("fatal: OOMKilled by kernel")
    logs = "\n".join(noise)
    res = detect_error(logs)
    Diagnosis(**res)
    assert res["category"] == "out_of_memory"
    assert any("OOMKilled" in line for line in res["evidence"])
