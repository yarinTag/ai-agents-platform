"""Scheduler public contracts; worker implementation loads only when requested."""
from .expressions import calculate_next_run, get_upcoming_runs, validate_cron_expression

__all__ = ["calculate_next_run", "get_upcoming_runs", "validate_cron_expression", "CronSchedulerEngine"]


def __getattr__(name):
    if name != "CronSchedulerEngine":
        raise AttributeError(name)
    from .engine import CronSchedulerEngine
    return CronSchedulerEngine
