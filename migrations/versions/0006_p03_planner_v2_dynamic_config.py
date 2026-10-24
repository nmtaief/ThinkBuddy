"""P03 v2 amendment: dynamic configuration layer, day types, and admin policies.

Revision ID: 0006_p03_planner_v2_dynamic_config
Revises: 0005_p03_student_plan_version
Create Date: 2026-10-23 18:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006_p03_planner_v2_config"
down_revision: str | None = "0005_p03_student_plan_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_OBSERVANCES = [
    {
        "key": "eid_ul_fitr",
        "name_bn": "ঈদুল ফিতর",
        "name_en": "Eid-ul-Fitr",
        "description": "Islamic celebration marking the end of Ramadan",
    },
    {
        "key": "eid_ul_adha",
        "name_bn": "ঈদুল আযহা",
        "name_en": "Eid-ul-Adha",
        "description": "Feast of Sacrifice",
    },
    {
        "key": "durga_puja",
        "name_bn": "দুর্গাপূজা",
        "name_en": "Durga Puja",
        "description": "Major Hindu festival celebrating Goddess Durga",
    },
    {
        "key": "christmas",
        "name_bn": "বড়দিন",
        "name_en": "Christmas",
        "description": "Christian celebration of the Nativity",
    },
    {
        "key": "buddha_purnima",
        "name_bn": "বুদ্ধ পূর্ণিমা",
        "name_en": "Buddha Purnima",
        "description": "Buddhist celebration of the birth and enlightenment of Gautama Buddha",
    },
    {
        "key": "shab_e_barat",
        "name_bn": "শবে বরাত",
        "name_en": "Shab-e-Barat",
        "description": "Night of Records and Fortune",
    },
    {
        "key": "shab_e_qadr",
        "name_bn": "শবে কদর",
        "name_en": "Shab-e-Qadr",
        "description": "Night of Power / Destiny",
    },
    {
        "key": "ashura",
        "name_bn": "পবিত্র আশুরা",
        "name_en": "Holy Ashura",
        "description": "10th of Muharram observance",
    },
    {
        "key": "janmashtami",
        "name_bn": "শুভ জন্মাষ্টমী",
        "name_en": "Janmashtami",
        "description": "Hindu celebration of Lord Krishna's birth",
    },
    {
        "key": "saraswati_puja",
        "name_bn": "সরস্বতী পূজা",
        "name_en": "Saraswati Puja",
        "description": "Festival of learning, music, and art",
    },
]

DEFAULT_PLANNER_PARAMS = {
    "study_share": 0.65,
    "revision_share": 0.25,
    "homework_quiz_share": 0.10,
    "revision_intervals": [1, 3, 7, 14, 30],
    "final_revision_window_pct": 0.15,
    "final_revision_min_days": 3,
    "weekly_buffer_interval": 7,
    "min_subject_daily_share": 0.10,
    "rolling_horizon_days": 60,
    "max_consecutive_days_per_subject": 2,
    "priority_weight_mapping": {"normal": 1.0, "main": 1.3, "difficult": 1.6},
}


def upgrade() -> None:
    # 1. Extend student_profiles for classes 6-12, group, and optional subjects
    op.add_column(
        "student_profiles",
        sa.Column("group", sa.String(32), nullable=True),
    )
    op.add_column(
        "student_profiles",
        sa.Column(
            "optional_subject_ids",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
    )

    # 2. Create observance_catalog table
    observance_catalog = op.create_table(
        "observance_catalog",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("name_bn", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed observance catalog
    op.bulk_insert(observance_catalog, DEFAULT_OBSERVANCES)

    # 3. Create holidays table (no dates invented; seeded only via user-provided files)
    op.create_table(
        "holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("holiday_type", sa.String(32), server_default="national", nullable=False),
        sa.Column("study_blackout", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "observance_key",
            sa.String(64),
            sa.ForeignKey("observance_catalog.key", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_holidays_dates_status",
        "holidays",
        ["start_date", "end_date", "status"],
    )

    # 4. Create admin_policies table
    admin_policies = op.create_table(
        "admin_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("class_band", sa.String(16), nullable=False),
        sa.Column("group", sa.String(32), server_default="general", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(20), server_default="published", nullable=False),
        sa.Column("min_daily_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_daily_minutes", sa.Integer(), server_default="600", nullable=False),
        sa.Column("recommended_daily_minutes", sa.Integer(), server_default="90", nullable=False),
        sa.Column("max_block_minutes", sa.Integer(), server_default="90", nullable=False),
        sa.Column("latest_end_time", sa.String(8), server_default="22:00", nullable=False),
        sa.Column(
            "weekly_off_days",
            postgresql.JSONB(),
            server_default='["fri", "sat"]',
            nullable=False,
        ),
        sa.Column("planner_parameters", postgresql.JSONB(), nullable=False),
        sa.Column(
            "updated_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "class_band", "group", "version", name="uq_admin_policies_band_group_version"
        ),
    )
    op.create_index(
        "ix_admin_policies_band_status",
        "admin_policies",
        ["class_band", "group", "status"],
    )

    # Seed baseline published policies for class bands 6-8, 9-10, 11-12
    import uuid

    baseline_policies = [
        {
            "id": uuid.uuid4(),
            "class_band": "6-8",
            "group": "general",
            "version": 1,
            "status": "published",
            "min_daily_minutes": 0,
            "max_daily_minutes": 600,
            "recommended_daily_minutes": 90,
            "max_block_minutes": 90,
            "latest_end_time": "21:30",
            "weekly_off_days": ["fri", "sat"],
            "planner_parameters": DEFAULT_PLANNER_PARAMS,
        },
        {
            "id": uuid.uuid4(),
            "class_band": "9-10",
            "group": "general",
            "version": 1,
            "status": "published",
            "min_daily_minutes": 0,
            "max_daily_minutes": 600,
            "recommended_daily_minutes": 150,
            "max_block_minutes": 90,
            "latest_end_time": "22:30",
            "weekly_off_days": ["fri", "sat"],
            "planner_parameters": DEFAULT_PLANNER_PARAMS,
        },
        {
            "id": uuid.uuid4(),
            "class_band": "9-10",
            "group": "science",
            "version": 1,
            "status": "published",
            "min_daily_minutes": 0,
            "max_daily_minutes": 600,
            "recommended_daily_minutes": 180,
            "max_block_minutes": 90,
            "latest_end_time": "22:30",
            "weekly_off_days": ["fri", "sat"],
            "planner_parameters": DEFAULT_PLANNER_PARAMS,
        },
        {
            "id": uuid.uuid4(),
            "class_band": "11-12",
            "group": "general",
            "version": 1,
            "status": "published",
            "min_daily_minutes": 0,
            "max_daily_minutes": 600,
            "recommended_daily_minutes": 210,
            "max_block_minutes": 90,
            "latest_end_time": "23:00",
            "weekly_off_days": ["fri", "sat"],
            "planner_parameters": DEFAULT_PLANNER_PARAMS,
        },
        {
            "id": uuid.uuid4(),
            "class_band": "11-12",
            "group": "science",
            "version": 1,
            "status": "published",
            "min_daily_minutes": 0,
            "max_daily_minutes": 600,
            "recommended_daily_minutes": 240,
            "max_block_minutes": 90,
            "latest_end_time": "23:00",
            "weekly_off_days": ["fri", "sat"],
            "planner_parameters": DEFAULT_PLANNER_PARAMS,
        },
    ]
    op.bulk_insert(admin_policies, baseline_policies)

    # 5. Create student_study_settings table (parent-controlled per student)
    op.create_table(
        "student_study_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("school_day_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("holiday_minutes", sa.Integer(), server_default="120", nullable=False),
        sa.Column("study_window_start", sa.String(8), server_default="17:00", nullable=False),
        sa.Column("study_window_end", sa.String(8), server_default="21:30", nullable=False),
        sa.Column(
            "recurring_unavailable_blocks",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "blocked_observance_keys",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "custom_blackout_dates",
            postgresql.JSONB(),
            server_default="[]",
            nullable=False,
        ),
        sa.Column(
            "subject_priorities",
            postgresql.JSONB(),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_student_study_settings_student_id",
        "student_study_settings",
        ["student_id"],
    )
    op.alter_column("student_change_requests", "setup_id", nullable=True)


def downgrade() -> None:
    op.alter_column("student_change_requests", "setup_id", nullable=False)
    op.drop_table("student_study_settings")
    op.drop_table("admin_policies")
    op.drop_table("holidays")
    op.drop_table("observance_catalog")
    op.drop_column("student_profiles", "optional_subject_ids")
    op.drop_column("student_profiles", "group")
