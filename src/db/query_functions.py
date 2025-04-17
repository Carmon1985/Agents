import sqlite3
import pandas as pd
import logging
from contextlib import contextmanager
from typing import Optional, Tuple

DATABASE_PATH = 'data/database.db'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Provides a database connection."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def get_period_data(start_date: str, end_date: str, employee_id: Optional[str] = None) -> Tuple[float, float, Optional[float]]:
    """
    Fetches total charged hours, total capacity hours, and average target utilization
    for a given period and optional employee ID.

    Args:
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        employee_id (Optional[str]): The employee ID to filter by. If None, aggregates for all employees.

    Returns:
        Tuple[float, float, Optional[float]]: A tuple containing:
            - total charged hours (float)
            - total capacity hours (float)
            - average target utilization (Optional[float], None if no target found)
            Returns (0.0, 0.0, None) if no data is found or an error occurs.
    """
    total_charged = 0.0
    total_capacity = 0.0
    avg_target = None

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # --- Fetch Charged Hours ---
            query_charged = """
                SELECT SUM(charged_hours)
                FROM charged_hours
                WHERE date >= ? AND date <= ?
            """
            params_charged = [start_date, end_date]
            if employee_id:
                query_charged += " AND employee_id = ?"
                params_charged.append(employee_id)

            cursor.execute(query_charged, params_charged)
            result_charged = cursor.fetchone()
            if result_charged and result_charged[0] is not None:
                total_charged = float(result_charged[0])
                logger.info(f"Fetched total charged hours: {total_charged}")
            else:
                logger.warning(f"No charged hours found for period {start_date}-{end_date}, employee: {employee_id}")


            # --- Fetch Capacity Hours ---
            # Assuming capacity is in master_file, adjust table/column names if different
            query_capacity = """
                SELECT SUM(capacity_hours)
                FROM master_file
                WHERE date >= ? AND date <= ?
            """
            params_capacity = [start_date, end_date]
            if employee_id:
                query_capacity += " AND employee_id = ?"
                params_capacity.append(employee_id)

            cursor.execute(query_capacity, params_capacity)
            result_capacity = cursor.fetchone()
            if result_capacity and result_capacity[0] is not None:
                total_capacity = float(result_capacity[0])
                logger.info(f"Fetched total capacity hours: {total_capacity}")
            else:
                logger.warning(f"No capacity hours found for period {start_date}-{end_date}, employee: {employee_id}")


            # --- Fetch Target Utilization ---
            # Assuming target is in targets table, adjust if different
            query_target = """
                SELECT AVG(target_utilization)
                FROM targets
                WHERE date >= ? AND date <= ?
            """
            params_target = [start_date, end_date]
            if employee_id:
                query_target += " AND employee_id = ?"
                params_target.append(employee_id)

            cursor.execute(query_target, params_target)
            result_target = cursor.fetchone()
            if result_target and result_target[0] is not None:
                avg_target = float(result_target[0]) / 100.0 # Assuming target is stored as percentage e.g., 85 for 85%
                logger.info(f"Fetched average target utilization: {avg_target:.2%}")
            else:
                 logger.warning(f"No target utilization found for period {start_date}-{end_date}, employee: {employee_id}")


            return total_charged, total_capacity, avg_target

    except sqlite3.Error as e:
        logger.error(f"Database query error in get_period_data: {e}")
        return 0.0, 0.0, None
    except Exception as e:
        logger.error(f"Unexpected error in get_period_data: {e}")
        return 0.0, 0.0, None

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # Ensure you have some data in your database.db for these examples to work
    print("Testing query functions...")

    # Test case 1: Specific employee and date range
    print("\n--- Test Case 1: Employee 'EMP001', Jan 2024 ---")
    charged, capacity, target = get_period_data('2024-01-01', '2024-01-31', 'EMP001')
    print(f"Charged: {charged}, Capacity: {capacity}, Target: {target}")
    if capacity > 0:
        utilization = (charged / capacity) * 100
        print(f"Calculated Utilization: {utilization:.2f}%")
        if target is not None:
            print(f"Comparison to Target ({target:.2%}): {'Above' if utilization / 100 >= target else 'Below'}")
    else:
        print("Cannot calculate utilization (Capacity is zero).")


    # Test case 2: All employees and a different date range
    print("\n--- Test Case 2: All Employees, Feb 2024 ---")
    charged_all, capacity_all, target_all = get_period_data('2024-02-01', '2024-02-29')
    print(f"Charged: {charged_all}, Capacity: {capacity_all}, Target: {target_all}")
    if capacity_all > 0:
         utilization_all = (charged_all / capacity_all) * 100
         print(f"Calculated Utilization: {utilization_all:.2f}%")
         if target_all is not None:
            print(f"Comparison to Target ({target_all:.2%}): {'Above' if utilization_all / 100 >= target_all else 'Below'}")
    else:
        print("Cannot calculate utilization (Capacity is zero).") 