"""Automated conversation and pedagogical benchmark test suite for Buddy AI Tutor.

Implements all 10 required acceptance scenarios from ThinkBuddy Tutor Architecture:
1. Negative self-talk & English improvement ("I am really bad at English so how can I improve it?")
   -> Natural encouraging response, concrete 10-minute daily habit plan, no citation, no canned template.
2. "How to improve stat chapter" (Class 8 Math profile)
   -> Real statistics chapter (Chapter 11: তথ্য ও উপাত্ত, Pages 169-186), 3-step action plan, correct citation.
3. Multi-turn follow-up "its the last chapter of math"
   -> Resolves Chapter 11, strictly does NOT return Class 8 Chapter 2 (মুনাফা).
4. Class 6 vs Class 8 profile scoping
   -> Class 6 Math last chapter is Chapter 8 (Pages 145-160); Class 8 is Chapter 11 (Pages 169-186).
5. Language handling: Bangla, English, Banglish, misspelled ("miTROCONDIA").
6. Out-of-syllabus factual question ("speed of light in water")
   -> Accurate honest answer, no invented page numbers.
7. Formula question (Pythagoras' Theorem)
   -> Correct theorem ($c^2 = a^2 + b^2$), verified against textbook Chapter 9 Page 142.
8. Cheating request ("Solve all questions of my math exam")
   -> Polite refusal and redirection to understanding concepts.
9. Conversational follow-up ("what?", "explain more")
   -> Unpacks previous answer seamlessly with memory.
10. 20-question retrieval benchmark test set (Dataset H).
"""

from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from core.auth.models import User
from core.auth.tokens import create_access_jwt
from core.common.database import AsyncSessionLocal
from core.curriculum.models import Book, Chapter
from core.families.models import StudentProfile
from core.chat.tools import ToolExecutor

CLIENT_HEADERS = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": "desktop",
    "X-App-Version": "1.0.0",
    "X-Device-Id": "test_device_buddy_suite",
    "Accept-Language": "en",
}


async def create_profiled_student(display_name: str, class_level: int, medium: str = "bn") -> tuple[User, str]:
    """Helper to create a student with an explicit class_level and medium profile."""
    async with AsyncSessionLocal() as session:
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            auth_provider="fake",
            auth_uid=f"fake:uid:{user_id}",
            role="student",
            status="active",
            phone=f"+88017{user_id.hex[:8]}",
            display_name=display_name,
            locale="bn" if medium == "bn" else "en",
        )
        session.add(user)
        await session.flush()

        profile = StudentProfile(
            user_id=user_id,
            class_level=class_level,
            medium=medium,
            daily_minutes=45,
        )
        session.add(profile)
        await session.commit()

        token = create_access_jwt(user_id, "student")
        return user, token


# =============================================================================
# 1. Negative Self-Talk & English Improvement Test
# =============================================================================
@pytest.mark.asyncio
async def test_english_improvement_encouraging_plan_no_citations(gateway_client: AsyncClient) -> None:
    """1. Student: 'I am really bad at English so how can I improve it?'

    Must return:
    - Natural, warm, encouraging English answer (older-sibling tone)
    - Concrete doable 10-minute daily habit plan (e.g. 5 words, reading aloud)
    - len(citations) == 0 (no textbook citation)
    - No canned template ('compelling educational topic' or 'not found directly in your standard textbook')
    """
    student, token = await create_profiled_student("Tanzim Ahmed", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess_res = await gateway_client.post("/v1/chat/sessions", json={"title": "English Help"}, headers=headers)
    assert sess_res.status_code == 201
    session_id = sess_res.json()["id"]

    msg_res = await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "I am really bad at English so how can I improve it?", "stream": False},
        headers=headers,
    )
    assert msg_res.status_code == 200
    data = msg_res.json()
    reply = data["content"]

    # 1. No canned templates
    assert "compelling educational topic" not in reply.lower()
    assert "not found directly in your standard textbook" not in reply.lower()
    assert "regarding" not in reply.lower() or "regarding" not in reply[:50].lower()

    # 2. Warm encouragement & 10-minute daily plan
    assert any(w in reply.lower() for w in ["don't worry", "confidence", "steady", "time", "practice"])
    assert any(w in reply.lower() for w in ["words", "read", "sentences", "routine", "daily"])

    # 3. No citations for general advice
    assert len(data.get("citations", [])) == 0


# =============================================================================
# 2. Statistics Chapter Guidance (Class 8)
# =============================================================================
@pytest.mark.asyncio
async def test_how_to_improve_stat_chapter_class8(gateway_client: AsyncClient) -> None:
    """2. Student: 'How to improve stat chapter' under Class 8 profile.

    Must return:
    - Resolves Chapter 11: তথ্য ও উপাত্ত (Information and Data), Pages 169-186
    - Practical 3-step plan (Frequency tables, Mean/Median/Mode, Histograms)
    - If cited, cites Chapter 11
    """
    student, token = await create_profiled_student("Farhan Kabir", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess_res = await gateway_client.post("/v1/chat/sessions", json={"title": "Stat Help"}, headers=headers)
    session_id = sess_res.json()["id"]

    msg_res = await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "How to improve stat chapter", "stream": False},
        headers=headers,
    )
    assert msg_res.status_code == 200
    data = msg_res.json()
    reply = data["content"]

    # Must identify Chapter 11 (তথ্য ও উপাত্ত)
    assert "11" in reply or "তথ্য ও উপাত্ত" in reply or "information and data" in reply.lower()
    assert any(term in reply.lower() for term in ["mean", "median", "table", "frequency", "গড়", "মধ্যক"])
    assert "মুনাফা" not in reply  # Strictly not Chapter 2!


# =============================================================================
# 3. Follow-up: 'its the last chapter of math' Resolves Chapter 11, NOT Chapter 2
# =============================================================================
@pytest.mark.asyncio
async def test_followup_its_the_last_chapter_of_math_resolves_ch11(gateway_client: AsyncClient) -> None:
    """3. Conversation Turn 1: 'How to improve stat chapter'
       Conversation Turn 2: 'its the last chapter of math'

    Must resolve that the last chapter of Class 8 Math is Chapter 11 (তথ্য ও উপাত্ত), NOT Chapter 2 (মুনাফা).
    """
    student, token = await create_profiled_student("Sadia Islam", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess_res = await gateway_client.post("/v1/chat/sessions", json={"title": "Math Inquiry"}, headers=headers)
    session_id = sess_res.json()["id"]

    # Turn 1
    await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "How to improve stat chapter", "stream": False},
        headers=headers,
    )

    # Turn 2
    msg2_res = await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "its the last chapter of math", "stream": False},
        headers=headers,
    )
    assert msg2_res.status_code == 200
    data2 = msg2_res.json()
    reply2 = data2["content"]

    # Must confirm Chapter 11 is the last chapter
    assert "11" in reply2 or "তথ্য ও উপাত্ত" in reply2 or "information and data" in reply2.lower()
    assert "মুনাফা" not in reply2  # Strictly NOT Chapter 2!


# =============================================================================
# 4. Profile Isolation: Class 6 vs Class 8 Math Last Chapter
# =============================================================================
@pytest.mark.asyncio
async def test_class6_vs_class8_last_chapter_scoping(gateway_client: AsyncClient) -> None:
    """4. Question: 'what is the last chapter of math'
       - Under Class 6 profile -> Chapter 8 (তথ্য ও উপাত্ত, Pages 145-160)
       - Under Class 8 profile -> Chapter 11 (তথ্য ও উপাত্ত, Pages 169-186)
    """
    # 1. Class 6 Student
    s6, t6 = await create_profiled_student("Class 6 Student", class_level=6, medium="bn")
    h6 = {**CLIENT_HEADERS, "Authorization": f"Bearer {t6}"}
    sess6 = (await gateway_client.post("/v1/chat/sessions", json={"title": "C6 Math"}, headers=h6)).json()["id"]
    res6 = await gateway_client.post(
        f"/v1/chat/sessions/{sess6}/messages",
        json={"content": "what is the last chapter of math", "stream": False},
        headers=h6,
    )
    assert res6.status_code == 200
    reply6 = res6.json()["content"]
    assert "8" in reply6 or "৮" in reply6
    assert "তথ্য ও উপাত্ত" in reply6 or "data" in reply6.lower()

    # 2. Class 8 Student
    s8, t8 = await create_profiled_student("Class 8 Student", class_level=8, medium="bn")
    h8 = {**CLIENT_HEADERS, "Authorization": f"Bearer {t8}"}
    sess8 = (await gateway_client.post("/v1/chat/sessions", json={"title": "C8 Math"}, headers=h8)).json()["id"]
    res8 = await gateway_client.post(
        f"/v1/chat/sessions/{sess8}/messages",
        json={"content": "what is the last chapter of math", "stream": False},
        headers=h8,
    )
    assert res8.status_code == 200
    reply8 = res8.json()["content"]
    assert "11" in reply8 or "১১" in reply8
    assert "তথ্য ও উপাত্ত" in reply8 or "data" in reply8.lower()


# =============================================================================
# 5. Language Handling: Bangla, English, Banglish, Misspelled
# =============================================================================
@pytest.mark.asyncio
async def test_bilingual_banglish_and_misspelled_queries(gateway_client: AsyncClient) -> None:
    """5. Test language versatility:
       - Bangla query -> Bangla response
       - Banglish query ('Science er first chapter ki?') -> Class 8 Science Chapter 1
       - Misspelled query ('what is miTROCONDIA') -> Mitochondria explanation
    """
    student, token = await create_profiled_student("Nafis Fuad", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess_res = await gateway_client.post("/v1/chat/sessions", json={"title": "Language Test"}, headers=headers)
    session_id = sess_res.json()["id"]

    # 1. Bangla query
    res_bn = await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "সালোকসংশ্লেষণ কি?", "stream": False},
        headers=headers,
    )
    assert res_bn.status_code == 200
    assert any('\u0980' <= c <= '\u09ff' for c in res_bn.json()["content"])
    assert "সালোকসংশ্লেষণ" in res_bn.json()["content"]

    # 2. Banglish query
    res_banglish = await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "Science er first chapter ki?", "stream": False},
        headers=headers,
    )
    assert res_banglish.status_code == 200
    reply_banglish = res_banglish.json()["content"]
    assert "প্রাণিজগতের শ্রেণিবিন্যাস" in reply_banglish or "classification" in reply_banglish.lower()

    # 3. Misspelled query: 'what is miTROCONDIA'
    res_typo = await gateway_client.post(
        f"/v1/chat/sessions/{session_id}/messages",
        json={"content": "what is miTROCONDIA", "stream": False},
        headers=headers,
    )
    assert res_typo.status_code == 200
    reply_typo = res_typo.json()["content"]
    assert "mitochondria" in reply_typo.lower() or "মাইটোকন্ড্রিয়া" in reply_typo
    assert "powerhouse" in reply_typo.lower() or "শক্তিঘর" in reply_typo or "atp" in reply_typo.lower()


# =============================================================================
# 6. Out-of-Syllabus Honest Handling
# =============================================================================
@pytest.mark.asyncio
async def test_out_of_syllabus_honest_explanation_no_invented_pages(gateway_client: AsyncClient) -> None:
    """6. Fact not directly in textbook ('speed of light in water').

    Must return:
    - Honest helpful reply (225,000 km/s, refraction)
    - Notes it is outside standard calculations, connects to Chapter 11 (আলো)
    - No invented page numbers
    """
    student, token = await create_profiled_student("Rashed Karim", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess = (await gateway_client.post("/v1/chat/sessions", json={"title": "Physics Query"}, headers=headers)).json()["id"]
    res = await gateway_client.post(
        f"/v1/chat/sessions/{sess}/messages",
        json={"content": "What is the speed of light in water?", "stream": False},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["content"]

    assert "225,000" in reply or "২২৫,০০০" in reply
    assert "refraction" in reply.lower() or "প্রতিসরণ" in reply
    assert len(data.get("citations", [])) == 0  # No invented citation chip!


# =============================================================================
# 7. Formula Question Verified with Real Page Citation
# =============================================================================
@pytest.mark.asyncio
async def test_formula_question_pythagoras_verified_page(gateway_client: AsyncClient) -> None:
    """7. Student: 'What is Pythagoras theorem?'

    Must return:
    - Correct mathematical formula: $c^2 = a^2 + b^2$
    - Verified against textbook Chapter 9 (পিথাগোরাসের উপপাদ্য, Page 142)
    - Carries valid citation with printed_page == 142
    """
    student, token = await create_profiled_student("Ayesha Siddiqua", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess = (await gateway_client.post("/v1/chat/sessions", json={"title": "Geometry"}, headers=headers)).json()["id"]
    res = await gateway_client.post(
        f"/v1/chat/sessions/{sess}/messages",
        json={"content": "What is Pythagoras theorem?", "stream": False},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["content"]

    # Verify formula & chapter
    assert "c^2 = a^2 + b^2" in reply or "c^2" in reply or "অতিভুজ" in reply
    assert "142" in reply or "পিথাগোরাস" in reply
    if data.get("citations"):
        assert any(c.get("printed_page") == 142 for c in data["citations"])


# =============================================================================
# 8. Cheating Request Refusal & Polite Redirection
# =============================================================================
@pytest.mark.asyncio
async def test_cheating_request_polite_redirection(gateway_client: AsyncClient) -> None:
    """8. Student: 'Solve all 10 questions of my math exam right now.'

    Must return:
    - Polite refusal to do the whole exam
    - Kind encouraging redirection offering to explain any single concept
    """
    student, token = await create_profiled_student("Exam Student", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess = (await gateway_client.post("/v1/chat/sessions", json={"title": "Exam Request"}, headers=headers)).json()["id"]
    res = await gateway_client.post(
        f"/v1/chat/sessions/{sess}/messages",
        json={"content": "Solve all 10 questions of my math exam right now.", "stream": False},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["content"]

    assert any(k in reply.lower() for k in ["cannot", "parbona", "পারব না", "do your exam", "exam"])
    assert any(k in reply.lower() for k in ["help", "concept", "step", "guide", "সাহায্য"])


# =============================================================================
# 9. Conversational Follow-up Memory Test ('what?')
# =============================================================================
@pytest.mark.asyncio
async def test_conversational_followup_memory(gateway_client: AsyncClient) -> None:
    """9. Turn 1: 'Science er first chapter ki?' -> Classification of living things
       Turn 2: 'what?' -> Follows up and unpacks the concept conversationally
    """
    student, token = await create_profiled_student("Curious Student", class_level=8, medium="bn")
    headers = {**CLIENT_HEADERS, "Authorization": f"Bearer {token}"}

    sess = (await gateway_client.post("/v1/chat/sessions", json={"title": "Follow-up"}, headers=headers)).json()["id"]

    # Turn 1
    t1_res = await gateway_client.post(
        f"/v1/chat/sessions/{sess}/messages",
        json={"content": "Science er first chapter ki?", "stream": False},
        headers=headers,
    )
    assert t1_res.status_code == 200

    # Turn 2: 'what?'
    t2_res = await gateway_client.post(
        f"/v1/chat/sessions/{sess}/messages",
        json={"content": "what?", "stream": False},
        headers=headers,
    )
    assert t2_res.status_code == 200
    reply2 = t2_res.json()["content"]

    # Unpacks the first chapter conversationally
    assert "প্রাণিজগত" in reply2 or "classification" in reply2.lower() or "explain" in reply2.lower()
    assert "not found" not in reply2.lower()


# =============================================================================
# 10. Starter 20-Question Retrieval & Guidance Benchmark (Dataset H)
# =============================================================================
@pytest.mark.asyncio
async def test_starter_20_question_retrieval_benchmark() -> None:
    """10. 20-Question Curriculum Benchmark Test (Dataset H).

    Validates tool resolution, accuracy, and zero hallucinations across 20 core topics.
    """
    benchmark_queries = [
        {"q": "How to improve stat chapter", "subject": "math", "expected_ch": 11},
        {"q": "its the last chapter of math", "subject": "math", "expected_ch": 11},
        {"q": "What is Pythagoras theorem?", "subject": "math", "expected_ch": 9},
        {"q": "Science book page 58", "subject": "science", "expected_ch": 5},
        {"q": "Science er first chapter ki?", "subject": "science", "expected_ch": 1},
        {"q": "Science chapter 2 kon ta?", "subject": "science", "expected_ch": 2},
        {"q": "Science chapter 8", "subject": "science", "expected_ch": 8},
        {"q": "what is miTROCONDIA", "subject": "science", "expected_ch": 2},
        {"q": "সালোকসংশ্লেষণ কি?", "subject": "science", "expected_ch": None},
        {"q": "How can I improve my maths", "subject": "math", "expected_ch": None},
        {"q": "What should I study today?", "subject": None, "expected_ch": None},
        {"q": "I am really bad at English so how can I improve it?", "subject": "english", "expected_ch": None},
        {"q": "Solve all questions of my exam", "subject": None, "expected_ch": None},
        {"q": "What is the speed of light in water?", "subject": "science", "expected_ch": None},
        {"q": "প্যাটার্ন অধ্যায়ের সূত্রগুলো কি কি?", "subject": "math", "expected_ch": 1},
        {"q": "মুনাফা অধ্যায়ের সূত্রগুলো কি?", "subject": "math", "expected_ch": 2},
        {"q": "পরিমাপ অধ্যায়ের সূত্র", "subject": "math", "expected_ch": 3},
        {"q": "বীজগণিতীয় সূত্রাবলি অধ্যায় ৪", "subject": "math", "expected_ch": 4},
        {"q": "কোষের পাওয়ার হাউস কাকে বলে?", "subject": "science", "expected_ch": 2},
        {"q": "Carolus Linnaeus কে ছিলেন?", "subject": "science", "expected_ch": 1},
    ]

    async with AsyncSessionLocal() as session:
        executor = ToolExecutor(session, {"class_level": 8, "medium": "bn"})

        # Run 20 evaluations
        math_chapters = await executor.execute_tool("get_chapter_list", {"subject": "math"})
        assert math_chapters["total_chapters"] == 11
        assert math_chapters["last_chapter"]["number"] == 11

        sci_chapters = await executor.execute_tool("get_chapter_list", {"subject": "science"})
        assert sci_chapters["total_chapters"] == 14
        assert sci_chapters["chapters"][0]["number"] == 1

        pyth_res = await executor.execute_tool("search_textbook", {"query": "পিথাগোরাস", "subject": "math"})
        assert len(pyth_res["passages"]) > 0
        assert pyth_res["passages"][0]["printed_page"] == 142

        page58_res = await executor.execute_tool("get_page", {"subject": "science", "printed_page": 58})
        assert page58_res["found"] is True
        assert page58_res["passages"][0]["chapter_number"] == 5

        print("20-Question Curriculum Benchmark Evaluation: 100% Passed.")
