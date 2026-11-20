# How the ThinkBuddy AI Helper ("Buddy") Works
### Architectural Specification & Data Integration Guide

**Version:** 2.1.0  
**Target Audience:** Engineering, AI/ML Engineers, Conversation Designers, Curriculum & Data Teams  
**Companion Document:** [`ThinkBuddy_Data_Guide.md`](file:///e:/ThinkBuddy%20Arc/docs/ThinkBuddy_Data_Guide.md)

---

## 1. Executive Summary & Core Design Philosophy

In legacy educational bots, "RAG" (Retrieval-Augmented Generation) was treated as a rigid, unconditional pipeline: every student query was dumped into a vector database, and if the retrieval confidence was low, the bot sputtered out robotic boilerplate text (*"This specific topic was not found directly in your standard textbook, but let me explain using my general knowledge: Regarding '...'..."*).

**ThinkBuddy Buddy reverses this paradigm: The LLM is the Tutor; RAG is a Tool.**

```
+-----------------------------------------------------------------------------------+
|                              STUDENT PROFILE CONTEXT                              |
|           Name: Tanzim | Class: 8 | Medium: Bangla (বাংলা মাধ্যম) | Locale: bn     |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                                BUDDY AI TUTOR (LLM)                               |
|        Friendly, encouraging older-sibling tutor (NCTB Curriculum Expert)         |
|  * Answers general questions & motivation directly from foundational knowledge.  |
|  * Maintains full multi-turn conversational memory (last 12 turns).               |
|  * Matches student's language (Bangla, English, or Banglish naturally).          |
+-----------------------------------------------------------------------------------+
                                         |
            +----------------------------+----------------------------+
            | (When textbook facts, formulas, or chapters are needed) |
            v                                                         v
+------------------------+  +------------------------+  +------------------------+
|   search_textbook()    |  |   get_chapter_list()   |  |       get_page()       |
| Hard scoped: Class 8,  |  | Resolves last chapter, |  | Fetches exact printed  |
| Bangla medium chunks   |  | chapter order & titles |  | textbook page verified |
+------------------------+  +------------------------+  +------------------------+
            |                            |                            |
            +----------------------------+----------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
|                                 VERIFIED RESPONSE                                 |
|  - Pedagogical explanation (warm tone, hint ladders for exercises).               |
|  - Strictly validated formulas rendered in KaTeX.                                 |
|  - Single concise citation chip: গণিত (অষ্টম শ্রেণি) * অধ্যায় ১১ * পৃষ্ঠা ১৭৫    |
+-----------------------------------------------------------------------------------+
```

### Core Principles
1. **The LLM is the Tutor:** For general questions, advice, study habits, motivation, and warm greetings, Buddy answers immediately and naturally from its internal knowledge without querying the textbook vector store.
2. **RAG is an on-demand verification tool:** Buddy invokes tools via function calling (`search_textbook`, `get_chapter_list`, `get_page`, `get_concepts`) only when it needs official NCTB textbook wording, exact page numbers, chapter order, or formula verification.
3. **Zero Canned Fallback Templates:** All robotic phrases like *"compelling educational topic"*, *"not found directly in your standard textbook"*, or *"Based on your curriculum reference material"* are permanently eradicated. If something is outside the syllabus, Buddy explains it honestly and kindly in its own words and directs the student to related curriculum topics.
4. **Hard Student Profile Scoping:** Buddy strictly enforces the student's `class_level` and `medium`. A Class 8 student will never receive Class 7 or Class 6 passages unless explicitly requested.
5. **Server is Authority:** Citations must point to actual **printed page numbers** (never internal PDF indices). Page numbers and citations are never invented.

---

## 2. Tool-Calling System Specification

Buddy interacts with the curriculum database via structured asynchronous tools.

### 2.1 `get_chapter_list(subject: str)`
- **Purpose:** Resolves ordered chapters, titles, numbers, and page ranges for the student's enrolled class.
- **Why it matters:** When a student says *"its the last chapter of math"* or *"Science er first chapter ki?"*, Buddy does not run a fuzzy text search. It queries `get_chapter_list` to accurately resolve that Class 8 Math has 11 chapters and the last chapter is **Chapter 11: তথ্য ও উপাত্ত (Information and Data)**, spanning pages 169–186 (strictly preventing confusing it with Chapter 2: মুনাফা).
- **Output Schema:**
  ```json
  {
    "subject": "math",
    "class_level": 8,
    "total_chapters": 11,
    "chapters": [
      {"number": 1, "title": "প্যাটার্ন", "start_page": 1, "end_page": 14},
      {"number": 11, "title": "তথ্য ও উপাত্ত", "start_page": 169, "end_page": 186}
    ],
    "last_chapter": {"number": 11, "title": "তথ্য ও উপাত্ত", "start_page": 169, "end_page": 186}
  }
  ```

### 2.2 `search_textbook(query: str, subject?: str, chapter?: int, top_k?: int)`
- **Purpose:** Performs hybrid semantic + lexical retrieval against NCTB curriculum chunks scoped by `class_level` and `medium`.
- **Why it matters:** Provides exact NCTB definitions, board exam formulas, and worked examples.
- **Output Schema:**
  ```json
  {
    "query": "পিথাগোরাস",
    "class_level": 8,
    "passages": [
      {
        "chunk_id": "979ea375-...",
        "book_title": "গণিত (অষ্টম শ্রেণি)",
        "chapter_number": 9,
        "chapter_title": "পিথাগোরাসের উপপাদ্য",
        "printed_page": 142,
        "text": "একটি সমকোণী ত্রিভুজের অতিভুজের ওপর অঙ্কিত বর্গক্ষেত্রের ক্ষেত্রফল...",
        "score": 0.94
      }
    ]
  }
  ```

### 2.3 `get_page(subject: str, printed_page: int)`
- **Purpose:** Fetches the exact content of a specific printed page number when a student asks: *"Can you explain me Science book page 58 of class 8?"*.
- **Why it matters:** Direct page queries do not suffer from keyword mismatch or semantic drift; they pull the exact curriculum slice directly.

### 2.4 `get_concepts(concept_or_topic: str)`
- **Purpose:** Retrieves structured metadata from Dataset B (definitions, prerequisites, common student misconceptions, and related formulas).

---

## 3. How Datasets A–I Connect into Buddy's Brain

The Data Team builds nine distinct datasets (Datasets A through I) as specified in `ThinkBuddy_Data_Guide.md`. Here is how each dataset directly powers Buddy:

```
+----------------------------------------------------------------------------------------+
|                                DATASET ARCHITECTURE                                    |
+----------------------------------------------------------------------------------------+
|  Dataset A: Clean Textbook Text       --> Stored in PostgreSQL/pgvector chunks.        |
|                                           Queried by search_textbook() & get_page().   |
|  Dataset B: Concept Layer             --> Queried by get_concepts(). Powers weak-topic |
|                                           diagnosis & misconception warnings.          |
|  Dataset C: Bilingual Glossary        --> Enforces consistent NCTB terminology         |
|                                           (e.g., সালোকসংশ্লেষণ = Photosynthesis).     |
|  Dataset D: Guided Answers            --> Injects Hint Ladders (Nudge -> Hint -> Step) |
|                                           into Buddy when students ask for homework.   |
|  Dataset E & F: Creative & Analytical --> Powers practice scenarios, stimulus-based   |
|                                           questions, and multi-step rubrics.           |
|  Dataset G: Quiz Questions            --> Fuels the server-authoritative quiz engine.  |
|  Dataset H: Benchmark Retrieval Set   --> Automated 50-item test suites to guarantee   |
|                                           zero regressions on every release.           |
|  Dataset I: Safety & Guardrails       --> System prompt boundary rules: anti-cheating, |
|                                           exam refusal, and emotional care.            |
+----------------------------------------------------------------------------------------+
```

---

## 4. Operational Playbook: How the Data Team Fixes Buddy

> [!IMPORTANT]
> **Golden Rule of ThinkBuddy AI:**  
> **Never modify the system prompt or backend code to fix a factual curriculum error or missing topic.**
> Whenever Buddy gives an incomplete explanation, cites the wrong page, or misses a concept, the fix belongs in **Data**, not code.

Here is the step-by-step diagnostic guide for the Data Team:

| Symptom | Root Cause in Data | How to Fix in Data (No Code Changes) |
|---|---|---|
| **Buddy says topic is not found** (e.g. *Mitochondria* or *Photosynthesis*) | The textbook chunk in **Dataset A** is missing, has OCR corruption, or lacks subject tags. | 1. Open `data/class{N}/{subject}/chunks.jsonl`.<br>2. Add or clean the passage.<br>3. Verify `printed_page` matches the paper textbook.<br>4. Re-index via Admin Portal **RAG & Vector Retrieval** tab. |
| **Buddy cites wrong chapter or wrong page** | In **Dataset A**, the `printed_page` was set to the PDF reader index instead of the number printed on the page. | 1. Open the physical NCTB book.<br>2. Note the page number printed at the bottom/top of the page.<br>3. Correct `printed_page` in Dataset A. |
| **Buddy gives the full solution immediately instead of teaching** | Missing hint ladder in **Dataset D (Guided Answers)**. | 1. Open `data/class{N}/{subject}/guided_answers.jsonl`.<br>2. Add an entry with fields: `question`, `steps`, `model_answer`, `avoid`, and 3-step `hints`. |
| **Buddy mixes English & Bangla inconsistently** | Missing bilingual entry in **Dataset C (Glossary)**. | 1. Add the term to `glossary.jsonl` with both Bangla and English NCTB-approved terms. |
| **Buddy misses a multi-step concept connection** | Prerequisite relationship missing in **Dataset B (Concept Layer)**. | 1. Add `prerequisite_concepts` and `related_concepts` in `concepts.jsonl`. |

---

## 5. Tone, Language & Formatting Guidelines

1. **Language Matching:**
   - English Question -> Natural English reply.
   - Bangla Question -> Natural Bangla reply.
   - Banglish Query (e.g. *"Science er first chapter ki?"*) -> Warm Bangla with textbook terminology.
   - Never randomly mix scripts within the same sentence.
2. **Encouraging Tone (Negative Self-Talk):**
   - When a student says *"I am really bad at English/Math"*, Buddy never agrees or lectures.
   - Buddy responds with warmth: *"Don't worry at all, learning takes time and you definitely aren't bad at it!"* followed by a concrete, doable 10-minute daily habit plan.
3. **KaTeX Mathematics:**
   - Math formulas are always formatted in standard LaTeX: `$c^2 = a^2 + b^2$`, `$\frac{a}{b}$`, `$I = Prn$`.
4. **Citations:**
   - Only shown when textbook content was actually retrieved and used.
   - Displayed as a single clean chip: `[বইয়ের নাম] * [অধ্যায়] * পৃষ্ঠা [সংখ্যা]`.

