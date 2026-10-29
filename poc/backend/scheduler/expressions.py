"""Pure schedule-expression helpers independent of the background worker."""
from datetime import datetime
from typing import Optional, List
from croniter import croniter

def calculate_next_run(cron_expr: str, base_time: Optional[datetime] = None) -> str:
    """Calculate the next execution timestamp as an ISO-8601 string."""
    base = base_time or datetime.now()
    iter_cron = croniter(cron_expr, base)
    next_dt = iter_cron.get_next(datetime)
    return next_dt.isoformat()


def get_upcoming_runs(cron_expr: str, count: int = 5, base_time: Optional[datetime] = None) -> List[str]:
    """Calculate the upcoming N execution timestamps as ISO-8601 strings."""
    base = base_time or datetime.now()
    iter_cron = croniter(cron_expr, base)
    upcoming = []
    for _ in range(count):
        upcoming.append(iter_cron.get_next(datetime).isoformat())
    return upcoming


def validate_cron_expression(cron_expr: str) -> bool:
    """Validate whether a cron expression is valid."""
    return croniter.is_valid(cron_expr)

