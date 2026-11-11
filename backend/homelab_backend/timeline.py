"""Bounded timestamp-based timeline over complete persisted job history."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from .database import Database
from .jobs import JOB_TIME, JobRepository, job_filter
from .models import Job, JobAction, JobState


class TimelinePoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: datetime
    end: datetime
    timestamp: datetime
    counts: dict[JobState, int]
    total: int
    jobs: tuple[Job, ...]


class JobTimeline(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: datetime
    end: datetime
    total: int
    points: tuple[TimelinePoint, ...]


def validate_period(start: datetime, end: datetime) -> None:
    """Limit scan ranges and reject ambiguous or inverted time windows."""
    if start >= end or (end - start).total_seconds() > 366 * 86400:
        raise ValueError("Choose a period longer than zero and at most 366 days")


class TimelineService:
    def __init__(self, database: Database, jobs: JobRepository) -> None:
        self._database = database
        self._jobs = jobs

    async def async_read(
        self,
        start: datetime,
        end: datetime,
        *,
        bins: int = 60,
        host_id: UUID | None = None,
        state: JobState | None = None,
        action: JobAction | None = None,
    ) -> JobTimeline:
        """Count every matching job; return at most six previews per time bucket."""
        validate_period(start, end)
        clause, parameters = job_filter(host_id, state, False, start, end, action)
        width = (end - start).total_seconds() / bins
        rows = await self._database.async_fetch_all(
            f"SELECT CAST((unixepoch({JOB_TIME}, 'subsec') - ?) / ? AS INTEGER) "
            f"AS bucket, jobs.state, COUNT(*) AS count, "
            f"AVG(unixepoch({JOB_TIME}, 'subsec')) AS timestamp "
            f"FROM jobs{clause} GROUP BY bucket,jobs.state ORDER BY bucket",
            (start.timestamp(), width, *parameters),
        )
        grouped: dict[int, dict[JobState, int]] = {}
        timestamps: dict[int, float] = {}
        for row in rows:
            bucket = row["bucket"]
            grouped.setdefault(bucket, {})[JobState(row["state"])] = row["count"]
            timestamps[bucket] = timestamps.get(bucket, 0.0) + (
                row["timestamp"] * row["count"]
            )
        points = []
        for bucket, counts in grouped.items():
            first = datetime.fromtimestamp(start.timestamp() + bucket * width, UTC)
            last = datetime.fromtimestamp(start.timestamp() + (bucket + 1) * width, UTC)
            total = sum(counts.values())
            points.append(
                TimelinePoint(
                    start=first,
                    end=last,
                    timestamp=datetime.fromtimestamp(timestamps[bucket] / total, UTC),
                    counts=counts,
                    total=total,
                    jobs=await self._jobs.async_list(
                        start=first,
                        end=last,
                        host_id=host_id,
                        state=state,
                        action=action,
                        limit=6,
                    ),
                )
            )
        return JobTimeline(
            start=start,
            end=end,
            total=sum(p.total for p in points),
            points=tuple(points),
        )
