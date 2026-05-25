# BullStrangle Refactor Implementation Checklist

Status: Not Started
Date: 2026-05-25
Scope: Progress tracker for the new self-contained `bullstrangle-platform` implementation. This checklist does not authorize runtime changes by itself.

Source documents:
- `BullStrangle_Product_Spec_Refactor_PRD.md`
- `BullStrangle_Target_Architecture_v4.md`
- `BullStrangle_Target_Schema_v4.md`
- `BullStrangle_Refactor_Implementation_Roadmap.md`

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete
- `[!]` Blocked or requires owner decision
- `[D]` Deferred

## 1. Non-Negotiable Guardrails

- [ ] Legacy `bullstrangle-mcp` runtime remains untouched.
- [ ] New implementation is created in a separate repository: `bullstrangle-platform`.
- [ ] New package name is `bullstrangle_platform`.
- [ ] New MCP server name is `bullstrangle_platform_mcp`.
- [ ] New CLI namespace is `bs-platform`.
- [ ] New runtime DB is PostgreSQL only.
- [ ] SQLite is used only as optional legacy one-way import source.
- [ ] New runtime has no imports from `src/bullstrangle_mcp`.
- [ ] New runtime scanner/decision/P/L/probability/execution services do not read raw files directly after ingestion.
- [ ] Live trading remains disabled until Product Owner live-readiness approval.
- [ ] All shell commands during implementation use RTK.

## 2. Pre-Implementation Decisions

- [ ] Product Owner approves final project identity.
- [ ] GitHub repository `bullstrangle-platform` is created.
- [ ] Repository/folder layout is approved.
- [ ] Lean `data/` layout is approved.
- [ ] Temporary `data/inbox/current_fixture/` lifecycle is approved.
- [ ] Agent/sub-agent scaffold is approved.
- [ ] Agent write ownership boundaries are approved.
- [ ] MVP orchestration order is approved.
- [ ] PostgreSQL schema design is approved.
- [ ] Alembic migration workflow is approved.
- [ ] Local dev DB setup approach is approved.
- [ ] Test DB setup approach is approved.
- [ ] Seed/reference data strategy is approved.
- [ ] Provider contract is approved.
- [ ] Tradier provider strategy is approved.
- [ ] Pricing policy is approved.
- [ ] Strike-selection policy is approved.
- [ ] P/L formula assumptions are approved.
- [ ] Probability model assumptions are approved.
- [ ] MCP-builder compliance checklist is approved.
- [ ] Live disabled-by-default config names are approved.

## 3. Repository Scaffold

- [ ] Create `bullstrangle-platform` GitHub repository.
- [ ] Add `README.md`.
- [ ] Add `AGENTS.md` with RTK, PostgreSQL-only, no-legacy-import, and live-disabled rules.
- [ ] Add `pyproject.toml`.
- [ ] Add `alembic.ini`.
- [ ] Add `migrations/env.py`.
- [ ] Add `migrations/versions/`.
- [ ] Add `data/README.md`.
- [ ] Add `data/.gitignore`.
- [ ] Add `data/inbox/newsletters/`.
- [ ] Add temporary `data/inbox/current_fixture/`.
- [ ] Add `data/fixtures/regression/`.
- [ ] Add `data/fixtures/provider_payloads/`.
- [ ] Add `data/imports/legacy/`.
- [ ] Add `data/benchmarks/os/`.
- [ ] Add `data/reports/replay/`.
- [ ] Confirm no `data/bullstrangle.db` exists in the new repo.
- [ ] Confirm no top-level `data/backups/` exists in the normal repo scaffold.
- [ ] Confirm no top-level `data/os_uploads/` exists in the normal repo scaffold.
- [ ] Confirm no top-level `data/positions/` exists in P0 scaffold.

## 4. Package Scaffold

- [ ] Add `src/bullstrangle_platform/__init__.py`.
- [ ] Add `src/bullstrangle_platform/config.py`.
- [ ] Add `src/bullstrangle_platform/logging.py`.
- [ ] Add `src/bullstrangle_platform/db/`.
- [ ] Add `src/bullstrangle_platform/domain/`.
- [ ] Add `src/bullstrangle_platform/agents/`.
- [ ] Add `src/bullstrangle_platform/providers/`.
- [ ] Add `src/bullstrangle_platform/services/`.
- [ ] Add `src/bullstrangle_platform/mcp/`.
- [ ] Add `src/bullstrangle_platform/cli/`.
- [ ] Add `src/bullstrangle_platform/reports/`.
- [ ] Add `src/bullstrangle_platform/safety/`.
- [ ] Add `tests/`.
- [ ] Add `tests/fixtures/`.

## 5. Agent Scaffold

- [ ] Add `agents/base.py`.
- [ ] Add `agents/ingestion_agent.py`.
- [ ] Add `agents/rule_policy_agent.py`.
- [ ] Add `agents/market_data_agent.py`.
- [ ] Add `agents/scanner_agent.py`.
- [ ] Add `agents/pl_agent.py`.
- [ ] Add `agents/probability_agent.py`.
- [ ] Add `agents/decision_agent.py`.
- [ ] Add `agents/portfolio_agent.py`.
- [ ] Add `agents/paper_trading_agent.py`.
- [ ] Add `agents/execution_agent.py`.
- [ ] Add `agents/monitoring_agent.py`.
- [ ] Add `agents/outcome_agent.py`.
- [ ] Add `agents/confidence_agent.py`.
- [ ] Add `agents/reporting_agent.py`.
- [ ] Define `AgentInput`.
- [ ] Define `AgentResult`.
- [ ] Define `UnitOfWork` port.
- [ ] Define `Clock` port.
- [ ] Define `ProviderRegistry` port.
- [ ] Define `PolicyResolver` port.
- [ ] Define `AuditLogger` port.
- [ ] Define `IdempotencyService` port.

## 6. PostgreSQL Foundation

- [ ] Create local PostgreSQL dev setup.
- [ ] Create PostgreSQL test DB setup.
- [ ] Create `bullstrangle` PostgreSQL schema.
- [ ] Configure Alembic.
- [ ] Add migration for artifact/newsletter domain.
- [ ] Add migration for rule/policy domain.
- [ ] Add migration for provider/market-data domain.
- [ ] Add migration for scanner/leg-selection domain.
- [ ] Add migration for P/L domain.
- [ ] Add migration for probability domain.
- [ ] Add migration for decision/confidence domain.
- [ ] Add migration for paper/shadow/live lifecycle domain.
- [ ] Add migration for audit/import lineage domain.
- [ ] Add indexes and constraints from schema design.
- [ ] Add seed script for initial policy bundle.
- [ ] Add migration smoke test for empty DB.
- [ ] Add rollback documentation.

## 7. Temporary Current Fixture Bootstrap

- [ ] Define accepted current fixture CSV/JSON format.
- [ ] Add fixture validation rules.
- [ ] Add fixture source metadata model.
- [ ] Implement ingestion of manually corrected current fixture rows into PostgreSQL.
- [ ] Persist current fixture as native `newsletters` and `watchlist_entries`.
- [ ] Store source file reference/checksum.
- [ ] Store validation warnings.
- [ ] Confirm fixture path does not become runtime dependency after ingestion.
- [ ] Define deprecation checkpoint for `data/inbox/current_fixture/`.

## 8. Optional Legacy Import

- [ ] Implement one-way legacy import command.
- [ ] Import reads copied SQLite file only by explicit path.
- [ ] Import does not import legacy Python modules.
- [ ] Import does not mutate legacy SQLite.
- [ ] Import records source hash and import batch.
- [ ] Import records legacy table/key lineage.
- [ ] Import is idempotent.
- [ ] Import validation report is generated.

## 9. Provider And Market Data

- [ ] Define provider quote contract.
- [ ] Define provider option-chain contract.
- [ ] Define provider health/status contract.
- [ ] Define typed provider errors.
- [ ] Implement fixture provider.
- [ ] Add recorded provider payload tests.
- [ ] Implement Tradier provider behind interface.
- [ ] Persist provider run.
- [ ] Persist stock quote snapshot.
- [ ] Persist option chain snapshot.
- [ ] Persist option chain rows.
- [ ] Persist raw provider payload as `jsonb`.
- [ ] Provider failures produce `DATA_UNAVAILABLE` path, not crash.

## 10. Scanner And Calculations

- [ ] Implement newsletter replication mode.
- [ ] Implement live strike-selection mode.
- [ ] Use newsletter fixture expiration for MVP validation.
- [ ] Record selected legs.
- [ ] Record alternatives and selected reason.
- [ ] Implement conservative pricing policy.
- [ ] Implement P/L engine.
- [ ] Store `include_commissions=false` for MVP.
- [ ] Implement simple lognormal probability model.
- [ ] Store probability assumptions and inputs.
- [ ] Ensure missing quote/chain/critical field creates `DATA_UNAVAILABLE`.

## 11. Decision And Paper Lifecycle MVP

- [ ] Implement decision statuses: `ACCEPT`, `WATCH`, `REJECT`, `DATA_UNAVAILABLE`.
- [ ] Persist `data_availability_status`.
- [ ] Persist decision evidence.
- [ ] Persist trade scorecard placeholder if needed.
- [ ] Create paper trade intent.
- [ ] Create broker-neutral order draft.
- [ ] Create order draft legs.
- [ ] Create simulated fill.
- [ ] Create lifecycle event.
- [ ] Ensure paper/simulated fills are distinguishable from live fills.
- [ ] Ensure no live submission code path exists in MVP.
- [ ] Generate replay report from PostgreSQL data only.

## 12. MVP End-To-End Gate

- [ ] Current fixture can be ingested.
- [ ] Symbols scan sequentially.
- [ ] Symbol-level provider/data failures are retained as `DATA_UNAVAILABLE`.
- [ ] At least one current-fixture symbol completes live quote.
- [ ] At least one current-fixture symbol completes option chain retrieval.
- [ ] At least one current-fixture symbol completes selected legs.
- [ ] At least one current-fixture symbol completes P/L evaluation.
- [ ] At least one current-fixture symbol completes probability evaluation.
- [ ] At least one current-fixture symbol completes entry decision.
- [ ] At least one current-fixture symbol completes paper lifecycle.
- [ ] Replay report explains source, provider snapshots, legs, P/L, probability, decision, and simulated fill.
- [ ] Legacy runtime remains untouched.
- [ ] New runtime has no legacy module dependency.
- [ ] New runtime has no SQLite runtime dependency.
- [ ] Live trading remains disabled.

## 13. MCP-Builder Compliance

- [ ] Latest MCP protocol documentation reviewed before implementation.
- [ ] MCP Python SDK/FastMCP documentation reviewed before implementation.
- [ ] MCP server named `bullstrangle_platform_mcp`.
- [ ] Tool names use `bullstrangle_` prefix and snake_case.
- [ ] Tools are workflow-oriented, not raw provider endpoint wrappers.
- [ ] Pydantic v2 inputs use strict validation and `extra='forbid'`.
- [ ] Tool descriptions include when to use, when not to use, params, returns, and error recovery.
- [ ] Read tools and write tools are separated.
- [ ] List tools implement pagination.
- [ ] Response format supports concise Markdown and optional JSON where useful.
- [ ] Character limit and truncation utility exists.
- [ ] Error messages are actionable and typed.
- [ ] Tool annotations are reviewed.
- [ ] Service fakes exist for MCP tests.
- [ ] At least 10 read-only MCP evaluation questions are drafted before tool surface expansion.
- [ ] No live-trading-capable MCP tool is registered before live-readiness approval.

## 14. Post-MVP Phases

- [D] Full watchlist paper run.
- [D] Large/Small portfolio sizing and capacity.
- [D] Monitoring and scenario classification.
- [D] Outcome attribution.
- [D] Confidence metrics.
- [D] Shadow mode order drafts and approval workflow.
- [D] Broker fake tests.
- [D] Live readiness checklist.
- [D] Product Owner live-readiness approval milestone.
- [D] Live broker submission tools.

## 15. Progress Summary

| Area | Status | Notes |
|---|---|---|
| Product/architecture docs | [x] | Refactor docs exist in legacy repo. |
| New GitHub repo | [ ] | `bullstrangle-platform` not created yet. |
| Runtime implementation | [ ] | Not started. |
| PostgreSQL migrations | [ ] | Not started. |
| Current fixture bootstrap | [ ] | Not started. |
| Tradier provider | [ ] | Not started. |
| Scanner/P/L/probability | [ ] | Not started. |
| Paper lifecycle | [ ] | Not started. |
| MCP server | [ ] | Not started. |
| Live trading | [D] | Deferred and disabled until explicit approval. |

## 16. Update Rules

- Update this checklist at the end of each implementation session.
- Do not mark an item complete unless code, tests, and documentation for that item are complete.
- If an item is blocked, mark `[!]` and add the owner decision or blocker.
- Do not add runtime work under the legacy repo unless the repository plan is explicitly changed and documented.
- Keep deferred live-trading items deferred until paper/shadow readiness and Product Owner approval gates are met.
