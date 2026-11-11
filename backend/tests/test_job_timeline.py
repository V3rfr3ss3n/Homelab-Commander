"""Timeline and table use complete persisted history with matching time filters."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from backend.homelab_backend.database import Database
from backend.homelab_backend.hosts import HostRepository
from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import HostCreate
from backend.homelab_backend.timeline import TimelineService
from backend.tests.test_backend_api import AUTH, FakeExecutor, _client


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
