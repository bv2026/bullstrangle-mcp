# BullStrangle Refactor Implementation Checklist

Status: Approved For Repo Creation And Phase 0 Scaffolding
Date: 2026-05-25
Scope: Progress tracker for the new self-contained `bullstrangle-platform` implementation. This checklist does not authorize runtime changes by itself.

Current tracking note:
- Refactor implementation tracking has moved to the new repo `https://github.com/bv2026/bullstrangle-platform`.
- Refactor planning docs were copied into `C:\work\bullstrangle-platform\docs\refactoring\` at platform commit `973a58d`.
- All further implementation activity, checklist updates, and refactor status changes should be captured in the new platform repo.
- This legacy repo remains the historical planning source and operational legacy runtime; do not use it for new platform implementation work.

Source documents:
- `BullStrangle_Product_Spec_Refactor_PRD.md`
- `BullStrangle_Target_Architecture_v4.md`
- `BullStrangle_Target_Schema_v4.md`
- `BullStrangle_Refactor_Implementation_Roadmap.md`

Product Owner approval:
- Approved at commit `a48b81d`.
- Approved for creating GitHub repo `bullstrangle-platform`.
- Approved for Phase 0 self-contained project scaffolding.
- Deferred decisions: exact delta bands, protective put method, P/L thresholds, probability thresholds, liquidity thresholds, Large/Small sizing, confidence thresholds.

Phase 0 scaffold:
- Planning approval recorded in legacy repo at commit `193007a`.
- New repo scaffold pushed to `https://github.com/bv2026/bullstrangle-platform` at commit `a80b993`.

## Status Legend

- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete
- `[!]` Blocked or requires owner decision
- `[D]` Deferred

## 1. Non-Negotiable Guardrails

- [x] Legacy `bullstrangle-mcp` runtime remains untouched.
- [x] New implementation is created in a separate repository: `bullstrangle-platform`.
- [x] New package name is `bullstrangle_platform`.
- [x] New MCP server name is `bullstrangle_platform_mcp`.
- [x] New CLI namespace is `bs-platform`.
- [x] New runtime DB is PostgreSQL only.
- [x] SQLite is used only as optional legacy one-way import source.
- [x] New runtime has no imports from `src/bullstrangle_mcp`.
- [x] New runtime scanner/decision/P/L/probability/execution services do not read raw files directly after ingestion.
- [x] Live trading remains disabled until Product Owner live-readiness approval.
- [x] All shell commands during implementation use RTK.

## 2. Pre-Implementation Decisions

- [x] Product Owner approves final project identity.
- [x] GitHub repository `bullstrangle-platform` is created.
- [x] Repository/folder layout is approved.
- [x] Lean `data/` layout is approved.
- [x] Temporary `data/inbox/current_fixture/` lifecycle is approved.
- [x] Agent/sub-agent scaffold is approved.
- [x] Agent write ownership boundaries are approved.
- [x] MVP orchestration order is approved.
- [x] PostgreSQL schema design is approved.
- [x] Alembic migration workflow is approved.
- [x] Local dev DB setup approach is approved.
- [x] Test DB setup approach is approved.
- [x] Seed/reference data strategy is approved.
- [x] Provider contract is approved.
- [x] Tradier provider strategy is approved.
- [x] Pricing policy is approved.
- [D] Strike-selection policy final thresholds are deferred until scanner phase.
- [D] P/L acceptance thresholds are deferred until decision phase.
- [D] Probability thresholds are deferred until decision/confidence phase.
- [x] MCP-builder compliance checklist is approved.
- [x] Live disabled-by-default config names are approved.

## 3. Repository Scaffold

- [x] Create `bullstrangle-platform` GitHub repository.
- [x] Add `README.md`.
- [x] Add `AGENTS.md` with RTK, PostgreSQL-only, no-legacy-import, and live-disabled rules.
- [x] Add `pyproject.toml`.
- [x] Add `alembic.ini`.
- [x] Add `migrations/env.py`.
- [x] Add `migrations/versions/`.
- [x] Add `data/README.md`.
- [x] Add `data/.gitignore`.
- [x] Add `data/inbox/newsletters/`.
- [x] Add temporary `data/inbox/current_fixture/`.
- [x] Add `data/fixtures/regression/`.
- [x] Add `data/fixtures/provider_payloads/`.
- [x] Add `data/imports/legacy/`.
- [x] Add `data/benchmarks/os/`.
- [x] Add `data/reports/replay/`.
- [x] Confirm no `data/bullstrangle.db` exists in the new repo.
- [x] Confirm no top-level `data/backups/` exists in the normal repo scaffold.
- [x] Confirm no top-level `data/os_uploads/` exists in the normal repo scaffold.
- [x] Confirm no top-level `data/positions/` exists in P0 scaffold.

## 4. Package Scaffold

- [x] Add `src/bullstrangle_platform/__init__.py`.
- [x] Add `src/bullstrangle_platform/config.py`.
- [x] Add `src/bullstrangle_platform/logging.py`.
- [x] Add `src/bullstrangle_platform/db/`.
- [x] Add `src/bullstrangle_platform/domain/`.
- [x] Add `src/bullstrangle_platform/agents/`.
- [x] Add `src/bullstrangle_platform/providers/`.
- [x] Add `src/bullstrangle_platform/services/`.
- [x] Add `src/bullstrangle_platform/mcp/`.
- [x] Add `src/bullstrangle_platform/cli/`.
- [x] Add `src/bullstrangle_platform/reports/`.
- [x] Add `src/bullstrangle_platform/safety/`.
- [x] Add `tests/`.
- [x] Add `tests/fixtures/`.

## 5. Agent Scaffold

- [x] Add `agents/base.py`.
- [x] Add `agents/ingestion_agent.py`.
- [x] Add `agents/rule_policy_agent.py`.
- [x] Add `agents/market_data_agent.py`.
- [x] Add `agents/scanner_agent.py`.
- [x] Add `agents/pl_agent.py`.
- [x] Add `agents/probability_agent.py`.
- [x] Add `agents/decision_agent.py`.
- [x] Add `agents/portfolio_agent.py`.
- [x] Add `agents/paper_trading_agent.py`.
- [x] Add `agents/execution_agent.py`.
- [x] Add `agents/monitoring_agent.py`.
- [x] Add `agents/outcome_agent.py`.
- [x] Add `agents/confidence_agent.py`.
- [x] Add `agents/reporting_agent.py`.
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
| Product/architecture docs | [x] | Refactor docs exist here historically; active copies and future updates now live in `bullstrangle-platform/docs/refactoring/`. |
| Product Owner approval | [x] | Approved at commit `a48b81d` for repo creation and Phase 0 scaffolding. |
| New GitHub repo | [x] | `bullstrangle-platform` created and pushed at commit `a80b993`. |
| Phase 0 scaffold | [~] | Repo/package/data/agent file scaffold exists; typed contracts still not implemented. |
| Runtime implementation | [ ] | Not started beyond placeholders. |
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
