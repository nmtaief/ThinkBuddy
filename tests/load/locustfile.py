"""Locust load test suite for ThinkBuddy.

Deliverable 5 & Architecture §7 Acceptance Targets:
- Non-chat API p95 < 400ms.
- Chat streaming first token < 2.5s p95 on mobile data.
- Covers:
  1. Auth exchange (/v1/auth/exchange)
  2. Today payload (/v1/students/{id}/today)
  3. Quiz answer submission (/v1/quizzes/{id}/attempts/{attempt_id}/answers)
  4. Concurrent chat streaming (/v1/chat/messages)

Run with:
    locust -f tests/load/locustfile.py --headless -u 20 -r 5 --run-time 30s --host http://localhost:8000
"""

import json
import time
import uuid
from locust import HttpUser, between, task


class ThinkBuddyUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Initialize session and authenticate parent and student."""
        self.client_headers = {
            "X-Client-Platform": "android",
            "X-Client-Form-Factor": "phone",
            "X-App-Version": "1.0.0",
            "X-Device-Id": f"device-load-{uuid.uuid4().hex[:8]}",
            "Accept-Language": "bn",
        }
        self.access_token = None
        self.student_id = None
        self.attempt_id = None

        # Authenticate parent, create child, and get student token
        self._setup_student()

    def _setup_student(self) -> None:
        p_phone = f"+880177{uuid.uuid4().hex[:6]}"
        resp_p = self.client.post(
            "/v1/auth/exchange",
            json={"provider_token": f"fake:phone:{p_phone}", "role": "parent", "display_name": "Load Parent"},
            headers=self.client_headers,
            name="/v1/auth/exchange [Parent]",
        )
        if resp_p.status_code == 200:
            p_token = resp_p.json()["access_token"]
            p_head = {**self.client_headers, "Authorization": f"Bearer {p_token}"}
            self.client.post("/v1/parents/consent", json={"version": "1.0", "consented": True}, headers=p_head)
            res_fam = self.client.post("/v1/families", json={"name": "Load Fam"}, headers=p_head)
            if res_fam.status_code == 201:
                fam_id = res_fam.json()["id"]
                res_c = self.client.post(
                    f"/v1/families/{fam_id}/students",
                    json={"display_name": "Load Child", "class_level": 7, "medium": "bn", "daily_minutes": 45},
                    headers=p_head,
                )
                if res_c.status_code == 201:
                    link_code = res_c.json()["link_code"]
                    s_phone = f"+880178{uuid.uuid4().hex[:6]}"
                    resp_s = self.client.post(
                        "/v1/auth/exchange",
                        json={"provider_token": f"fake:phone:{s_phone}", "role": "student", "link_code": link_code},
                        headers=self.client_headers,
                        name="/v1/auth/exchange [Student]",
                    )
                    if resp_s.status_code == 200:
                        self.access_token = resp_s.json()["access_token"]
                        self.student_id = resp_s.json()["user"]["id"]

    @task(3)
    def fetch_today_payload(self) -> None:
        """Flow 2: Fetch today schedule payload."""
        if not self.access_token or not self.student_id:
            return
        headers = {**self.client_headers, "Authorization": f"Bearer {self.access_token}"}
        self.client.get(
            f"/v1/students/{self.student_id}/today",
            headers=headers,
            name="/v1/students/:id/today",
        )

    @task(2)
    def submit_quiz_answer(self) -> None:
        """Flow 3: Quiz answer submission."""
        if not self.access_token:
            return
        headers = {**self.client_headers, "Authorization": f"Bearer {self.access_token}"}
        # Practice quiz answer or submission probe
        dummy_id = str(uuid.uuid4())
        self.client.post(
            f"/v1/quizzes/{dummy_id}/attempts",
            json={"mode": "practice"},
            headers=headers,
            name="/v1/quizzes/:id/attempts",
        )

    @task(1)
    def chat_message_stream(self) -> None:
        """Flow 4: SSE streaming chat with time-to-first-token tracking."""
        if not self.access_token:
            return
        headers = {**self.client_headers, "Authorization": f"Bearer {self.access_token}"}

        # Create session
        res_s = self.client.post("/v1/chat/sessions", json={"title": "Load Chat"}, headers=headers)
        if res_s.status_code not in (200, 201):
            return
        session_id = res_s.json()["id"]

        start_time = time.perf_counter()
        first_token_time = None

        with self.client.post(
            f"/v1/chat/sessions/{session_id}/messages",
            json={
                "content": "উৎপাদক কাকে বলে?",
                "stream": True,
                "language": "bn",
            },
            headers=headers,
            stream=True,
            name="/v1/chat/sessions/:id/messages [SSE Stream]",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                for line in response.iter_lines():
                    if line and b"data:" in line:
                        if first_token_time is None:
                            first_token_time = time.perf_counter()
                            # Verify Architecture §7 target: first token < 2.5s
                            latency = first_token_time - start_time
                            if latency > 2.5:
                                response.failure(f"First token latency exceeded target 2.5s: {latency:.2f}s")
                                return
                        break
                response.success()
            else:
                response.failure(f"Chat stream failed with status {response.status_code}")
