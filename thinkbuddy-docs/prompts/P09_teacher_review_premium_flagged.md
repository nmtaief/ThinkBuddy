# P09 – Teacher Review & Premium Entitlements (feature-flagged OFF in beta)

**Read first:** `AGENT_RULES.md`, `docs/02_PRODUCT_FLOWS.md` (§4.7, §5), `docs/06_ADAPTIVE_ENGINE.md` (§7).

## Task
Build the teacher workflow and premium gating so they can be switched on after beta without redesign.

## Deliverables
1. Teacher role routes under `/teacher/*`, hidden behind `feature_flags` (404 when off).
2. Assignment of teachers to students (admin-controlled), review queue for `broad_submissions`, comment + score + topic flagging.
3. Teacher feedback → `learning_signals` with high weight and slower decay.
4. Entitlements service: free vs premium, per-family, enforced server-side; premium gates teacher review and higher chat quota.
5. Payment integration is **out of scope**; provide an admin endpoint/CLI to grant or revoke premium.
6. Notifications: parent and student alerted when a review is posted.

## Acceptance
- With the flag off, all teacher endpoints are unreachable and absent from `/client/config`.
- With the flag on in tests, a teacher only sees assigned students.
- Premium-gated routes return a stable `ENTITLEMENT_REQUIRED` error for free families.
