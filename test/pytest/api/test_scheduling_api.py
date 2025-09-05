from unittest.mock import AsyncMock, MagicMock, patch

import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from satop_plugins.flight_planning.scheduling import Scheduling

import pytest


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.auth = MagicMock()
    app.gs = MagicMock()
    app.syslog = MagicMock()
    return app


@pytest.fixture
def scheduling_plugin(tmp_path, mock_app):
    plugin_data_dir = tmp_path / "data"
    plugin_data_dir.mkdir()
    (tmp_path / "config.yaml").write_text(
        yaml.dump({"name": "Scheduling_Test", "capabilities": ["http.add_routes"]})
    )
    plugin = Scheduling(
        plugin_dir=str(tmp_path), app=mock_app, data_dir=str(plugin_data_dir)
    )
    plugin.call_function = AsyncMock(
        return_value=("compiled_plan_bytes", "compiled_artifact_id")
    )
    plugin.startup()
    yield plugin
    plugin.shutdown()


@pytest.fixture
def client(scheduling_plugin):
    test_app = FastAPI()

    async def fake_require_login(req: Request):
        req.state.userid = "test-user"
        return True

    test_app.dependency_overrides[scheduling_plugin.app.auth.require_login] = (
        fake_require_login
    )
    test_app.include_router(scheduling_plugin.api_router)
    return TestClient(test_app)


def test_save_new_flightplan(client: TestClient, scheduling_plugin: Scheduling):
    """Test the POST /save endpoint with valid data."""
    scheduling_plugin.app.syslog.create_artifact.return_value = MagicMock(
        sha1="mock_artifact_sha1"
    )
    flight_plan_data = {
        "flight_plan": {"name": "test_plan", "body": []},
        "datetime": "2025-01-01T12:00:00+00:00",
        "gs_id": "86c8a92b-571a-46cb-b306-e9be71959279",
        "sat_name": "DISCO-2",
    }
    response = client.post("/save", json=flight_plan_data)
    assert response.status_code == 201
    json_response = response.json()
    assert json_response["message"] == "Flight plan scheduled for approval"
    assert json_response["fp_id"] == "mock_artifact_sha1"


def test_save_flightplan_invalid_datetime(client: TestClient):
    """Test POST /save with a bad datetime format."""
    flight_plan_data = {
        "flight_plan": {"name": "test_plan", "body": []},
        "datetime": "not-a-real-date",
        "gs_id": "86c8a92b-571a-46cb-b306-e9be71959279",
        "sat_name": "DISCO-2",
    }
    response = client.post("/save", json=flight_plan_data)
    assert response.status_code == 201
    assert "Rejected: Invalid datetime format" in response.text


@pytest.mark.asyncio
async def test_approve_flight_plan(client: TestClient, scheduling_plugin: Scheduling):
    """Test the POST /approve/{uuid} endpoint."""
    fp_uuid = "mock_artifact_sha1_for_approval"
    scheduling_plugin.app.syslog.create_artifact.return_value = MagicMock(sha1=fp_uuid)
    flight_plan_data = {
        "flight_plan": {"name": "plan_to_approve", "body": [{"name": "do-something"}]},
        "datetime": "2025-01-01T13:00:00+00:00",
        "gs_id": "86c8a92b-571a-46cb-b306-e9be71959279",
        "sat_name": "DISCO-2",
    }
    save_response = client.post("/save", json=flight_plan_data)
    assert save_response.status_code == 201

    with patch(
        "satop_plugins.flight_planning.scheduling.BackgroundTasks.add_task"
    ) as mock_add_task:
        response = client.post(f"/approve/{fp_uuid}?approved=true")
        assert response.status_code == 202
        assert (
            response.json()["message"]
            == "Flight plan approved and scheduled for transmission to ground station."
        )
        scheduling_plugin.call_function.assert_awaited_once_with(
            "Compiler", "compile", flight_plan_data["flight_plan"], "test-user"
        )
        mock_add_task.assert_called_once()
