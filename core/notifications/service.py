"""Service layer for notifications, delivery dispatch, and user preferences (P07).

Standing Rules & Deliverables:
- Push notifications sent via NotificationSender interface (FCM or fail-closed fake).
- Push tokens registered via existing `devices` table.
- Asia/Dhaka quiet hours enforcement.
- Per-user daily push caps (max 5/day) and coalescing.
- Generic push text; granular details live securely inside the app.
- Triggers for: daily_reminder, task_missed, quiz_ready, plan_changed, integrity_flag, weekly_parent_summary.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.devices.models import Device
from core.notifications.models import Notification, NotificationDelivery, NotificationPreference
from core.notifications.sender import InvalidPushTokenError, PushMessage, get_notification_sender

logger = logging.getLogger("thinkbuddy.notifications")

DHAKA_TZ = ZoneInfo("Asia/Dhaka")
MAX_DAILY_PUSH_CAP = 5
COALESCE_WINDOW_MINUTES = 30


def utcnow() -> datetime:
    return datetime.now(UTC)


def now_in_dhaka() -> datetime:
    return datetime.now(DHAKA_TZ)


class NotificationService:
    """Handles notification dispatch, localization, push delivery, quiet hours, and reading."""

    @staticmethod
    def is_in_quiet_hours(pref: NotificationPreference, current_dhaka_dt: datetime | None = None) -> bool:
        """Check if current time in Asia/Dhaka falls within user's configured quiet hours."""
        if not pref.quiet_hours_start or not pref.quiet_hours_end:
            return False

        try:
            start_parts = [int(p) for p in pref.quiet_hours_start.split(":")]
            end_parts = [int(p) for p in pref.quiet_hours_end.split(":")]
            t_start = time(start_parts[0], start_parts[1])
            t_end = time(end_parts[0], end_parts[1])
        except (ValueError, IndexError):
            return False

        dt = current_dhaka_dt or now_in_dhaka()
        cur_t = dt.time()

        if t_start <= t_end:
            return t_start <= cur_t <= t_end
        # Overnight quiet hours (e.g. 22:00 to 07:00)
        return cur_t >= t_start or cur_t <= t_end

    @staticmethod
    def get_quiet_hours_end_utc(pref: NotificationPreference, dhaka_now: datetime) -> datetime:
        """Calculate the UTC timestamp when the current quiet hours window ends in Asia/Dhaka (Item 2)."""
        try:
            end_parts = [int(p) for p in (pref.quiet_hours_end or "07:00").split(":")]
            start_parts = [int(p) for p in (pref.quiet_hours_start or "22:00").split(":")]
            t_end = time(end_parts[0], end_parts[1])
            t_start = time(start_parts[0], start_parts[1])
        except (ValueError, IndexError):
            t_end = time(7, 0)
            t_start = time(22, 0)

        cur_t = dhaka_now.time()
        if t_start <= t_end:
            # Daytime quiet hours
            end_dhaka = dhaka_now.replace(hour=t_end.hour, minute=t_end.minute, second=0, microsecond=0)
        else:
            # Overnight quiet hours (e.g. 22:00 to 07:00)
            if cur_t >= t_start:
                # Before midnight Dhaka: ends tomorrow morning
                end_dhaka = (dhaka_now + timedelta(days=1)).replace(hour=t_end.hour, minute=t_end.minute, second=0, microsecond=0)
            else:
                # After midnight Dhaka: ends today morning
                end_dhaka = dhaka_now.replace(hour=t_end.hour, minute=t_end.minute, second=0, microsecond=0)
        return end_dhaka.astimezone(UTC)

    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: uuid.UUID,
        type: str,
        title: str,
        body: str,
        title_bn: str,
        body_bn: str,
        data: dict[str, Any] | None = None,
    ) -> Notification:
        """Create and persist an in-app bilingual notification."""
        notif = Notification(
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            title_bn=title_bn,
            body_bn=body_bn,
            data=data or {},
            created_at=utcnow(),
        )
        db.add(notif)
        await db.flush()
        logger.info("Created notification %s for user %s (type=%s)", notif.id, user_id, type)
        return notif

    @staticmethod
    async def dispatch_notification(
        db: AsyncSession,
        user_id: uuid.UUID,
        type: str,
        title: str,
        body: str,
        title_bn: str,
        body_bn: str,
        data: dict[str, Any] | None = None,
        current_dhaka_dt: datetime | None = None,
        student_id: uuid.UUID | None = None,
    ) -> tuple[Notification, list[NotificationDelivery]]:
        """Create notification and attempt delivery over push channels with quiet hours, coalescing, and cap checks."""
        dhaka_now = current_dhaka_dt or now_in_dhaka()
        current_utc = dhaka_now.astimezone(UTC)

        # 1. Persist full detailed notification in-app
        notif = await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            title_bn=title_bn,
            body_bn=body_bn,
            data=data,
        )

        deliveries: list[NotificationDelivery] = []
        # Always record in-app delivery
        in_app_delivery = NotificationDelivery(
            notification_id=notif.id,
            user_id=user_id,
            channel="in_app",
            status="delivered",
            payload={"title": title, "body": body},
            sent_at=current_utc,
        )
        db.add(in_app_delivery)
        deliveries.append(in_app_delivery)

        # 2. Check preferences
        pref = await NotificationService.get_or_create_preferences(db, user_id)
        if not pref.channels.get("push", False):
            await db.flush()
            return notif, deliveries

        generic_title, generic_body = NotificationService._get_generic_push_content(type)

        # 3. Check Quiet Hours (Asia/Dhaka) - Defer push until quiet hours end (Item 2)
        if NotificationService.is_in_quiet_hours(pref, dhaka_now):
            logger.info("Push suppressed for user %s during quiet hours (Asia/Dhaka); deferred", user_id)
            deferred_until_utc = NotificationService.get_quiet_hours_end_utc(pref, dhaka_now)
            quiet_delivery = NotificationDelivery(
                notification_id=notif.id,
                user_id=user_id,
                channel="push",
                status="deferred_quiet_hours",
                deferred_until=deferred_until_utc,
                reason=f"Current time in Asia/Dhaka is within quiet hours ({pref.quiet_hours_start}-{pref.quiet_hours_end}). Deferred until quiet hours end.",
                payload={
                    "type": type,
                    "student_id": str(student_id) if student_id else None,
                    "title": generic_title,
                    "body": generic_body,
                },
                sent_at=current_utc,
            )
            db.add(quiet_delivery)
            deliveries.append(quiet_delivery)
            await db.flush()
            return notif, deliveries

        # 4. Check Coalescing (keyed by user, type, AND student; Item 3)
        window_start = current_utc - timedelta(minutes=COALESCE_WINDOW_MINUTES)
        stmt_recent = (
            select(func.count(NotificationDelivery.id))
            .where(
                NotificationDelivery.user_id == user_id,
                NotificationDelivery.channel == "push",
                NotificationDelivery.status == "delivered",
                NotificationDelivery.sent_at >= window_start,
                NotificationDelivery.payload["type"].astext == type,
            )
        )
        if student_id:
            stmt_recent = stmt_recent.where(
                NotificationDelivery.payload["student_id"].astext == str(student_id)
            )
        else:
            stmt_recent = stmt_recent.where(
                (NotificationDelivery.payload["student_id"].astext.is_(None))
                | (NotificationDelivery.payload["student_id"].astext == "None")
                | (NotificationDelivery.payload["student_id"].astext == "")
            )

        recent_count = (await db.execute(stmt_recent)).scalar() or 0
        if recent_count > 0:
            logger.info("Push for user %s coalesced (type=%s, student=%s in past 30m)", user_id, type, student_id)
            coalesce_delivery = NotificationDelivery(
                notification_id=notif.id,
                user_id=user_id,
                channel="push",
                status="suppressed_coalesced",
                reason=f"Notification of type {type} for student {student_id} was already sent within past 30 minutes",
                payload={
                    "type": type,
                    "student_id": str(student_id) if student_id else None,
                    "title": generic_title,
                    "body": generic_body,
                },
                sent_at=utcnow(),
            )
            db.add(coalesce_delivery)
            deliveries.append(coalesce_delivery)
            await db.flush()
            return notif, deliveries

        # 5. Check Per-User Daily Push Cap (Asia/Dhaka start of day)
        today_start_dhaka = dhaka_now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start_dhaka.astimezone(UTC)
        stmt_cap = (
            select(func.count(NotificationDelivery.id))
            .where(
                NotificationDelivery.user_id == user_id,
                NotificationDelivery.channel == "push",
                NotificationDelivery.status == "delivered",
                NotificationDelivery.sent_at >= today_start_utc,
            )
        )
        today_sent = (await db.execute(stmt_cap)).scalar() or 0
        if today_sent >= MAX_DAILY_PUSH_CAP:
            logger.info("Push suppressed for user %s (daily cap %d reached)", user_id, MAX_DAILY_PUSH_CAP)
            cap_delivery = NotificationDelivery(
                notification_id=notif.id,
                user_id=user_id,
                channel="push",
                status="suppressed_daily_cap",
                reason=f"Daily cap of {MAX_DAILY_PUSH_CAP} push notifications reached for today",
                payload={
                    "type": type,
                    "student_id": str(student_id) if student_id else None,
                    "title": generic_title,
                    "body": generic_body,
                },
                sent_at=current_utc,
            )
            db.add(cap_delivery)
            deliveries.append(cap_delivery)
            await db.flush()
            return notif, deliveries

        # 6. Fetch devices with push tokens
        stmt_devices = select(Device).where(Device.user_id == user_id, Device.push_token.is_not(None))
        res_devices = await db.execute(stmt_devices)
        devices = res_devices.scalars().all()

        if not devices:
            logger.debug("No registered push devices found for user %s", user_id)
            await db.flush()
            return notif, deliveries

        # 7. Generic Push Text Rule: Generic header/body; details stay inside app
        push_sender = get_notification_sender()

        for d in devices:
            msg = PushMessage(
                device_token=d.push_token,
                title=generic_title,
                body=generic_body,
                data={
                    "notification_id": str(notif.id),
                    "type": type,
                    "target_url": f"/notifications/{notif.id}",
                },
                notification_type=type,
            )
            success = False
            try:
                success = await push_sender.send_push(msg)
            except InvalidPushTokenError as ex:
                logger.warning("Push delivery reported unparseable address; removing device %s", d.id)
                await db.execute(
                    update(Device).where(Device.push_token == ex.token).values(push_token=None)
                )

            push_delivery = NotificationDelivery(
                notification_id=notif.id,
                user_id=user_id,
                device_id=d.id,
                channel="push",
                status="delivered" if success else "failed",
                payload={
                    "title": generic_title,
                    "type": type,
                    "student_id": str(student_id) if student_id else None,
                },
                sent_at=current_utc,
            )
            db.add(push_delivery)
            deliveries.append(push_delivery)

        await db.flush()
        return notif, deliveries

    @staticmethod
    async def dispatch_deferred_pushes(
        db: AsyncSession,
        current_dt: datetime | None = None,
    ) -> list[NotificationDelivery]:
        """Idempotent scheduled job to dispatch deferred pushes whose quiet hours have ended (Item 2).

        Re-checks preferences and daily cap at send time, expires stale items,
        merges multiple deferred items per user into a single push alert,
        and tests cleanly across Dhaka midnight.
        """
        now_utc = current_dt or utcnow()
        dhaka_now = now_utc.astimezone(DHAKA_TZ)

        # 1. Fetch pending deferred deliveries whose deferred_until time has passed
        # Use SKIP LOCKED for idempotency across parallel worker executions
        stmt = (
            select(NotificationDelivery)
            .where(
                NotificationDelivery.channel == "push",
                NotificationDelivery.status == "deferred_quiet_hours",
                NotificationDelivery.deferred_until <= now_utc,
            )
            .order_by(NotificationDelivery.sent_at.asc())
            .with_for_update(skip_locked=True)
        )
        res = await db.execute(stmt)
        deferred_records = res.scalars().all()
        if not deferred_records:
            return []

        # 2. Group by user_id
        from collections import defaultdict
        user_items: dict[uuid.UUID, list[NotificationDelivery]] = defaultdict(list)
        stale_threshold = now_utc - timedelta(hours=24)

        for d in deferred_records:
            if d.sent_at < stale_threshold:
                d.status = "expired_stale"
                d.reason = "Notification expired while deferred (>24 hours stale)"
            else:
                user_items[d.user_id].append(d)

        processed_deliveries: list[NotificationDelivery] = []
        sender = get_notification_sender()

        for u_id, items in user_items.items():
            if not items:
                continue

            # Re-check user preferences
            pref = await NotificationService.get_or_create_preferences(db, u_id)
            if not pref.channels.get("push", False):
                for item in items:
                    item.status = "suppressed_preferences_disabled"
                    item.reason = "Push notifications disabled in preferences at send time"
                    processed_deliveries.append(item)
                continue

            # Re-check quiet hours in Asia/Dhaka at send time
            if NotificationService.is_in_quiet_hours(pref, dhaka_now):
                # Still in quiet hours (e.g. settings changed or scheduled early)
                new_deferred_until = NotificationService.get_quiet_hours_end_utc(pref, dhaka_now)
                for item in items:
                    item.deferred_until = new_deferred_until
                continue

            # Re-check daily cap in Asia/Dhaka at send time
            today_start_dhaka = dhaka_now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_start_utc = today_start_dhaka.astimezone(UTC)
            stmt_cap = select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.user_id == u_id,
                NotificationDelivery.channel == "push",
                NotificationDelivery.status == "delivered",
                NotificationDelivery.sent_at >= today_start_utc,
            )
            already_sent = (await db.execute(stmt_cap)).scalar() or 0
            if already_sent >= MAX_DAILY_PUSH_CAP:
                for item in items:
                    item.status = "suppressed_daily_cap"
                    item.reason = f"Daily push cap of {MAX_DAILY_PUSH_CAP} reached for today"
                    processed_deliveries.append(item)
                continue

            # Fetch active registered devices for this user
            stmt_dev = select(Device).where(Device.user_id == u_id, Device.push_token.is_not(None))
            res_dev = await db.execute(stmt_dev)
            devices = res_dev.scalars().all()
            if not devices:
                for item in items:
                    item.status = "no_devices"
                    item.reason = "No registered push devices found at send time"
                    processed_deliveries.append(item)
                continue

            # Merged into one push if multiple items exist for user (Item 2)
            n_items = len(items)
            if n_items == 1:
                single_item = items[0]
                push_title = single_item.payload.get("title") or "Study Reminder"
                push_body = single_item.payload.get("body") or "You have an update in ThinkBuddy."
            else:
                push_title = "ThinkBuddy Updates"
                push_body = f"You have {n_items} new updates in ThinkBuddy."

            success = False
            for dev in devices:
                msg = PushMessage(
                    device_token=dev.push_token,
                    title=push_title,
                    body=push_body,
                    notification_type="merged_deferred" if n_items > 1 else items[0].payload.get("type", "deferred_push"),
                    data={"count": str(n_items)},
                )
                try:
                    res_push = await sender.send_push(msg)
                    if res_push:
                        success = True
                except InvalidPushTokenError as ex:
                    logger.warning("Push delivery reported unparseable address; removing device %s", dev.id)
                    await db.execute(
                        update(Device).where(Device.push_token == ex.token).values(push_token=None)
                    )

            final_status = "delivered" if success else "failed"
            for item in items:
                item.status = final_status
                item.sent_at = now_utc
                if n_items > 1:
                    item.reason = f"Delivered via merged batch of {n_items} notifications"
                processed_deliveries.append(item)

        await db.flush()
        return processed_deliveries

    @staticmethod
    def _get_generic_push_content(notif_type: str) -> tuple[str, str]:
        """Produce generic push titles and bodies so privacy-sensitive details remain inside the app."""
        generic_map = {
            "daily_reminder": (
                "ThinkBuddy Daily Study",
                "Your scheduled study session is ready. Tap to view your plan.",
            ),
            "task_missed": (
                "ThinkBuddy Study Update",
                "You have pending study tasks. Tap to resume your learning loop.",
            ),
            "quiz_ready": (
                "ThinkBuddy Assessment",
                "A new quiz is ready. Tap to start your session.",
            ),
            "plan_changed": (
                "ThinkBuddy Schedule Update",
                "Your study schedule has been updated. Tap to view changes.",
            ),
            "integrity_flag": (
                "ThinkBuddy Learning Notice",
                "An assessment event was noted. Tap to review details.",
            ),
            "weekly_parent_summary": (
                "ThinkBuddy Weekly Summary",
                "Your student's weekly learning progress summary is available.",
            ),
            "ai_adjustment_auto_applied": (
                "ThinkBuddy Schedule Update",
                "Study plan automatically adjusted. Tap to review.",
            ),
            "student_change_request": (
                "ThinkBuddy Change Request",
                "A new study change request requires your approval.",
            ),
        }
        return generic_map.get(
            notif_type,
            ("ThinkBuddy Update", "You have a new update in ThinkBuddy. Tap to view."),
        )

    # -------------------------------------------------------------------------
    # High-level trigger helpers
    # -------------------------------------------------------------------------

    @staticmethod
    async def trigger_daily_reminder(
        db: AsyncSession,
        user_id: uuid.UUID,
        tasks_count: int,
        student_id: uuid.UUID | None = None,
    ) -> tuple[Notification, list[NotificationDelivery]]:
        return await NotificationService.dispatch_notification(
            db=db,
            user_id=user_id,
            type="daily_reminder",
            title="Today's study tasks are ready",
            body=f"You have {tasks_count} study tasks scheduled for today.",
            title_bn="আজকের পড়ার বিষয় প্রস্তুত",
            body_bn=f"আজকের জন্য আপনার {tasks_count}টি পড়ার বিষয় নির্ধারিত রয়েছে।",
            data={"tasks_count": tasks_count},
            student_id=student_id,
        )

    @staticmethod
    async def trigger_task_missed(
        db: AsyncSession,
        user_id: uuid.UUID,
        subject: str,
        student_id: uuid.UUID | None = None,
    ) -> tuple[Notification, list[NotificationDelivery]]:
        return await NotificationService.dispatch_notification(
            db=db,
            user_id=user_id,
            type="task_missed",
            title=f"Unfinished study tasks in {subject}",
            body=f"You have incomplete tasks in {subject}. Don't lose your study momentum!",
            title_bn=f"{subject} বিষয়ে অসমাপ্ত পড়া",
            body_bn=f"{subject} বিষয়ে কিছু পড়া বাকি আছে। পড়াশোনার ধারাবাহিকতা বজায় রাখুন!",
            data={"subject": subject},
            student_id=student_id,
        )

    @staticmethod
    async def trigger_quiz_ready(
        db: AsyncSession,
        user_id: uuid.UUID,
        quiz_id: uuid.UUID,
        subject: str,
        student_id: uuid.UUID | None = None,
    ) -> tuple[Notification, list[NotificationDelivery]]:
        return await NotificationService.dispatch_notification(
            db=db,
            user_id=user_id,
            type="quiz_ready",
            title=f"New quiz available in {subject}",
            body=f"A new practice quiz is ready in {subject} to reinforce recent topics.",
            title_bn=f"{subject} বিষয়ে নতুন কুইজ",
            body_bn=f"সাম্প্রতিক বিষয়গুলো যাচাই করতে {subject} বিষয়ে নতুন কুইজ প্রস্তুত।",
            data={"quiz_id": str(quiz_id), "subject": subject},
            student_id=student_id,
        )

    @staticmethod
    async def trigger_plan_changed(
        db: AsyncSession,
        user_id: uuid.UUID,
        reason: str,
        reason_bn: str,
        student_id: uuid.UUID | None = None,
    ) -> tuple[Notification, list[NotificationDelivery]]:
        return await NotificationService.dispatch_notification(
            db=db,
            user_id=user_id,
            type="plan_changed",
            title="Study schedule updated",
            body=f"Your study schedule was recalculated: {reason}",
            title_bn="পড়ার রুটিন হালনাগাদ করা হয়েছে",
            body_bn=f"আপনার পড়ার সময়সূচি পুনর্বণ্টন করা হয়েছে: {reason_bn}",
            data={"reason": reason},
            student_id=student_id,
        )

    @staticmethod
    async def trigger_integrity_flag(
        db: AsyncSession,
        user_id: uuid.UUID,
        attempt_id: uuid.UUID,
        flag_type: str,
        student_id: uuid.UUID | None = None,
    ) -> tuple[Notification, list[NotificationDelivery]]:
        return await NotificationService.dispatch_notification(
            db=db,
            user_id=user_id,
            type="integrity_flag",
            title="Quiz session notice",
            body=f"A quiz session required review due to: {flag_type}.",
            title_bn="কুইজ সেশনের সতর্কতা",
            body_bn=f"কুইজ সেশনে সতর্কতা পরিলক্ষিত হয়েছে: {flag_type}।",
            data={"attempt_id": str(attempt_id), "flag_type": flag_type},
            student_id=student_id,
        )

    @staticmethod
    async def trigger_weekly_parent_summary(
        db: AsyncSession,
        parent_id: uuid.UUID,
        student_name: str,
        total_minutes: int,
        streak_days: int,
        completion_pct: float,
        student_id: uuid.UUID | None = None,
    ) -> tuple[Notification, list[NotificationDelivery]]:
        return await NotificationService.dispatch_notification(
            db=db,
            user_id=parent_id,
            type="weekly_parent_summary",
            title=f"Weekly learning summary for {student_name}",
            body=(
                f"{student_name} studied for {total_minutes} minutes with a {completion_pct}% completion rate "
                f"and an active {streak_days}-day streak this week."
            ),
            title_bn=f"{student_name}-এর সাপ্তাহিক শিক্ষণ সারসংক্ষেপ",
            body_bn=(
                f"এই সপ্তাহে {student_name} মোট {total_minutes} মিনিট পড়াশোনা করেছে, "
                f"কাজের সমাপ্তির হার {completion_pct}% এবং চলমান স্ট্রিক {streak_days} দিন।"
            ),
            data={
                "student_name": student_name,
                "total_minutes": total_minutes,
                "streak_days": streak_days,
                "completion_pct": completion_pct,
            },
            student_id=student_id,
        )

    # -------------------------------------------------------------------------
    # List & Mark Read
    # -------------------------------------------------------------------------

    @staticmethod
    async def list_notifications(
        db: AsyncSession,
        user_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int, int]:
        """Fetch notifications strictly owned by user with pagination and counts."""
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        res = await db.execute(stmt)
        items = list(res.scalars().all())

        total_stmt = select(func.count(Notification.id)).where(Notification.user_id == user_id)
        unread_stmt = (
            select(func.count(Notification.id))
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        total_count = (await db.execute(total_stmt)).scalar() or 0
        unread_count = (await db.execute(unread_stmt)).scalar() or 0

        return items, total_count, unread_count

    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        user_id: uuid.UUID,
        notification_id: uuid.UUID,
    ) -> Notification | None:
        """Mark a single notification owned by user as read."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        res = await db.execute(stmt)
        item = res.scalars().first()
        if item and item.read_at is None:
            item.read_at = utcnow()
            await db.flush()
        return item

    @staticmethod
    async def mark_all_as_read(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> int:
        """Mark all unread notifications for a user as read."""
        stmt = (
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=utcnow())
        )
        res = await db.execute(stmt)
        await db.flush()
        return getattr(res, "rowcount", 0)

    @staticmethod
    async def get_or_create_preferences(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> NotificationPreference:
        """Retrieve existing preferences or instantiate defaults."""
        stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        res = await db.execute(stmt)
        pref = res.scalars().first()
        if not pref:
            pref = NotificationPreference(
                user_id=user_id,
                channels={"in_app": True, "push": True},
                categories={
                    "ai_adjustments": True,
                    "streaks": True,
                    "progress": True,
                    "exams": True,
                },
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(pref)
            await db.flush()
        return pref

    @staticmethod
    async def update_preferences(
        db: AsyncSession,
        user_id: uuid.UUID,
        channels: dict[str, bool] | None = None,
        quiet_hours_start: str | None = None,
        quiet_hours_end: str | None = None,
        categories: dict[str, bool] | None = None,
    ) -> NotificationPreference:
        """Update user preferences."""
        pref = await NotificationService.get_or_create_preferences(db, user_id)
        if channels is not None:
            pref.channels = channels
        if quiet_hours_start is not None:
            pref.quiet_hours_start = quiet_hours_start
        if quiet_hours_end is not None:
            pref.quiet_hours_end = quiet_hours_end
        if categories is not None:
            pref.categories = categories
        pref.updated_at = utcnow()
        await db.flush()
        return pref
