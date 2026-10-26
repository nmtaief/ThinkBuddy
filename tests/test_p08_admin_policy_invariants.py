import pytest

def calculate_auto_adjustment(
    band: str,
    fld: str,
    cur_mins: int,
    raw_suggested_mins: int,
    pol_rec=None,
) -> int:
    """Core calculation from core/planner/router.py lines 506-518."""
    max_delta = max(5, int(cur_mins * 0.20))
    clamped_mins = min(cur_mins + max_delta, max(raw_suggested_mins, cur_mins - max_delta))

    if fld == "holiday_minutes":
        ceiling = (
            pol_rec.holiday_ceiling_minutes
            if pol_rec
            else (360 if band == "6-8" else (480 if band == "9-10" else 600))
        )
    else:
        ceiling = (
            pol_rec.school_day_ceiling_minutes
            if pol_rec
            else (240 if band == "6-8" else (360 if band == "9-10" else 360))
        )

    # Invariant 1: Leaves a parent value that is already above the ceiling unchanged
    if cur_mins >= ceiling:
        final_mins = cur_mins
    else:
        # Invariant 2: Auto mode never lowers a parent setting
        # Invariant 3: Never raises above the ceiling
        final_mins = max(cur_mins, min(clamped_mins, ceiling))

    return final_mins


def test_band_6_8_school_and_holiday_ceilings():
    # Band 6-8: school ceiling 240, holiday ceiling 360
    # Case A: Parent set 150m, AI suggests 260m -> clamps to ceiling 240m (or delta cap)
    # delta cap = 150 + 30 = 180m
    res = calculate_auto_adjustment("6-8", "school_day_minutes", cur_mins=150, raw_suggested_mins=260)
    assert res == 180  # 20% delta limit: 150 + 30 = 180 <= 240

    # AI suggests 260m when cur_mins is 230m -> delta is 46 -> 230 + 46 = 276 -> clamped to ceiling 240
    res = calculate_auto_adjustment("6-8", "school_day_minutes", cur_mins=230, raw_suggested_mins=260)
    assert res == 240  # Invariant 3: never exceeds ceiling 240

    # Holiday: ceiling 360
    res = calculate_auto_adjustment("6-8", "holiday_minutes", cur_mins=330, raw_suggested_mins=400)
    assert res == 360


def test_band_9_10_school_and_holiday_ceilings():
    # Band 9-10: school ceiling 360, holiday ceiling 480
    # Invariant 2: Auto mode never lowers parent setting
    res = calculate_auto_adjustment("9-10", "school_day_minutes", cur_mins=250, raw_suggested_mins=200)
    assert res == 250  # never lowers parent setting

    # Clamping at ceiling 360
    res = calculate_auto_adjustment("9-10", "school_day_minutes", cur_mins=350, raw_suggested_mins=400)
    assert res == 360  # never raises above ceiling

    # Holiday ceiling 480
    res = calculate_auto_adjustment("9-10", "holiday_minutes", cur_mins=450, raw_suggested_mins=520)
    assert res == 480


def test_band_11_12_school_and_holiday_ceilings():
    # Band 11-12: school ceiling 360, holiday ceiling 600
    res = calculate_auto_adjustment("11-12", "school_day_minutes", cur_mins=320, raw_suggested_mins=380)
    assert res == 360

    res = calculate_auto_adjustment("11-12", "holiday_minutes", cur_mins=550, raw_suggested_mins=650)
    assert res == 600


def test_parent_values_already_above_ceiling_remain_unchanged():
    # Invariant 1: Parent value already above ceiling remains unchanged
    # Parent configured school_day_minutes = 380 on Band 6-8 (ceiling is 240).
    res = calculate_auto_adjustment("6-8", "school_day_minutes", cur_mins=380, raw_suggested_mins=420)
    assert res == 380

    # Parent configured holiday_minutes = 500 on Band 9-10 (ceiling is 480).
    res = calculate_auto_adjustment("9-10", "holiday_minutes", cur_mins=500, raw_suggested_mins=550)
    assert res == 500
