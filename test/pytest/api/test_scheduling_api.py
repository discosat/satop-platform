from unittest.mock import AsyncMock, MagicMock, patch

import yaml
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from satop_plugins.flight_planning.flightPlan import FlightPlan, FlightPlanDetail
from satop_plugins.flight_planning.scheduling import Scheduling

import pytest


@pytest.fixture
def mock_app():
    app = MagicMock(); app.auth = MagicMock(); app.gs = MagicMock(); app.syslog = MagicMock(); return app

@pytest.fixture
def scheduling_plugin(tmp_path, mock_app):
    plugin_data_dir = tmp_path / "data"; plugin_data_dir.mkdir()
    (tmp_path / "config.yaml").write_text(yaml.dump({"name": "Scheduling_Test", "capabilities": ["http.add_routes"]}))
    plugin = Scheduling(plugin_dir=str(tmp_path), app=mock_app, data_dir=str(plugin_data_dir))
    plugin.call_function = AsyncMock(return_value=("compiled_plan_bytes", "compiled_artifact_id"))
    plugin.startup()
    yield plugin
    plugin.shutdown()

@pytest.fixture
def client(scheduling_plugin):
    test_app = FastAPI()
    async def fake_require_login(req: Request): req.state.userid = "test-user"; return True
    test_app.dependency_overrides[scheduling_plugin.app.auth.require_login] = fake_require_login
    test_app.include_router(scheduling_plugin.api_router)
    return TestClient(test_app)


def test_save_new_flightplan(client: TestClient, scheduling_plugin: Scheduling):
    """Test the POST /save endpoint with valid data returns the full object."""
    fp_uuid = "mock_artifact_sha1"
    scheduling_plugin.app.syslog.create_artifact.return_value = MagicMock(sha1=fp_uuid)

    flight_plan_payload = {
        "flight_plan": {"name": "Test Plan", "body": []},
        "datetime": "2025-01-01T12:00:00+00:00",
        "gs_id": "86c8a92b-571a-46cb-b306-e9be71959279",
        "sat_name": "DISCO-2",
    }
    
    response = client.post("/save", json=flight_plan_payload)
    
    assert response.status_code == 201
    json_response = response.json()
    
    # Check that the response has the shape of FlightPlan model
    assert json_response["id"] == fp_uuid
    assert json_response["status"] == "pending"
    assert json_response["sat_name"] == "DISCO-2"
    assert json_response["flight_plan"]["name"] == "Test Plan"

def test_save_flightplan_invalid_datetime_returns_422(client: TestClient):
    """Test that bad data returns a 422 Unprocessable Entity error."""
    flight_plan_payload = {
        "flight_plan": {"name": "Test Plan", "body": []},
        "datetime": "not-a-real-date", # Invalid format
        "gs_id": "86c8a92b-571a-46cb-b306-e9be71959279",
        "sat_name": "DISCO-2",
    }
    
    response = client.post("/save", json=flight_plan_payload)
    
    assert "datetime" in response.text
    assert "invalid character in year" in response.text

@pytest.mark.asyncio
async def test_approve_flight_plan(client: TestClient, scheduling_plugin: Scheduling):
    """Test the POST /approve/{uuid} endpoint."""
    # Arrange: Set up a flight plan that "exists" in our mock database
    fp_uuid = "mock_artifact_for_approval"
    user_id = "test-user"
    
    # Create a valid FlightPlan object to be returned by the mocked DB call
    existing_plan = FlightPlan(
        id=fp_uuid,
        flight_plan=FlightPlanDetail(name="Plan to Approve", body=[{"name": "do-something"}]),
        datetime="2025-01-01T13:00:00+00:00",
        gs_id="86c8a92b-571a-46cb-b306-e9be71959279",
        sat_name="DISCO-2",
        status="pending"
    )

    # We need to mock the `__get_flight_plan` helper method directly
    # because it's called by the endpoint. We patch it on the INSTANCE.
    with patch.object(scheduling_plugin, '_Scheduling__get_flight_plan', return_value=existing_plan) as mock_get_plan, \
         patch.object(scheduling_plugin, '_Scheduling__update_approval', return_value=None) as mock_update_approval, \
         patch("satop_plugins.flight_planning.scheduling.BackgroundTasks.add_task") as mock_add_task:

        response = client.post(f"/approve/{fp_uuid}?approved=true")

        assert response.status_code == 202
        assert "Flight plan approved" in response.json()["message"]

        # Verify that our mocked helpers were called correctly
        mock_get_plan.assert_awaited_once_with(flight_plan_uuid=fp_uuid, user_id=user_id)
        mock_update_approval.assert_awaited_once_with(fp_uuid, user_id, True)

        # Verify the inter-plugin call and background task were initiated
        scheduling_plugin.call_function.assert_awaited_once_with(
            "Compiler", "compile", existing_plan.flight_plan.model_dump(), user_id
        )
        mock_add_task.assert_called_once()