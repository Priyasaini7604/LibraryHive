## What and why

<!-- Task ID from IMPLEMENTATION_PLAN.md (e.g. T08) and a short summary. -->

## Definition of Done (IMPLEMENTATION_PLAN.md section 6)

- [ ] Matches the contracts in `SPEC.md` / `BACKEND_ARCHITECTURE.md` / `UI_ARCHITECTURE.md` (or this PR updates them)
- [ ] Business rules enforced in backend services; frontend validation is only a convenience
- [ ] Tenant-isolation tests for new endpoints (Owner A vs Library B, Student A vs Student B)
- [ ] State changes write audit rows and log events
- [ ] No `any`, no inline styles, no hardcoded business data, no mocks in product code
- [ ] New screens have loading, error, empty and success states and work at 375, 768 and 1366 px
- [ ] Obsolete code for this task removed; no legacy pattern reintroduced (IMPLEMENTATION_PLAN.md section 5)
- [ ] CI is green

## Contract changes

<!-- Endpoints, error codes, fields or constraints changed? List them and the documents updated. -->

## Screenshots (UI changes)

<!-- Phone and desktop screenshots. -->
