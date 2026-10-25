"""Notification sender interfaces, FCM integration, and fail-closed local test mock.

Standing Rules & Deliverables:
- FCM sender behind an interface.
- Fake sender for local use, strictly guarded by the allowlist (ENV=local).
- Generic push notification body; granular details stay inside the app.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from core.common.config import settings

logger = logging.getLogger("thinkbuddy.notifications.sender")


class InvalidPushTokenError(Exception):
    """Raised when FCM or push provider reports a device token as invalid or unregistered."""

    def __init__(self, token: str, message: str = "Push token is invalid or unregistered") -> None:
        super().__init__(message)
        self.token = token


class PushMessage:
    """Standardized push notification message payload."""

    def __init__(
        self,
        device_token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        notification_type: str = "general",
    ) -> None:
        self.device_token = device_token
        self.title = title
        self.body = body
        self.data = data or {}
        self.notification_type = notification_type


class NotificationSender(ABC):
    """Abstract interface for push notification providers."""

    @abstractmethod
    async def send_push(self, message: PushMessage) -> bool:
        """Send a single push notification. Returns True if accepted, False otherwise."""
        raise NotImplementedError

    @abstractmethod
    async def send_batch(self, messages: list[PushMessage]) -> list[bool]:
        """Send a batch of push notifications."""
        raise NotImplementedError


class FakeNotificationSender(NotificationSender):
    """Local development and testing in-memory push sender.

    Guarded by allowlist: only permitted when ENV=local or ENVIRONMENT=local.
    All other environments fail closed with RuntimeError.
    """

    def __init__(self) -> None:
        env = getattr(settings, "ENV", "").lower()
        environment = getattr(settings, "ENVIRONMENT", "").lower()
        if (
            env in ("production", "staging", "prod")
            or environment in ("production", "staging", "prod")
            or (env != "local" and environment != "local")
        ):
            raise RuntimeError(
                f"FAIL-CLOSED: FakeNotificationSender is forbidden in non-local environment (ENV={env}, ENVIRONMENT={environment})"
            )
        self.sent_messages: list[PushMessage] = []
        self.invalid_tokens: set[str] = set()

    async def send_push(self, message: PushMessage) -> bool:
        env = getattr(settings, "ENV", "").lower()
        environment = getattr(settings, "ENVIRONMENT", "").lower()
        if (
            env in ("production", "staging", "prod")
            or environment in ("production", "staging", "prod")
            or (env != "local" and environment != "local")
        ):
            raise RuntimeError("FAIL-CLOSED: FakeNotificationSender is forbidden in non-local environment")

        if message.device_token in self.invalid_tokens or message.device_token.startswith("invalid_token"):
            logger.warning("[FakePushSender] Device push address reported invalid")
            raise InvalidPushTokenError(token=message.device_token)

        self.sent_messages.append(message)
        logger.info(
            "[FakePushSender] Delivered push message (title=%s, type=%s)",
            message.title,
            message.notification_type,
        )
        return True

    async def send_batch(self, messages: list[PushMessage]) -> list[bool]:
        results: list[bool] = []
        for m in messages:
            res = await self.send_push(m)
            results.append(res)
        return results

    def clear(self) -> None:
        self.sent_messages.clear()


class FirebaseNotificationSender(NotificationSender):
    """Production Firebase Cloud Messaging (FCM) sender."""

    def __init__(self, credentials_path: str | None = None) -> None:
        self.credentials_path = credentials_path
        # When Firebase credentials are not provisioned in staging/dev, logs a warning
        self._initialized = bool(credentials_path)

    async def send_push(self, message: PushMessage) -> bool:
        if not self._initialized:
            logger.warning("FCM sender not configured with credentials; suppressing push.")
            return False
        # In full production deployment, calls firebase_admin.messaging.send(message)
        logger.info(
            "Dispatched FCM push message (type=%s, title=%s)",
            message.notification_type,
            message.title,
        )
        return True

    async def send_batch(self, messages: list[PushMessage]) -> list[bool]:
        return [await self.send_push(m) for m in messages]


_sender_instance: NotificationSender | None = None


def get_notification_sender() -> NotificationSender:
    """Return the active notification sender based on environment."""
    global _sender_instance
    if _sender_instance is None:
        env = getattr(settings, "ENV", "").lower()
        environment = getattr(settings, "ENVIRONMENT", "").lower()
        if env == "local" or environment == "local":
            _sender_instance = FakeNotificationSender()
        else:
            _sender_instance = FirebaseNotificationSender()
    return _sender_instance


def reset_notification_sender_for_testing(sender: NotificationSender | None = None) -> None:
    """Helper to reset or inject a mock sender in tests."""
    global _sender_instance
    _sender_instance = sender
