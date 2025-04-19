import pandas as pd
import logging
from typing import Optional, Tuple
from datetime import datetime
import os

# Constants for file paths
EXCEL_DIR = 'data/excel'
MASTER_FILE = os.path.join(EXCEL_DIR, 'master.xlsx')
CHARGED_HOURS_FILE = os.path.join(EXCEL_DIR, 'charged_hours.xlsx')
TARGETS_FILE = os.path.join(EXCEL_DIR, 'targets.xlsx')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_period_data(start_date: str, end_date: str, employee_id: Optional[str] = None) -> Tuple[float, float, Optional[float]]:
    """
    Fetches total charged hours, total capacity hours, and average target utilization
    for a given period and optional employee ID from Excel files.
    """
    try:
        # Convert dates to pandas datetime
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Read charged hours data
        charged_df = pd.read_excel(CHARGED_HOURS_FILE)
        charged_df['Date'] = pd.to_datetime(charged_df[['Year', 'Month']].assign(Day=1))
        
        # Filter by date range and employee
        mask = (charged_df['Date'] >= start_dt) & (charged_df['Date'] <= end_dt)
        if employee_id:
            mask &= (charged_df['GPN'] == employee_id)
        
        period_data = charged_df[mask]
        
        total_charged = period_data['Charged_Hours'].sum()
        total_capacity = period_data['Capacity_Hours'].sum()
        
        # Read master data for employee details
        master_df = pd.read_excel(MASTER_FILE)
        if employee_id:
            employee_data = master_df[master_df['GPN'] == employee_id].iloc[0]
        else:
            employee_data = master_df.iloc[0]  # Use first record for segment info
            
        # Read targets data
        targets_df = pd.read_excel(TARGETS_FILE)
        
        # Filter targets by employee segment and date
        target_mask = (
            (targets_df['Person Segment'] == employee_data['Person Segment']) &
            (targets_df['Employee Category'] == employee_data['Employee Category']) &
            (targets_df['Level Group'] == employee_data['Level Group'])
        )
        
        if not targets_df[target_mask].empty:
            avg_target = targets_df[target_mask]['Target Utilization'].mean()
        else:
            avg_target = None
            
        logger.info(f"Period data retrieved - Charged: {total_charged}, Capacity: {total_capacity}, Target: {avg_target}")
        return total_charged, total_capacity, avg_target
        
    except Exception as e:
        logger.error(f"Error in get_period_data: {e}")
        return 0.0, 0.0, None

def get_monthly_utilization_history(num_months: int, end_date_str: str, employee_id: Optional[str] = None) -> pd.DataFrame | None:
    """
    Fetches monthly utilization history from Excel files.
    """
    try:
        # Convert end date and calculate start date
        end_date = pd.to_datetime(end_date_str)
        start_date = end_date - pd.DateOffset(months=num_months)
        
        # Read charged hours data
        charged_df = pd.read_excel(CHARGED_HOURS_FILE)
        charged_df['Date'] = pd.to_datetime(charged_df[['Year', 'Month']].assign(Day=1))
        
        # Filter by date range and employee
        mask = (charged_df['Date'] >= start_date) & (charged_df['Date'] < end_date)
        if employee_id:
            mask &= (charged_df['GPN'] == employee_id)
            
        history_data = charged_df[mask].copy()
        
        if history_data.empty:
            logger.warning("No historical data found for the specified period and criteria.")
            return None
            
        # Group by year and month
        history_data['year_month'] = history_data['Date'].dt.strftime('%Y-%m')
        monthly_data = history_data.groupby('year_month').agg({
            'Charged_Hours': 'sum',
            'Capacity_Hours': 'sum'
        }).reset_index()
        
        # Calculate utilization rate
        monthly_data['monthly_utilization_rate'] = (monthly_data['Charged_Hours'] / monthly_data['Capacity_Hours']) * 100
        monthly_data['monthly_utilization_rate'].fillna(0, inplace=True)
        
        # Rename columns to match expected interface
        monthly_data = monthly_data.rename(columns={
            'Charged_Hours': 'total_charged_hours',
            'Capacity_Hours': 'total_capacity_hours'
        })
        
        logger.info(f"Successfully fetched {len(monthly_data)} months of history.")
        return monthly_data.sort_values('year_month')
        
    except Exception as e:
        logger.error(f"Error in get_monthly_utilization_history: {e}")
        return None

def forecast_next_month_utilization(num_history_months: int, current_date_str: str, employee_id: Optional[str] = None, forecast_window: int = 3) -> str:
    """
    Forecasts next month's utilization based on historical data from Excel files.
    """
    try:
        # Get historical data
        history_df = get_monthly_utilization_history(num_history_months, current_date_str, employee_id)
        if history_df is None or len(history_df) < forecast_window:
            return f"Insufficient historical data. Need at least {forecast_window} months of history."
            
        # Calculate average utilization for the forecast window
        recent_utilization = history_df.tail(forecast_window)['monthly_utilization_rate'].mean()
        
        # Get employee details for context
        master_df = pd.read_excel(MASTER_FILE)
        if employee_id:
            employee_data = master_df[master_df['GPN'] == employee_id]
            employee_context = f"Employee {employee_data['Person_Name'].iloc[0]} ({employee_id})"
        else:
            employee_context = "all employees"
            
        # Format the forecast message
        forecast_msg = (
            f"Based on the last {forecast_window} months of data for {employee_context}, "
            f"the forecasted utilization for next month is {recent_utilization:.1f}%"
        )
        
        # Add trend analysis
        if len(history_df) >= 2:
            last_month = history_df['monthly_utilization_rate'].iloc[-1]
            prev_month = history_df['monthly_utilization_rate'].iloc[-2]
            trend = last_month - prev_month
            trend_msg = (
                "\nTrend Analysis: "
                f"{'Increasing' if trend > 0 else 'Decreasing' if trend < 0 else 'Stable'} "
                f"({abs(trend):.1f}% {'increase' if trend > 0 else 'decrease' if trend < 0 else 'change'} "
                "from previous month)"
            )
            forecast_msg += trend_msg
            
        return forecast_msg
        
    except Exception as e:
        logger.error(f"Error in forecast_next_month_utilization: {e}")
        return f"Error generating forecast: {str(e)}"

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