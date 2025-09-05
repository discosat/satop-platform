import os
import sqlite3

from satop_plugins.flight_planning.flightPlan import FlightPlan
from satop_plugins.flight_planning.storageDatabase import StorageDatabase

import pytest


@pytest.fixture
def db(tmp_path):
    """Creates a StorageDatabase instance using a temporary file for isolation."""
    db_instance = StorageDatabase(data_dir=tmp_path)
    yield db_instance


@pytest.fixture
def sample_flight_plan():
    """Provides a sample FlightPlan object for tests."""
    return FlightPlan(
        flight_plan={"name": "test_plan", "body": []},
        datetime="2025-01-01T12:00:00+00:00",
        gs_id="86c8a92b-571a-46cb-b306-e9be71959279",
        sat_name="DISCO-2",
    )


def test_initialization_creates_db_and_tables(db: StorageDatabase):
    """Test that the DB file and tables are created on initialization."""
    assert os.path.exists(db.db_path)
    try:
        with db._get_connection() as conn:
            conn.execute("SELECT 1 FROM flight_plans LIMIT 1")
            conn.execute("SELECT 1 FROM approval LIMIT 1")
    except sqlite3.OperationalError as e:
        pytest.fail(f"Table check failed: {e}")


def test_save_and_get_flight_plan(db: StorageDatabase, sample_flight_plan: FlightPlan):
    """Test saving a flight plan and retrieving it."""
    fp_uuid = "test-uuid-123"

    # First, check that it doesn't exist
    assert db.get_flight_plan(fp_uuid) is None

    # Save it
    db.save_flight_plan(sample_flight_plan, fp_uuid)

    # Retrieve it and check if it's the same
    retrieved_fp = db.get_flight_plan(fp_uuid)
    assert retrieved_fp is not None
    # Compare field by field
    assert retrieved_fp.flight_plan == sample_flight_plan.flight_plan
    assert retrieved_fp.sat_name == sample_flight_plan.sat_name
    assert str(retrieved_fp.datetime) == str(sample_flight_plan.datetime)


def test_get_all_flight_plans(db: StorageDatabase, sample_flight_plan: FlightPlan):
    """Test retrieving all flight plans."""
    db.save_flight_plan(sample_flight_plan, "uuid1")

    fp2 = sample_flight_plan.model_copy(deep=True)
    fp2.sat_name = "DISCO-3"
    db.save_flight_plan(fp2, "uuid2")

    all_fps_with_ids = db.get_all_flight_plans_with_ids()
    assert len(all_fps_with_ids) == 2
    assert all_fps_with_ids[0]["id"] == "uuid1"
    assert all_fps_with_ids[1]["sat_name"] == "DISCO-3"


def test_save_and_update_approval(db: StorageDatabase):
    """Test the approval workflow."""
    fp_uuid = "test-approval-uuid"
    user_id = "test-operator"

    db.save_approval(fp_uuid, user_id)

    approval_status = db.get_approval_index(fp_uuid)
    assert approval_status is not None
    assert approval_status.flight_plan_uuid == fp_uuid
    assert approval_status.approver == user_id
    assert approval_status.approval_status is None

    db.update_approval(fp_uuid, approval=True, user_id="approver-x")

    updated_status = db.get_approval_index(fp_uuid)
    assert updated_status.approval_status is True
    assert updated_status.approver == "approver-x"
    assert updated_status.approval_date is not None
