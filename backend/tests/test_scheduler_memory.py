"""Tests for memory scheduler jobs registration."""

from unittest.mock import MagicMock, patch

from aegis.scheduler import create_scheduler


class TestMemoryJobsRegistered:
    def test_memory_jobs_registered(self):
        with patch("aegis.scheduler.BackgroundScheduler") as mock_scheduler_cls, \
             patch("aegis.scheduler._load_schedule_config") as mock_load_schedule, \
             patch("aegis.scheduler._load_memory_config") as mock_load_memory:
            mock_scheduler = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler
            mock_load_schedule.return_value = {
                "schedules": {
                    "weight_adapter": {
                        "observation_check": {"cron": "0 1 * * *", "timezone": "US/Eastern"},
                        "weight_update": {"cron": "0 4 * * 0", "timezone": "US/Eastern"},
                    },
                    "memory": {
                        "compression": {"cron": "0 2 * * *", "timezone": "US/Eastern"},
                        "cleanup": {"cron": "0 3 * * *", "timezone": "US/Eastern"},
                    },
                }
            }
            mock_load_memory.return_value = {}

            scheduler = create_scheduler()

            # Check all 4 jobs registered
            job_ids = [call.kwargs.get("id") for call in mock_scheduler.add_job.call_args_list]
            assert "observation_check" in job_ids
            assert "weight_update" in job_ids
            assert "memory_compression" in job_ids
            assert "short_term_cleanup" in job_ids
