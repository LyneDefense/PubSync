from datetime import datetime

from app.models import PublishingSettings
from app.services import task_service


def test_daily_schedule_matches_only_at_configured_minute():
    publishing = PublishingSettings(publish_frequency="daily", publish_time_hour=8, publish_time_minute=0)
    assert task_service.should_run_schedule(publishing, datetime(2026, 6, 11, 8, 0)) is True
    assert task_service.should_run_schedule(publishing, datetime(2026, 6, 11, 8, 1)) is False
    assert task_service.should_run_schedule(publishing, datetime(2026, 6, 11, 9, 0)) is False


def test_weekly_schedule_matches_only_on_configured_weekday():
    # 2026-06-11 is a Thursday (isoweekday 4).
    publishing = PublishingSettings(
        publish_frequency="weekly", publish_weekday=4, publish_time_hour=8, publish_time_minute=0
    )
    assert task_service.should_run_schedule(publishing, datetime(2026, 6, 11, 8, 0)) is True
    assert task_service.should_run_schedule(publishing, datetime(2026, 6, 12, 8, 0)) is False


def test_monthly_schedule_clamps_to_last_day_of_month():
    publishing = PublishingSettings(
        publish_frequency="monthly", publish_month_day=31, publish_time_hour=8, publish_time_minute=0
    )
    # June has 30 days, so day 31 clamps to the 30th.
    assert task_service.should_run_schedule(publishing, datetime(2026, 6, 30, 8, 0)) is True
    assert task_service.should_run_schedule(publishing, datetime(2026, 6, 29, 8, 0)) is False


def test_marker_value_is_stable_within_a_day_and_distinct_across_days():
    publishing = PublishingSettings(publish_frequency="daily", publish_time_hour=8, publish_time_minute=0)
    monday = task_service.schedule_marker_value(publishing, datetime(2026, 6, 11, 8, 0))
    monday_again = task_service.schedule_marker_value(publishing, datetime(2026, 6, 11, 8, 0))
    tuesday = task_service.schedule_marker_value(publishing, datetime(2026, 6, 12, 8, 0))
    assert monday == monday_again
    assert monday != tuesday
