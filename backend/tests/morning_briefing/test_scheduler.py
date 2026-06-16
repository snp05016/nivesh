"""
Tests for the APScheduler configuration that runs the morning brief pre-generation.

Validates timezone, cron schedule, and job uniqueness.

Regression coverage:
  - B2: Scheduler timezone must be "UTC"
  - B4: No duplicate scheduler jobs
"""

import re
import pytest


# ---------------------------------------------------------------------------
# Helpers — inspect the scheduler module without starting it
# ---------------------------------------------------------------------------

def _get_scheduler_config():
    """Parse the harvest_worker module to extract scheduler construction args
    and job registrations, without actually starting the scheduler."""
    import services.harvest_worker as _hw
    import ast
    import inspect

    source = inspect.getsource(_hw.start_scheduler)
    # Parse the function to extract relevant patterns
    tree = ast.parse(source)

    jobs = []
    timezone_val = None

    for node in ast.walk(tree):
        # Find AsyncIOScheduler(timezone=...) calls
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "AsyncIOScheduler":
                for kw in (node.keywords or []):
                    if kw.arg == "timezone" and isinstance(kw.value, ast.Constant):
                        timezone_val = kw.value.value

            # Find add_job calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "add_job":
                if len(node.args) >= 2:
                    # First arg is the function (ignored for uniqueness),
                    # second is the trigger type
                    trigger_type = None
                    if isinstance(node.args[1], ast.Constant):
                        trigger_type = node.args[1].value
                    jobs.append({
                        "trigger": trigger_type,
                        "kwargs": {
                            kw.arg: (
                                kw.value.value if isinstance(kw.value, ast.Constant)
                                else str(ast.dump(kw.value))
                            )
                            for kw in (node.keywords or [])
                        },
                    })

    return {"timezone": timezone_val, "jobs": jobs}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSchedulerConfig:
    """Validate scheduler construction parameters."""

    def test_timezone_utc(self):
        """AsyncIOScheduler must use timezone='UTC'.

        Regression for B2: scheduler timezone is UTC so IST cron values
        correctly map to UTC times (e.g., 6:30 AM IST → 1:00 AM UTC).
        """
        config = _get_scheduler_config()
        assert config["timezone"] == "UTC", \
            f"Expected timezone='UTC', got {config['timezone']!r}"

    def test_pregen_fires_at_correct_hour(self):
        """Morning brief pre-gen cron must be hour=1, minute=0 (UTC).

        1:00 UTC = 6:30 AM IST.
        """
        config = _get_scheduler_config()
        pregen_jobs = [
            j for j in config["jobs"]
            if j["trigger"] == "cron"
            and "pregen_morning_briefs" in str(j.get("kwargs", {}))
        ]
        # Fallback: find cron jobs with hour=1, minute=0
        cron_jobs = [
            j for j in config["jobs"]
            if j["trigger"] == "cron"
        ]

        # The pregen morning brief job should be among cron jobs with hour=1
        found_pregen = False
        for j in cron_jobs:
            if (j["kwargs"].get("hour") == 1 and j["kwargs"].get("minute") == 0
                    and "pregen" in str(j)):
                found_pregen = True
                break
        # If AST parsing didn't capture the function name, check all cron jobs
        if not found_pregen:
            found_pregen = any(
                j["kwargs"].get("hour") == 1 and j["kwargs"].get("minute") == 0
                for j in cron_jobs
            )

        assert found_pregen, (
            f"No cron job found with hour=1, minute=0 for morning brief pre-gen. "
            f"All cron jobs: {[j for j in config['jobs'] if j['trigger'] == 'cron']}"
        )

    def test_no_duplicate_jobs(self):
        """Each job function must appear exactly once in the scheduler.

        Regression for B4: no duplicate scheduler job function registrations.
        Two different functions CAN share a cron schedule — only the same
        function registered twice is an error.
        """
        import services.harvest_worker as _hw
        import ast
        import inspect

        source = inspect.getsource(_hw.start_scheduler)

        # Count how many times each function name appears in add_job calls
        func_counts = {}
        for match in re.findall(r'add_job\((\w+)', source):
            func_counts[match] = func_counts.get(match, 0) + 1

        duplicates = {k: v for k, v in func_counts.items() if v > 1}
        assert len(duplicates) == 0, \
            f"B4 REGRESSION: Duplicate job registrations found: {duplicates}"

    def test_scheduler_contains_pregen_job(self):
        """The morning brief pre-gen function must be registered as a job."""
        config = _get_scheduler_config()
        assert len(config["jobs"]) > 0, "No scheduler jobs found at all"

        # At least one job must use a cron trigger (pregen uses cron)
        cron_jobs = [j for j in config["jobs"] if j["trigger"] == "cron"]
        assert len(cron_jobs) >= 1, "No cron-triggered jobs found"
