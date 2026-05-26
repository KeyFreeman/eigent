# Eigent Office Architecture for Taiwan Architecture Firms

This fork is prepared for a local-first office deployment on a Windows workstation or a small office server. The intended operator is a Taiwan architecture practice that needs AI assistance for drawings, meeting notes, RFIs, code checks, bid documents, and internal knowledge lookup while keeping project data under office control.

## Recommended Runtime

Use the office sandbox instead of the cloud-connected quick start:

```powershell
.\scripts\setup-office-sandbox.ps1 -Start
npm install
npm run dev
```

The script generates `server/.env.office`, validates `server/docker-compose.office.yml`, and starts the API on `127.0.0.1:3001`. PostgreSQL and Redis stay inside Docker and are not exposed to the LAN. If another local service already uses `3001`, start the sandbox on an alternate loopback port:

```powershell
.\scripts\setup-office-sandbox.ps1 -Start -ApiPort 3002
```

For browser-based UI development, start the frontend with the same API port:

```powershell
.\scripts\start-office-ui.ps1 -ApiPort 3002
```

## Security Review Summary

Reviewed risk surfaces:

- Electron main windows, webviews, external links, update mechanism, and login browser.
- Python backend/server dependency manifests and startup scripts.
- Docker Compose defaults, database credentials, Redis, CORS, and data persistence.
- Subprocess-capable agent tools and MCP import surfaces.
- Secret-like strings in the repository.

Findings and actions:

- No intentional malware, credential exfiltration routine, or destructive payload was found in the reviewed source.
- The original development defaults connected to `dev.eigent.ai`; `.env.development` now prefers the local backend.
- Electron had permissive defaults (`webSecurity: false`, `nodeIntegration: true`, disabled update signature verification). These are now hardened by default with explicit environment-variable escape hatches.
- The separate login browser used `nodeIntegration: true` with `contextIsolation: false`; it now runs with Node disabled and context isolation enabled.
- The default server Docker Compose exposed PostgreSQL and Redis with fixed passwords. The new office compose uses generated secrets, localhost-only API publishing, internal DB/Redis networking, Redis password auth, and container privilege reduction.

Residual risks:

- The developer/code-execution agent can run local commands by design. Use it only in the Docker sandbox or a dedicated Windows VM account with restricted project folders.
- Remote MCP servers, cloud LLM providers, Slack/Google/Notion/LinkedIn connectors, and web browsing can send data outside the office if configured.
- Dependency installation downloads packages from external registries. For stricter offices, mirror npm/PyPI/Docker images into an internal registry and build from there.

## Taiwan Architecture Workflow Fit

Recommended default workflows:

- Project folder convention: `年度/案號_案名/00_合約/01_會議/02_法規/03_設計/04_BIM/05_請照/06_施工/07_發包/99_封存`.
- Each AI task should bind to one project folder and produce outputs under a task-specific subfolder.
- Store PDFs, DOCX meeting records, Excel area tables, code review notes, and BIM-exported schedules locally; avoid uploading full client folders to cloud providers.
- Use Traditional Chinese as the default user-facing language for office SOPs and prompt templates.
- Create reusable prompts for common office tasks: zoning/code checklist, meeting minutes, RFI draft, drawing issue list, bid comparison, room/area table QA, and permit submission checklist.

Suggested guardrails:

- Require human approval before sending email, Slack messages, uploading files, or modifying project documents.
- Keep browser cookies in the dedicated Eigent profile only; do not reuse the principal architect's main browser profile.
- Do not give the AI unrestricted access to accounting, HR, or confidential legal folders.
- Use local models for client-confidential documents; use cloud models only for redacted summaries or approved projects.

## Enterprise Database Plan

The current server already uses FastAPI, SQLModel/Alembic, PostgreSQL, Redis, and Celery. That is a reasonable enterprise base if it is deployed with stricter operations:

- PostgreSQL: one DB per environment, SCRAM password auth, daily logical backups, weekly restore drills, and encrypted host volume or BitLocker.
- Redis: internal-only, password-protected, append-only persistence for trigger/session durability.
- Alembic: migrations run during container startup; production should promote through dev/staging/office with backup before migration.
- Pooling: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, and `DB_POOL_RECYCLE_SECONDS` are configurable for office workload tuning.
- Audit: keep application logs for 10-30 days locally; mask secrets; export sensitive logs only with approval.
- Backup: store `postgres_data` backups in an office NAS path with project retention policy.

Small office topology:

- One Windows workstation or office mini server runs Docker Desktop.
- API exposed only on `127.0.0.1:3001`.
- Frontend Electron/Vite connects to `http://localhost:3001`.
- PostgreSQL and Redis are private Docker services.

Larger office topology:

- Put API behind an internal HTTPS reverse proxy.
- Use managed PostgreSQL or a dedicated VM with encrypted disks.
- Add SSO/AD integration before multi-user rollout.
- Add network egress allowlists for approved model providers only.

## Operational Checklist

- Run `scripts/setup-office-sandbox.ps1 -Start`.
- Confirm `server/.env.office` is never committed.
- Confirm `http://127.0.0.1:3001/health` returns `status: ok`, or use the alternate `-ApiPort` value.
- Use `.env.development` local proxy settings for frontend development.
- Configure Ollama under `Agents > Models > Ollama`, then save it as the default local provider.
- In office local mode, `POST /chat` streams responses to the selected local model through the OpenAI-compatible Ollama endpoint. Compatibility routes under `/task/...` and `/chat/{project_id}/...` are available so the browser UI does not fail with 404 while full multi-agent tool execution is being integrated.
- Before production use, review every configured model provider and MCP connector with the office data policy.
- Schedule daily PostgreSQL backups and monthly restore tests.

## Current Local Execution Scope

The hardened office sandbox is suitable for local model validation, chat history, provider configuration, and direct local LLM responses. It now supports a browser UI flow where new tasks reach Ollama instead of failing at the missing `/chat` endpoint.

The original upstream multi-agent runtime still needs a full office-safe implementation for project tool execution, including `/task/{project_id}/start` orchestration, file generation, command execution policy, and human approval checkpoints. Until that is completed, use the local chat flow for planning, drafting, checklists, and structured office output; treat actual file modification and document production as a supervised step.
