# P05 – RAG Chat with Streaming and Citations

**Read first:** `AGENT_RULES.md`, `docs/01_ARCHITECTURE.md` (§2, §6), `docs/04_API_CONTRACT.md` (Chat, SSE), `docs/05_SECURE_QUIZ.md` (chat block), P02 outputs.

## Task
Implement the chat orchestrator in the gateway, the retrieval pipeline, and LLM calls through LiteLLM, with SSE streaming.

## Deliverables
1. **Retriever:** hybrid (vector + lexical), filter by student's class/subject/medium, boost the current chapter or `document_context` page, then rerank (interface `Reranker`, multilingual reranker or LLM-free scoring first).
2. **Query understanding:** classify (study question / off-topic / unsafe / quiz-integrity) with a cheap model; rewrite follow-ups using session history.
3. **Answer generation:** system prompt rules: answer only from retrieved context; step-by-step, age-appropriate for the student's class; respond in the student's chosen language regardless of source language; say "not found in your textbook" when confidence is low and suggest the likely chapter.
4. **Citations:** every answer ends with book, chapter, printed page for each used chunk, sent as SSE `citation` events and stored in `chat_citations`.
5. **SSE endpoint** per `docs/04_API_CONTRACT.md §3`; non-stream fallback; client-disconnect cancels the LLM call.
6. **Safeguards:** refuse while an assessed attempt is active (log event); per-student daily quota from entitlements; prompt-injection resistance (treat retrieved text as data); profanity/unsafe handling suitable for children.
7. **Persistence (async):** save messages, usage, retrieval confidence; emit `ai_question` learning signals (with repeat detection).
8. **LLM gateway:** LiteLLM config with model routing per task, timeouts, retries, fallback model, and cost logging.
9. **Eval:** extend the P02 harness to check answer groundedness (citations present and pointing to chunks that contain the facts) on a Bangla + English set.

## Acceptance
- First token latency measured and logged; p95 target in `01_ARCHITECTURE.md §7`.
- No answer is returned without citations unless it is an explicit "not found".
- Chat during an active assessed attempt returns the correct error code.
- Disconnecting the client stops token spend.
