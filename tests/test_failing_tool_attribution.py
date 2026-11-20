"""Test proving that a failing tool never produces an answer claiming textbook verification."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.chat.llm import OpenRouterGateway


@pytest.mark.asyncio
async def test_failing_tool_does_not_claim_verification():
    # 1. Setup mock tool executor where tool raises an exception
    failing_tool_executor = MagicMock()
    failing_tool_executor.execute_tool = AsyncMock(
        side_effect=RuntimeError("Database connection lost during textbook search")
    )

    gateway = OpenRouterGateway(
        primary_model="openai/gpt-4o-mini",
        fallback_model="google/gemini-2.5-flash",
    )

    test_messages = [
        {"role": "user", "content": "Class 8 math chapter 1 er 3 no question bujhiye deo"}
    ]

    # Iteration 1: Model calls search_textbook
    mock_tool_call_resp = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "search_textbook",
                        "arguments": '{"query": "pattern", "class_level": 8, "subject": "math"}'
                    }
                }]
            }
        }],
        "usage": {"prompt_tokens": 50, "completion_tokens": 20}
    }

    # Iteration 2: After seeing tool error, model stops calling tools
    mock_tool_done_resp = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": None
            }
        }],
        "usage": {"prompt_tokens": 80, "completion_tokens": 10}
    }

    # Mock final tutor response acknowledging failure
    mock_final_answer = "একটি কারিগরি ত্রুটির কারণে পাঠ্যবই যাচাই করা সম্ভব হয়নি। তবে প্যাটার্ন সম্পর্কিত সাধারণ ধারণায়..."

    async def fake_lines():
        yield 'data: {"choices": [{"delta": {"content": "' + mock_final_answer + '"}}]}'
        yield 'data: [DONE]'

    with patch("httpx.AsyncClient.post") as mock_post, \
         patch("httpx.AsyncClient.stream") as mock_stream:
        
        # 1st post for tool call, 2nd post sees tool error and terminates tool iteration
        resp1 = MagicMock(status_code=200, is_success=True)
        resp1.json.return_value = mock_tool_call_resp

        resp2 = MagicMock(status_code=200, is_success=True)
        resp2.json.return_value = mock_tool_done_resp

        mock_post.side_effect = [resp1, resp2]

        # Streaming response
        mock_stream_ctx = MagicMock()
        mock_resp_stream = MagicMock(status_code=200)
        mock_resp_stream.aiter_lines = fake_lines
        mock_stream_ctx.__aenter__.return_value = mock_resp_stream
        mock_stream_ctx.__aexit__.return_value = None
        mock_stream.return_value = mock_stream_ctx

        tokens = []
        async for token in gateway.stream_chat(
            messages=test_messages,
            tools=[{"type": "function", "function": {"name": "search_textbook"}}],
            tool_executor=failing_tool_executor
        ):
            tokens.append(token)

        full_reply = "".join(tokens)

        # Assertions:
        # 1. Tool executor was called once and failed
        failing_tool_executor.execute_tool.assert_called_once_with("search_textbook", {"query": "pattern", "class_level": 8, "subject": "math"})

        # 2. Response contains explicit disclaimer that book verification failed
        assert "পাঠ্যবই যাচাই করা সম্ভব হয়নি" in full_reply

        # 3. Response NEVER claims book verification
        assert "বই থেকে যাচাই করেছি" not in full_reply
        assert "আমি পাঠ্যবই থেকে পেয়েছি" not in full_reply
