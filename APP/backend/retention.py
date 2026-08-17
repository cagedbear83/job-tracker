"""
retention.py — NEW module, written during the admin_portal integration.

admin_compliance.py (ported from admin_portal) imports
`deletion_date_for` and `today_chicago` from a `retention.py` module that
was referenced but never included in the admin_portal file set, and does
not exist anywhere else in this codebase. Rather than drop the retention
monitor from the compliance panel entirely, this file provides the two
small, read-only helpers it needs.

IMPORTANT — scope of what this actually does:
  This codebase's ONLY real automated deletion job today is the account
  soft-delete purge in core.py (`_purge_due_accounts`, keyed off
  `users.purge_after`, ACCOUNT_PURGE_GRACE_DAYS from core.py, default 30
  days after a user requests account deletion).

  There is NO scheduled job anywhere in this codebase that hard-deletes
  individual `benefit_weeks` records 53 weeks after `week_end`. The
  admin_portal README describes that as a separate "retention.py" system
  ("the actual deletion + notices are the scheduled jobs in retention.py")
  that was apparently never shipped to this repo.

  So: `RETENTION_WEEKS` below documents Illinois's commonly-cited 53-week
  UI-record-retention guidance, and `deletion_date_for` / `today_chicago`
  let the compliance panel show which weeks WOULD be approaching that
  mark IF such a job existed — this is a read-only projection, not a
  promise that anything will actually be deleted on that date. If/when a
  real 53-week purge job is built, it should import these same helpers so
  the dashboard and the job never drift apart.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

import pytz

RETENTION_WEEKS = 53
_CHICAGO = pytz.timezone("America/Chicago")


def today_chicago() -> date:
    return datetime.now(_CHICAGO).date()


def deletion_date_for(week_end: Optional[str]) -> Optional[date]:
    """
    week_end is stored as a 'YYYY-MM-DD' string (see core.py's
    BenefitWeekIn/BenefitWeek models). Returns the date RETENTION_WEEKS
    weeks after week_end, or None if week_end is missing/unparseable.
    """
    if not week_end:
        return None
    try:
        we = datetime.strptime(week_end, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return we + timedelta(weeks=RETENTION_WEEKS)
