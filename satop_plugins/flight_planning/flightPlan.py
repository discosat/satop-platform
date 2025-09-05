from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel


class FlightPlanDetail(BaseModel):
    name: str
    body: List[Dict[str, Any]]


class FlightPlan(BaseModel):
    id: str | None = None
    flight_plan: FlightPlanDetail
    datetime: datetime
    gs_id: str
    sat_name: str
    status: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": None,
                    "flight_plan": {
                        "name": "Sample Imaging Plan",
                        "body": [
                            {"name": "gpio-write", "pin": 16, "value": 1},
                            {"name": "wait-sec", "duration": 5},
                            {"name": "gpio-write", "pin": 16, "value": 0},
                        ],
                    },
                    "datetime": "2025-01-01T12:12:30+01:00",
                    "gs_id": "86c8a92b-571a-46cb-b306-e9be71959279",
                    "sat_name": "DISCO-2",
                    "status": None,
                }
            ]
        }
    }


class FlightPlanStatus(BaseModel):
    flight_plan_uuid: str
    approval_status: bool | None
    approver: str | None
    approval_date: datetime | None
