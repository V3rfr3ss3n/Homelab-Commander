"""Complete dashboard aggregates and bounded job queries over stored history."""

from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, ConfigDict

from .database import Database
from .jobs import JobRepository
from .models import Job, JobState


class HistoryDay(BaseModel):
    model_config = ConfigDict(frozen=True)
    day: date
    counts: dict[JobState, int]


class DashboardSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    backend_online: bool = True
    hosts: int
    running_jobs: int
    queued_jobs: int
    last_job: Job | None
    last_failed_job: Job | None
    recent_jobs: tuple[Job, ...]
    recent_completions: tuple[Job, ...]
    history: tuple[HistoryDay, ...]


class JobPage(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: tuple[Job, ...]
    total: int
    offset: int
    limit: int


class DashboardService:
    """Aggregate the entire database, never a capped frontend job snapshot."""

    def __init__(self, database: Database, jobs: JobRepository) -> None:
        self._database = database
        self._jobs = jobs

    async def async_summary(self) -> DashboardSummary:
        today = datetime.now(UTC).date()
        first = today - timedelta(days=6)
        rows = await self._database.async_fetch_all(
            "SELECT date(COALESCE(finished_at,created_at)) AS day, state, "
            "COUNT(*) AS count "
            "FROM jobs WHERE date(COALESCE(finished_at,created_at)) BETWEEN ? "
            "AND ? GROUP BY day,state",
            (first.isoformat(), today.isoformat()),
        )
        days = {
            first + timedelta(days=offset): dict.fromkeys(JobState, 0)
            for offset in range(7)
        }
        for row in rows:
            days[date.fromisoformat(row["day"])][JobState(row["state"])] = row["count"]
        counts = await self._database.async_fetch_all(
            "SELECT state, COUNT(*) AS count FROM jobs GROUP BY state"
        )
        totals = {row["state"]: row["count"] for row in counts}
        hosts = await self._database.async_fetch_one(
            "SELECT COUNT(*) AS count FROM hosts"
        )
        recent = await self._jobs.async_list(limit=5)
        failed = await self._jobs.async_list(limit=1, state=JobState.FAILED)
        return DashboardSummary(
            hosts=hosts["count"] if hosts is not None else 0,
            running_jobs=totals.get("running", 0),
            queued_jobs=totals.get("queued", 0),
            last_job=next(iter(recent), None),
            last_failed_job=next(iter(failed), None),
            recent_jobs=recent,
            recent_completions=await self._jobs.async_list(limit=5, completed=True),
            history=tuple(
                HistoryDay(day=day, counts=counts) for day, counts in days.items()
            ),
        )
