from .flightPlan import FlightPlan, FlightPlanStatus
from datetime import datetime

import sqlite3
import os
import logging
import ast

class StorageDatabase:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.connection = self.get_connection()

        self.create_flight_plans_table()
        self.create_approval_table()
		
    # TODO: Needs testing
    def get_connection(self) -> sqlite3.Connection:
        """Get a connection to the database

        Returns:
            sqlite3.Connection: The connection to the database
        """
        _path = os.path.join(self.data_dir, f'DISCO_FP_DB.db')
        _conn = sqlite3.connect(_path)
        return _conn
        
    # TODO: Needs testing
    def close_connection(self) -> bool:
        """Close the connection to the database"
        """
        # Ensure the connection is open
        self.__check_connection()

        self.connection.close()
        return True
    
    # TODO: Needs testing
    async def check_table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database

        Args:
            table_name (str): The name of the table

        Returns:
            bool: True if the table exists, False otherwise
        """
        c = self.connection.cursor()
        c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        return c.fetchone() is not None
    
    # TODO: Needs testing
    def create_flight_plans_table(self) -> None:
        """Create the flight_plans table in the database

        Args:
            flight_plan (FlightPlan): The flight plan to be stored in the database
            flight_plan_uuid (str): The UUID of the flight plan
        """
        # Ensure the connection is open
        self.__check_connection()

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute("""
                    CREATE TABLE IF NOT EXISTS flight_plans (
                    id TEXT PRIMARY KEY, 
                    flight_plan TEXT, 
                    datetime TEXT, 
                    gs_id TEXT, 
                    sat_name TEXT
                    )
                    """)
        self.connection.commit()

    # TODO: Needs testing
    def create_approval_table(self) -> None:
        """Create the approval table in the database
        """
        # Ensure the connection is open
        self.__check_connection()

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute("""
                    CREATE TABLE IF NOT EXISTS approval (
                    id TEXT PRIMARY KEY, 
                    approver TEXT,
                    approval BOOLEAN,
                    approval_date DATETIME2
                    )
                    """)
        self.connection.commit()


    # TODO: Needs testing
    async def get_flight_plan(self, flight_plan_uuid: str) -> FlightPlan | None:
        """Get a flight plan from the database

        Args:
            flight_plan_uuid (str): The UUID of the flight plan

        Returns:
            FlightPlan: The flight plan
        """
        # Ensure the connection is open and the flight_plans table exists
        self.__check_connection()
        self.__check_table_exists('flight_plans')

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute(f"SELECT * FROM flight_plans WHERE id = '{flight_plan_uuid}'")
        flight_plan = c.fetchone()

        if flight_plan:
            fp_dict = ast.literal_eval(flight_plan[1])
            return FlightPlan(
                flight_plan=fp_dict,
                datetime=flight_plan[2],
                gs_id=flight_plan[3],
                sat_name=flight_plan[4]
            )
        return None  

    # TODO: Needs testing
    async def get_all_flight_plans(self) -> list[FlightPlan]:
        """Get all flight plans from the database

        Returns:
            list[FlightPlan]: A list of flight plans
        """
        # Ensure the connection is open and the flight_plans table exists
        self.__check_connection()
        self.__check_table_exists('flight_plans')

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute("SELECT * FROM flight_plans")
        flight_plans = c.fetchall()

        return [FlightPlan(
            flight_plan=ast.literal_eval(flight_plan[1]),
            datetime=flight_plan[2],
            gs_id=flight_plan[3],
            sat_name=flight_plan[4]
        ) for flight_plan in flight_plans]
    
    # TODO: Needs testing
    async def get_approval_index(self, flight_plan_uuid: str) -> FlightPlanStatus:
        """Retrieve the approval index of a flight plan
        
        Args:
            flight_plan_uuid (str): The UUID of the flight plan

        Returns:
            : The approval index of the flight plan
        """
        # Ensure the connection is open and the flight_plans table exists
        self.__check_connection()
        self.__check_table_exists('approval')

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute(f"SELECT * FROM approval WHERE id = '{flight_plan_uuid}'")
        approval = c.fetchone()
        if approval:
            print("---")
            print(approval)
            print("---")
            return FlightPlanStatus(
                flight_plan_uuid=approval[0],
                approval_status=approval[2],
                approver=approval[1],
                approval_date=approval[3]
            )
        return None


    # TODO: Needs testing
    async def get_approval_status(self, flight_plan_uuid: str) -> bool:
        """Get the approval status of a flight plan

        Args:
            flight_plan_uuid (str): The UUID of the flight plan

        Returns:
            bool: The approval status of the flight plan
        """
        # Ensure the connection is open and the flight_plans table exists
        self.__check_connection()
        self.__check_table_exists('approval')

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute(f"SELECT approval FROM approval WHERE id = '{flight_plan_uuid}'")
        approval = c.fetchone()
        if approval:
            return approval[2]
        return None  
    
    # TODO: Needs testing
    async def save_flight_plan(self, flight_plan: FlightPlan, flight_plan_uuid: str) -> None:
        # Ensure the connection is open and the flight_plans table exists
        self.__check_connection()
        self.__check_table_exists('flight_plans')

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute("""
                INSERT INTO flight_plans (id, flight_plan, datetime, gs_id, sat_name) 
                VALUES (?, ?, ?, ?, ?)
                """
                , (flight_plan_uuid, str(flight_plan.flight_plan), flight_plan.datetime, flight_plan.gs_id, flight_plan.sat_name)
                )
        
        self.connection.commit()

    # TODO: Needs testing
    async def update_flight_plan(self, flight_plan: FlightPlan, flight_plan_uuid: str) -> None:
        # Ensure the connection is open and the flight_plans table exists
        self.__check_connection()
        self.__check_table_exists('flight_plans')

        # Create a cursor and execute the query
        c = self.connection.cursor()
        c.execute("""
                UPDATE flight_plans
                SET flight_plan = ?,
                    datetime = ?,
                    gs_id = ?,
                    sat_name = ?
                WHERE id = ?
                """
                , (str(flight_plan.flight_plan), flight_plan.datetime, flight_plan.gs_id, flight_plan.sat_name, flight_plan_uuid)
                )
        
        self.connection.commit()

    # TODO: Needs testing
    async def save_approval(self, flight_plan_uuid: str, user_id: str, approval: bool = None) -> None:
        # Ensure the connection is open and the approval table exists
        self.__check_connection()
        self.__check_table_exists('approval')

        # Create a cursor and execute the query
        c = self.connection.cursor()

        c.execute("""
                INSERT INTO approval (id, approval, approver) 
                VALUES (?, ?, ?)
                """
                , (flight_plan_uuid, approval, user_id)
                )
        
        self.connection.commit()

    # TODO: Needs testing
    async def update_approval(self, flight_plan_uuid: str, approval: bool, user_id:str) -> None:
        # Ensure the connection is open and the approval table exists
        self.__check_connection()
        self.__check_table_exists('approval')

        # Create a cursor and execute the query
        c = self.connection.cursor()
        approval_time = datetime.now().isoformat()
        c.execute("""
                UPDATE approval
                SET approval = ?,
                    approval_date = ?,
                  approver = ?
                WHERE id = ?
                """
                , (approval, approval_time, user_id, flight_plan_uuid)
                )
        
        self.connection.commit()


    def __check_connection(self) -> None:
        """Check if the connection to the database is open
            
        Raises:
            ValueError: If the connection to the database is not open
        """
        if not self.connection:
            raise ValueError("Connection to the database is not open")
        
    def __check_table_exists(self, table_name: str) -> None:
        """Check if a table exists in the database

        Args:
            table_name (str): The name of the table

        Raises:
            ValueError: If the table does not exist
        """
        self.__check_connection()

        c = self.connection.cursor()
        c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if c.fetchone() is None:
            raise ValueError(f"Table {table_name} does not exist")













    async def __test_database(self, logger: logging.Logger):
        """Test all aspects of the database and clean up afterwards"""

        # Test the creation of the flight_plans table
        await self.create_flight_plans_table()
        assert await self.check_table_exists('flight_plans')
        logger.debug("Table flight_plans exists")
        
        # Test the creation of the approval table
        await self.create_approval_table()
        assert await self.check_table_exists('approval')
        logger.debug("Table approval exists")

        # Test saving a flight plan
        flight_plan = FlightPlan(
            flight_plan={
                "name": "commands",
                "body": [
                    {
                        "name": "repeat-n",
                        "count": 10,
                        "body": [
                            {
                                "name": "gpio-write",
                                "pin": 16,
                                "value": 1
                            },
                            {
                                "name": "wait-sec",
                                "duration": 1
                            },
                            {
                                "name": "gpio-write",
                                "pin": 16,
                                "value": 0
                            },
                            {
                                "name": "wait-sec",
                                "duration": 1
                            }
                        ]
                    }
                ]
            },
            datetime="2025-01-01T12:12:30+01:00",
            gs_id="86c8a92b-571a-46cb-b306-e9be71959279",
            sat_name="DISCO-2"
        )
        await self.save_flight_plan(flight_plan, "test_flight_plan")
        assert await self.get_flight_plan("test_flight_plan") == flight_plan
        logger.debug("Flight plan saved")

        # Test saving an approval
        await self.save_approval("test_flight_plan", "test_user")
        assert await self.get_approval_index("test_flight_plan") == FlightPlanStatus(
            flight_plan_uuid="test_flight_plan",
            approval_status=None,
            approver="test_user",
            approval_date=None
        )
        
        # Test updating an approval
        await self.update_approval("test_flight_plan", True)
        assert await self.get_approval_status("test_flight_plan") == True
        logger.debug("Approval updated")

        # Test updating a flight plan
        flight_plan = FlightPlan(
            flight_plan={
                "name": "commands",
                "body": [
                    {
                        "name": "repeat-n",
                        "count": 10,
                        "body": [
                            {
                                "name": "gpio-write",
                                "pin": 16,
                                "value": 1
                            },
                            {
                                "name": "wait-sec",
                                "duration": 1
                            },
                            {
                                "name": "gpio-write",
                                "pin": 16,
                                "value": 0
                            },
                            {
                                "name": "wait-sec",
                                "duration": 1
                            }
                        ]
                    }
                ]
            },
            datetime="2025-01-01T12:12:30+01:00",
            gs_id="86c8a92b-571a-46cb-b306-e9be71959279",
            sat_name="DISCO-2"
        )
        await self.update_flight_plan(flight_plan, "test_flight_plan")
        assert await self.get_flight_plan("test_flight_plan") == flight_plan
        logger.debug("Flight plan updated")

        # Clean up
        c = self.connection.cursor()
        c.execute("DROP TABLE flight_plans")
        c.execute("DROP TABLE approval")
        self.connection.commit()
        self.close_connection()
        os.remove(os.path.join(self.data_dir, f'DISCO_FP_DB.db'))
        logger.debug("Test complete")