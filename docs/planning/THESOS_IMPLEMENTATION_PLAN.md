# Thesos: Full Implementation Plan

Status: revised implementation baseline with an early hosted private-alpha track
Scope: frontend, backend, corpus and retrieval, LLM integration, agent runtime, operations  
Primary deployment: one OCI ARM64 VM with PostgreSQL, Caddy, and Docker Compose  
Related documents: `scribbledoc.md`, `THESOS_VM_MANIFEST.md`, `THESOS_PROMPTING_NOTES.md`

This document defines how Thesos should be built. It is deliberately more specific than a product brief: it establishes component boundaries, data contracts, control flow, safety limits, testing expectations, and release gates.

The current delivery order inserts Phases 3A-3C between the generic LLM loop and corpus work. These phases move the existing prototype onto PostgreSQL, add allowlisted authentication and enforceable usage limits, and deploy a deliberately small private alpha at `cephalonthesos.com`. This does not declare the ungrounded Phase 3 model intelligent or production-ready; the hosted alpha remains visibly labelled as an early, non-source-backed evaluation build while permission and corpus work are pending.

Where this document conflicts with the current VM manifest, this document represents the newer application decision. The manifest should be amended before deployment.

## 1. Product Objective

Thesos is an unofficial Warframe research assistant that should answer ordinary questions quickly while also supporting deeper research, build planning, deterministic build mathematics, and live read-only data tools.

The product must feel like consulting a knowledgeable system, but correctness and inspectability take priority over theatrical autonomy. It should:

- Answer Warframe questions with linked, inspectable sources.
- Distinguish durable game knowledge from live or rotation-sensitive state.
- Retrieve before making factual Warframe claims.
- Use deterministic code for calculations and structured API operations.
- State uncertainty and assumptions instead of filling gaps silently.
- Support long research without allowing unbounded autonomous loops.
- Remain affordable on a two-core, 12 GB ARM64 host.
- Preserve user privacy by default and avoid permanent chat storage unless explicitly requested.
- Support a mandatory-login private alpha without turning account creation into public self-service registration.

## 2. Architectural Principles

1. **The application owns the loop.** The model may plan and select tools within a bounded workflow, but Python controls state transitions, budgets, retries, permissions, and stop conditions.
2. **Retrieval is independent of generation.** Corpus ingestion, candidate retrieval, reranking, and context packing remain replaceable without changing the agent or provider integration.
3. **Tools are narrow domain services.** The model receives typed Warframe tools, not unrestricted HTTP, SQL, shell, or browser access.
4. **Calculations are deterministic.** The LLM identifies inputs and explains results; versioned Python code performs arithmetic.
5. **Evidence is first-class state.** Sources are not decorative links added after generation. The agent builds an evidence ledger before drafting an answer.
6. **Simple questions remain simple.** Most turns should not invoke a planner, critic, subagent, or neural reranker.
7. **Durability is selective but consistent.** Every public run has a durable identity and event history. Long workflows additionally checkpoint model and tool steps.
8. **No hidden product dependency on one provider.** Code refers to model roles and capabilities, not hard-coded provider model names.
9. **Privacy and cost are runtime policies.** Provider eligibility, retention, quotas, and data collection settings are enforced by code and configuration.
10. **Agent quality is measured.** Tool choice, retrieval coverage, citation support, calculation correctness, latency, and cost all receive regression tests.

## 3. Selected Stack

### 3.1 Frontend

- TypeScript with strict checking.
- React and React Router Framework Mode.
- Vite as the build system.
- Tailwind CSS with project-owned design tokens and a small component layer.
- Static pre-rendering for `/`, `/about`, `/privacy`, and `/terms`; no production Node server.
- IndexedDB for browser-local conversations and settings.
- Native `fetch`, `ReadableStream`, and server-sent events for run updates.
- Vitest, React Testing Library, axe, and Playwright.

Avoid a large client state framework initially. Use route state, component reducers, and small context providers. Add a dedicated state library only if measured complexity justifies it.

### 3.2 Backend

- Python 3.12, subject to final ARM64 dependency validation.
- FastAPI and Pydantic.
- Pydantic AI for typed agents, toolsets, model abstraction, event streaming, usage limits, and testing.
- DBOS with PostgreSQL for durable agent workflows and queues.
- Psycopg 3 async connection pooling.
- HTTPX with one application-lifetime async client.
- PostgreSQL for corpus metadata, runtime state, cache, operations, and DBOS state.
- BM25S for the initial lexical index, stored on the attached volume and memory-mapped by serving processes.
- Alembic for application-owned schema migrations.
- `pwdlib[argon2]` for versioned Argon2id password hashing and verification.
- Resend behind a narrow transactional-email adapter for verification and password-reset messages during the private alpha.
- `uv` for dependency locking and reproducible environments.
- Ruff, Pyright, pytest, pytest-asyncio, Hypothesis, and respx.

### 3.3 LLM and retrieval

- Pydantic AI native `OpenRouterModel` initially.
- Pydantic AI native Mistral provider when direct Mistral access is added.
- `FallbackModel` for eligible pre-response failures across providers.
- No LiteLLM service initially.
- No embeddings or neural reranker in the initial retrieval path.
- Exact entity lookup, fielded BM25 retrieval, reciprocal rank fusion, metadata scoring, deduplication, and context packing.

## 4. System Topology

```text
Browser
  |
  | HTTPS
  v
Cloudflare DNS/proxy and Turnstile
  |
  v
Caddy
  |-- static pre-rendered React application
  `-- /api/* -> FastAPI
                  |
                  | create/cancel/read runs
                  v
              PostgreSQL
              |-- application data
              |-- agent run/event state
              |-- cache and usage
              `-- DBOS workflow state and queues
                  ^
                  |
             Agent worker
             |-- controller
             |-- Pydantic AI
             |-- BM25 index reader
             |-- Warframe tools
             `-- OpenRouter/Mistral clients

Scheduled one-shot containers
  |-- corpus ingestion and BM25 publication
  |-- backup
  `-- migrations
```

### 4.1 Runtime processes

Continuously running:

| Process | Initial count | Responsibility |
|---|---:|---|
| Caddy | 1 | TLS, compression, static files, reverse proxy |
| FastAPI API | 1 worker | Request validation, run creation, SSE, read APIs, admin APIs |
| Agent worker | 1 process | DBOS queues, agent workflows, provider and tool execution |
| PostgreSQL | 1 | All durable state |

The API and agent worker use the same application package but different entry points. This prevents long research from occupying the web process and allows the web process to restart while runs continue or recover.

Start with one API worker. A second API worker is permitted only after memory and connection-pool measurements. The agent worker may execute multiple I/O-bound runs concurrently, but provider, tool, and calculation semaphores enforce hard limits.

Run creation uses a transactional outbox. The API commits the `agent_run`, initial event, and dispatch record together. The worker claims dispatch records and starts a workflow whose stable workflow ID is the run ID. Dispatch is at-least-once; workflow identity and step idempotency make repeated dispatch harmless. This avoids claiming impossible exactly-once network semantics while still preventing duplicate paid work in normal failure cases.

## 5. Repository Layout

Thesos should be separated from the existing riven scanner before implementation begins.

```text
thesos/
|-- apps/
|   |-- web/
|   |   |-- app/
|   |   |   |-- components/
|   |   |   |-- features/
|   |   |   |-- routes/
|   |   |   |-- state/
|   |   |   |-- styles/
|   |   |   `-- transport/
|   |   |-- public/
|   |   `-- tests/
|   `-- server/
|       |-- veris/
|       |   |-- api/
|       |   |-- agent/
|       |   |-- cache/
|       |   |-- calculations/
|       |   |-- config/
|       |   |-- corpus/
|       |   |-- db/
|       |   |-- ingestion/
|       |   |-- llm/
|       |   |-- market/
|       |   |-- observability/
|       |   |-- retrieval/
|       |   |-- security/
|       |   `-- world_state/
|       |-- migrations/
|       `-- tests/
|-- evals/
|   |-- datasets/
|   |-- evaluators/
|   `-- reports/
|-- infra/
|   |-- compose/
|   |-- caddy/
|   |-- terraform/
|   `-- systemd/
|-- docs/
|-- scripts/
|-- compose.yaml
`-- README.md
```

Do not create a generic `utils.py`, `helpers.py`, or single agent module containing the entire system. Shared code should live beside the domain it serves.

## 6. Frontend Implementation Plan

### 6.1 Routes

| Route | Rendering | Purpose |
|---|---|---|
| `/` | Pre-rendered shell, hydrated | Landing state and active conversation |
| `/about` | Pre-rendered | Project purpose, methodology, unofficial status |
| `/privacy` | Pre-rendered | Data handling and provider disclosure |
| `/terms` | Pre-rendered | Usage terms and disclaimers |
| `/login` | Client-only | Email/password login, alpha status, and password recovery |
| `/register` | Client-only | Allowlisted email/password registration and access-request path |
| `/verify-email` | Client-only | Consume an emailed verification token without exposing it to server access logs |
| `/reset-password` | Client-only | Consume an emailed reset token and set a replacement password |
| `/account` | Client-only, protected | Session, daily allowance, reset time, and allowance requests |
| `/admin` | Client-only, role-protected | Users, access, usage, provider cost, failures, health, and later corpus operations |

Conversation and shared-answer presentation remain modes of `/`, not separate public content sections. A short share identifier may be represented by a query parameter or history state while keeping the main experience visually unchanged.

### 6.2 Main experience states

The main route has explicit UI states:

1. **Authentication required:** The visual shell remains available, but chat creation is replaced by the private-alpha login action.
2. **Empty:** Archives prompt, four suggested questions, composer, and unobtrusive remaining-allowance status.
3. **Submitting:** User message committed locally, run being accepted and one allowance unit reserved.
4. **Working:** Assistant activity summary, sources appearing, cancel control.
5. **Streaming:** Answer text arrives while citations and structured blocks resolve.
6. **Complete:** Final validated answer, sources, freshness, feedback, follow-ups.
7. **Needs clarification:** A focused question with preserved prior work.
8. **Interrupted:** Connection lost; automatic event reconnection shown unobtrusively.
9. **Failed:** Human-readable reason, retained user prompt, safe retry action.
10. **Cancelled:** Partial work clearly marked as incomplete.
11. **Allowance exhausted:** Composer is replaced by the reset time and a `Request more` action; existing local conversations remain readable.
12. **Archives unavailable:** Brief non-echoing Thesos response; composer remains available.
13. **Conversation terminated:** No assistant response; the composer is replaced by a same-scale termination banner with `New chat` and `Edit earlier message` actions.

### 6.3 Component boundaries

```text
AppShell
|-- SideNavigation
|-- ProviderPrivacyStatus
|-- ConversationViewport
|   |-- EmptyArchiveState
|   |-- MessageList
|   |   |-- UserMessage
|   |   `-- ThesosResponse
|   |       |-- ActivitySummary
|   |       |-- AnswerRenderer
|   |       |-- StructuredResultBlocks
|   |       `-- CitationDrawer
|   `-- ScrollAnchor
`-- Composer
    |-- PromptInput
    |-- ModeControl
    |-- AttachmentControl (disabled until supported)
    `-- SubmitOrCancel
```

Feature modules own their state and views:

- `chat`: conversations, turns, streaming reducer, retries.
- `sources`: citation previews, source drawer, freshness display.
- `research`: progress summary and plan status.
- `builds`: build inputs, assumptions, calculations, comparisons.
- `market`: price snapshots and listing links.
- `settings`: local history, privacy, provider preferences where permitted.
- `admin`: protected operational views.

### 6.4 Run transport

Use a two-request run protocol rather than holding the creation request open:

```text
POST /api/v1/runs
  -> 202 { run_id, event_url, cancel_url }

GET /api/v1/runs/{run_id}/events
  Accept: text/event-stream
  Last-Event-ID: optional
```

This allows browser refresh, mobile network interruption, API restart, and event replay. The SSE client must:

- Persist the latest event sequence per active run.
- Reconnect with exponential backoff and jitter.
- Supply `Last-Event-ID` on reconnect.
- Treat duplicate events as harmless.
- Stop reconnecting after terminal events.
- Show connection status only when degraded long enough to matter.

Run access is bound to an authenticated account and one server-side session represented by an opaque Secure, HttpOnly, SameSite cookie. IndexedDB stores run IDs and event positions, never an identity-provider token or reusable API bearer credential. State-changing requests require same-origin validation and CSRF protection. Signing out revokes the server session without deleting browser-local conversations; another account on the same browser must not inherit access to the prior account's server-side runs.

### 6.5 Public event contract

Every event has:

```json
{
  "event_id": "monotonic identifier",
  "run_id": "uuid",
  "type": "status.changed",
  "created_at": "RFC3339 timestamp",
  "payload": {}
}
```

Initial event types:

| Event | Purpose |
|---|---|
| `run.accepted` | Establish mode, limits, and corpus revision |
| `status.changed` | Short user-facing activity text |
| `plan.updated` | Sanitized objectives and completion, never chain-of-thought |
| `source.added` | Citation metadata available before final answer |
| `tool.started` | Safe tool label, not raw arguments or secrets |
| `tool.completed` | Outcome summary and freshness |
| `answer.started` | Clear transition into answer generation |
| `answer.delta` | Incremental display text |
| `answer.block` | Completed structured result block |
| `warning` | Assumption, stale data, partial source coverage, or quota issue |
| `response.archive_unavailable` | Approved response identifier and display copy with no echoed user or topic text |
| `conversation.terminated` | Terminal control event that replaces the composer; contains no reason or user text |
| `run.completed` | Final answer envelope and usage summary |
| `run.failed` | Typed failure and retry eligibility |
| `run.cancelled` | Terminal cancellation |

The frontend reducer must be deterministic and replayable from an event fixture. Event order and duplicate delivery require tests.

Events are durable rows before they are notifications. The worker inserts an event with a per-run monotonic sequence and commits it, then sends a PostgreSQL notification as a low-latency wake-up. The SSE endpoint always queries rows after the client's last sequence before waiting for notifications. A missed notification therefore delays delivery briefly but never loses an event.

### 6.6 Structured answer rendering

Do not make every response an unstructured Markdown blob. The final answer envelope supports:

```text
markdown answer
citations
assumptions
warnings
freshness
suggested follow-ups
structured blocks[]
```

Initial block types:

- `fact_table`
- `build_summary`
- `build_comparison`
- `calculation_breakdown`
- `market_snapshot`
- `rotation_status`
- `source_conflict`

Unknown block types fall back to a safe JSON-free explanatory presentation. Markdown is sanitized with a strict allowlist; raw HTML is never rendered.

### 6.7 Browser-local persistence

IndexedDB stores:

- Conversations and completed answer envelopes.
- Stable message IDs, edit/truncation relationships, and server-issued safety dispositions.
- User settings and privacy acknowledgement version.
- Active run IDs and latest received event IDs.
- Cached suggestion responses subject to server-provided expiry.

Local history is the default. Follow-up requests send a bounded conversation window plus an optional generated summary. The UI must make clearing all local data straightforward.

The server stores run content temporarily for execution and recovery. It also retains minimal, content-free active-history control metadata long enough to enforce a termination disposition at the backend. Creating an account does not silently enable cloud chat history: completed conversations remain browser-local unless the user explicitly creates a share or a later, separately consented synchronization feature changes this policy.

Editing a user message deletes every later turn from that conversation before submitting the replacement. The frontend removes the suffix from IndexedDB and the visible history; the backend atomically removes its corresponding active-history control records and schedules any temporary run content for purge. Content-free aggregate security metrics may remain under their ordinary retention policy. If the deleted suffix contained a terminating message, the composer returns only after the backend confirms the new history and evaluates the replacement. A page refresh or direct API submission cannot clear termination merely by hiding the banner locally.

### 6.8 Accessibility and interaction quality

- Full keyboard operation and visible focus states.
- Semantic buttons, navigation, headings, lists, and dialog behavior.
- Status updates through a restrained `aria-live` region.
- `prefers-reduced-motion` removes nonessential movement while preserving state clarity.
- Focus remains in the composer after submission unless clarification requires it elsewhere.
- Source drawers and menus trap and restore focus correctly.
- Mobile composer respects safe areas and virtual keyboards.
- Answer streaming must not continuously steal scroll position after the user scrolls upward.
- Contrast and text scaling pass WCAG AA checks.

### 6.9 Performance and SEO

- Pre-render `/`, `/about`, `/privacy`, and `/terms` at build time.
- Serve hashed immutable assets with Brotli or gzip compression.
- Route-level code splitting for admin and secondary legal pages.
- Keep the initial page functional before noncritical icons and animations load.
- Target under 170 KB gzipped first-route JavaScript before optional visualization modules.
- Include canonical URL, Open Graph metadata, structured organization/software metadata, sitemap, and robots policy.
- Do not index private runs, local conversations, admin pages, or transient shared content by default.

### 6.10 Frontend testing

- Reducer tests for every event sequence and reconnect case.
- Component tests for empty, working, streaming, complete, warning, failure, Archives-unavailable, and conversation-terminated states.
- Accessibility checks on every principal screen state.
- Playwright desktop and mobile coverage for submit, stream, reconnect, cancel, source inspection, local history, and clearing data.
- Visual regression baselines for the selected desktop and mobile design.
- Tests with slow tokens, bursty tokens, long citations, long names, and structured blocks.

## 7. Backend Implementation Plan

### 7.1 Application entry points

```text
veris.api.main:create_app       FastAPI process
veris.agent.worker:main         DBOS queue and workflow worker
veris.ingestion.cli:main        one-shot ingestion process
veris.db.migrate:main           one-shot migration process
veris.backup.cli:main           one-shot backup process
```

Application startup must validate configuration, database migrations, writable paths, active corpus revision, model-role configuration, and provider credentials. Readiness fails if required dependencies are unavailable; liveness only indicates that the process event loop remains responsive.

### 7.2 API surface

Unauthenticated:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register an allowlisted email and send its verification message |
| `POST` | `/api/v1/auth/login` | Verify email/password and establish a server session |
| `POST` | `/api/v1/auth/verify-email` | Consume a single-use email-verification token |
| `POST` | `/api/v1/auth/resend-verification` | Request another verification message with generic responses |
| `POST` | `/api/v1/auth/password/forgot` | Request a reset message without revealing account existence |
| `POST` | `/api/v1/auth/password/reset` | Consume a reset token, replace the credential, and revoke sessions |
| `POST` | `/api/v1/access-requests` | Request private-alpha access without creating an account |
| `GET` | `/api/v1/health/live` | Process liveness |
| `GET` | `/api/v1/health/ready` | Dependency readiness |

Authenticated application:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/runs` | Validate and create a turn |
| `GET` | `/api/v1/runs/{id}` | Current run snapshot |
| `GET` | `/api/v1/runs/{id}/events` | Replayable SSE stream |
| `DELETE` | `/api/v1/runs/{id}` | Request cancellation |
| `POST` | `/api/v1/runs/{id}/clarification` | Continue a suspended clarification |
| `GET` | `/api/v1/suggestions` | Reset-aware suggested prompts and cached answers |
| `POST` | `/api/v1/feedback` | Authenticated structured feedback |
| `POST` | `/api/v1/shares` | Explicitly persist a shareable answer snapshot |
| `GET` | `/api/v1/shares/{id}` | Load a shared snapshot in main-page mode |
| `PATCH` | `/api/v1/conversations/{id}/messages/{message_id}` | Edit one user message and atomically truncate all later active turns |
| `GET` | `/api/v1/me` | Account, role, session, allowance, and reset summary |
| `POST` | `/api/v1/auth/logout` | Revoke the current server session |
| `POST` | `/api/v1/auth/password/change` | Change the password after checking the current credential |
| `POST` | `/api/v1/quota-requests` | Ask an administrator for an additional allowance grant |

Admin endpoints under `/api/v1/admin/*` cover allowlist management, user suspension, session revocation, quota grants, pending access/quota requests, aggregate traffic, provider usage and cost, recent failures, service health, and later ingestion and corpus operations. Every endpoint requires the `admin` role, a recently authenticated session for mutations, CSRF protection, and an audit event. Admin authorization is enforced by the backend and never by route visibility alone.

FastAPI's OpenAPI document is the public contract. CI generates TypeScript request, response, event-payload, and error types for the web application and fails when generated artifacts are stale. Handwritten frontend interfaces must not duplicate backend schemas.

### 7.3 Request creation contract

`POST /api/v1/runs` accepts:

```text
message
bounded conversation context
requested mode: auto | quick | research
locale
platform and crossplay preferences
privacy/provider constraints
client conversation ID
idempotency key
```

Validation rules:

- Reject empty, oversized, malformed, or excessive-history requests.
- Normalize Unicode and line endings without destroying item names.
- Strip unsupported attachments rather than silently forwarding them.
- Require an idempotency key so browser retries cannot create duplicate paid runs.
- Bind run access to the authenticated account and current server session.
- Atomically reserve one daily allowance unit in the same transaction that accepts a new run; idempotent retries reuse the original reservation.
- Reject continuation when any server-validated message in the active history has a `terminate_conversation` disposition.
- Never trust client-supplied safety fields or omission of a previously flagged active message.
- Record the exact accepted privacy and model policy version.

### 7.4 Database domains

#### Corpus

- `source`
- `document`
- `document_revision`
- `document_section`
- `retrieval_chunk`
- `entity`
- `entity_alias`
- `chunk_entity`
- `corpus_revision`
- `bm25_index_manifest`
- `ingestion_run`
- `ingestion_failure`

#### Agent runtime

- `conversation_message_control`
- `agent_run`
- `agent_dispatch_outbox`
- `agent_event`
- `agent_step`
- `agent_plan_step`
- `agent_tool_call`
- `agent_evidence`
- `agent_model_call`
- `agent_clarification`
- `agent_final_answer`

#### Product and operations

- `access_allowlist`
- `access_request`
- `user_account`
- `password_credential`
- `email_action_token`
- `auth_session`
- `user_role`
- `admin_mfa`
- `user_device`
- `daily_usage_ledger`
- `quota_grant`
- `quota_request`
- `answer_cache`
- `tool_cache`
- `suggested_prompt`
- `shared_answer`
- `feedback`
- `provider_budget`
- `provider_usage`
- `rate_limit_bucket`
- `audit_event`

DBOS uses its own documented tables or schema. Application migrations must not alter DBOS-owned tables.

### 7.5 Runtime retention

Proposed private-alpha defaults:

| Data | Retention |
|---|---|
| In-progress run content | Until completion plus recovery window |
| Completed raw run content | 24 hours |
| Sanitized run metadata and usage | 30 days |
| Event payloads containing answer text | 24 hours |
| Aggregate metrics | 90 days or longer if non-identifying |
| Explicit shared answer | Until user deletion policy or expiry |
| Account and role record | While access is active, then according to the published deletion policy |
| Revoked/expired authentication session | 30 days after expiry or revocation |
| HMAC-pseudonymized IP/device security signal | 30 days unless attached to an unresolved abuse event |
| Quota ledger and grants | 90 days, then aggregate or delete |
| Security/admin audit event | 180 days by default, content-free |
| Active message safety disposition | Until the local conversation expires server-side or the message is removed from active history |

A scheduled purge must enforce retention. Removing content means removing prompts, model text, tool text that contains user material, and answer event deltas, not merely hiding them from the UI.

### 7.6 Connection and concurrency policy

Initial limits:

```text
API database pool:                 min 1, max 4
Agent worker database pool:        min 1, max 6
Interactive agent runs:            4 queued/running, tune by provider quota
Research runs:                     1 running initially
Provider concurrency:              per-provider semaphore
Warframe.market concurrency:       1-2, with endpoint-specific pacing
Calculation concurrency:           1 CPU-bound task at a time
Ingestion concurrency:             1 process, low priority
```

Never hold a database transaction or checked-out connection while waiting for a model stream. Write events and checkpoints in short, independent transactions.

### 7.7 Caching

Cache classes have distinct policies:

- **Answer cache:** normalized question, resolved entities, platform, locale, corpus revision, live-data revision, prompt version, and model-policy version. Follow-up turns also require a relevant-context hash or are ineligible.
- **Tool cache:** tool name, canonical arguments, source revision, and freshness class.
- **Retrieval cache:** normalized query, filters, corpus revision, and retrieval-policy version.
- **Suggested-answer cache:** explicit invalidation at daily or weekly Warframe reset boundaries.

Cache entries store provenance and expiry. Live data is never presented without its observed time. Cache failures must fall back to ordinary execution rather than fail the user request.

### 7.8 Private-alpha identity and access policy

The private alpha uses first-party email/password authentication. Registration deliberately collects only:

- Email address.
- Password and a client-side confirmation of that same password.
- Acceptance of the current Terms version, presented with the Privacy notice. This is a legal acknowledgement, not an additional profile field.

Thesos does not require a username, real name, date of birth, phone number, location, Warframe account name, profile image, or demographic information. The optional name currently used by the browser to address the user remains local UI preference data and is not copied into the account automatically.

Account creation remains closed:

- An administrator adds an exact normalized email address to `access_allowlist` or approves an email-only `access_request`.
- Email normalization is limited to trimming and case normalization. Thesos must not rewrite dots, plus-addressing, or domains.
- Registering an approved address creates a `pending_verification` account, stores its password verifier, records the accepted Terms version/time, and sends a verification link. An unapproved address creates no account.
- Registration, recovery, and login responses avoid revealing whether an address is allowlisted, registered, disabled, or merely has the wrong password. Expensive password verification also uses a dummy verifier for unknown addresses to reduce timing differences.
- Verification and password-reset links carry high-entropy, single-use tokens. Only token digests are stored. Verification tokens expire after 24 hours; reset tokens expire after 30 minutes. The frontend receives tokens in the URL fragment and submits them in a POST body so they do not enter ordinary server access logs or referrer headers.
- Account states are `pending_verification`, `active`, `suspended`, and `revoked`; only verified active accounts can create sessions or runs.
- Password reset revokes every existing session. Password change requires the current password and revokes every other session.
- Changing the account email and linking external identity providers are out of scope for the private alpha because both require separate identity-recovery policy.

Password policy follows modern single-factor guidance:

- Minimum 15 Unicode characters and maximum 128 characters; spaces and password-manager paste are allowed.
- Normalize Unicode with NFC before hashing, but never trim, change case, or silently truncate a password.
- No mandatory uppercase, lowercase, digit, or symbol mixture and no periodic password rotation.
- Reject passwords found in a maintained local blocklist of common/compromised values, including context-specific Thesos terms, without sending the proposed password to an external service.
- Hash with Argon2id using a unique salt, versioned parameters, and commissioning measurements at or above the current OWASP minimum. Rehash on successful login when policy parameters increase.
- Never log, encrypt for later recovery, or otherwise retain the submitted password. Only the Argon2id verifier is stored.

Transactional email is sent through a narrow adapter, initially Resend on a dedicated Thesos sending subdomain with SPF, DKIM, and DMARC. Messages contain no prompt/chat content. Delivery failures, bounces, and provider use are observable, while API keys and complete action URLs never enter logs. The privacy notice identifies the email provider and the recipient data it processes.

After login, Thesos issues a high-entropy opaque session token in a `Secure`, `HttpOnly`, `SameSite=Lax`, `__Host-` cookie and stores only its digest server-side. Ordinary sessions start with a seven-day idle and 30-day absolute lifetime; admin sessions use a 30-minute idle and eight-hour absolute lifetime, and sensitive mutations require authentication within the last 15 minutes. Sessions rotate at login and privilege changes, can be revoked individually or per account, and never contain roles or quota claims that can become stale. State-changing routes require a separate CSRF token plus strict Origin/Host checks.

Roles are stored in the database. A one-shot management command seeds the first exact admin email and refuses to run once an admin exists; no permanent environment variable silently re-grants the role. The first administrator must enroll TOTP before accessing admin operations, recovery codes are shown once and stored only as hashes, and all role or access changes are audited. Ordinary-user MFA and optional social login may be added later without changing the account's stable internal ID.

### 7.9 Daily allowance and abuse controls

The private-alpha base allowance is 10 accepted model runs per account per UTC day. The UI shows the remaining allowance and exact reset time. A "request more" form creates a pending `quota_request`; an administrator may issue a dated one-off grant or change an account-specific daily limit without editing application configuration. Separate configurable global daily run, token, cost, and concurrent-generation ceilings protect the service even when every account is individually within quota; exhausting a global ceiling pauses new generations without disabling login, existing-history access, or administration.

Allowance accounting is a PostgreSQL transaction, not an in-memory counter:

1. Run acceptance locks or atomically updates the account/day bucket and creates one `reserved` ledger entry alongside the run.
2. An idempotent retry returns the existing run and reservation.
3. The reservation becomes `charged` when the first provider request starts.
4. Validation failures and dispatch failures before provider work release the reservation.
5. User cancellation before provider work releases it; cancellation after provider work starts remains charged.
6. Provider retries, fallbacks, and tool calls within one run remain one user-visible allowance unit while their real token and cost usage is still recorded separately.

The account limit is authoritative. Additional signals defend against automation and account sharing without treating a shared household, university, mobile carrier, or VPN address as one person:

- Caddy accepts the client IP header only from the configured Cloudflare proxy path. The application stores a rotating HMAC pseudonym, never the raw IP in ordinary usage tables.
- A first-party random device identifier is issued as a security-purpose secure cookie and stored server-side by digest. It is not a canvas, audio, font, GPU, or behavioural fingerprint; its PECR/consent treatment must be reflected accurately in the launch privacy and cookie review.
- Per-IP and per-device burst limits, daily anomaly thresholds, failed-login limits, and concurrent-run limits sit above the ordinary per-account allowance. They may require Turnstile or administrative review before hard rejection.
- Turnstile is mandatory on access requests and conditionally required for suspicious login or generation traffic. Its token is always validated server-side.
- Security signals have short retention, are excluded from model context and ordinary logs, and are described in the privacy/cookie notice.

This layered design makes clearing one cookie insufficient to obtain more account quota, while avoiding invasive fingerprinting and unnecessary false positives. No client-reported remaining count or device identity is trusted for enforcement.

## 8. Corpus and Retrieval Plan

### 8.1 Ingestion pipeline

```text
input source
-> source adapter
-> fetch and immutable raw snapshot
-> clean and normalize
-> extract hierarchy and typed structures
-> structure-aware chunks
-> metadata and entity links
-> validation report
-> database revision
-> BM25 index build
-> retrieval smoke tests
-> atomic corpus publication
```

Each source adapter defines fetch policy, crawl delay, canonical URL behavior, parser, update detection, and authority classification. Generic scraping logic must not guess structure for every source.

### 8.2 Chunk types

Chunks should represent meaningful Warframe knowledge units:

- Explanatory section under a heading path.
- Weapon, Warframe, mod, arcane, resource, mission, or enemy entry.
- Drop table or acquisition rule.
- Damage or status formula and associated caveats.
- Patch-note change with version and date.
- Rotation or event definition.
- FAQ-like question and answer.

Tables, formulas, lists, warnings, and heading context must remain attached. Arbitrary fixed-token slicing is a fallback only for unusually long prose sections.

### 8.3 Chunk metadata

Every chunk includes:

```text
chunk ID and checksum
source and canonical URL
document and immutable revision
title and heading path
chunk type
entities and aliases
game version or effective interval
published and observed timestamps
platform and locale applicability
authority and editorial status
active corpus revision
```

### 8.4 Candidate retrieval

Initial retrieval combines:

1. Exact canonical entity and alias lookup.
2. BM25 title retrieval.
3. BM25 heading-path retrieval.
4. BM25 body retrieval.
5. Metadata filtering for platform, source type, time, and entity.
6. Reciprocal rank fusion across candidate lists.
7. Deterministic score adjustments.

Suggested initial bounds:

```text
Per candidate source:          top 30
Fused candidate pool:          at most 60
Post-score candidate set:      12-20
Final context chunks:          6-10, token-budget dependent
Per-document duplicate cap:    configurable by question type
```

### 8.5 Deterministic second-stage scoring

The first release uses a transparent domain score:

```text
retrieval score
+ exact entity match
+ title or heading match
+ source authority
+ current-version relevance
+ required freshness
+ chunk-type/intent compatibility
+ direct answer pattern
- stale or superseded revision
- duplicate coverage
- unresolved source conflict
```

Weights are configuration with an evaluation version. Changes require retrieval regression results, not intuition alone.

### 8.6 Context packing

The context packer:

- Selects evidence for each question facet, not only the globally highest scores.
- Preserves source IDs and heading paths around every excerpt.
- Removes near-duplicate chunks.
- Prefers current authoritative evidence while retaining conflicting evidence when relevant.
- Allocates space for tool outputs, conversation context, and answer generation.
- Never truncates a formula, table row set, or citation identity halfway.
- Marks source content as untrusted evidence, not instructions.

### 8.7 Optional reranking later

A small local cross-encoder may be added behind a `Reranker` protocol only if evaluation demonstrates a material gain. It should run on the top 15-25 candidates and only when retrieval confidence is low or research mode warrants it.

Embeddings may later become an additional candidate generator. Neither addition changes chunk IDs, provenance, the evidence ledger, or agent tool contracts.

## 9. LLM Integration Layer

### 9.1 Model roles

Application code requests a role plus capability constraints:

| Role | Purpose | Required capabilities |
|---|---|---|
| `intent` | Ambiguous intent and entity interpretation | structured output, low cost |
| `planner` | Complex execution plans | tools, structured output, reliable instruction following |
| `tool_agent` | Bounded tool selection and synthesis | tools, streaming, structured output |
| `research` | Evidence-driven multi-step research | tools, long context, reasoning controls |
| `answer` | Grounded final response | streaming, citations contract |
| `verifier` | Claim/evidence and calculation checks | structured output |
| `summarizer` | Conversation and evidence compression | structured output, low cost |

One physical model may fill several roles. Role separation is an application contract, not a requirement to pay for seven different models.

### 9.2 Model registry

Each configured deployment records:

```text
logical name
provider and model ID
supported capabilities
context and output limits
reasoning parameter support
tool and schema reliability class
privacy/data-collection class
cost and quota class
timeout and concurrency
fallback eligibility
enabled state
```

The registry resolves `(role, requirements, privacy policy, budget)` to a primary model and eligible fallback chain. Model IDs never appear directly in workflow code.

### 9.3 Initial routing

Initially:

```text
Pydantic AI agent
-> OpenRouterModel
-> selected OpenRouter model/provider route
```

Later:

```text
FallbackModel(
    OpenRouterModel(...),
    MistralModel(...),
)
```

OpenRouter performs routing among inference endpoints for the selected model. Thesos performs routing among logical roles and top-level API providers. Do not add a second generic routing gateway until central key, spend, or multi-service management justifies LiteLLM.

The selected model route is recorded at run start. If a fallback succeeds, the controller pins that compatible fallback for subsequent model steps in the run unless it becomes unavailable. It does not alternate providers opportunistically inside one tool conversation. Every fallback candidate must satisfy the same required tool, schema, context, and privacy capabilities.

### 9.4 Provider request policy

- Require support for all requested parameters on tool-bearing requests.
- Apply provider data-retention constraints from the user's selected privacy policy.
- Set explicit connect, first-token, inter-token, and total timeouts.
- Disable overlapping retry layers when DBOS owns retries.
- Record actual provider and model returned, where available.
- Capture token and cost data without recording prompt content in ordinary logs.
- Use stable application attribution headers for OpenRouter.
- Reject configurations that silently drop required tools or structured output.

### 9.5 Prompt management

Prompts live as versioned files grouped by role:

```text
prompts/
|-- controller/
|-- intent/
|-- planner/
|-- research/
|-- answer/
|-- verifier/
`-- summarizer/
```

Every model call records prompt version hashes, model-policy version, corpus revision, and toolset version. Dynamic material such as current time, platform, evidence, and user preferences is passed as typed context rather than concatenated into an opaque mega-prompt.

Prompt changes require eval comparison. Production prompts are immutable within a deployed image.

### 9.6 Structured model outputs

Semantic decisions use Pydantic models, including:

- `IntentAssessment`
- `EntityResolutionDecision`
- `ExecutionPlan`
- `PlanStepDecision`
- `EvidenceAssessment`
- `ClarificationRequest`
- `AnswerDraft`
- `VerificationReport`
- `FinalAnswer`

Schema failures receive at most two model correction attempts. Repeated failure changes model or terminates gracefully; it never creates an unbounded retry loop.

## 10. Production Agent Loop

### 10.1 Control model

The Thesos agent is a deterministic controller containing several narrow model-assisted operations. It is not a single prompt that repeatedly calls tools until the model decides to stop.

```text
Intake
-> Understand
-> Route
-> Retrieve
-> Decide whether planning is required
-> Plan if required
-> Execute bounded steps
-> Assess evidence
-> Replan, clarify, or answer
-> Draft
-> Verify
-> Finalize
```

Pydantic AI supplies model interaction, typed tools, event streaming, and per-run usage limits. The Thesos controller supplies product policy and domain state transitions. DBOS checkpoints workflow and I/O steps.

#### Model-assisted primitives

Use several narrow, globally constructed Pydantic AI agents rather than one omnipotent agent:

| Primitive | Tools | Maximum behavior |
|---|---|---|
| Intent agent | None | One structured interpretation request |
| Planner agent | None | One structured plan or plan-tail revision |
| Step executor | Only the current step's filtered toolset | Bounded tool loop ending in `StepOutcome` |
| Evidence assessor | None | One structured sufficiency decision |
| Answer agent | None | One evidence-constrained draft |
| Verifier agent | None | One issue report; never an answer replacement |
| Summarizer | None | One bounded conversation/evidence digest |

The step executor is the only primitive allowed to enter Pydantic AI's internal tool loop. It receives strict `UsageLimits`, a plan-step-specific toolset, and a required structured `StepOutcome`. The outer controller gets control back after every step. No primitive can recursively create another agent run or increase its own tools or budget.

### 10.2 Agent state

Persist a typed `AgentRunState` containing references rather than uncontrolled raw blobs:

```text
identity
  run ID, conversation ID, parent run, timestamps

request
  normalized question, bounded history, locale, platform, privacy policy

routing
  requested mode, selected workflow, model roles, toolsets, corpus revision

understanding
  intents, entities, constraints, ambiguities, freshness requirements

execution
  plan, current step, completed steps, tool-call signatures, retry counters

evidence
  evidence item IDs, facet coverage, conflicts, unresolved requirements

budgets
  wall time, model requests, tokens, tool calls, provider cost, retrieval passes

output
  assumptions, warnings, citations, draft reference, verification status

control
  status, cancellation flag, clarification state, terminal reason
```

Every state transition validates invariants. For example, `DRAFT` requires either sufficient evidence or an explicit `insufficient_evidence` warning.

### 10.3 Run modes and initial budgets

These are commissioning limits to be tuned through evaluation and provider quotas:

| Limit | Quick | Standard/auto | Research |
|---|---:|---:|---:|
| Wall-clock target | 30 s | 90 s | 5 min |
| Hard timeout | 45 s | 2 min | 10 min |
| Model requests | 3 | 6 | 16 |
| Tool calls | 6 | 16 | 40 |
| Retrieval passes | 1 | 2 | 4 |
| Replans | 0 | 2 | 4 |
| Clarification rounds | 1 | 2 | 3 |
| Concurrent tool calls | 2 read-only | 3 read-only | 4 read-only |

Every mode also has input-token, output-token, and monetary ceilings from configuration. Child agents and retries contribute to the parent's budget.

### 10.4 Phase 0: Intake and policy

Keep this phase deterministic for request handling and unambiguous safety cases:

1. Validate request, authenticated account/session ownership, idempotency key, daily allowance, and abuse limits.
2. Normalize text and conversation history.
3. Apply deterministic safety rules before retrieval or tool selection and check active history for a terminating message.
4. Mark genuinely ambiguous safety interpretation for the existing intent step; do not make a provider call solely to classify harmless topical drift.
5. Detect locale and apply explicit user platform preferences.
6. Select the maximum permitted run mode from user request, quota, and service health.
7. Check exact answer-cache eligibility.
8. Establish budget, cancellation token, trace, and corpus revision.

User text never directly changes provider, budget, system prompt, available secret-bearing tools, or retention policy.

During the early generic-chat milestone, topic and product-safety behavior lives in the answer model's operational prompt. Before any tool-bearing workflow is added, ambiguous safety classification can ride on the intent request already required for tool selection. This avoids adding a standalone validation call to every message.

### 10.5 Phase 1: Understanding

Use deterministic entity matching first:

- Canonical names and aliases.
- Case and punctuation normalization.
- Common abbreviations and community shorthand.
- Platform and game-mode terms.

Invoke the `intent` model only when deterministic interpretation is incomplete. It returns:

```text
one or more intents
resolved entity candidates with confidence
required currentness
question facets
explicit constraints
consequential ambiguities
recommended workflow class
safety action when deterministic policy left genuine ambiguity: allowed, archive_unavailable, terminate_conversation, or urgent_safety
topic posture: warframe_direct, thread_connected, open_drift, or sustained_drift
short topic-trajectory summary
return-to-Warframe strength: none, light, or clear
```

The controller may ask a clarification only when different interpretations materially change the answer and cannot be addressed by clearly stated assumptions.

Topic posture is guidance, not an authorization boundary. Harmless off-topic turns remain answerable. The answer agent uses bounded conversation history to follow natural side discussions and gradually steer sustained drift back toward Warframe without forced analogies, policy announcements, or scope refusals. When deterministic understanding is already sufficient and the intent model is skipped, the answer agent applies this behavior itself; the initial architecture does not pay for a dedicated topic-governor call.

Safety output is a typed union, never inferred from generated wording. `archive_unavailable` selects approved non-echoing copy and leaves the composer active. `terminate_conversation` emits no assistant prose, marks the user message in server-owned active-history metadata, and ends the run with `conversation.terminated`. New runs against that active history are rejected until an ordinary edit truncates the flagged message from the history.

### 10.6 Phase 2: Workflow and toolset selection

The controller selects one primary workflow:

- `direct_conversation`
- `archive_answer`
- `live_state_answer`
- `market_lookup`
- `build_analysis`
- `mechanics_calculation`
- `research`

It then constructs the smallest relevant runtime toolset. A market question should not expose calculation tools; a calculation question should not expose market or network tools. Tool filtering is enforced in Python, not requested politely in the prompt.

### 10.7 Phase 3: Initial retrieval

For factual Warframe questions, retrieval occurs before open-ended planning:

1. Generate exact and alias-expanded lexical queries.
2. Apply entity, platform, version, and source filters.
3. Retrieve and score candidates.
4. Pack an initial context.
5. Create evidence-ledger items with provenance.
6. Calculate initial facet coverage and retrieval confidence.

This gives the planner real evidence and prevents it from inventing research steps based solely on model memory.

### 10.8 Phase 4: Planning decision

Planning is required when any of these apply:

- The question has multiple dependent facets.
- It asks for comparison, optimization, or build design.
- It combines retrieved facts with calculations.
- It needs several live and archival sources.
- Initial evidence coverage is inadequate.
- The user explicitly selected research mode.

Planning is skipped for direct definitions, locations, simple current-state queries, and ordinary conversation.

### 10.9 Execution plan contract

The planner produces no free-form hidden essay. It returns:

```text
objective
answer facets
ordered plan steps
dependencies
allowed tool category per step
success criteria per step
maximum attempts per step
expected evidence type
stop conditions
```

Each step is independently validated against the selected workflow, tool permissions, and remaining budget. Invalid or redundant steps are rejected or simplified by the controller.

Example build plan:

```text
1. Resolve weapon variant and Incarnon evolution assumptions.
2. Retrieve current weapon, mod, and relevant mechanics facts.
3. Construct a typed candidate build within stated constraints.
4. Run deterministic damage and status calculations.
5. Compare alternatives against the user's target content.
6. Verify assumptions, caveats, and source support.
```

### 10.10 Phase 5: Step execution

For each plan step:

1. Confirm dependencies and budget.
2. Select allowed tools and model role.
3. Generate validated tool arguments.
4. Run independent read-only calls concurrently where safe.
5. Normalize tool results into the standard result envelope.
6. Add evidence, assumptions, warnings, and observed timestamps.
7. Mark step success, partial success, retryable failure, or terminal failure.
8. Emit a sanitized progress event.

The controller, not the model, decides whether a failed step may retry or whether alternate evidence is acceptable.

### 10.11 Tool result contract

Every tool returns a typed envelope:

```text
status: success | partial | not_found | unavailable | invalid
data: bounded typed payload
evidence: source/provenance records
observed_at
expires_at or revision
confidence or completeness
warnings
retry_after when applicable
```

Raw third-party payloads are never placed directly into model context. Adapters validate, reduce, and label them first.

### 10.12 Tool execution policy

Each tool declares:

```text
stable name and version
input and output schemas
read-only or side-effect class
idempotency behavior
authorization scope
timeout
retry policy
cache policy
maximum result size
concurrency key
freshness class
audit requirements
```

Initial tools are read-only. Future side-effecting tools require both server authorization and explicit per-call user approval. Approval is an interaction mechanism, not a substitute for authorization.

The first tool catalog should include:

- `resolve_warframe_entities`
- `search_archives`
- `get_source_sections`
- `get_current_world_state`
- `get_rotation_status`
- `lookup_market_orders`
- `get_market_item_metadata`
- `calculate_build`
- `compare_builds`
- `explain_calculation_inputs`

Do not expose generic `fetch_url`, SQL, filesystem, shell, Python execution, or arbitrary MCP servers to the public agent.

### 10.13 Evidence ledger

Every usable evidence item records:

```text
evidence ID
claim facets it supports
source and canonical URL
document/chunk revision or live tool observation
verbatim supporting excerpt or structured fact
authority class
relevance and directness
freshness and expiry
platform applicability
conflicts and supersession links
tool or retrieval step that produced it
```

Evidence remains separate from model-generated notes. A model summary of a source is not itself a source.

### 10.14 Phase 6: Evidence assessment

After each meaningful step, the controller computes deterministic coverage:

- Are all requested facets represented?
- Is evidence direct or merely adjacent?
- Are time-sensitive claims fresh enough?
- Are numerical inputs complete and unit-consistent?
- Are authoritative sources preferred where available?
- Do sources conflict?
- Is there excessive dependence on one duplicated document?
- Is the result applicable to the user's platform and game version?

For complex cases, an `EvidenceAssessment` model evaluates the bounded ledger and returns structured missing facets and conflicts. It cannot mark unsupported evidence as authoritative or bypass deterministic freshness rules.

Possible decisions:

- `sufficient`: proceed to answer.
- `retrieve_more`: run a targeted retrieval pass.
- `execute_next_step`: continue plan.
- `replan`: change remaining steps only.
- `clarify`: suspend and ask one consequential question.
- `answer_with_limits`: evidence is incomplete but a useful qualified answer is possible.
- `stop`: cannot answer responsibly within budget.

### 10.15 Replanning rules

Replanning modifies only the unfinished tail of the plan. It must identify:

- What evidence or operation failed.
- Which unresolved facet remains.
- Why the proposed replacement can resolve it.
- Its additional budget requirement.

The controller rejects a replan that repeats an equivalent query or tool call without new constraints. Standard mode permits at most two replans; research mode at most four.

### 10.16 No-progress and loop detection

Terminate or degrade gracefully when any applies:

- Same canonical tool name and arguments are requested again without changed freshness.
- Two consecutive iterations add no new evidence or facet coverage.
- The planner recreates a previously rejected step.
- Remaining budget cannot complete a required step and final synthesis.
- Model, tool, token, wall-clock, cost, or replan limit is reached.
- Cancellation is requested.

Tool calls use canonical argument hashes. A repeated read call normally returns the cached prior result without consuming an external request, but it still counts against loop analysis.

### 10.17 Clarification behavior

Ask the user only when ambiguity is consequential. Good clarification:

- Names the ambiguity plainly.
- Offers two or three likely interpretations when useful.
- Preserves completed research and budget state.
- Does not ask for information that can be retrieved safely.

If a reasonable default exists, answer under an explicit assumption instead. Clarification runs suspend durably and expire after a configured period.

### 10.18 Phase 7: Drafting

The answer model receives:

- Original question and bounded relevant conversation context.
- Resolved entities and user constraints.
- Approved assumptions.
- Evidence ledger excerpts with stable citation IDs.
- Structured tool results.
- Required output shape and style.
- Explicit instruction to avoid unsupported additions.

It produces an internal `AnswerDraft` with claim-to-evidence references. The draft is not public output and is not considered complete until verification finishes.

By default, answer-generation deltas are consumed internally and buffered while the UI continues to receive useful progress and source events. After verification, the validated answer is released as quick `answer.delta` events and a final envelope. This avoids presenting an unsupported provisional claim and then silently changing it. A future true-live mode may stream provisional prose only if the UI labels it clearly and evaluation demonstrates that the trade-off is worthwhile.

For workflows with structured results, validated deterministic blocks may be emitted before the prose. Calculations and market values come from tool output, never regenerated from memory.

### 10.19 Phase 8: Verification

Verification combines deterministic checks and, when justified, a narrow verifier model.

Deterministic checks:

- Every citation ID exists and belongs to the run.
- URLs and source labels match stored provenance.
- Numerical values match calculation or tool output within declared formatting rules.
- Market data includes platform, status filter, currency, and observation time.
- Live claims are not served beyond expiry.
- No unsupported HTML, dangerous links, or accidental secrets appear.
- Required warnings and assumptions are present.
- Output fits schema and size limits.

Model-assisted checks:

- Factual claims are entailed by cited evidence.
- Contradictory evidence is acknowledged.
- The response answers each requested facet.
- Confidence language matches evidence quality.
- No cited source is being used for a claim it does not support.

The verifier returns issues, not a replacement answer. The controller may allow one targeted repair. Repeated verification failure returns a qualified partial answer or a transparent failure, never an infinite writer-critic cycle.

### 10.20 Phase 9: Finalization

1. Validate final `FinalAnswer` schema.
2. Persist answer envelope, evidence links, usage, and terminal state.
3. Emit any remaining structured blocks and citations.
4. Emit `run.completed` with freshness and assumptions.
5. Populate eligible caches.
6. Schedule content purge according to retention policy.
7. Record eval sampling eligibility without logging content by default.

### 10.21 User-visible reasoning policy

Expose useful progress, not private chain-of-thought. Acceptable messages include:

- `Searching the Archives for current Incarnon information`
- `Checking the latest market listings`
- `Calculating the two build variants`
- `Comparing conflicting mechanics sources`
- `Verifying figures and citations`

Do not expose hidden prompts, raw model reasoning, security policy, provider secrets, unsanitized tool arguments, or third-party response dumps.

### 10.22 Retry and fallback policy

There is one owner for each retry class:

| Failure | Owner | Policy |
|---|---|---|
| Provider connect/429/5xx before output | DBOS/model layer | Respect `Retry-After`, bounded jitter, then eligible fallback |
| Provider failure during internally buffered draft | Controller | Discard partial draft and retry the whole step within budget |
| Provider failure after public prose begins | Controller | Stop stream, preserve partial state, offer retry; do not splice a second model invisibly |
| Tool transient network failure | DBOS tool step | Retry only idempotent reads, endpoint-specific limit |
| Tool permanent 4xx/validation | Controller | Do not retry unchanged arguments |
| Model schema failure | Pydantic AI/controller | At most two correction attempts |
| Verification failure | Controller | One targeted answer repair |
| Worker crash/redeploy | DBOS | Resume from completed durable step |

Provider SDK retries should be disabled or minimized when DBOS owns the step retry, preventing multiplied retries and unexpected cost.

For internally buffered answer generation, a mid-stream provider failure does not expose partial prose to the user. The controller may retry the whole draft step within budget. For any future genuinely live prose stream, mid-stream output remains terminal for that attempt and cannot be invisibly replaced.

### 10.23 Cancellation and recovery

- Cancellation sets a durable flag checked before every model request, tool call, and plan transition.
- Active HTTP/model requests receive best-effort cancellation.
- Completed idempotent steps remain checkpointed.
- The final state distinguishes user cancellation, quota cancellation, timeout, and administrative cancellation.
- Event replay allows the browser to reconnect from its last event ID.
- A worker startup recovery pass resumes leased runs whose lease expired.
- Deployments must drain or version workflows safely; incompatible workflow changes cannot reinterpret in-flight state.

### 10.24 Controller implementation shape

The durable workflow should resemble the following structure. I/O-bearing functions are DBOS steps; state decisions remain deterministic workflow code.

```python
@DBOS.workflow()
async def execute_run(run_id: UUID) -> None:
    state = await load_or_create_state(run_id)

    while not state.is_terminal:
        enforce_cancellation_and_budgets(state)

        match state.phase:
            case Phase.INTAKE:
                state = apply_intake_policy(state)

            case Phase.UNDERSTAND:
                state = await understand_step(state)

            case Phase.RETRIEVE:
                result = await retrieve_step(state)
                state = add_retrieval_evidence(state, result)

            case Phase.PLAN:
                plan = await planner_step(state)
                state = validate_and_accept_plan(state, plan)

            case Phase.EXECUTE:
                outcome = await execute_plan_step(state)
                state = apply_step_outcome(state, outcome)

            case Phase.ASSESS:
                decision = await assess_evidence_step(state)
                state = apply_assessment_decision(state, decision)

            case Phase.WAIT_FOR_CLARIFICATION:
                await suspend_until_clarified(state)

            case Phase.DRAFT:
                draft = await draft_answer_step(state)
                state = attach_internal_draft(state, draft)

            case Phase.VERIFY:
                report = await verify_answer_step(state)
                state = apply_verification_report(state, report)

            case Phase.FINALIZE:
                await finalize_run_step(state)
                state = state.completed()

        await persist_transition_and_public_events(state)
```

Production implementation details:

- State transitions use a closed `Phase` enum and an explicit allowed-transition table.
- Workflow state contains IDs and compact typed summaries; large evidence and text live in application tables.
- Every I/O step has a stable name, version, timeout, and retry policy.
- Every externally visible event has a deterministic deduplication key.
- A transition and its public events commit atomically where practical.
- Model and tool dependencies are created outside serialized workflow state and resolved from stable IDs.
- Workflow code versions are pinned for in-flight runs; incompatible releases drain or migrate old workflows explicitly.
- Tests run the controller with scripted model primitives and injected tool failures, making every path reproducible.

## 11. Specialist Workflows

### 11.1 Archive answer

```text
resolve entities
-> retrieve
-> deterministic evidence check
-> answer
-> verify citations
```

No planner unless evidence is incomplete or the question has several facets.

### 11.2 Live state and rotations

```text
resolve platform/time scope
-> call structured live source
-> combine with archive explanation if needed
-> attach observed time and expiry
-> answer
```

Prefer deterministic assembly for simple rotation answers. An LLM is unnecessary when a template and structured data fully answer the question.

### 11.3 Market lookup

```text
resolve canonical item
-> validate platform/crossplay/order/status filters
-> use paced cached market client
-> normalize listings
-> compute requested aggregates
-> present snapshot with timestamp and direct links
```

The agent may identify cheapest or representative listings but cannot contact sellers, authenticate as a user, or execute trades.

### 11.4 Build analysis

```text
resolve equipment and variants
-> identify target content and constraints
-> retrieve current mechanics and equipment facts
-> construct typed build candidates
-> validate mod capacity, compatibility, and assumptions
-> run deterministic simulations
-> compare results
-> explain trade-offs and caveats
-> verify numbers and sources
```

The calculation result includes input snapshot, formula/mechanics version, rounding behavior, intermediate values, and warnings. Property-based tests cover invariants and edge cases.

### 11.5 Research

Research mode uses a plan with evidence-oriented steps, not an unconstrained browsing agent:

```text
decompose question
-> initial archive retrieval
-> identify missing facets
-> run targeted archive/live tools
-> compare source authority and chronology
-> compress evidence if necessary
-> synthesize
-> verify claim coverage
```

Initial public research does not include unrestricted web browsing. Additional external sources enter through approved source adapters or a future allowlisted research tool with its own security review.

## 12. Calculation Engine Plan

### 12.1 Separation

```text
Natural-language request
-> typed domain inputs
-> mechanics data and formula registry
-> deterministic evaluator
-> typed calculation result
-> natural-language explanation
```

### 12.2 Requirements

- Version formulas and constants by game update/effective date.
- Represent modifier categories explicitly instead of generic dictionaries.
- Encode Warframe ordering, stacking, caps, conditional effects, and rounding deliberately.
- Preserve every assumption made to complete missing build inputs.
- Return intermediate stages so results are auditable.
- Keep display rounding separate from computational precision.
- Support comparison with one shared baseline and controlled changed variables.
- Build fixtures from known in-game examples and manually verified cases.
- Use Hypothesis to test monotonicity and other mechanics invariants where valid.

The LLM is prohibited from supplying an unvalidated formula string for execution.

## 13. Security and Abuse Controls

### 13.1 Prompt injection boundaries

- Treat user text, retrieved pages, API notes, seller messages, and source metadata as untrusted data.
- Delimit evidence from instructions in every model request.
- Never allow retrieved text to introduce tools, change policy, request secrets, or alter retention.
- Strip active content and sanitize markup during ingestion.
- Keep provider keys and internal URLs out of model context.
- Detect source passages containing instruction-like attacks and preserve them only as quoted evidence when necessary.
- Restricted-response templates and termination banners never interpolate user text, detected topic labels, entities, or model-generated explanations.

### 13.2 Least agency

- Public tools are read-only and domain-specific.
- Tool arguments are validated against server-side schemas and policy.
- External network destinations are allowlisted in adapters.
- No arbitrary URL fetching, shell, code execution, filesystem access, or database query tool.
- Future actions require explicit authorization, idempotency, audit, and user approval.
- Child agents inherit a smaller or equal capability set and share the parent budget.

### 13.3 Web security

- Strict Content Security Policy and trusted asset origins.
- Argon2id password verifiers, breached/common-password blocking, generic auth responses, bounded password-verification concurrency, and account/IP/device login throttling.
- Single-use, digest-only verification/reset tokens; no password, complete action URL, or token is written to logs.
- Opaque, revocable server sessions in `__Host-` Secure, HttpOnly, SameSite cookies; no password verifier or role claim is stored in browser-readable state.
- CSRF protection for every cookie-authenticated mutation, including ordinary run creation and cancellation.
- Origin and host validation.
- Request size and content-type enforcement.
- Per-account, pseudonymous-device, and HMAC-pseudonymized-IP controls in both edge and backend, with the account allowance authoritative.
- Turnstile on access requests and risk-triggered authentication/generation traffic, always validated server-side.
- Markdown and outbound-link sanitization.
- SSRF-safe source adapters with DNS/IP checks and redirect limits.
- Backend role checks, recent-authentication checks for admin mutations, session revocation, and audit logging.
- Mandatory TOTP and recovery codes for administrators; TOTP secrets are encrypted at rest and recovery codes are stored as hashes.
- Production developer mode and content-bearing diagnostic logs are unavailable to ordinary users.

## 14. Observability

### 14.1 Trace hierarchy

Use OpenTelemetry spans without content by default:

```text
HTTP request
`-- agent run
    |-- intake
    |-- understanding
    |-- retrieval
    |-- planning
    |-- plan step
    |   |-- model request
    |   `-- tool call
    |-- evidence assessment
    |-- drafting
    `-- verification
```

Record IDs, durations, counts, model route, result class, cache status, corpus revision, and error category. Prompt, answer, evidence text, and tool payloads require an explicit debug-only policy and must never be enabled casually in production.

### 14.2 Metrics

- Runs by workflow, mode, and terminal state.
- Time to acceptance, first status, first source, first answer token, and completion.
- Queue wait and active concurrency.
- Model requests, tokens, cost, fallback, rate limit, and schema failure.
- Tool latency, cache hit, failure, and external request count.
- Retrieval recall proxy, candidate count, evidence coverage, and no-result rate.
- Replan, clarification, no-progress, and verification-repair rates.
- Citation count, unsupported-claim eval rate, and freshness warnings.
- User feedback and answer-cache effectiveness.
- Authenticated active users, successful and failed logins, access requests, quota reservations/charges/releases, allowance denials, and grants.
- Per-account provider cost and token totals, with admin aggregates that do not expose prompt or answer contents.
- IP/device anomaly counts and Turnstile outcomes without raw IPs or invasive fingerprint material.
- Count `archive_unavailable` and `terminate_conversation` actions by policy version without recording prompt content or public topic labels.
- VM, container, PostgreSQL, disk, backup, and ingestion health.

### 14.3 Operational logs

Structured logs include request/run IDs and stable error codes. They exclude raw chat and source content by default. Known exceptions are redacted before logging. Every user-visible failure maps to an internal error code that can be searched without exposing content.

## 15. Testing and Evaluation Strategy

### 15.1 Ordinary software tests

- Unit tests for normalization, entity aliases, metadata scoring, RRF, context packing, cache keys, rate limits, and state transitions.
- Unit and integration tests for allowlist checks, registration/verification/reset tokens, Argon2 parameter upgrades, generic auth responses, login throttling, session rotation/revocation, CSRF, admin TOTP, role enforcement, quota races, idempotent reservations, grants, and IP/device privacy boundaries.
- Property-based tests for calculation engines and agent-loop invariants.
- Contract tests for every tool adapter using recorded and synthetic payloads.
- Integration tests against a real PostgreSQL instance.
- Migration upgrade and rollback-compatibility checks.
- Tests with Pydantic AI `TestModel` and `FunctionModel`; live model calls disabled by default in tests.
- Failure injection for 429, 500, timeout, malformed JSON, partial stream, worker death, and event reconnection.

### 15.2 Retrieval evaluation set

Build a curated Warframe dataset containing:

- Exact entity questions.
- Aliases, abbreviations, misspellings, and renamed content.
- Acquisition and drop questions.
- Mechanics and formula questions.
- Version-sensitive questions.
- Multi-entity comparisons.
- Questions with no supported answer.
- Conflicting or superseded sources.

Track Recall@K, MRR, nDCG, facet coverage, duplicate rate, stale-source rate, and context token cost.

### 15.3 Agent evaluation set

Cases cover:

- Correct workflow selection.
- Correct toolset restriction.
- Tool argument accuracy.
- No unnecessary planner or tool calls.
- Required clarification versus valid assumption.
- Loop termination and budget adherence.
- Correct handling of empty, stale, and conflicting evidence.
- Citation entailment and citation completeness.
- Calculation fidelity.
- Market freshness and filter correctness.
- Prompt injection in user text and retrieved source content.
- Medium-risk turns select approved Archives copy with no user-text echo and leave continuation enabled.
- Severe operational-harm turns emit only `conversation.terminated`, with no answer or tool events.
- A terminated active history is rejected by the backend even when the frontend request is crafted manually.
- Editing an earlier user message atomically truncates the suffix; continuation is restored only when no terminating message remains active.
- Benign lore, prevention, historical description, quoted discussion, and emergency-safety wording do not trigger termination from keyword overlap alone.
- Provider outage and mid-stream failure.
- Cancellation and durable resume.

Prefer deterministic evaluators. Use an LLM judge only for qualities that cannot be checked reliably in code, and calibrate it against human-reviewed examples.

### 15.4 Release eval gates

No prompt, model, retrieval weight, chunking, or agent-policy change ships unless:

- It passes deterministic safety and schema tests.
- It does not regress critical retrieval cases.
- It does not increase unsupported-claim or wrong-tool rates beyond tolerance.
- Cost and p95 latency remain within the release budget.
- A report identifies changed cases and known trade-offs.

Live-provider evals run manually or on a controlled schedule. CI uses deterministic fake models for every commit.

## 16. Deployment Plan Amendments

The VM manifest should be updated before implementation deployment:

1. Start the FastAPI service with one Uvicorn worker, not two.
2. Add one lightweight `agent-worker` process using the same application image.
3. Add DBOS-owned PostgreSQL state and migrations according to DBOS guidance.
4. Replace the initial local embedding-model directory with a general `/srv/veris/indexes` directory; embeddings remain optional.
5. Make pgvector extension and vector indexes optional rather than launch requirements.
6. Budget memory for the agent worker and memory-mapped BM25 index.
7. Set the initial public origin to `cephalonthesos.com`, with `www` redirected and API traffic remaining same-origin under `/api`.
8. Add the transactional-email, password-hashing, admin-TOTP, Turnstile, session/CSRF/HMAC, GHCR, deploy-user, backup, and trusted-Cloudflare configuration introduced by Phases 3A-3C.
9. Make PostgreSQL, the API, the agent worker, and Caddy continuously running; migrations, backups, and future ingestion remain one-shot jobs.
10. Commission the hosted private alpha before corpus services exist, then add ingestion/index storage without replacing the authentication, quota, or deployment substrate.

Proposed steady-state memory planning:

| Component | Expected range |
|---|---:|
| OS, Docker, Caddy | 1.0-1.5 GB |
| PostgreSQL | 2.0-3.5 GB |
| FastAPI API | 0.25-0.6 GB |
| Agent worker and BM25 mappings | 0.5-1.5 GB |
| Filesystem cache and headroom | 4.9-8.2 GB |

Actual container limits follow load testing, not these estimates alone.

## 17. Delivery Phases

Development proceeds through observable vertical slices. A phase is complete only when its exit gate passes; partially implemented later-phase systems must not be allowed to distort the current working slice.

### Phase 0: Repository and development foundation

Objective: establish a reproducible project before product implementation.

Deliver:

- Create a separate Thesos Git repository.
- Establish the `apps/web`, `apps/server`, `evals`, `infra`, and `docs` layout.
- Pin Python, Node, frontend, and container dependencies.
- Add local Compose services for PostgreSQL and development support.
- Initialize Alembic with an empty baseline migration and migration CI checks.
- Add configuration models, `.env.example`, secret-loading rules, and startup validation.
- Configure Ruff, Pyright, pytest, ESLint, TypeScript strict mode, Vitest, and Playwright.
- Add CI for linting, type checking, tests, frontend build, migration verification, and ARM64 container builds.
- Add one documented local runner that starts the required development services.
- Establish API versioning, error envelopes, request IDs, and logging conventions.

Database work:

- PostgreSQL runs locally from the beginning.
- Create application, migration, and test roles.
- Prove migration upgrade and clean-database rebuild paths.
- Do not create speculative product tables yet.

Exit gate:

- A clean checkout installs, migrates, tests, and starts with documented commands.
- CI passes on an empty product shell.
- No secret, machine-specific path, or mutable generated artifact is committed accidentally.

### Phase 1: Initial frontend with simulated runs

Objective: build and validate the user experience before backend behavior constrains it.

Deliver:

- Implement the selected desktop and mobile visual direction.
- Build the application shell, side navigation, Archives prompt, four suggestions, composer, and conversation viewport.
- Pre-render `/`, `/about`, `/privacy`, and `/terms` with no production Node server.
- Implement user messages, Thesos responses, source drawer, warnings, error states, cancel state, and empty state.
- Implement Archives-unavailable and conversation-terminated fixtures, including composer replacement, `New chat`, and edit-and-truncate behavior.
- Create the structured answer block renderers with representative fixtures.
- Build a mock run transport that replays realistic event fixtures with adjustable delay, interruption, duplicates, and failures.
- Implement the deterministic frontend event reducer.
- Add browser-local conversation and settings persistence in IndexedDB.
- Complete responsive, keyboard, reduced-motion, accessibility, and visual-regression coverage.

Database work:

- None beyond the Phase 0 development database. All frontend data is fixture-backed or browser-local.

Exit gate:

- The complete question-to-answer experience is convincing with simulated events.
- Desktop and mobile screenshots match the accepted design direction.
- Event replay, duplicate events, cancellation, and failure presentations pass frontend tests.
- Static routes contain useful indexable HTML.

### Phase 2: API, event protocol, and first runtime schema

Objective: replace the simulated transport with a real backend while still returning deterministic fixture answers.

Deliver:

- Create the FastAPI application factory and configuration lifecycle.
- Add liveness, readiness, run creation, run status, event stream, cancellation, and suggestion endpoints.
- Add message editing with atomic truncation of all later active turns.
- Establish the anonymous Secure/HttpOnly session and CSRF/origin policy.
- Generate frontend TypeScript contracts from FastAPI OpenAPI schemas.
- Implement idempotent run creation.
- Implement durable event rows, per-run sequence numbers, event replay, and PostgreSQL notification wake-ups.
- Connect the frontend to real `POST /runs` and SSE endpoints.
- Return deterministic server-side fixture answers through the production event protocol.
- Implement deterministic `response.archive_unavailable` and `conversation.terminated` fixtures plus backend continuation rejection for terminated active histories.
- Add typed errors, request limits, basic rate limiting, and structured logs.

Database work:

- Add `conversation_message_control`, `agent_run`, `agent_event`, `agent_dispatch_outbox`, anonymous-session ownership, and migration bookkeeping.
- Add retention timestamps and a tested purge job.
- Add indexes for run ownership, active status, idempotency keys, event sequence, and expiry.

Exit gate:

- The browser uses no mock transport for its normal development path.
- Refresh and connection loss resume from the last event without missing or duplicating visible state.
- Repeated run-creation requests with one idempotency key produce one run.
- Database purge tests demonstrate that expired content is removed.

### Phase 3: Basic generic LLM chat loop

Objective: prove the complete browser -> API -> worker -> provider -> browser path before retrieval and agent planning are added.

Deliver:

- Integrate Pydantic AI and `OpenRouterModel`.
- Introduce the minimal model registry with a single `answer` role and configuration-selected model.
- Add the agent worker process and basic DBOS queue ownership using run ID as workflow identity.
- Dispatch accepted runs through the transactional outbox.
- Implement a basic bounded conversation loop with system instructions, user message, bounded recent history, and plain answer output.
- Return a typed turn-result union so normal answers, Archives-unavailable responses, termination, and urgent-safety handling cannot be confused with generated prose.
- Stream provider activity internally and deliver answer events through the established event protocol.
- Add cancellation, provider timeout, 429/5xx handling, usage limits, and one eligible fallback path.
- Record model route, latency, token usage, estimated cost, and terminal outcome.
- Add Pydantic AI `TestModel`/`FunctionModel` tests and a small controlled live-provider smoke suite.

This is explicitly a development milestone, not a production-quality Warframe answerer. Its answers are ungrounded and the UI must label the development environment accordingly. No public deployment occurs at this phase.

Database work:

- Add `agent_model_call`, `provider_usage`, `provider_budget`, and basic workflow-dispatch state.
- Retain only the temporary content needed to complete and recover a run.

Exit gate:

- A real browser question reaches OpenRouter and returns through the worker and event stream.
- Cancellation and provider failure produce stable terminal states.
- Hard request, token, time, concurrency, and provisional cost limits are enforced.
- One network retry cannot create two model runs.

### Phase 3A: Hosted-alpha data and runtime foundation

Implementation checkpoint (2026-08-16): implemented in the repository. PostgreSQL migrations,
transactional dispatch ownership, API/worker separation, cancellation propagation, provider-attempt
accounting, retention, production containers, Compose topology, and PostgreSQL integration coverage
are present. Live local checks passed for stream, cancel, API restart/replay, worker restart, and
idempotent submission. ARM64 container builds are enforced by CI because this workstation does not
run a container engine.

Objective: replace local-only shortcuts with the smallest production-shaped substrate needed to host the existing generic loop safely.

Deliver:

- Make PostgreSQL the authoritative application and DBOS database in development and production. SQLite remains permitted only for isolated unit tests that do not claim migration or concurrency coverage.
- Add a PostgreSQL development profile and a clean-database migration test. Production starts must reject SQLite URLs and unsafe/default secrets.
- Complete the API/agent-worker process split, transactional dispatch ownership, replayable event sequencing, cancellation propagation, and retention purge required by the existing Phase 2/3 contracts.
- Record provider route, latency, token usage, estimated cost, cancellation point, and terminal outcome for every model attempt.
- Produce pinned ARM64 images for the static frontend/Caddy, API, agent worker, migration job, and backup job.
- Add production Compose definitions with health checks, non-root users, bounded logs, read-only filesystems where practical, explicit persistent mounts, and initial memory/concurrency ceilings.
- Add one-way, expand-first migration rules. Local prototype data is not copied into production; the hosted alpha begins from a clean PostgreSQL database.
- Add production configuration validation for the Phase 3A domain/origin, provider keys, PostgreSQL URLs, secure cookies, pool bounds, and retention periods. Extend this fail-closed validation in Phase 3B as trusted proxy mode, transactional email, password hashing, admin TOTP encryption, Turnstile, and session/CSRF/HMAC secrets are introduced.

Database work:

- Recreate the current run, event, message-control, provider-usage, dispatch, and DBOS state in PostgreSQL through Alembic and DBOS-owned migrations.
- Replace SQLite-dependent autoincrement, JSON, timestamp, locking, and sequence assumptions with PostgreSQL-correct behavior.
- Add expiry indexes and a tested purge path for temporary content.

Exit gate:

- A clean local Compose environment migrates, starts, streams a model response, cancels it, restarts API/worker processes, and resumes/replays without losing ownership or duplicating paid work.
- The complete production image set builds for ARM64 and runs its health checks.
- PostgreSQL migration, concurrency, idempotency, and purge tests pass against a real PostgreSQL service.
- Production configuration fails closed when a required secret, trusted origin, or non-SQLite database is missing.

### Phase 3B: Allowlisted identity, quotas, and alpha administration

Objective: make every generation attributable to an approved private-alpha account and keep use within explicit per-user and service budgets.

Deliver:

- Implement the allowlisted email/password registration, verification, login, password change/reset, and transactional-email flows defined in Section 7.8.
- Add exact-email allowlisting, account activation/suspension/revocation, server-side roles, logout, per-session revocation, mandatory admin TOTP, and an initial admin bootstrap command.
- Require authentication for run creation, run/event access, cancellation, editing, feedback, quota requests, and any share creation. Health, legal pages, registration, verification/reset, login, and access requests remain unauthenticated.
- Replace anonymous run ownership with `user_id` plus the creating auth-session ID. Verify ownership on every snapshot, stream, cancellation, branch, and edit operation.
- Implement the atomic 10-runs-per-UTC-day allowance, reservation/charge/release lifecycle, account overrides, one-off grants, remaining/reset API, and request-more workflow described in Section 7.9.
- Add short-window backend limits for login, access requests, run creation, concurrent streams, and administrative mutations. Configure Turnstile for access requests and risk-triggered challenges.
- Issue a first-party random device cookie and HMAC-pseudonymize trusted client IPs. Do not implement canvas/font/audio/GPU fingerprinting.
- Build the login gate, account/allowance presentation, quota-exhausted state, access-request result, request-more form, and account-disabled state across every theme and viewport.
- Build an admin-only interface for allowlist entries, pending access and quota requests, user status, sessions, grants, daily runs, token/cost totals, failures, queue/health status, and content-free audit events.
- Disable the production Developer panel for ordinary accounts and ensure production logs/admin tables do not expose prompts or answers by default.
- Update privacy, cookie, terms, provider-disclosure, and early-alpha accuracy copy before any tester is invited.

Database work:

- Add `access_allowlist`, `access_request`, `user_account`, `password_credential`, `email_action_token`, `auth_session`, `user_role`, `admin_mfa`, `user_device`, `daily_usage_ledger`, `quota_grant`, `quota_request`, and content-free `audit_event` records.
- Add `user_id` ownership to existing run and active-message-control records and indexes for account status, session expiry, usage day, pending requests, and purge windows.
- Store only digests for session/device/email-action/recovery tokens and rotating HMAC pseudonyms for IP signals. Store password verifiers, never passwords; encrypt admin TOTP secrets outside the database key domain. Do not store ordinary raw IP addresses.

Exit gate:

- An unapproved email cannot create an account or a run; an approved email can create exactly one local account; a suspended or revoked account loses run access immediately.
- Cross-account run IDs, event streams, branches, edits, cancellations, and admin APIs remain inaccessible under direct crafted requests.
- Ten concurrent create requests cannot exceed one account's allowance, and an idempotent retry consumes one unit.
- Cancellation and provider-failure cases settle allowance exactly as documented.
- Admin actions require the role server-side, create an audit record, and cannot reveal chat contents through the ordinary dashboard.
- Registration, verification, reset, Argon2, login throttling, session, CSRF, admin TOTP, quota, privilege, and trusted-proxy tests pass.

### Phase 3C: CI/CD and gated private-alpha launch

Objective: deploy the authenticated Phase 3 build to `cephalonthesos.com` on the single OCI host with a repeatable release and recovery path.

Deliver:

- Amend and apply the OCI VM manifest for the confirmed domain, PostgreSQL data volume, Caddy, API, agent worker, migration/backup jobs, and Cloudflare proxy path.
- Provision the VM, network rules, volume mount, deploy user, Docker runtime, log rotation, and required OCI monitoring through reviewed OpenTofu/Terraform and cloud-init where practical; document any one-time console operation.
- Configure `cephalonthesos.com`, redirect `www.cephalonthesos.com`, Cloudflare proxying, strict origin TLS, Turnstile, security headers, and an origin firewall that does not trust arbitrary forwarding headers.
- Configure a dedicated transactional-email subdomain with Resend verification, SPF, DKIM, and DMARC; exercise registration, verification, and password reset against production URLs before inviting users.
- Publish immutable SHA-tagged ARM64 images to GHCR from GitHub Actions. The VM pulls images; no compiler, repository checkout, or self-hosted GitHub runner is required on production.
- Keep the deployment gate compact but mandatory: dependency lock validation, frontend typecheck/build, API import/startup, focused auth/quota tests, and PostgreSQL migration from an empty database. Full browser, visual, and live-provider suites run separately rather than blocking every deployment.
- On an approved main-branch deployment, serialize production jobs, verify the SSH host key, pull the exact image digest, take a pre-migration logical backup when schema changes, run the one-shot migration, update services, and check external login/static/API readiness.
- Retain the previous application image set and automatically roll it back if post-deploy health checks fail. Database migrations use expand/contract sequencing and are never blindly downgraded by automation.
- Configure nightly encrypted PostgreSQL backups to private Object Storage, backup-age monitoring, container/disk/API/provider alarms, and one documented restore drill.
- Seed the admin email and initial allowlist out of band, then invite a deliberately small tester cohort. The site remains noindex for private chat/account/admin routes and clearly labels answers as ungrounded early-alpha output.
- Establish an operations checklist for deployment, rollback, user suspension, quota grant, provider-budget exhaustion, key rotation, backup restore, and taking generation offline while leaving static status/legal pages available.

CI/CD policy:

- Pull requests run ordinary lint/type/unit checks without production secrets.
- A push to `main` builds and publishes immutable images.
- Production deployment uses a GitHub `production` environment and begins with manual approval during the private alpha. Only one deployment may run at a time.
- Production secrets remain on the VM or in the protected deployment environment and are never baked into images, frontend bundles, logs, or workflow artifacts.
- There is no second VM or permanent staging environment initially; local PostgreSQL/Compose is the pre-production integration environment.

Exit gate:

- `https://cephalonthesos.com` serves the pinned release with strict TLS and same-origin API access after a fresh VM rebuild.
- Only allowlisted authenticated users can generate, each account receives the documented allowance, and the admin can approve access/extra usage and inspect content-free traffic/cost data.
- A failed application rollout returns to the prior image set, and a clean PostgreSQL restore from Object Storage has been demonstrated.
- Provider and global daily budgets can stop new generations without taking down login, account, legal, or admin status pages.
- The first private-alpha week has an explicit user ceiling, provider-cost ceiling, and daily operator review.

### Phase 4: Corpus ingestion and candidate retrieval

Objective: build trustworthy evidence retrieval independently of answer generation.

Deliver:

- Define source, document, immutable revision, section, chunk, entity, and alias models.
- Implement one authoritative source adapter and one structured-data adapter.
- Build cleaning, normalization, structure-aware chunking, metadata, and provenance stages.
- Implement entity and alias resolution.
- Build BM25S title, heading, and body indexes with reciprocal rank fusion and deterministic second-stage scoring.
- Implement context packing and an internal retrieval inspection endpoint or admin view.
- Publish indexes atomically with corpus revision manifests.
- Build the initial retrieval evaluation dataset and report.

Database work:

- Add all corpus, ingestion, entity, alias, chunk, revision, and index-manifest tables.
- Add activation constraints so only a fully validated corpus revision becomes current.
- Store large raw snapshots outside PostgreSQL and retain hashes/object keys in the database.

Exit gate:

- Representative Warframe questions retrieve the expected evidence and stable source identity.
- Corpus rebuilds do not interrupt active queries.
- Failed or partial ingestion cannot become active.
- Retrieval quality has measured baselines rather than subjective approval alone.

### Phase 5: Grounded RAG answer loop

Objective: replace generic model memory with evidence-backed Warframe answers while keeping the control path simple.

Deliver:

- Add deterministic entity resolution and retrieval before answer generation.
- Create the typed evidence ledger.
- Pack evidence with stable citation IDs and untrusted-source boundaries.
- Implement the `archive_answer` workflow without a planner.
- Produce internal answer drafts with claim-to-evidence references.
- Add deterministic citation, URL, freshness, and output-schema verification.
- Buffer draft prose until verification, then release the validated answer.
- Render citations, assumptions, warnings, and freshness in the frontend.
- Add answer and retrieval caches keyed by corpus and policy versions.
- Build factual, unsupported, stale, conflicting-source, and citation eval cases.

Database work:

- Add `agent_evidence`, `agent_final_answer`, `answer_cache`, `tool_cache`, and source-link tables.
- Link every final citation to immutable evidence and corpus revisions.

Exit gate:

- Simple factual questions retrieve, answer, cite, and stop without planning.
- Unsupported questions are qualified rather than answered from unsupported model memory.
- Citation links and claim support pass deterministic and sampled semantic checks.
- Changing the active corpus revision invalidates affected caches correctly.

### Phase 6: Production bounded agent controller

Objective: introduce professional agentic behavior only after the grounded single-pass path is reliable.

Deliver:

- Implement the closed, typed controller state machine.
- Add intent assessment, workflow routing, and dynamic toolset selection.
- Implement planner, plan validation, bounded step executor, evidence assessment, plan-tail revision, and clarification.
- Enforce parent-shared model, token, tool, time, replan, and cost budgets.
- Add canonical tool-call hashes, duplicate suppression, no-progress detection, and all terminal states.
- Add answer verification and one targeted repair path.
- Emit sanitized plan and progress events without chain-of-thought.
- Add scripted controller tests and span-based behavioral evaluations.

Database work:

- Add `agent_step`, `agent_plan_step`, `agent_tool_call`, `agent_clarification`, transition-version, and compact controller-state records.
- Preserve large evidence and drafts by reference rather than serializing them into workflow state.

Exit gate:

- Complex evaluation cases take the expected workflow paths.
- Repeated tools, runaway replans, retry multiplication, recursive delegation, and budget escalation are impossible under tests.
- Every failure, clarification, partial answer, cancellation, and successful completion is recoverable and understandable.

### Phase 7: Warframe domain tools and specialist workflows

Objective: add useful agency through independently trustworthy, read-only domain capabilities.

Deliver in this order:

1. World-state and reset/rotation tools.
2. Warframe.market read-only item and listing tools with respectful pacing and caching.
3. Versioned mechanics and formula registry.
4. Deterministic calculation engine.
5. Build construction, validation, calculation, and comparison workflow.

Each tool requires:

- Typed contracts and normalized result envelopes.
- Fixtures and failure tests.
- Source provenance and freshness.
- Cache, timeout, retry, and concurrency policies.
- Rate-limit and external-request accounting.
- Agent evaluation cases before toolset exposure.

Database work:

- Add structured world-state snapshots, reset schedules, mechanics versions, market cache records, and calculation-result schemas as their tools are implemented.
- Do not mix transient third-party payload dumps with canonical game data.

Exit gate:

- Tool outputs are trustworthy when called without an LLM.
- Numerical, rotation, and market answers remain correct when prose generation uses a deterministic test model.
- The agent cannot access a domain tool outside its selected workflow.

### Phase 8: Durable long research

Objective: make multi-minute research resumable without adding Redis, Celery, or another workflow service.

Deliver:

- Add step-level DBOS durability to model requests, retrieval passes, tool calls, plans, and evidence assessments.
- Add queue priorities so ordinary interactive questions outrank background research work.
- Implement worker leases, bounded concurrency, cancellation, and startup recovery.
- Add durable clarification suspension and continuation.
- Implement the long research workflow and evidence-digest compaction.
- Establish workflow code-version, deployment-drain, and in-flight migration policy.
- Test crash, restart, network partition, provider outage, and mid-deployment recovery.

Database work:

- Enable and migrate DBOS-owned production tables according to DBOS guidance.
- Add workflow-version and recovery metadata to application run records without editing DBOS-owned schemas.
- Establish retention and cleanup for completed workflow state.

Exit gate:

- A research run survives API restart, worker restart, browser refresh, and transient provider failure.
- Completed external reads are not unnecessarily repeated after recovery.
- Queueing research cannot materially degrade quick-answer latency.

### Phase 9: Intelligence-complete hardening and expanded private alpha

Objective: requalify the hosted system after retrieval, tools, the bounded controller, and durable research materially increase its risk and resource use.

Deliver:

- Edge and backend rate limiting plus abuse challenge integration.
- Full retention, purge, and privacy verification.
- Extend the Phase 3B admin interface for corpus, tools, research queues, and eval operations.
- Provider quota alarms and hard daily budget controls.
- Backups, restore drill, monitoring, alerts, and operational runbooks.
- CSP, security headers, admin authentication, dependency review, and penetration checklist.
- Load tests for cached, generic, grounded, agentic, and research paths.
- Re-review privacy, terms, about, provider disclosure, unofficial-project copy, and account deletion/export procedures.
- VM manifest amendments and final measured container limits.

Database work:

- Add only the additional operations, feedback, audit, and admin-support tables demonstrated as necessary after the Phase 3B baseline.
- Test production-like backup and restore with application and DBOS schemas together.

Exit gate:

- All VM commissioning and production-readiness gates pass.
- One account, device, or network cannot exhaust provider quotas or monopolize the worker.
- Restore, rollback, workflow recovery, and corpus rollback are demonstrated.

### Phase 10: Public beta and controlled expansion

Objective: learn from real traffic without destabilizing the cost or trust model.

Deliver:

- Controlled traffic ramp and explicit concurrency ceilings.
- Daily review of failures, cost, retrieval gaps, and user feedback.
- Public status communication for provider, live-data, or corpus degradation.
- Weekly eval expansion from opt-in, anonymized, manually recreated, or synthetic failure cases.
- Model and prompt changes only through recorded evaluation comparisons.

Do not add embeddings, unrestricted web research, public self-service registration, side-effecting tools, or additional providers during the initial ramp unless an observed failure demonstrates the need and the appropriate earlier-phase quality gates are extended.

### 17.1 Progressive database map

The database evolves with the product rather than being designed in one speculative pass:

| Development phase | Database increment |
|---|---|
| 0 | PostgreSQL, roles, Alembic baseline, migration and test infrastructure |
| 1 | No product schema; browser-local fixtures and state |
| 2 | Anonymous sessions, runs, events, idempotency, dispatch outbox, retention |
| 3 | Model calls, provider usage/budgets, basic workflow dispatch |
| 3A | PostgreSQL production parity, completed dispatch/event ownership, purge, and production runtime configuration |
| 3B | Allowlist, accounts, password credentials, email-action tokens, sessions, roles/admin MFA, device signals, quota ledger/grants/requests, and admin audit |
| 3C | Production deployment state, backup records, release metadata, and operational health baselines |
| 4 | Sources, documents, revisions, sections, chunks, entities, ingestion, index manifests |
| 5 | Evidence, citations, final answers, retrieval/answer caches |
| 6 | Plans, steps, tool calls, clarifications, controller transitions |
| 7 | World state, mechanics versions, market cache, calculation records as needed |
| 8 | DBOS workflow state, recovery metadata, workflow retention |
| 9-10 | Intelligence-era operational, feedback, audit, and measured product additions only |

Every phase includes a forward migration, clean-database test, representative data fixture, index review, and backup/restore impact assessment. Database design remains progressive, but schema ownership and migration discipline begin in Phase 0.

## 18. Production Readiness Checklist

### Correctness

- Retrieval eval thresholds met.
- Citation IDs and links verified server-side.
- Calculation fixtures and property tests pass.
- Live data displays observation and expiry.
- Unsupported claims fail closed or carry explicit warnings.

### Agent behavior

- Every run has enforced model, token, tool, time, and cost budgets.
- No-progress and duplicate-call guards tested.
- Toolsets are workflow-scoped.
- Planner output is validated before execution.
- Verifier cannot create uncited replacement content.
- Child agents share parent usage limits.
- Cancellation is checked at every expensive boundary.

### Reliability

- Event replay and SSE reconnect tested.
- Provider fallback tested before first output.
- Mid-stream failure behavior tested.
- Worker recovery and durable steps tested.
- Cache and ingestion publication fail safely.
- PostgreSQL restore drill completed.

### Security and privacy

- No arbitrary network or execution tool exists.
- Prompt injection fixtures pass.
- Logs contain no chat content by default.
- Retention purge verified against database and backups policy.
- Admin endpoints require authentication.
- CSP and output sanitization pass browser tests.
- Provider privacy behavior matches published disclosure.

### Performance and cost

- p50 and p95 latency recorded by workflow.
- First-token and queue-wait targets met.
- Concurrent run load does not starve PostgreSQL or Caddy.
- Provider concurrency and daily budgets enforced.
- Ingestion yields or pauses under interactive load.
- ARM64 production images remain within disk and memory budgets.

## 19. Explicit Non-Goals for Initial Release

- A general-purpose autonomous web agent.
- Multi-agent swarms or open-ended agent delegation.
- Embedding-based retrieval without evaluation evidence.
- A neural reranker by default.
- Local generative model hosting.
- Unrestricted public registration, federated social login/account linking, or paid account tiers during the private alpha.
- Cloud-synchronized chat history; authentication does not move browser-local conversations into the account automatically.
- Invasive canvas, font, audio, GPU, behavioural, or cross-site device fingerprinting.
- Automated trading, seller messaging, or account-authenticated market actions.
- Arbitrary code execution or user-supplied plugins.
- Redis, Celery, Elasticsearch, Kubernetes, or a separate vector database.
- A permanent Node server.
- A LiteLLM proxy before multiple internal services require a shared gateway.

## 20. Open Decisions and Required Spikes

1. Select the initial OpenRouter models for each role through tool-use, structured-output, latency, privacy, and cost evaluation.
2. Validate DBOS and Pydantic AI event streaming together under worker restart and deployment.
3. Benchmark BM25S memory-mapped indexes on ARM64 with the estimated corpus.
4. Confirm the Warframe Wiki permission, export route, attribution terms, and synchronization limits, then define the remaining authoritative/community source policies.
5. Specify Warframe entity ontology and alias governance.
6. Establish exact account, authentication, security-signal, temporary-content, and share-expiry periods in privacy copy.
7. Define build-calculation scope for the first supported weapon and damage modes.
8. Confirm Warframe.market API policies, caching, and endpoint rate limits before public tooling.
9. Set measured quick, standard, and research budgets from provider quotas and alpha traces.
10. Choose the OpenTelemetry backend or local retention strategy without compromising privacy or free-tier goals.
11. Confirm the initial admin email, tester allowlist, Resend account/sending subdomain, Cloudflare zone, OCI home region, and production GitHub environment before Phase 3C commissioning.
12. Set the private-alpha maximum active accounts, global daily run ceiling, per-IP/device anomaly thresholds, and OpenRouter hard-spend response from measured local/provider data.

## 21. Framework References

- NIST password-authenticator requirements: <https://pages.nist.gov/800-63-4/sp800-63b/authenticators/>
- OWASP password storage and Argon2id guidance: <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html>
- OWASP email validation and verification guidance: <https://cheatsheetseries.owasp.org/cheatsheets/Email_Validation_and_Verification_Cheat_Sheet.html>
- Resend transactional-email quotas and limits: <https://resend.com/docs/knowledge-base/account-quotas-and-limits>
- OWASP authentication, session, and CSRF guidance: <https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html>
- Cloudflare Turnstile server-side validation: <https://developers.cloudflare.com/turnstile/get-started/server-side-validation/>
- ICO storage/access technology guidance, including device fingerprinting: <https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-the-use-of-storage-and-access-technologies/>
- GitHub Actions deployment environments and concurrency: <https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments>
- OCI Always Free resource limits: <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm>
- Pydantic AI agents and event streaming: <https://pydantic.dev/docs/ai/core-concepts/agent/>
- Pydantic AI tools and toolsets: <https://pydantic.dev/docs/ai/tools-toolsets/tools/>
- Pydantic AI multi-agent patterns: <https://pydantic.dev/docs/ai/guides/multi-agent-applications/>
- Pydantic AI fallback models: <https://pydantic.dev/docs/ai/models/overview/>
- Pydantic AI DBOS durability: <https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/>
- Pydantic AI testing: <https://pydantic.dev/docs/ai/guides/testing/>
- Pydantic Evals: <https://pydantic.dev/docs/ai/evals/evals/>
- OpenRouter provider routing: <https://openrouter.ai/docs/guides/routing/provider-selection>
- OpenRouter tool calling: <https://openrouter.ai/docs/guides/features/tool-calling>
- React Router static pre-rendering: <https://reactrouter.com/how-to/pre-rendering>
- BM25S: <https://github.com/xhluca/bm25s>
- OWASP excessive agency guidance: <https://genai.owasp.org/llmrisk/llm062025-excessive-agency/>
