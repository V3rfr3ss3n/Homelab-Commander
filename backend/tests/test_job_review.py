"""Durable, per-failure acknowledgements never rewrite job outcomes."""

from pathlib import Path
from uuid import uuid4

import pytest

from backend.homelab_backend.jobs import JobRepository
from backend.homelab_backend.models import JobAction, JobState
from backend.tests.test_backend_api import (
    AUTH,
    FakeExecutor,
    _client,
    _create_host,
    _csrf,
    _terminal_job,
)
from backend.tests.test_dashboard import _services


async def test_review_is_durable_and_new_failures_still_need_attention(tmp_path: Path):
    db, _, _, _, _, host, _ = await _services(tmp_path)
    jobs = JobRepository(db)
    failure = await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
    with pytest.raises(ValueError, match="Only failed"):
        await jobs.async_review(failure.id)
    await jobs.async_finish(
        failure.id, state=JobState.FAILED, output="Synthetic failure", truncated=False
    )
    assert (await jobs.async_unresolved_failure()).id == failure.id
    reviewed = await jobs.async_review(failure.id)
    assert reviewed.reviewed_at is not None
    assert (await jobs.async_review(failure.id)).reviewed_at == reviewed.reviewed_at
    assert await JobRepository(db).async_unresolved_failure() is None
    assert (await jobs.async_log(failure.id)).output == "Synthetic failure"
    assert (await jobs.async_get(failure.id)).state == JobState.FAILED
    later = await jobs.async_create(JobAction.TEST_CONNECTION, host.id)
    await jobs.async_finish(later.id, state=JobState.FAILED, output="", truncated=False)
    assert (await jobs.async_unresolved_failure()).id == later.id
    with pytest.raises(KeyError):
        await jobs.async_review(uuid4())


def test_review_requires_auth_and_ui_csrf(tmp_path: Path):
    executor = FakeExecutor()
    executor.fail = True
    with _client(tmp_path, executor, ingress_mode=True) as client:
        host = _create_host(client)
        job = client.post(
            f"/api/v1/hosts/{host['id']}/actions/test-connection", headers=AUTH
        ).json()
        # Wait only for the synthetic executor to finish.
        _terminal_job(client, job["id"])
        endpoint = f"/ui-api/jobs/{job['id']}/review"
        assert client.post(endpoint).status_code == 403
        assert (
            client.post(endpoint, headers={"X-CSRF-Token": _csrf(client)}).status_code
            == 200
        )
        assert client.post(f"/api/v1/jobs/{job['id']}/review").status_code == 401
        result = client.post(f"/api/v1/jobs/{job['id']}/review", headers=AUTH)
        assert result.status_code == 200
        assert result.json()["state"] == "failed"
        assert result.json()["reviewed_at"] is not None
        assert client.get("/ui-api/dashboard").json()["attention_job"] is None
        assert client.get("/ui-api/dashboard").json()["last_failed_job"] is not None
        assert (
            client.post(
                f"/ui-api/jobs/{uuid4()}/review",
                headers={"X-CSRF-Token": _csrf(client)},
            ).status_code
            == 404
        )


def test_review_rejects_success_and_unauthenticated_ui(tmp_path: Path):
    with _client(tmp_path, FakeExecutor()) as client:
        host = _create_host(client)
        response = client.post(
            f"/api/v1/hosts/{host['id']}/actions/test-connection", headers=AUTH
        )
        job = _terminal_job(client, response.json()["id"])
        assert (
            client.post(f"/api/v1/jobs/{job['id']}/review", headers=AUTH).status_code
            == 409
        )
        assert (
            client.post(
                f"/ui-api/jobs/{job['id']}/review",
                headers={"X-CSRF-Token": _csrf(client)},
            ).status_code
            == 401
        )
