import json
import os
import sqlite3
from datetime import datetime

from .flightPlan import FlightPlan, FlightPlanStatusEnum


class StorageDatabase:
    def __init__(self, data_dir):
        self.db_path = os.path.join(data_dir, "DISCO_FP_DB.db")
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize_database(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS flight_plans (
                    id TEXT PRIMARY KEY,
                    flight_plan TEXT NOT NULL,
                    scheduled_at TEXT NOT NULL,
                    gs_id TEXT NOT NULL,
                    sat_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    previous_plan_id TEXT,
                    approver_id TEXT,
                    approval_date TEXT
                )
                """
            )
            cursor.execute("DROP TABLE IF EXISTS approval")
            conn.commit()

    def get_flight_plan(self, flight_plan_id: str) -> FlightPlan | None:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM flight_plans WHERE id = ?", (flight_plan_id,))
            row = cursor.fetchone()

            if row:
                fp_dict = json.loads(row["flight_plan"])
                return FlightPlan(
                    id=row["id"],
                    flight_plan=fp_dict,
                    scheduled_at=row["scheduled_at"],
                    gs_id=row["gs_id"],
                    sat_name=row["sat_name"],
                    status=row["status"],
                    previous_plan_id=row["previous_plan_id"],
                    approver_id=row["approver_id"],
                    approval_date=row["approval_date"],
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
                        scheduled_at=row["scheduled_at"],
                        gs_id=row["gs_id"],
                        sat_name=row["sat_name"],
                        status=row["status"],
                        previous_plan_id=row["previous_plan_id"],
                        approver_id=row["approver_id"],
                        approval_date=row["approval_date"],
                    )
                )
            return result

    def save_flight_plan(self, flight_plan: FlightPlan) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            flight_plan_dict = flight_plan.flight_plan.model_dump()
            flight_plan_json = json.dumps(flight_plan_dict)
            cursor.execute(
                """
                INSERT INTO flight_plans
                (id, flight_plan, scheduled_at, gs_id, sat_name, status, previous_plan_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    flight_plan.id,
                    flight_plan_json,
                    flight_plan.scheduled_at.isoformat(),
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
                    """
                    INSERT INTO flight_plans
                    (id, flight_plan, scheduled_at, gs_id, sat_name, status, previous_plan_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_plan_uuid,
                        flight_plan_json,
                        new_plan.scheduled_at.isoformat(),
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

    def update_flight_plan_approval_status(
        self, flight_plan_id: str, status: FlightPlanStatusEnum, user_id: str
    ) -> int:
        """
        Updates the status of a specific flight plan and records the approver.
        Returns the number of rows affected.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            approval_time = datetime.now().isoformat()
            cursor.execute(
                """
                UPDATE flight_plans
                SET status = ?, approver_id = ?, approval_date = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status.value, user_id, approval_time, flight_plan_id),
            )
            conn.commit()
            return cursor.rowcount
