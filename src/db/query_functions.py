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

def get_monthly_utilization_history(num_months: int, end_date_str: str, employee_id: Optional[str] = None) -> pd.DataFrame | None:
    """
    Fetches monthly aggregated charged hours and capacity hours for the last 'num_months'
    ending before the specified end_date_str, optionally filtered by employee_id.
    Calculates monthly utilization.

    Args:
        num_months (int): The number of past months of history to retrieve.
        end_date_str (str): The end date (exclusive) for the history period (YYYY-MM-DD).
                             History will be retrieved for months *before* this date's month.
        employee_id (Optional[str]): The employee ID to filter by. If None, aggregates for all.

    Returns:
        pd.DataFrame | None: A DataFrame with columns ['year_month', 'total_charged_hours', 
                             'total_capacity_hours', 'monthly_utilization_rate'], 
                             sorted by year_month. Returns None if an error occurs or no data found.
    """
    try:
        # Calculate the start date for the query (num_months prior to end_date_str's month)
        end_date = pd.to_datetime(end_date_str)
        start_date = end_date - pd.DateOffset(months=num_months)
        # Adjust to start of the month
        start_date_str = start_date.strftime('%Y-%m-01')
        # Adjust end_date to the beginning of its month to make the range exclusive of the end_date's month
        end_month_start_str = end_date.strftime('%Y-%m-01')
        
        logger.info(f"Fetching monthly history for {num_months} months ending before {end_month_start_str}, Employee: {employee_id or 'All'}")

        with get_db_connection() as conn:
            # Query to get monthly sums for charged and capacity hours
            # We join charged_hours and master_file based on employee_id and month/year
            # Note: This assumes dates are stored as 'YYYY-MM-DD'. SQLite substr works.
            # Note: This assumes one capacity entry per employee per month in master_file for simplicity.
            #       A more complex schema might require different aggregation.
            query = """
            SELECT 
                strftime('%Y-%m', h.date) as year_month,
                SUM(h.charged_hours) as total_charged_hours,
                SUM(mf.capacity_hours) as total_capacity_hours
            FROM 
                charged_hours h
            JOIN 
                master_file mf ON h.employee_id = mf.employee_id AND strftime('%Y-%m', h.date) = strftime('%Y-%m', mf.date)
            WHERE 
                h.date >= ? AND h.date < ? 
            """
            params = [start_date_str, end_month_start_str]

            if employee_id:
                query += " AND h.employee_id = ? "
                params.append(employee_id)
            
            query += " GROUP BY year_month ORDER BY year_month; "
            
            df_history = pd.read_sql_query(query, conn, params=params)

            if df_history.empty:
                logger.warning("No historical data found for the specified period and criteria.")
                return None

            # Calculate monthly utilization rate
            df_history['monthly_utilization_rate'] = (df_history['total_charged_hours'] / df_history['total_capacity_hours']) * 100
            # Handle potential division by zero if capacity was 0 for a month
            df_history['monthly_utilization_rate'].fillna(0, inplace=True)
            
            logger.info(f"Successfully fetched and calculated {len(df_history)} months of history.")
            return df_history

    except sqlite3.Error as e:
        logger.error(f"Database query error in get_monthly_utilization_history: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_monthly_utilization_history: {e}", exc_info=True)
        return None

def forecast_next_month_utilization(num_history_months: int, current_date_str: str, employee_id: Optional[str] = None, forecast_window: int = 3) -> str:
    """
    Forecasts the next month's utilization based on historical average.

    Args:
        num_history_months (int): How many months of history to fetch (should be >= forecast_window).
        current_date_str (str): The current date (YYYY-MM-DD), used to determine the history period.
        employee_id (Optional[str]): Employee ID to filter history for, or None for all.
        forecast_window (int): Number of recent months to average for the forecast.

    Returns:
        str: A string describing the forecast or an error message.
    """
    logger.info(f"Forecasting next month utilization based on last {forecast_window} months of data. History length: {num_history_months}. Employee: {employee_id or 'All'}")
    
    if num_history_months < forecast_window:
        msg = f"Error: Not enough history ({num_history_months} months) requested to create a forecast based on the last {forecast_window} months."
        logger.error(msg)
        return msg
        
    # Fetch historical data
    history_df = get_monthly_utilization_history(num_months=num_history_months, end_date_str=current_date_str, employee_id=employee_id)

    if history_df is None:
        msg = "Error: Could not retrieve historical data for forecasting."
        logger.error(msg)
        return msg
        
    if len(history_df) < forecast_window:
        msg = f"Error: Not enough historical data available ({len(history_df)} months found) to create a forecast based on the last {forecast_window} months."
        logger.error(msg)
        return msg

    # Calculate the average utilization of the last 'forecast_window' months
    try:
        last_n_months = history_df.tail(forecast_window)
        forecasted_utilization = last_n_months['monthly_utilization_rate'].mean()
        
        last_month_str = last_n_months['year_month'].iloc[-1]
        forecast_month = (pd.to_datetime(last_month_str + '-01') + pd.DateOffset(months=1)).strftime('%Y-%m')

        result_str = f"Utilization Forecast for {forecast_month} (based on avg of last {forecast_window} months ending {last_month_str}): {forecasted_utilization:.2f}%"
        if employee_id:
             result_str += f" (Employee: {employee_id})"
        else:
            result_str += " (All Employees)"
            
        logger.info(f"Forecast successful: {result_str}")
        return result_str
        
    except Exception as e:
        logger.error(f"Error calculating forecast: {e}", exc_info=True)
        return f"Error during forecast calculation: {e}"

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # Ensure you have some data in your database.db for these examples to work
    print("Testing query functions...")

    # Test case 1: Specific employee and date range (e.g., Jan 2024)
    # print("\n--- Test Case 1: Employee 'EMP001', Jan 2024 ---")
    # charged, capacity, target = get_period_data('2024-01-01', '2024-01-31', 'EMP001')
    # print(f"Charged: {charged}, Capacity: {capacity}, Target: {target}")
    # ... (rest of Test Case 1)

    # Test case 2: All employees for April 2025
    print("\n--- Test Case 2: All Employees, April 2025 ---")
    start_apr = '2025-04-01'
    end_apr = '2025-04-30'
    charged_all, capacity_all, target_all = get_period_data(start_apr, end_apr)
    print(f"Query Period: {start_apr} to {end_apr}")
    print(f"Charged: {charged_all}, Capacity: {capacity_all}, Target: {target_all}")
    if capacity_all > 0:
         utilization_all = (charged_all / capacity_all) * 100
         print(f"Calculated Utilization: {utilization_all:.2f}%")
         if target_all is not None:
            # Determine deviation status (using same logic as agent)
            SIGNIFICANT_DEVIATION_THRESHOLD = 5.0
            deviation = utilization_all - (target_all * 100)
            if deviation >= 0:
                deviation_status = "Met/Exceeded Target"
            elif abs(deviation) <= SIGNIFICANT_DEVIATION_THRESHOLD:
                deviation_status = "Slightly Below Target"
            else:
                deviation_status = "Significantly Below Target"
            print(f"Target: {target_all:.2%}, Deviation: {deviation:.2f}%, Status: {deviation_status}")
         else:
            print("Target not found. Cannot assess deviation.")
    else:
        print("Cannot calculate utilization (Capacity is zero).")

    # --- Test Case 3: Historical Data --- 
    print("\n--- Test Case 3: Historical Data (Last 6 months before Apr 2025) ---")
    history_df = get_monthly_utilization_history(num_months=6, end_date_str='2025-04-01')
    if history_df is not None:
        print(history_df)
    else:
        print("Could not retrieve historical data.")
    
    print("\n--- Test Case 4: Historical Data for EMP001 (Last 3 months before Apr 2025) ---")
    history_emp_df = get_monthly_utilization_history(num_months=3, end_date_str='2025-04-01', employee_id='EMP001')
    if history_emp_df is not None:
        print(history_emp_df)
    else:
        print("Could not retrieve historical data for EMP001.")

    # --- Test Case 5: Forecasting --- 
    print("\n--- Test Case 5: Forecast next month (after Apr 2025) ---")
    # Use current date that allows fetching relevant history (e.g., May 1st to get history up to April)
    forecast_result = forecast_next_month_utilization(num_history_months=6, current_date_str='2025-05-01', forecast_window=3)
    print(forecast_result)
    
    print("\n--- Test Case 6: Forecast next month for EMP001 --- ")
    forecast_emp_result = forecast_next_month_utilization(num_history_months=3, current_date_str='2025-05-01', employee_id='EMP001', forecast_window=2)
    print(forecast_emp_result) 