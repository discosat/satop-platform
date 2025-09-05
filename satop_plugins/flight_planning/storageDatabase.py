import json
import os
import sqlite3
from datetime import datetime

from .flightPlan import FlightPlan, FlightPlanApproval, FlightPlanStatusEnum


class StorageDatabase:
    def __init__(self, data_dir):
        self.db_path = os.path.join(data_dir, "DISCO_FP_DB.db")
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a new connection to the database."""
        return sqlite3.connect(self.db_path)

    def _initialize_database(self):
        """
        Ensures the necessary tables exist.
        In a real production environment with an existing database,
        you would use an ALTER TABLE statement to add new columns.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS flight_plans (
                    id TEXT PRIMARY KEY, 
                    flight_plan TEXT, 
                    datetime TEXT, 
                    gs_id TEXT, 
                    sat_name TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    previous_plan_id TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS approval (
                    id TEXT PRIMARY KEY, 
                    approver TEXT,
                    approval BOOLEAN,
                    approval_date DATETIME2
                )
                """
            )
            conn.commit()

    def get_flight_plan(self, flight_plan_uuid: str) -> FlightPlan | None:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM flight_plans WHERE id = ?", (flight_plan_uuid,)
            )
            row = cursor.fetchone()

            if row:
                fp_dict = json.loads(row["flight_plan"])
                return FlightPlan(
                    id=row["id"],
                    flight_plan=fp_dict,
                    datetime=row["datetime"],
                    gs_id=row["gs_id"],
                    sat_name=row["sat_name"],
                    status=row["status"],
                    previous_plan_id=row["previous_plan_id"],
                )
            return None

    def get_all_flight_plans(self) -> list[FlightPlan]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flight_plans")
            rows = cursor.fetchall()

            result = []
            for row in rows:
                fp_dict = json.loads(row["flight_plan"])
                result.append(
                    FlightPlan(
                        id=row["id"],
                        flight_plan=fp_dict,
                        datetime=row["datetime"],
                        gs_id=row["gs_id"],
                        sat_name=row["sat_name"],
                        status=row["status"],
                        previous_plan_id=row["previous_plan_id"],
                    )
                )
            return result

    def get_approval_index(self, flight_plan_uuid: str) -> FlightPlanApproval | None:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM approval WHERE id = ?", (flight_plan_uuid,))
            row = cursor.fetchone()
            if row:
                return FlightPlanApproval(
                    flight_plan_uuid=row["id"],
                    approval_status=row["approval"],
                    approver=row["approver"],
                    approval_date=row["approval_date"],
                )
            return None

    def save_flight_plan(self, flight_plan: FlightPlan, flight_plan_uuid: str) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            flight_plan_dict = flight_plan.flight_plan.model_dump()
            flight_plan_json = json.dumps(flight_plan_dict)
            cursor.execute(
                "INSERT INTO flight_plans (id, flight_plan, datetime, gs_id, sat_name, status, previous_plan_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    flight_plan_uuid,
                    flight_plan_json,
                    flight_plan.datetime,
                    flight_plan.gs_id,
                    flight_plan.sat_name,
                    flight_plan.status.value,
                    flight_plan.previous_plan_id,
                ),
            )
            conn.commit()

    def supersede_and_create_flight_plan(
        self, old_plan_uuid: str, new_plan: FlightPlan, new_plan_uuid: str
    ) -> None:
        """Atomically supersedes an old plan and creates a new one."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Mark the old plan as superseded
                cursor.execute(
                    "UPDATE flight_plans SET status = ? WHERE id = ?",
                    (FlightPlanStatusEnum.SUPERSEDED.value, old_plan_uuid),
                )

                # Insert the new plan
                flight_plan_dict = new_plan.flight_plan.model_dump()
                flight_plan_json = json.dumps(flight_plan_dict)
                cursor.execute(
                    "INSERT INTO flight_plans (id, flight_plan, datetime, gs_id, sat_name, status, previous_plan_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        new_plan_uuid,
                        flight_plan_json,
                        new_plan.datetime,
                        new_plan.gs_id,
                        new_plan.sat_name,
                        FlightPlanStatusEnum.PENDING.value,
                        old_plan_uuid,
                    ),
                )
                conn.commit()
            except sqlite3.Error as e:
                conn.rollback()
                raise e

    def save_approval(
        self, flight_plan_uuid: str, user_id: str, approval: bool = None
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO approval (id, approval, approver) VALUES (?, ?, ?)",
                (flight_plan_uuid, approval, user_id),
            )
            conn.commit()

    def update_approval(
        self, flight_plan_uuid: str, approval: bool, user_id: str
    ) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            approval_time = datetime.now().isoformat()
            cursor.execute(
                "UPDATE approval SET approval = ?, approval_date = ?, approver = ? WHERE id = ?",
                (approval, approval_time, user_id, flight_plan_uuid),
            )
            conn.commit()

    def update_flight_plan_status(
        self, flight_plan_uuid: str, status: FlightPlanStatusEnum
    ) -> None:
        """Updates the status of a specific flight plan."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE flight_plans SET status = ? WHERE id = ?",
                (status.value, flight_plan_uuid),
            )
            conn.commit()
