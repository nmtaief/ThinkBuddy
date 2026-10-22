# 03 – Data Model (PostgreSQL 16 + pgvector)

Conventions: UUID primary keys (`uuid7` if available), `created_at`/`updated_at` timestamptz, soft delete via `deleted_at` where noted, all text UTF-8 (Bangla-safe), enums as Postgres enums or checked text.

## 1. Identity & family
| Table | Key columns |
|---|---|
| `users` | id, auth_provider, auth_uid (unique), role (`student`/`parent`/`teacher`/`admin`), display_name, phone, email, locale (`bn`/`en`), status |
| `student_profiles` | user_id (pk/fk), class_level (6–8 for beta), medium (`bn`/`en`), school, daily_minutes, available_days (bitmask or array) |
| `families` | id, owner_parent_id |
| `family_members` | family_id, user_id, relation |
| `parent_student_links` | id, parent_id, student_id, status (`pending`/`active`/`revoked`), link_code_hash, consent_at, revoked_at |
| `devices` | id, user_id, platform (`android`/`ios`/`web`), form_factor, push_token, app_version, last_seen_at, integrity_status |
| `sessions` | id, user_id, device_id, refresh_token_hash, expires_at, revoked_at |
| `entitlements` | id, family_id, plan (`free`/`premium`), features jsonb, valid_until |
| `feature_flags` | key, enabled, rules jsonb (platform, version, role, percentage) |
| `audit_log` | id, actor_id, action, target_type, target_id, meta jsonb, at |

## 2. Curriculum & knowledge (from Knowledge Factory)
| Table | Key columns |
|---|---|
| `books` | id, title, class_level, subject, medium, edition, source_uri |
| `chapters` | id, book_id, number, title, printed_page_start, printed_page_end, order_index |
| `concepts` | id, chapter_id, title, kind (`definition`/`formula`/`example`/`concept`/`exercise`) |
| `chunks` | id, book_id, chapter_id, concept_id?, text, text_original, language, **printed_page**, **pdf_page_index**, ocr_quality, validation_flags, `embedding vector(N)`, `tsv tsvector`, ingest_batch_id |
| `ingest_batches` | id, source_manifest, status, stats jsonb |

Indexes: HNSW on `chunks.embedding`, GIN on `chunks.tsv`, btree on (class_level via book, subject, chapter_id). Only chunks with `validation_flags` clean are `retrievable = true`.

## 3. Planning
| Table | Key columns |
|---|---|
| `study_setups` | id, student_id, subject, exam_name, exam_date, set_by_user_id, active_plan_version |
| `syllabus_items` | id, setup_id, chapter_id, included bool, custom_order int, weight |
| `plans` | id, setup_id, version, generated_at, reason (`initial`/`syllabus_change`/`exam_change`/`adaptive`/`missed_work`), params jsonb |
| `plan_days` | id, plan_id, date, planned_minutes |
| `tasks` | id, plan_day_id, student_id, type (`study`/`revision`/`homework`/`quiz`/`broad`/`review_quiz`), chapter_id, refs jsonb (book/page ranges), est_minutes, status (`todo`/`in_progress`/`done`/`skipped`/`rolled`), source (`planner`/`adaptive`/`teacher`), completed_at |

## 4. Questions & quizzes
| Table | Key columns |
|---|---|
| `questions` | id, type (`mcq`/`short`/`broad`), chapter_id, concept_id?, difficulty, language, stem jsonb (blocks), options jsonb, **answer_key (encrypted/separate access)**, rubric jsonb, explanation jsonb, source_chunk_ids[], origin (`curated`/`ai_generated`), review_status (`draft`/`validated`/`approved`/`retired`), variant_group_id |
| `quizzes` | id, student_id, task_id?, kind (`diagnostic`/`daily`/`review`/`chapter`/`practice`), mode (`practice`/`assessed`), time_limit_s, per_question_limit_s?, question_count |
| `quiz_attempts` | id, quiz_id, student_id, device_id, state (`created`/`active`/`submitted`/`expired`/`invalidated`), started_at, deadline_at, submitted_at, score, integrity_score, invalid_reason |
| `attempt_items` | id, attempt_id, position, question_id, served_at, answered_at, response jsonb, is_correct, points, time_spent_ms |
| `attempt_events` | id, attempt_id, type (`app_background`/`focus_lost`/`screenshot_attempt`/`multi_window`/`overlay`/`clipboard`/`device_change`/`time_anomaly`/`chat_attempt`), at, meta jsonb |
| `broad_submissions` | id, attempt_item_id, text, image_uris[], ai_feedback jsonb, ai_score, status (`ai_reviewed`/`teacher_pending`/`teacher_reviewed`) |
| `teacher_reviews` | id, submission_id, teacher_id, score, comment, flagged_topics[], at |

Answer keys live in a separate column group/table (`question_keys`) readable only by the grading service role, so an accidental `SELECT *` in a student endpoint cannot leak them.

## 5. Chat
| Table | Key columns |
|---|---|
| `chat_sessions` | id, student_id, title, subject?, started_at |
| `chat_messages` | id, session_id, role (`user`/`assistant`), content, language, model, tokens_in/out, latency_ms, retrieval_confidence, created_at |
| `chat_citations` | id, message_id, chunk_id, book_id, chapter_id, printed_page, score |
| `usage_counters` | student_id, date, chat_messages, tokens |

## 6. Progress & adaptation
| Table | Key columns |
|---|---|
| `learning_signals` | id, student_id, source (`quiz_wrong`/`quiz_slow`/`ai_question`/`ai_repeat`/`teacher_flag`/`task_skipped`), chapter_id, concept_id?, weight, at, ref_id |
| `mastery` | student_id, chapter_id, concept_id (nullable), score 0–1, confidence, last_seen_at, updated_at |
| `revision_items` | id, student_id, chapter_id, concept_id?, question_id?, box (1–5), due_at, last_result |
| `progress_daily` | student_id, date, minutes, tasks_done, tasks_total, quiz_avg, streak |
| `notifications` | id, user_id, kind, payload jsonb, channel, sent_at, read_at |

## 7. Rules
- Parents read student data only through `parent_student_links.status = 'active'`; enforced in a single policy function used by all queries (and optionally Postgres RLS).
- Every parent edit to `study_setups`/`syllabus_items` writes an `audit_log` row and bumps plan version.
- Retention: attempt_events and chat messages follow a configurable retention period.
