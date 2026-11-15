"""Timeline and table use complete persisted history with matching time filters."""

import sqlite3
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import HostCreate
from backend.homelab_backend.timeline import TimelineService
from backend.tests.test_backend_api import AUTH, FakeExecutor, _client


async def test_history_on_sqlite_without_subsecond_modifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Older container SQLite returns NULL for the unsupported subsec modifier."""
    connect = Database._connect

    def legacy_connect(database: Database) -> sqlite3.Connection:
        connection = connect(database)
        connection.create_function("unixepoch", 2, lambda _value, _modifier: None)
        return connection

    monkeypatch.setattr(Database, "_connect", legacy_connect)
    database = Database(tmp_path / "homelab_updates.db")
    await database.async_migrate()
    host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    start = datetime(2026, 11, 15, 4, tzinfo=UTC)
    for state in ("success", "failed"):
        await database.async_execute(
            "INSERT INTO jobs(id,action,host_id,state,created_at,finished_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                str(uuid4()),
                "check_updates",
                str(host.id),
                state,
                start.isoformat(),
                (start + timedelta(seconds=1)).isoformat(),
            ),
        )
    end = start + timedelta(hours=1)
    with _client(tmp_path, FakeExecutor()) as client:
        params = {"start": start.isoformat(), "end": end.isoformat()}
        page = client.get("/api/v1/jobs/page", params=params, headers=AUTH)
        timeline = client.get("/api/v1/jobs/timeline", params=params, headers=AUTH)
        assert page.status_code == timeline.status_code == 200
        assert page.json()["total"] == timeline.json()["total"] == 2
        assert len(page.json()["items"]) == 2


async def test_history_boundaries_offsets_and_live_job_timestamps(
    tmp_path: Path,
) -> None:
    """Equivalent offsets and microseconds use the same half-open time window."""
    database = Database(tmp_path / "history.db")
    await database.async_migrate()
    host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 01", address="node-01.example.invalid", username="automation"
        )
    )
    start = datetime(2026, 11, 15, 4, 0, 0, 123456, tzinfo=UTC)
    end = start + timedelta(seconds=60)
    included = []
    for state, instant, include in [
        ("success", start - timedelta(microseconds=1), False),
        ("failed", start, True),
        ("running", start + timedelta(seconds=10), True),
        ("queued", end - timedelta(microseconds=1), True),
        ("success", end, False),
    ]:
        job_id = str(uuid4())
        if include:
            included.append(job_id)
        # ISO offsets must not change instant-based filtering or sorting.
        time = instant.astimezone(timezone(timedelta(hours=2))).isoformat()
        await database.async_execute(
            "INSERT INTO jobs(id,action,host_id,state,created_at,"
            "started_at,finished_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                job_id,
                "check_updates",
                str(host.id),
                state,
                time,
                time if state != "queued" else None,
                time if state in {"success", "failed"} else None,
            ),
        )
    jobs = JobRepository(database)
    assert await jobs.async_count(start=start, end=end) == 3
    listed = await jobs.async_list(start=start, end=end, sort="oldest")
    assert [str(job.id) for job in listed] == included
    page = await jobs.async_list(start=start, end=end, sort="oldest", offset=1, limit=1)
    assert str(page[0].id) == included[1]
    timeline = await TimelineService(database, jobs).async_read(start, end, bins=12)
    assert timeline.total == 3
    assert {str(job.id) for point in timeline.points for job in point.jobs} == set(
        included
    )
    assert sum(point.counts.get("failed", 0) for point in timeline.points) == 1
    assert (await jobs.async_list(start=start, end=end, state="failed"))[
        0
    ].state == "failed"


async def test_timestamp_buckets_match_bounded_table_and_full_count(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "homelab_updates.db")
    await database.async_migrate()
    host = await HostRepository(database).async_create(
        HostCreate(
            name="Node 01",
            address="node-01.example.invalid",
            username="automation",
        )
    )
    start = datetime(2026, 10, 1, tzinfo=UTC)
    first = start + timedelta(hours=1, minutes=12)
    second = start + timedelta(hours=23, minutes=11)
    for index in range(150):
        created = first if index < 120 else second
        finished = created + timedelta(minutes=1) if index % 2 else created
        await database.async_execute(
            "INSERT INTO jobs(id,action,host_id,state,created_at,finished_at) "
            "VALUES(?,?,?,?,?,?)",
            (
                str(uuid4()),
                "check_updates",
                str(host.id),
                "success" if index % 2 else "failed",
                created.isoformat(),
                finished.isoformat() if finished else None,
            ),
        )
    end = start + timedelta(days=1)
    timeline = await TimelineService(database, JobRepository(database)).async_read(
        start,
        end,
        bins=24,
    )
    assert timeline.total == 150
    assert len(timeline.points) == 2
    assert sorted(point.total for point in timeline.points) == [30, 120]
    assert all(len(point.jobs) == 6 for point in timeline.points)
    assert first <= timeline.points[0].timestamp <= first + timedelta(minutes=1)
    assert second <= timeline.points[1].timestamp <= second + timedelta(minutes=1)
    assert sum(point.total for point in timeline.points) == 150
    assert [point.review_required for point in timeline.points] == [0, 15]
    assert all(
        job.needs_review == (job.state == "failed") for job in timeline.points[1].jobs
    )
    await database.async_execute("UPDATE jobs SET reviewed_at=?", (end.isoformat(),))
    reviewed = await TimelineService(database, JobRepository(database)).async_read(
        start, end, bins=24
    )
    assert all(point.review_required == 0 for point in reviewed.points)
    assert all(not job.needs_review for point in reviewed.points for job in point.jobs)
    await database.async_execute("UPDATE jobs SET reviewed_at=NULL")
    await database.async_execute(
        "INSERT INTO jobs(id,action,host_id,state,created_at,finished_at) "
        "VALUES(?,?,?,?,?,?)",
        (
            str(uuid4()),
            "check_updates",
            str(host.id),
            "success",
            end.isoformat(),
            end.isoformat(),
        ),
    )
    resolved = await TimelineService(database, JobRepository(database)).async_read(
        start, end, bins=24
    )
    assert all(point.review_required == 0 for point in resolved.points)
    assert all(not job.needs_review for point in resolved.points for job in point.jobs)
    for point in timeline.points:
        assert (
            await JobRepository(database).async_count(
                start=point.start,
                end=point.end,
            )
            == point.total
        )
    with _client(tmp_path, FakeExecutor()) as client:
        params = {"start": start.isoformat(), "end": end.isoformat(), "bins": 24}
        response = client.get("/api/v1/jobs/timeline", params=params, headers=AUTH)
        assert response.status_code == 200
        assert response.json()["total"] == 150
        page = client.get(
            "/api/v1/jobs/page", params={**params, "limit": 25}, headers=AUTH
        )
        assert page.status_code == 200
        assert page.json()["total"] == 150
        assert len(page.json()["items"]) == 25
        filtered = client.get(
            "/api/v1/jobs/page", params={**params, "state": "success"}, headers=AUTH
        )
        assert filtered.json()["total"] == 75
        assert client.get("/api/v1/jobs/timeline", params=params).status_code in (
            401,
            403,
        )
        assert (
            client.get(
                "/api/v1/jobs/timeline", params={**params, "bins": 121}, headers=AUTH
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/jobs/page", params={"start": start.isoformat()}, headers=AUTH
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/jobs/timeline",
                params={"start": end.isoformat(), "end": start.isoformat()},
                headers=AUTH,
            ).status_code
            == 422
        )
