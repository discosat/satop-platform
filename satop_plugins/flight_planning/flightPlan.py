from datetime import datetime

from pydantic import BaseModel


class FlightPlan(BaseModel):
    flight_plan: dict
    datetime: str
    gs_id: str
    sat_name: str

    def validate_datetime_format(self):
        # Convert datetime string to datetime object
        try:
            self.datetime = datetime.fromisoformat(self.datetime)
        except ValueError:
            raise ValueError("Invalid datetime format. Expected ISO format.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "flight_plan": {
                        "name": "commands",
                        "body": [
                            {
                                "name": "repeat-n",
                                "count": 10,
                                "body": [
                                    {"name": "gpio-write", "pin": 16, "value": 1},
                                    {"name": "wait-sec", "duration": 1},
                                    {"name": "gpio-write", "pin": 16, "value": 0},
                                    {"name": "wait-sec", "duration": 1},
                                ],
                            }
                        ],
                    },
                    "datetime": "2025-01-01T12:12:30+01:00",
                    "gs_id": "86c8a92b-571a-46cb-b306-e9be71959279",
                    "sat_name": "DISCO-2",
                }
            ]
        }
    }


class FlightPlanStatus(BaseModel):
    flight_plan_uuid: str
    approval_status: bool | None
    approver: str | None
    approval_date: datetime | None
