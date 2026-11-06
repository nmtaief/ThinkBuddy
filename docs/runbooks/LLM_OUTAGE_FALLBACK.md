# Runbook: LLM Provider Outage & Model Fallback

## 1. Trigger & Severity
- **Severity:** P1 (Degraded User Experience)
- **Symptoms:**
  - AI Tutoring `/v1/chat/sessions/{id}/messages` returns HTTP 502/504 or timeouts.
  - Sentry reports `litellm.exceptions.ServiceUnavailableError` or `RateLimitError`.
  - Prometheus metric `thinkbuddy_chat_first_token_latency_seconds` exceeds 2500ms or error rate spikes above 5%.

---

## 2. Architecture & Redundancy
ThinkBuddy routes LLM generation through LiteLLM provider proxy with automated primary and secondary model cascades:
- **Primary Hosted Model:** `gemini-1.5-pro` (High reasoning, bilingual Bangla/English curriculum grounding).
- **Secondary Fallback Model:** `gemini-1.5-flash` or `hosted-claude-3-5-haiku` / `mistral-large`.
- **Offline / Local Fallback:** Rule-based curriculum excerpt delivery (returns top retrieved chunks directly with "Low confidence / model offline" notice).

---

## 3. Immediate Action Procedure

### Step 1: Verify Provider Status
Check external provider status pages:
- Google Cloud / Gemini Status Dashboard
- OpenRouter / LiteLLM proxy status

### Step 2: Switch Active Model Cascade
Update environment configuration in `/etc/thinkbuddy/production.env` or dynamic Redis config:
```bash
# Force fallback model in production
LLM_MODEL=gemini-1.5-flash
LLM_FALLBACK_MODELS=claude-3-5-haiku-20241022,gpt-4o-mini
```

Apply without downtime:
```bash
docker compose -f docker-compose.prod.yml restart gateway
```

### Step 3: Enable Degraded Mode if All External Providers Down
If all frontier LLM endpoints are unreachable, enable curriculum retrieval fallback:
```bash
# In Redis:
redis-cli -a $REDIS_PASSWORD SET thinkbuddy:config:llm_degraded_mode "true"
```
When `llm_degraded_mode` is `"true"`, the chat orchestrator immediately serves the top 3 textbook chunk excerpts with printed page citations directly to the student, informing them:
*"আমাদের এআই মডেল সাময়িকভাবে অনুপলব্ধ। তবে আপনার পাঠ্যবই থেকে এই তথ্যগুলো খুঁজে পাওয়া গেছে:"*

### Step 4: Verification
Run synthetic probe:
```bash
python scripts/eval_retrieval.py
```
Monitor Gateway logs:
```bash
docker compose -f docker-compose.prod.yml logs -f --tail=50 gateway | grep "chat_turn"
```
Confirm `HTTP 200 OK` on SSE streams.
