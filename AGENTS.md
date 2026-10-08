# Pipeline Doctor

AI-powered CI/CD failure analyzer. A failed pipeline sends its logs, the tool finds the root cause, suggests a fix, and explains it in English or Hinglish.

## Stack
- Python 3.12, FastAPI, boto3
- AWS: SQS (queue), DynamoDB (results), Bedrock (LLM), CloudWatch (monitoring)
- Docker
- Deploy: AWS Elastic Beanstalk (web environment + worker environment)

## Architecture
```
GitHub Actions (on failure)
        |
        v
FastAPI (web env)  -->  SQS  -->  Worker (worker env, sqsd -> POST /process)
                                      |
                                      v
                          Log parser (rules) -- known error --> diagnosis
                                      |
                                   unknown
                                      v
                                  Bedrock LLM
                                      |
                                      v
                                  DynamoDB  -->  Dashboard / Telegram alert
```

## Project structure
```
pipeline-doctor/
├── api/
│   ├── main.py
│   ├── routes/ (analyze.py, webhook.py)
│   └── services/ (queue.py, store.py, github.py)
├── worker/
│   ├── worker.py
│   ├── analyzer.py
│   ├── log_parser.py
│   └── llm.py
├── models/schemas.py
├── static/ (dashboard: index.html)
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Rules (always follow)
- Build locally first. AWS services sit behind small interfaces (`queue.py`, `store.py`, `llm.py`) with local/mock implementations. Switch implementations with an env var (e.g. `BACKEND=local|aws`).
- Rule-based parser first. Use the LLM only for errors the parser marks as `unknown`.
- Never hardcode credentials. Use env vars locally and an IAM instance role on Elastic Beanstalk.
- Keep code simple. Add basic pytest tests for every module.
- Small steps. Work on ONE step at a time, run the tests, then explain what you changed. Do not start the next step until the user says so.
- Elastic Beanstalk worker environments do not run a polling loop. The built-in sqsd daemon reads SQS and sends an HTTP POST to the app, so the worker must expose `POST /process` and return 200 on success (non-200 means retry). A local polling loop is only for local testing.
- Protect the webhook with a shared secret header (`X-PD-Secret`).
- Do not add: Kubernetes, Terraform, complex auth, RBAC, mobile app, multiple LLM providers, fancy animations.

## Progress checklist
Update this as steps finish.

- [x] Step 1: Skeleton, `/health`, `/api/analyze` (dummy)
- [x] Step 2: Rule-based log parser
- [x] Step 3: Queue and store abstractions (local), `GET /api/analysis/{job_id}`
- [ ] Step 4: Dashboard
- [ ] Step 5: Bedrock LLM fallback + Hinglish mode
- [ ] Step 6: Real SQS + DynamoDB + `POST /process`
- [ ] Step 7: GitHub Actions webhook
- [ ] Step 8: Dockerfile + Elastic Beanstalk deploy (web + worker)
- [ ] Step 9: Telegram alert, CloudWatch metrics, README, architecture diagram, demo video

---

## Step-by-step guide

### Step 1: Skeleton + basic API
Goal: runnable FastAPI app.
- Create the folder structure above, `requirements.txt` (fastapi, uvicorn, pydantic, boto3, pytest, httpx).
- `GET /health` returns `{"status": "healthy"}`.
- `POST /api/analyze` accepts `repository`, `pipeline`, `status`, `logs`, `language` (Pydantic schema) and returns `{"job_id": "pd-xxxxxx", "status": "queued"}` (dummy for now).
- Add pytest tests for both endpoints.
- Done when: `uvicorn api.main:app --reload` runs, `/docs` works, tests pass.

### Step 2: Rule-based log parser (core)
Goal: `detect_error(logs)` in `worker/log_parser.py`.
- Return `category`, `severity`, `root_cause`, `fix`, `evidence` (matching log lines), `confidence`.
- Categories: dependency_error (npm/pip), permission_error, docker_build_error, network_error, test_failure, out_of_memory, unknown.
- Add pytest cases using realistic sample logs for each category.
- Done when: all categories are detected and `unknown` is returned for unmatched logs.

### Step 3: Queue + store abstractions (local first)
Goal: full flow working with no AWS.
- `api/services/queue.py` and `api/services/store.py` as interfaces with in-memory implementations.
- `/api/analyze` pushes a job. A local worker function processes it (parser, then save result).
- Add `GET /api/analysis/{job_id}` returning status (`queued`, `processing`, `done`) and the result.
- Done when: submit logs, then fetch the diagnosis by `job_id`, all locally.

### Step 4: Dashboard
Goal: simple HTML/JS page served by FastAPI (`static/index.html`).
- Form: repository, pipeline dropdown, language dropdown (English/Hinglish), logs textarea, Analyze button.
- Poll `GET /api/analysis/{job_id}` and show: root cause, confidence, evidence, recommended fix, prevention.
- Keep it clean and minimal, no heavy frameworks.
- Done when: the full flow works from the browser.

### Step 5: Bedrock LLM fallback + Hinglish
Goal: `worker/llm.py` using boto3 Bedrock runtime.
- Called only when the parser returns `unknown`.
- Prompt: Pipeline Doctor, expert DevOps assistant, return JSON with summary, category, likely_root_cause, evidence, recommended_fix, prevention, confidence. Do not invent information.
- Support `language=hinglish` (simple Hinglish explanation).
- Parse JSON safely; on any error return a graceful fallback result.
- Provide a mock LLM for local tests and an env var to choose mock or real.
- Done when: unknown logs produce a structured diagnosis (mock locally, real with AWS credentials).

### Step 6: Real SQS + DynamoDB
Goal: swap in AWS implementations.
- boto3 implementations of queue and store, selected by `BACKEND=aws`.
- DynamoDB table `PipelineAnalysis` with `job_id` as partition key; fields: repository, pipeline, status, created_at, category, root_cause, fix, language, confidence.
- Add `POST /process` for sqsd: receives the SQS message body, runs the analyzer, saves to DynamoDB, returns 200.
- Done when: a job goes API, SQS, `/process`, DynamoDB, and `GET /api/analysis/{job_id}` returns it (test with a real SQS queue and table in a dev AWS account).

### Step 7: GitHub Actions integration
Goal: real failure triggers analysis.
- `POST /api/webhook/github`: validate the `X-PD-Secret` header; accept repository, run_id, and the last ~200 log lines; queue the job.
- Provide a sample workflow step:
  ```yaml
  - name: Send failure to Pipeline Doctor
    if: failure()
    run: |
      curl -X POST "$PIPELINE_DOCTOR_URL/api/webhook/github" \
        -H "Content-Type: application/json" \
        -H "X-PD-Secret: ${{ secrets.PD_SECRET }}" \
        -d '{"repository":"${{ github.repository }}","run_id":"${{ github.run_id }}","status":"failed","logs":"..."}'
  ```
- Fetching full logs via the GitHub API is optional and comes later.
- Done when: a deliberately broken workflow run produces a diagnosis on the dashboard.

### Step 8: Docker + Elastic Beanstalk
Goal: deploy to AWS.
- Dockerfile: python:3.12-slim, install requirements, run uvicorn on port 8000 (expose what EB's Docker platform expects).
- Test locally: `docker build -t pipeline-doctor .` and `docker run -p 8000:8000 pipeline-doctor`.
- Web environment: API + dashboard behind a load balancer, auto scaling min 1, max 3.
- Worker environment: same code, connected to the SQS queue, sqsd posts to `/process`.
- IAM instance role with least privilege: SQS, DynamoDB, Bedrock, CloudWatch. Config via EB environment variables; GitHub token and `PD_SECRET` as secrets.
- Done when: the live EB URL works and the end-to-end demo runs on AWS.

### Step 9: Polish
- Telegram alert after analysis (repository, status, root cause, confidence, link).
- CloudWatch metrics: pipelines_analyzed, analysis_success_rate, analysis_duration, queue_depth, llm_errors.
- README with architecture diagram, setup, and demo steps.
- Demo video.

## Demo flow (for judges)
1. Push intentionally broken code
2. GitHub Actions fails
3. Pipeline Doctor receives the failure
4. SQS gets the job
5. Worker analyzes the logs
6. Bedrock identifies the root cause (if the parser doesn't know it)
7. DynamoDB stores the result
8. Dashboard shows the diagnosis
9. Telegram sends an alert

## Priorities
- Must have: FastAPI, SQS, worker, Bedrock, DynamoDB, GitHub Actions, dashboard, Docker, Elastic Beanstalk.
- Good to have: Hinglish, Telegram, CloudWatch, Jenkins support.
- Skip for now: Kubernetes, Terraform, complex auth, animations, mobile app, multiple LLM providers, RBAC.