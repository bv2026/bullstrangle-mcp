# BullStrangle Refactor Implementation Roadmap

Status: Draft Roadmap
Date: 2026-05-25
Scope: Implementation roadmap only. No runtime code, migrations, or MCP tools are implemented by this document.

Inputs:
- `BullStrangle_Product_Spec_Refactor_PRD.md`
- `BullStrangle_Target_Architecture_v4.md`
- `BullStrangle_Target_Schema_v4.md`

## 1. Superseding Guardrails

This roadmap treats the refactor as a new self-contained project from scratch.

Hard constraints:
- Do not mutate the legacy BullStrangle runtime.
- Do not entangle the new project with legacy modules.
- Do not introduce runtime dependency from the new project back into the legacy project.
- Legacy code may be read for context only.
- Legacy SQLite may be read only through explicit one-way import tooling.
- The new runtime database is PostgreSQL.
- SQLite is not allowed for the new runtime.
- The new project owns its own package, config, migrations, MCP server, provider abstraction, tests, and deployment path.
- Live trading remains disabled until paper/shadow confidence thresholds, operator approvals, broker reconciliation, and safety guardrails are implemented and approved.

## 2. Target Outcome

The first usable system is a self-contained one-symbol MVP:

```text
newsletter symbol
  -> Tradier provider
  -> live option chain
  -> live strike selection
  -> P/L + probability
  -> explainable entry decision
  -> paper trade intent
  -> order draft
  -> simulated fill
  -> lifecycle event
  -> replay report
```

The MVP must not require legacy runtime modules, legacy SQLite tables, Option Samurai Excel, or live broker submission.

## 3. Proposed New Project Structure

Recommended location if created inside this repository:

```text
refactor_v4/
  pyproject.toml
  README.md
  AGENTS.md
  alembic.ini
  migrations/
    env.py
    versions/
  src/
    bullstrangle_v4/
      __init__.py
      config.py
      logging.py
      db/
        __init__.py
        models.py
        session.py
        migrations.py
        seed.py
        import_legacy.py
      domain/
        artifacts.py
        policies.py
        market_data.py
        scanner.py
        pl.py
        probability.py
        decisions.py
        execution.py
        portfolio.py
        outcomes.py
        confidence.py
      providers/
        __init__.py
        base.py
        tradier.py
        fixtures.py
      services/
        ingest_newsletter.py
        run_scan.py
        create_paper_trade.py
        replay_decision.py
      mcp/
        server.py
        tools_read.py
        tools_write.py
        schemas.py
        formatters.py
      cli/
        main.py
      reports/
        replay_report.py
      safety/
        live_guardrails.py
      tests/
        fixtures/
```

Alternative: create a sibling repository. That is cleaner if the refactor will have independent release cadence. If kept in this repo, it must remain isolated under a new top-level folder/package and must not import `src/bullstrangle_mcp`.

## 4. Package And Module Boundaries

Core boundaries:
- `bullstrangle_v4.db`: PostgreSQL models, sessions, Alembic integration, seed data, one-way legacy import.
- `bullstrangle_v4.domain`: pure domain logic and typed dataclasses/Pydantic models.
- `bullstrangle_v4.providers`: provider abstraction and provider implementations.
- `bullstrangle_v4.services`: use-case orchestration; no MCP-specific assumptions.
- `bullstrangle_v4.mcp`: MCP tool layer only; validates inputs, calls services, formats responses.
- `bullstrangle_v4.cli`: local operator/dev commands using the same services.
- `bullstrangle_v4.safety`: mode flags, live-trading hard blocks, approval checks.

Forbidden dependencies:
- `bullstrangle_v4.*` importing `bullstrangle_mcp.*`.
- Runtime queries against legacy SQLite.
- Runtime reads from legacy OS workbook tables.
- Runtime reliance on Option Samurai Excel.

Allowed dependencies:
- One-way import scripts reading legacy SQLite by file path.
- Test fixtures derived from legacy data snapshots.
- Documentation references to legacy behavior.

## 5. PostgreSQL Infrastructure

### Local Dev

Use local PostgreSQL through Docker Compose or installed PostgreSQL.

Recommended databases:
- `bullstrangle_dev`
- `bullstrangle_test`

Recommended environment:

```text
BULLSTRANGLE_DATABASE_URL=postgresql+psycopg://bullstrangle:bullstrangle@localhost:5432/bullstrangle_dev
BULLSTRANGLE_TEST_DATABASE_URL=postgresql+psycopg://bullstrangle:bullstrangle@localhost:5432/bullstrangle_test
BULLSTRANGLE_SCHEMA=bullstrangle
TRADIER_BASE_URL=...
TRADIER_TOKEN=...
LIVE_TRADING_ENABLED=false
BROKER_SUBMISSION_ENABLED=false
```

### Test DB

Test DB requirements:
- Separate PostgreSQL database.
- Tests run Alembic migrations from base to head.
- Tests either use transaction rollback fixtures or recreate schema.
- No test requires legacy SQLite unless marked `legacy_import`.
- Provider tests use recorded fixtures by default.
- Live provider tests are opt-in and skipped unless credentials are present.

### Migration Workflow

Use Alembic with SQLAlchemy 2.x.

Rules:
- Every schema change is an Alembic migration.
- No ad-hoc DDL in runtime services.
- Migration PRs include downgrade/rollback notes.
- Migration tests run `alembic upgrade head` against empty test DB.
- Destructive migrations are not allowed until after explicit architecture review.
- Seed/reference data is versioned either as migrations or deterministic seed scripts.

### Seed Data

Initial seed data:
- strategy rules, including Gate 7 as advisory/retired by default.
- pricing policy: conservative paper pricing.
- strike-selection policy: provisional values once strategy owner approves.
- P/L formula version.
- probability model version.
- strategy policy bundle.
- paper portfolio definitions for Large and Small.

Seed strategy:
- policy/rule seeds are deterministic and idempotent.
- seed scripts fail on incompatible existing active versions.
- seed outputs are logged for audit.

### Rollback Strategy

Rollback levels:
- Code rollback: redeploy prior app version against compatible DB schema.
- Migration rollback: Alembic downgrade only for non-destructive early migrations.
- Data rollback: restore PostgreSQL backup for destructive data corruption.
- Provider rollback: disable provider or switch to fixture/imported benchmark mode.
- Product fallback: keep legacy runtime operational and untouched throughout.

Before any migration touching existing production data:
- take PostgreSQL backup.
- run migration on test DB.
- run migration on staging/dev snapshot.
- verify smoke tests.

## 6. RTK-Compliant Development Workflow

Future engineering work must use RTK for shell commands.

Examples:

```powershell
rtk powershell -NoProfile -Command "Get-Content README.md"
rtk py -m pytest
rtk py -m ruff check .
rtk py -m mypy src
rtk alembic upgrade head
```

Before implementation starts:
- re-check repo-local instructions with RTK, including any `AGENTS.md`.
- use RTK-wrapped commands for tests, linting, type checks, migration checks, and local service checks.
- do not bypass RTK for direct shell execution.

Roadmap note: current roadmap creation did not implement code. Future command examples are illustrative and should be adapted to the new project tooling once created.

## 7. MCP Design Principles

The MCP server must follow the MCP builder guidance.

MCP rules:
- Design tools around workflows, not raw API endpoints.
- Keep tools small, typed, explainable, and safe.
- Use clear service-prefixed names, e.g. `bullstrangle_scan_symbol`.
- Use Pydantic input models for Python.
- Return concise default responses with optional detailed JSON.
- Include pagination for list tools.
- Add character limits and truncation guidance.
- Provide actionable error messages.
- Annotate tools with read-only/destructive/idempotent/open-world hints.
- Split read-only tools from write/create tools.
- No live-trading-capable tool is registered until live readiness is approved.
- Broker submission tools remain absent or hard-disabled until live phase.

MCP tool implementation must be preceded by an MCP tool design review.

## 8. MCP Tool Design Milestones

### MCP Review 1: MVP Tool Surface

Candidate read-only tools:
- `bullstrangle_get_newsletter`
- `bullstrangle_list_watchlist`
- `bullstrangle_get_provider_status`
- `bullstrangle_get_scan_result`
- `bullstrangle_get_entry_decision`
- `bullstrangle_replay_decision`

Candidate write/non-destructive creation tools:
- `bullstrangle_import_legacy_newsletter`
- `bullstrangle_scan_symbol`
- `bullstrangle_create_paper_trade`

Guardrails:
- `bullstrangle_scan_symbol` may call Tradier, so it is `openWorldHint=true`.
- `bullstrangle_create_paper_trade` writes to PostgreSQL but is non-live and idempotent by key.
- No broker submission tool in MVP.

### MCP Review 2: Full Watchlist Paper Run

Candidate tools:
- `bullstrangle_scan_watchlist`
- `bullstrangle_create_paper_portfolio_run`
- `bullstrangle_list_paper_trades`
- `bullstrangle_get_portfolio_snapshot`
- `bullstrangle_compare_replication_vs_live`

Guardrails:
- Full watchlist scan must have limits, batching, provider rate-limit handling, and resumability.
- Tool response defaults to summary with links/IDs for detail retrieval.

### MCP Review 3: Shadow Mode

Candidate tools:
- `bullstrangle_create_shadow_order_draft`
- `bullstrangle_list_order_drafts`
- `bullstrangle_get_order_draft`
- `bullstrangle_request_operator_approval`

Guardrails:
- Shadow tools do not submit broker orders.
- Approval records are audit artifacts only until live mode is approved.

### MCP Review 4: Live Readiness

Candidate tools only after approval:
- `bullstrangle_submit_approved_live_order`
- `bullstrangle_sync_broker_positions`
- `bullstrangle_reconcile_live_position`

Guardrails:
- Tools are disabled unless `LIVE_TRADING_ENABLED=true` and `BROKER_SUBMISSION_ENABLED=true`.
- Require approved immutable draft hash.
- Require idempotency/client order ID.
- Require account allowlist.
- Require fresh market data.
- Require audit event.

## 9. Phase 0: Project Foundation And Contracts

Goal: establish the self-contained project boundary, PostgreSQL foundation, and implementation contracts.

Tasks:
- Create new project folder/package boundary.
- Add project README that states legacy isolation rules.
- Add project-local `AGENTS.md` with RTK usage, no legacy imports, PostgreSQL-only runtime, and live-trading disabled-by-default rules.
- Select Python stack: Python 3.13, SQLAlchemy 2.x, Alembic, psycopg, Pydantic v2, FastMCP or MCP Python SDK.
- Define config model and environment variables.
- Create PostgreSQL local dev/test setup plan.
- Define provider interfaces and normalized quote/chain dataclasses.
- Define P/L formula contract.
- Define probability model contract.
- Define strike-selection policy contract.
- Define pricing policy contract.
- Define execution lifecycle state machine.
- Define MCP tool design review checklist.

Non-goals:
- No runtime implementation.
- No migrations.
- No provider calls.
- No MCP tools.
- No legacy import.

Validation gates:
- Architecture owner approves package boundary.
- Schema owner approves PostgreSQL-only migration strategy.
- MCP tool design checklist exists.
- Live trading disabled-by-default requirements are documented.

Definition of Done:
- New project boundary is approved.
- Engineering contracts are written and reviewed.
- No legacy runtime files are changed.

## 10. Phase 1: PostgreSQL Schema And Seed Baseline

Goal: create the new runtime database foundation.

Tasks:
- Initialize Alembic.
- Create `bullstrangle` PostgreSQL schema.
- Add migrations for artifact, policy, provider, scanner, decision, execution, portfolio, outcome, confidence, and audit tables from schema design.
- Add migration tests for empty DB upgrade.
- Add deterministic seed scripts for rules and policy versions.
- Add local dev DB and test DB setup docs.
- Add backup and rollback docs.
- Add schema lint/review checklist.

Non-goals:
- No provider implementation.
- No scanner implementation.
- No MCP tools.
- No live broker integration.
- No dependency on legacy SQLite at runtime.

Validation gates:
- `rtk alembic upgrade head` works on empty dev DB.
- test DB can be created and migrated from scratch.
- seed script creates required active policies.
- schema contains live-ready tables but no live execution code exists.

Definition of Done:
- PostgreSQL migrations and seed strategy are ready for implementation review.
- Local dev/test DB instructions are complete.
- Rollback plan is documented.

## 11. Phase 2: One-Way Legacy Import Foundation

Goal: optionally load starter newsletter/watchlist data without coupling to legacy runtime.

Tasks:
- Build import service that reads legacy SQLite by file path only.
- Import newsletters, sections, watchlist entries, and short-list entries into PostgreSQL-native tables.
- Record import batches, source hash, legacy table names, and legacy primary keys.
- Add idempotency for re-imports.
- Add import validation report.
- Add fixtures for one-symbol MVP if import is unavailable.

Non-goals:
- No runtime reads from legacy SQLite.
- No import of legacy Python modules.
- No mutation of legacy SQLite.
- No OS workbook dependency.

Validation gates:
- Import can run against copied read-only SQLite DB.
- Imported data is queryable from PostgreSQL only.
- Re-import is idempotent.
- Legacy runtime remains operational and unchanged.

Definition of Done:
- New project has enough native PostgreSQL data to select one newsletter symbol.
- Legacy import is optional and isolated.

## 12. Phase 3: Provider Abstraction And Tradier Read Path

Goal: retrieve and normalize live market data through a provider contract.

Tasks:
- Implement provider interface: quote, option chain, provider status.
- Implement Tradier provider behind interface.
- Normalize stock quotes and option chain rows.
- Persist `market_data_runs`, `stock_quote_snapshots`, `option_chain_snapshots`, and `option_chain_rows`.
- Add typed provider errors: auth, entitlement, rate limit, stale data, partial data, missing critical fields, network error.
- Add recorded fixture provider for tests.
- Add provider status service.

Non-goals:
- No scanner decisions yet.
- No paper trades yet.
- No broker execution.
- No dependency on broker MCP/control plane.

Validation gates:
- Fixture provider tests pass without network.
- Tradier live test is opt-in and skipped without credentials.
- Provider failures persist `market_data_runs` with structured error evidence.
- No provider-specific payload leaks into scanner/domain contracts except raw `jsonb`.

Definition of Done:
- One symbol quote and option chain can be normalized and persisted in PostgreSQL.
- Provider abstraction can be mocked in tests.

## 13. Phase 4: Scanner, Strike Selection, P/L, Probability

Goal: produce replayable candidate evaluations from live provider snapshots.

Tasks:
- Implement expiration selection based on approved DTE policy.
- Implement newsletter replication mode.
- Implement live strike-selection mode.
- Implement liquidity filtering and deterministic tie-breakers.
- Persist `live_watchlist_snapshots` and `selected_trade_legs`.
- Implement conservative pricing policy.
- Implement P/L engine and persist `pl_evaluations`.
- Implement scenario table persistence where in scope.
- Implement probability engine and persist `probability_evaluations`.
- Add replay fixture for `AA` or approved MVP symbol.

Non-goals:
- No portfolio optimization.
- No full watchlist batch scan.
- No live order drafts.
- No broker integration.

Validation gates:
- For one symbol, selected legs can be replayed from stored snapshots.
- P/L outputs include formula version and assumptions.
- Probability outputs include model version and assumptions.
- Provider failure leads to `DATA_UNAVAILABLE`, not `REJECT`.
- Paper pricing is no more favorable than the configured conservative policy.

Definition of Done:
- One-symbol scanner can produce complete persisted market, leg, P/L, and probability evidence.

## 14. Phase 5: Entry Decision And Paper Lifecycle MVP

Goal: complete the first vertical slice from symbol to paper trade lifecycle.

Tasks:
- Implement entry decision service with statuses `ACCEPT`, `WATCH`, `REJECT`, `DATA_UNAVAILABLE`.
- Persist decision evidence, liquidity summary, portfolio fit placeholder, and explanation.
- Implement trade intent creation for accepted paper decisions.
- Implement broker-neutral order draft and order draft legs.
- Implement simulated fill and fill legs.
- Implement lifecycle event append.
- Implement replay report from PostgreSQL data only.
- Implement audit events for scan, decision, intent, draft, and fill.
- Build service-level idempotency for scan, decision, intent, and draft.

Non-goals:
- No live submission.
- No shadow approval workflow.
- No full monitoring.
- No full portfolio constraints beyond minimal paper metadata.
- No MCP tools until MCP review gate passes.

Validation gates:
- One-symbol MVP path runs end-to-end in paper mode.
- No live broker order table row is created in MVP path.
- No code path can submit live order.
- Replay report can explain source newsletter, provider snapshots, selected legs, P/L, probability, decision, and paper fill.
- Legacy runtime remains untouched.

Definition of Done:
- The one-symbol MVP is complete.
- OS Excel is not required.
- PostgreSQL is the only runtime DB.

## 15. Phase 6: MCP Server MVP

Goal: expose the MVP through a safe, typed MCP tool surface.

Prerequisite: MCP tool design review 1 is approved.

Tasks:
- Create self-contained MCP server under new package.
- Implement Pydantic input/output schemas.
- Implement read-only tools for newsletter, watchlist, provider status, scan result, decision, replay.
- Implement non-live write tools for import, scan symbol, create paper trade if not already created by service.
- Add tool annotations.
- Add response formats: concise Markdown default, JSON detailed option.
- Add pagination to list tools.
- Add character limit/truncation utility.
- Add actionable error messages.
- Add MCP tool unit tests using service fakes.
- Add MCP evaluation scenarios for read-only workflows.

Non-goals:
- No shadow/live tools.
- No broker order submission tools.
- No destructive tools.

Validation gates:
- MCP tools have reviewed names, descriptions, schemas, and annotations.
- Read/write boundaries are documented.
- Tools do not expose internal stack traces.
- Tool responses are bounded and explain truncation.
- Tests cover invalid inputs and provider failure.

Definition of Done:
- MVP can be operated through safe MCP tools.
- MCP surface remains self-contained and legacy-isolated.

## 16. Phase 7: Full Watchlist Paper Run

Goal: expand from one-symbol MVP to complete newsletter watchlist paper evaluation.

Tasks:
- Implement batch scan orchestration with provider rate-limit handling.
- Support resumable scan runs.
- Run newsletter replication and live strike-selection side by side.
- Create Large and Small paper portfolio records.
- Apply preliminary portfolio constraints: max positions, cash assumption, duplicate policy, assignment capacity.
- Generate weekly paper entry report.
- Add MCP tools for full watchlist scan and portfolio snapshots after MCP review 2.

Non-goals:
- No live execution.
- No broker sync.
- No automated exit management beyond marks if explicitly included.

Validation gates:
- Full watchlist scan completes or fails partially with clear retry state.
- Large and Small books are separated.
- Rejected/WATCH/DATA_UNAVAILABLE candidates are retained for later comparison.
- Provider errors do not crash entire run.

Definition of Done:
- A full newsletter can be paper-scanned without OS Excel or legacy runtime dependency.

## 17. Phase 8: Monitoring, Scenarios, Outcomes

Goal: track open paper trades through expiration and classify outcomes.

Tasks:
- Implement mark-to-market service.
- Persist paper marks.
- Detect strike proximity and close-price availability.
- Classify Darren's five scenarios.
- Persist assignment events where modeled.
- Persist trade outcomes.
- Generate scenario scoreboard.
- Add monitoring reports.

Non-goals:
- No live broker reconciliation.
- No automated live exits.
- No live order tools.

Validation gates:
- Paper trades progress through lifecycle events.
- Expiration outcomes are reproducible from marks and fills.
- Scenario scoreboard separates Large and Small.
- Operator override is auditable.

Definition of Done:
- Paper lifecycle produces outcome data suitable for confidence scoring.

## 18. Phase 9: Confidence Reporting

Goal: quantify evidence from paper history before shadow/live.

Tasks:
- Implement trade scorecards.
- Implement system confidence metrics.
- Compare expected vs realized P/L.
- Compare accepted vs watched/rejected candidates.
- Compare newsletter replication vs live strike-selection.
- Compare Large vs Small portfolios.
- Define shadow readiness threshold.
- Define live readiness threshold.

Non-goals:
- No live execution enablement.
- No broker order submission.

Validation gates:
- Confidence calculations are versioned and explainable.
- Metrics show sample size and confidence limitations.
- Shadow/live thresholds are configured but do not enable live trading.

Definition of Done:
- Operator can see whether paper evidence is improving or deteriorating.
- Shadow/live promotion gates are explicit but inactive until approved.

## 19. Phase 10: Shadow Mode

Goal: create live-like order drafts without broker submission.

Tasks:
- Implement shadow trade intent flow.
- Implement order draft approval records.
- Implement immutable draft hash.
- Add operator approval UI/MCP workflow if approved.
- Compare shadow recommendations to actual operator action.
- Add MCP tools after MCP review 3.

Non-goals:
- No broker submission.
- No live fills.
- No broker position sync as source of truth.

Validation gates:
- Shadow mode cannot submit orders.
- Approval records are immutable to draft version.
- Changing price/account/quantity/legs requires new draft and approval.

Definition of Done:
- Shadow mode exercises order construction and approval workflow safely.

## 20. Phase 11: Live Trading Readiness

Goal: prepare, review, and only then enable live broker execution.

Prerequisites:
- Paper confidence threshold met.
- Shadow confidence threshold met.
- Operator approval workflow implemented.
- Broker account allowlist configured.
- Live safety review approved.
- MCP live tool review approved.

Tasks:
- Implement broker execution interface.
- Implement broker-specific adapter behind execution interface.
- Implement account allowlist.
- Implement stale-data hard blocker.
- Implement max notional, max contracts, max buying-power, and max loss guardrails.
- Implement idempotent client order IDs.
- Implement broker order submission only for approved immutable drafts.
- Implement broker fills and live positions.
- Implement broker reconciliation.
- Implement kill switch.
- Add live MCP tools only after MCP review 4.

Non-goals:
- No fully automated trading without operator approval.
- No live execution when confidence thresholds are unmet.
- No bypass of idempotency or approvals.

Validation gates:
- Live tool disabled by default.
- Live submission fails closed without approval.
- Live submission fails closed on stale data.
- Duplicate submission is prevented.
- Broker payloads and responses are audited.
- Reconciliation flags mismatches.

Definition of Done:
- Live execution can be enabled only by explicit configuration and approved operational procedure.

## 21. OS Excel Deprecation Checkpoints

Checkpoint OS-0: Legacy unchanged
- Legacy OS Excel workflow remains operational.
- New project does not depend on OS Excel.

Checkpoint OS-1: Benchmark import
- Optional import of OS historical data for comparison only.
- Store imported OS as `legacy_os` provider-like benchmark or separate benchmark records.

Checkpoint OS-2: Parallel comparison
- Reports compare newsletter published strikes, OS benchmark, Tradier refreshed chain, and live-selected strikes.

Checkpoint OS-3: New normal paper path
- Paper workflow uses live provider scanner.
- OS Excel no longer required for new project operation.

Checkpoint OS-4: Legacy remains available
- Do not delete or modify legacy OS workflow as part of refactor.

## 22. Legacy Isolation Plan

Rules:
- New project package cannot import legacy package.
- New project tests should fail if legacy package imports appear in runtime modules.
- Legacy SQLite file path is accepted only by import scripts.
- Import scripts are not called by normal runtime services.
- Imported records carry legacy source metadata.
- Legacy runtime remains operational through all phases.

Suggested validation:
- static check for forbidden imports.
- test that runtime config has no legacy SQLite connection.
- test that services use PostgreSQL session only.
- import tests use copied read-only SQLite fixture.

## 23. Test Strategy

Test layers:
- unit tests for domain logic: pricing, strike selection, P/L, probability, decision status.
- DB tests against PostgreSQL test DB.
- migration tests: Alembic base to head.
- provider tests with fixture provider.
- optional live Tradier smoke tests behind env flag.
- service tests for one-symbol MVP.
- MCP tool tests with service fakes.
- import tests with copied legacy SQLite fixture.
- safety tests for live disabled, stale data blocked, duplicate order blocked.

Required test gates by phase:
- Phase 1: migration and seed tests.
- Phase 2: import idempotency tests.
- Phase 3: provider normalization and failure tests.
- Phase 4: scanner/P&L/probability replay tests.
- Phase 5: paper lifecycle end-to-end service test.
- Phase 6: MCP schema/error/annotation tests.
- Phase 7: full watchlist batch scan tests with fixture provider.
- Phase 8: monitoring/outcome scenario tests.
- Phase 9: confidence metric tests.
- Phase 10: shadow approval immutability tests.
- Phase 11: live guardrail tests with broker fake.

## 24. Validation Gates Summary

No phase advances unless:
- legacy runtime remains unchanged.
- PostgreSQL migrations are clean.
- tests for the phase pass.
- RTK command usage is followed.
- MCP design review is complete before tool implementation.
- live trading remains disabled unless in approved live phase.

MVP readiness gate:
- one-symbol paper lifecycle completes.
- replay report is generated from PostgreSQL only.
- provider data is persisted and replayable.
- no legacy runtime dependency exists.
- no live submission path exists.

## 25. Rollback And Fallback Plan

Fallback always available:
- continue using legacy BullStrangle runtime because it remains untouched.

New project rollback:
- revert code deployment.
- run Alembic downgrade only for safe, reviewed migrations.
- restore PostgreSQL backup if data corruption occurs.
- disable provider via config if Tradier fails.
- disable MCP write tools via config if tool safety issue appears.
- keep `LIVE_TRADING_ENABLED=false` unless live readiness is approved.

Provider fallback:
- use fixture provider for tests.
- use imported OS benchmark only for comparison, not primary runtime execution.
- mark scans `DATA_UNAVAILABLE` on provider failure.

## 26. Phase Definitions Of Done

| Phase | Definition of Done |
|---|---|
| 0 | Contracts, boundaries, and safety rules approved; no implementation. |
| 1 | PostgreSQL schema/migrations/seed plan implemented and tested. |
| 2 | Legacy import is one-way, idempotent, and optional. |
| 3 | Tradier quote/chain normalized and persisted behind provider interface. |
| 4 | One symbol can be scanned with persisted legs, P/L, and probability. |
| 5 | One-symbol paper lifecycle is complete and replayable. |
| 6 | Safe MCP MVP tools expose the paper MVP. |
| 7 | Full watchlist paper run works for Large and Small books. |
| 8 | Paper trades are monitored and outcomes classified. |
| 9 | Confidence metrics are generated from paper history. |
| 10 | Shadow mode creates approved drafts without submission. |
| 11 | Live readiness is implemented but enabled only after explicit approval. |

## 27. Immediate Next Decisions

Before any implementation:
- Confirm new project location: subdirectory vs separate repository.
- Confirm Python/MCP stack: FastMCP vs lower-level MCP Python SDK.
- Confirm local PostgreSQL setup approach.
- Confirm Alembic as migration tool.
- Confirm MVP symbol and source newsletter.
- Confirm provisional strike-selection rules.
- Confirm conservative pricing policy.
- Confirm P/L formula assumptions.
- Confirm probability model assumptions.
- Confirm exact MCP MVP tool list.
- Confirm live trading disabled-by-default configuration names.

## 28. Non-Goals For This Roadmap

- No runtime code changes.
- No migrations.
- No MCP tool wiring.
- No database creation.
- No provider API calls.
- No legacy runtime modifications.
- No live broker execution.
