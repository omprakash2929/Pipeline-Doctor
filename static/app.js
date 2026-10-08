// Pipeline Doctor frontend logic

const SAMPLE_LOG = `> frontend-app@1.0.0 build
> tsc && vite build

npm ERR! code 1
npm ERR! path /app
npm ERR! command failed
npm ERR! command sh -c tsc && vite build
npm ERR! src/App.tsx(3,24): error TS2307: Cannot find module '@tanstack/react-query' or its corresponding type declarations.
npm ERR! A complete log can be found in: /root/.npm/_logs/2026-10-08-debug-0.log`;

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("analyze-form");
  const repoInput = document.getElementById("repo-input");
  const pipelineSelect = document.getElementById("pipeline-select");
  const languageSelect = document.getElementById("language-select");
  const logsInput = document.getElementById("logs-input");
  const submitBtn = document.getElementById("submit-btn");
  const loadSampleBtn = document.getElementById("load-sample-btn");
  const errorBox = document.getElementById("error-message");
  const loadingIndicator = document.getElementById("loading-indicator");
  const loadingText = document.getElementById("loading-text");
  const placeholderBox = document.getElementById("result-placeholder");
  const resultContainer = document.getElementById("result-container");
  const recentTbody = document.getElementById("recent-tbody");
  const refreshRecentBtn = document.getElementById("refresh-recent-btn");

  let pollingTimer = null;

  // Load sample failure
  loadSampleBtn.addEventListener("click", () => {
    repoInput.value = "omprakash/demo-app";
    pipelineSelect.value = "GitHub Actions";
    languageSelect.value = "english";
    logsInput.value = SAMPLE_LOG;
    hideError();
  });

  // Refresh recent analyses
  refreshRecentBtn.addEventListener("click", () => {
    loadRecentAnalyses();
  });

  // Form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();

    const logs = logsInput.value.trim();
    if (!logs) {
      showError("Logs cannot be empty or whitespace only.");
      return;
    }

    const payload = {
      repository: repoInput.value.trim(),
      pipeline: pipelineSelect.value,
      language: languageSelect.value,
      logs: logsInput.value,
      status: "failed",
    };

    setLoading(true, "Submitting failure logs...");

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (response.status === 422) {
        const errJson = await response.json().catch(() => null);
        let detail = "Validation error: Logs cannot be empty.";
        if (errJson && errJson.detail) {
          detail = Array.isArray(errJson.detail)
            ? errJson.detail.map((d) => d.msg || d).join(", ")
            : errJson.detail;
        }
        showError(detail);
        setLoading(false);
        return;
      }

      if (!response.ok) {
        showError(`Request failed with status ${response.status}: ${response.statusText}`);
        setLoading(false);
        return;
      }

      const data = await response.json();
      const jobId = data.job_id;

      // Start polling
      pollAnalysis(jobId);
    } catch (err) {
      showError(`Network error: ${err.message || "Failed to reach server"}`);
      setLoading(false);
    }
  });

  // Polling function (every 1s, max 30s)
  function pollAnalysis(jobId) {
    const startTime = Date.now();
    const timeoutMs = 30000;
    setLoading(true, `Analyzing job ${jobId}...`);

    if (pollingTimer) {
      clearInterval(pollingTimer);
    }

    pollingTimer = setInterval(async () => {
      const elapsed = Date.now() - startTime;
      if (elapsed >= timeoutMs) {
        clearInterval(pollingTimer);
        pollingTimer = null;
        setLoading(false);
        showError("Analysis timed out after 30 seconds. Please check back later.");
        return;
      }

      try {
        const res = await fetch(`/api/analysis/${encodeURIComponent(jobId)}`);
        if (res.status === 404) {
          clearInterval(pollingTimer);
          pollingTimer = null;
          setLoading(false);
          showError(`Analysis job ${jobId} was not found (404).`);
          return;
        }

        if (!res.ok) {
          // Continue polling on transient errors unless 4xx/5xx repeat
          return;
        }

        const job = await res.json();
        if (job.status === "done" || job.status === "failed") {
          clearInterval(pollingTimer);
          pollingTimer = null;
          setLoading(false);
          renderResultCard(job);
          loadRecentAnalyses();
        }
      } catch (pollErr) {
        // Transient network error while polling, keep trying until timeout
      }
    }, 1000);
  }

  // Safe DOM result renderer (escapes all raw inputs)
  function renderResultCard(data) {
    placeholderBox.classList.add("hidden");
    resultContainer.classList.remove("hidden");
    resultContainer.textContent = ""; // Clear existing

    // Header container
    const headerDiv = document.createElement("div");
    headerDiv.className = "result-header";

    const badgeFailed = document.createElement("span");
    badgeFailed.className = "badge badge-failed";
    badgeFailed.textContent = "Pipeline Failed";
    headerDiv.appendChild(badgeFailed);

    const metaSpan = document.createElement("span");
    metaSpan.className = "result-meta";
    metaSpan.textContent = `${data.repository || "Unknown repo"} • ${data.pipeline || "Pipeline"} • Job: ${data.job_id}`;
    headerDiv.appendChild(metaSpan);

    resultContainer.appendChild(headerDiv);

    // If job failed internally
    if (data.status === "failed") {
      const failedBlock = document.createElement("div");
      failedBlock.className = "alert-box error";
      failedBlock.style.marginTop = "14px";
      failedBlock.textContent = `Analysis failed: ${data.error || "Internal error occurred"}`;
      resultContainer.appendChild(failedBlock);
      return;
    }

    // Category and Severity Badges
    const badgesRow = document.createElement("div");
    badgesRow.style.display = "flex";
    badgesRow.style.gap = "8px";
    badgesRow.style.marginTop = "12px";

    const categoryBadge = document.createElement("span");
    categoryBadge.className = "badge badge-category";
    categoryBadge.textContent = `Category: ${data.category || "unknown"}`;
    badgesRow.appendChild(categoryBadge);

    if (data.severity) {
      const sevBadge = document.createElement("span");
      const sevKey = String(data.severity).toLowerCase();
      sevBadge.className = `badge badge-severity-${sevKey}`;
      sevBadge.textContent = `Severity: ${data.severity.toUpperCase()}`;
      badgesRow.appendChild(sevBadge);
    }
    resultContainer.appendChild(badgesRow);

    // Root Cause block
    const rootCauseBlock = document.createElement("div");
    rootCauseBlock.className = "result-section-block";
    const rcTitle = document.createElement("div");
    rcTitle.className = "result-section-title";
    rcTitle.textContent = "Likely Root Cause";
    const rcContent = document.createElement("div");
    rcContent.className = "result-content-text";
    if (data.category === "unknown") {
      rcContent.textContent = "Could not identify this error yet. Full logs may need manual review or AI diagnosis.";
    } else {
      rcContent.textContent = data.root_cause || "No root cause details available.";
    }
    rootCauseBlock.appendChild(rcTitle);
    rootCauseBlock.appendChild(rcContent);
    resultContainer.appendChild(rootCauseBlock);

    // Confidence Progress Bar
    const confBlock = document.createElement("div");
    confBlock.className = "result-section-block";
    const confTitle = document.createElement("div");
    confTitle.className = "result-section-title";
    confTitle.textContent = "Detection Confidence";
    confBlock.appendChild(confTitle);

    const confVal = typeof data.confidence === "number" ? Math.round(data.confidence * 100) : 0;
    const confContainer = document.createElement("div");
    confContainer.className = "confidence-container";

    const bar = document.createElement("div");
    bar.className = "confidence-bar";
    const fill = document.createElement("div");
    fill.className = "confidence-fill";
    fill.style.width = `${confVal}%`;
    bar.appendChild(fill);

    const pctText = document.createElement("span");
    pctText.className = "confidence-pct";
    pctText.textContent = `${confVal}%`;

    confContainer.appendChild(bar);
    confContainer.appendChild(pctText);
    confBlock.appendChild(confContainer);
    resultContainer.appendChild(confBlock);

    // Evidence List
    if (Array.isArray(data.evidence) && data.evidence.length > 0) {
      const evBlock = document.createElement("div");
      evBlock.className = "result-section-block";
      const evTitle = document.createElement("div");
      evTitle.className = "result-section-title";
      evTitle.textContent = "Evidence (Matching Log Lines)";
      evBlock.appendChild(evTitle);

      const evList = document.createElement("ul");
      evList.className = "evidence-list";
      data.evidence.forEach((line) => {
        const item = document.createElement("li");
        item.className = "evidence-item";
        item.textContent = line;
        evList.appendChild(item);
      });
      evBlock.appendChild(evList);
      resultContainer.appendChild(evBlock);
    }

    // Recommended Fix
    if (data.fix) {
      const fixBlock = document.createElement("div");
      fixBlock.className = "result-section-block";
      const fixTitle = document.createElement("div");
      fixTitle.className = "result-section-title";
      fixTitle.textContent = "Recommended Fix";
      const fixContent = document.createElement("div");
      fixContent.className = "result-content-text";
      fixContent.textContent = data.fix;
      fixBlock.appendChild(fixTitle);
      fixBlock.appendChild(fixContent);
      resultContainer.appendChild(fixBlock);
    }

    // Prevention section (only if data has prevention)
    if (data.prevention) {
      const prevBlock = document.createElement("div");
      prevBlock.className = "result-section-block";
      const prevTitle = document.createElement("div");
      prevTitle.className = "result-section-title";
      prevTitle.textContent = "Prevention";
      const prevContent = document.createElement("div");
      prevContent.className = "result-content-text";
      prevContent.textContent = data.prevention;
      prevBlock.appendChild(prevTitle);
      prevBlock.appendChild(prevContent);
      resultContainer.appendChild(prevBlock);
    }
  }

  // Load recent analyses into table
  async function loadRecentAnalyses() {
    try {
      const res = await fetch("/api/analyses?limit=10");
      if (!res.ok) return;
      const analyses = await res.json();

      recentTbody.textContent = "";

      if (!analyses || analyses.length === 0) {
        const emptyTr = document.createElement("tr");
        const emptyTd = document.createElement("td");
        emptyTd.colSpan = 6;
        emptyTd.className = "text-center text-muted";
        emptyTd.textContent = "No recent analyses yet";
        emptyTr.appendChild(emptyTd);
        recentTbody.appendChild(emptyTr);
        return;
      }

      analyses.forEach((item) => {
        const tr = document.createElement("tr");
        tr.title = "Click to view analysis";

        const tdJob = document.createElement("td");
        tdJob.textContent = item.job_id;
        tdJob.style.fontWeight = "600";
        tr.appendChild(tdJob);

        const tdRepo = document.createElement("td");
        tdRepo.textContent = item.repository;
        tr.appendChild(tdRepo);

        const tdPipe = document.createElement("td");
        tdPipe.textContent = item.pipeline;
        tr.appendChild(tdPipe);

        const tdStatus = document.createElement("td");
        const statusBadge = document.createElement("span");
        statusBadge.className = "badge";
        if (item.status === "done") {
          statusBadge.className += " badge-severity-low";
        } else if (item.status === "failed") {
          statusBadge.className += " badge-failed";
        } else {
          statusBadge.className += " badge-severity-medium";
        }
        statusBadge.textContent = item.status;
        tdStatus.appendChild(statusBadge);
        tr.appendChild(tdStatus);

        const tdCategory = document.createElement("td");
        tdCategory.textContent = item.category || "-";
        tr.appendChild(tdCategory);

        const tdCreated = document.createElement("td");
        if (item.created_at) {
          const date = new Date(item.created_at);
          tdCreated.textContent = isNaN(date.getTime()) ? item.created_at : date.toLocaleTimeString();
        } else {
          tdCreated.textContent = "-";
        }
        tr.appendChild(tdCreated);

        // Click row to show details
        tr.addEventListener("click", () => {
          renderResultCard(item);
        });

        recentTbody.appendChild(tr);
      });
    } catch (e) {
      // Ignore background refresh errors
    }
  }

  function setLoading(isLoading, text = "Analyzing...") {
    if (isLoading) {
      submitBtn.disabled = true;
      loadingIndicator.classList.remove("hidden");
      loadingText.textContent = text;
    } else {
      submitBtn.disabled = false;
      loadingIndicator.classList.add("hidden");
    }
  }

  function showError(msg) {
    errorBox.textContent = msg;
    errorBox.classList.remove("hidden");
  }

  function hideError() {
    errorBox.textContent = "";
    errorBox.classList.add("hidden");
  }

  // Initial load
  loadRecentAnalyses();
});
