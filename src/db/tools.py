import sqlite3
import pandas as pd
import os
import logging

# Basic Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the database path relative to the project root
# Assumes the script is run from the project root or adjusts path accordingly
DB_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'db') 
DB_PATH = os.path.join(DB_DIR, 'database.db')

# Ensure the db directory exists
os.makedirs(DB_DIR, exist_ok=True)

def get_db_connection(db_path=DB_PATH):
    """Establishes a connection to the SQLite database.

    Args:
        db_path (str, optional): The path to the database file. 
                                 Defaults to DB_PATH.

    Returns:
        sqlite3.Connection: A connection object to the database.
                            Returns None if connection fails.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        logging.info(f"Successfully connected to database at {db_path}")
    except sqlite3.Error as e:
        logging.error(f"Error connecting to database at {db_path}: {e}", exc_info=True)
    return conn

def execute_query(query: str, params: tuple = None, db_path: str = DB_PATH) -> pd.DataFrame | None:
    """Executes a SQL query and returns the result as a Pandas DataFrame.

    Args:
        query (str): The SQL query string to execute.
        params (tuple, optional): A tuple of parameters to substitute into the query 
                                  (for safe parameterized queries). Defaults to None.
        db_path (str, optional): The path to the database file. 
                                 Defaults to DB_PATH.

    Returns:
        pd.DataFrame | None: A DataFrame containing the query results, 
                             or None if an error occurs or no data is returned.
    """
    # Connection is now managed by the fixture or higher-level context
    conn = get_db_connection(db_path) 
    if conn is None:
        # If connection failed initially, return None
        return None

    try:
        logging.info(f"Executing query: {query} with params: {params}")
        if params:
            df = pd.read_sql_query(query, conn, params=params)
        else:
            df = pd.read_sql_query(query, conn)
        logging.info(f"Query executed successfully, returned {len(df)} rows.")
        return df
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        logging.error(f"Error executing query: {query} - {e}", exc_info=True)
        # Close connection here ONLY if an error occurred during query execution?
        # No, let the fixture handle closing even on error.
        return None
    # finally:
        # REMOVED: Connection closing responsibility is moved to the caller/fixture
        # if conn:
        #     conn.close()
        #     logging.info("Database connection closed.")

def get_performance_data(start_date: str | None = None, end_date: str | None = None, 
                         employee_id: str | None = None, project_id: str | None = None,
                         db_path: str = DB_PATH) -> pd.DataFrame | None:
    """Retrieves performance data (charged hours) from the database, 
    optionally filtered by date range, employee, or project.

    Args:
        start_date (str | None, optional): Start date in 'YYYY-MM-DD' format. Defaults to None.
        end_date (str | None, optional): End date in 'YYYY-MM-DD' format. Defaults to None.
        employee_id (str | None, optional): Employee ID to filter by. Defaults to None.
        project_id (str | None, optional): Project ID to filter by. Defaults to None.
        db_path (str, optional): Path to the database file. Defaults to DB_PATH.

    Returns:
        pd.DataFrame | None: DataFrame with performance data or None if an error occurs.
    """
    base_query = "SELECT employee_id, project_id, charge_date, charged_hours FROM charged_hours"
    conditions = []
    params = []

    if start_date:
        conditions.append("charge_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("charge_date <= ?")
        params.append(end_date)
    if employee_id:
        conditions.append("employee_id = ?")
        params.append(employee_id)
    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)

    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)};"
    else:
        query = f"{base_query};"
        
    return execute_query(query, params=tuple(params) if params else None, db_path=db_path)

def get_targets(year: int | None = None, month: int | None = None, 
                employee_id: str | None = None, db_path: str = DB_PATH) -> pd.DataFrame | None:
    """Retrieves target data from the database, optionally filtered by 
    year, month, or employee.

    Assumes a 'targets' table with columns like 'year', 'month', 'employee_id', etc.
    Adjust column names and table name as per actual schema.

    Args:
        year (int | None, optional): Year to filter by. Defaults to None.
        month (int | None, optional): Month (1-12) to filter by. Defaults to None.
        employee_id (str | None, optional): Employee ID to filter by. Defaults to None.
        db_path (str, optional): Path to the database file. Defaults to DB_PATH.

    Returns:
        pd.DataFrame | None: DataFrame with target data or None if an error occurs.
    """
    # Adjust SELECT clause based on actual columns in your 'targets' table
    base_query = "SELECT year, month, employee_id, target_utilization, target_hours FROM targets" 
    conditions = []
    params = []

    if year:
        conditions.append("year = ?")
        params.append(year)
    if month:
        conditions.append("month = ?")
        params.append(month)
    if employee_id:
        conditions.append("employee_id = ?")
        params.append(employee_id)

    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)};"
    else:
        query = f"{base_query};"
        
    return execute_query(query, params=tuple(params) if params else None, db_path=db_path)

def get_employee_data(employee_id: str | None = None, 
                      segment: str | None = None, 
                      db_path: str = DB_PATH) -> pd.DataFrame | None:
    """Retrieves employee data from the master file, optionally filtered by 
    employee ID or segment.

    Assumes a 'master_file' table with relevant employee columns like 
    'employee_id', 'employee_name', 'segment', 'practice', 'title', etc.
    Adjust columns and table name as needed.

    Args:
        employee_id (str | None, optional): Employee ID to filter by. Defaults to None.
        segment (str | None, optional): Segment to filter by. Defaults to None.
        db_path (str, optional): Path to the database file. Defaults to DB_PATH.

    Returns:
        pd.DataFrame | None: DataFrame with employee data or None if an error occurs.
    """
    # Adjust SELECT clause based on actual columns in your master_file table
    base_query = "SELECT DISTINCT employee_id, employee_name, segment, practice, title FROM master_file"
    conditions = []
    params = []

    if employee_id:
        conditions.append("employee_id = ?")
        params.append(employee_id)
    if segment:
        conditions.append("segment = ?")
        params.append(segment)

    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)};"
    else:
        query = f"{base_query};" # Select all unique employees
        
    return execute_query(query, params=tuple(params) if params else None, db_path=db_path)

def get_project_data(project_id: str | None = None, 
                     manager_id: str | None = None, 
                     db_path: str = DB_PATH) -> pd.DataFrame | None:
    """Retrieves project data from the master file, optionally filtered by 
    project ID or manager ID.

    Assumes a 'master_file' table with relevant project columns like 
    'project_id', 'project_name', 'manager_id', 'client_name', etc.
    Adjust columns and table name as needed.

    Args:
        project_id (str | None, optional): Project ID to filter by. Defaults to None.
        manager_id (str | None, optional): Manager ID to filter by. Defaults to None.
        db_path (str, optional): Path to the database file. Defaults to DB_PATH.

    Returns:
        pd.DataFrame | None: DataFrame with project data or None if an error occurs.
    """
    # Adjust SELECT clause based on actual columns in your master_file table
    base_query = "SELECT DISTINCT project_id, project_name, manager_id, client_name FROM master_file"
    conditions = []
    params = []

    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)
    if manager_id:
        # Assuming the column name is manager_id, adjust if different
        conditions.append("manager_id = ?") 
        params.append(manager_id)

    if conditions:
        query = f"{base_query} WHERE {' AND '.join(conditions)};"
    else:
        query = f"{base_query};" # Select all unique projects
        
    return execute_query(query, params=tuple(params) if params else None, db_path=db_path)

def calculate_utilization(start_date: str, end_date: str, 
                          employee_id: str | None = None, 
                          db_path: str = DB_PATH) -> float | pd.DataFrame | None:
    """Calculates utilization for a given period and optionally for a specific employee.

    Utilization = Total Charged Hours / Total Target Hours

    Args:
        start_date (str): Start date in 'YYYY-MM-DD' format.
        end_date (str): End date in 'YYYY-MM-DD' format.
        employee_id (str | None, optional): Employee ID to filter by. If None, calculates 
                                           overall utilization for the period across employees 
                                           found in both charged hours and targets.
                                           Defaults to None.
        db_path (str, optional): Path to the database file. Defaults to DB_PATH.

    Returns:
        float | pd.DataFrame | None: 
            - If employee_id is specified, returns a single float representing utilization.
            - If employee_id is None, returns a DataFrame with 'employee_id' and 'utilization'.
            - Returns None if data is insufficient or an error occurs.
    """
    # --- DEBUG PRINT --- 
    print(f"--- DEBUG: calculate_utilization called with start={start_date}, end={end_date}, employee={employee_id} ---")
    # --- END DEBUG PRINT ---
    
    logging.info(f"Calculating utilization from {start_date} to {end_date} for employee: {employee_id or 'All'}")

    # 1. Get Charged Hours
    charged_hours_df = get_performance_data(
        start_date=start_date, end_date=end_date, 
        employee_id=employee_id, db_path=db_path
    )
    if charged_hours_df is None or charged_hours_df.empty:
        logging.warning("No charged hours data found for the specified criteria.")
        return None
        
    # Convert charge_date to datetime to extract year and month
    charged_hours_df['charge_date'] = pd.to_datetime(charged_hours_df['charge_date'])
    charged_hours_df['year'] = charged_hours_df['charge_date'].dt.year
    charged_hours_df['month'] = charged_hours_df['charge_date'].dt.month

    # 2. Get Target Hours 
    # Need to fetch targets for all relevant year/month combinations in the date range
    years = charged_hours_df['year'].unique()
    months = charged_hours_df['month'].unique()
    
    all_targets_df = pd.DataFrame()
    for year in years:
        # Fetch targets for specific months within the year present in charged data
        months_in_year = charged_hours_df[charged_hours_df['year'] == year]['month'].unique()
        for month in months_in_year:
            targets_df = get_targets(year=int(year), month=int(month), employee_id=employee_id, db_path=db_path)
            if targets_df is not None and not targets_df.empty:
                all_targets_df = pd.concat([all_targets_df, targets_df], ignore_index=True)

    if all_targets_df.empty:
        logging.warning("No target hours data found for the specified criteria.")
        return None

    # Ensure required columns exist and handle potential missing values
    if 'charged_hours' not in charged_hours_df.columns or 'target_hours' not in all_targets_df.columns:
         logging.error("Required columns ('charged_hours' or 'target_hours') not found in retrieved data.")
         return None
         
    charged_hours_df['charged_hours'] = pd.to_numeric(charged_hours_df['charged_hours'], errors='coerce').fillna(0)
    all_targets_df['target_hours'] = pd.to_numeric(all_targets_df['target_hours'], errors='coerce')

    # 3. Calculate Utilization
    if employee_id:
        # Calculate for a single employee
        total_charged = charged_hours_df['charged_hours'].sum()
        # Sum target hours for the specific employee across the relevant months/years
        total_target = all_targets_df[all_targets_df['employee_id'] == employee_id]['target_hours'].sum()
        
        if total_target == 0:
            logging.warning(f"Total target hours are zero for employee {employee_id}. Cannot calculate utilization.")
            return None # Or return 0.0, depending on desired behavior
            
        utilization = total_charged / total_target
        logging.info(f"Calculated utilization for {employee_id}: {utilization:.2f}")
        return utilization
    else:
        # Calculate for multiple employees (group by employee)
        charged_grouped = charged_hours_df.groupby('employee_id')['charged_hours'].sum().reset_index()
        targets_grouped = all_targets_df.groupby('employee_id')['target_hours'].sum().reset_index()
        
        # Merge charged and target hours
        utilization_df = pd.merge(charged_grouped, targets_grouped, on='employee_id', how='inner')
        
        # Calculate utilization, handle division by zero
        utilization_df['utilization'] = utilization_df.apply(
            lambda row: (row['charged_hours'] / row['target_hours']) if row['target_hours'] != 0 else 0.0, 
            axis=1
        )
        
        logging.info(f"Calculated utilization for {len(utilization_df)} employees.")
        return utilization_df[['employee_id', 'utilization']]

# Example usage (optional - can be removed or commented out)
if __name__ == '__main__':
    # Create dummy data for testing if db doesn't exist or is empty
    conn_main = get_db_connection()
    if conn_main:
        try:
            # Check if 'employees' table exists and has data
            cursor = conn_main.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employees';")
            table_exists = cursor.fetchone()
            if not table_exists:
                 logging.info("Creating dummy 'employees' table for example usage.")
                 cursor.execute('''
                 CREATE TABLE employees (
                     id INTEGER PRIMARY KEY,
                     name TEXT NOT NULL,
                     department TEXT
                 )
                 ''')
                 cursor.execute("INSERT INTO employees (name, department) VALUES (?, ?)", ('Alice', 'Engineering'))
                 cursor.execute("INSERT INTO employees (name, department) VALUES (?, ?)", ('Bob', 'Marketing'))
                 conn_main.commit()
            else:
                 # Optional: Check if table is empty
                 cursor.execute("SELECT COUNT(*) FROM employees")
                 count = cursor.fetchone()[0]
                 if count == 0:
                     logging.info("Populating empty 'employees' table for example usage.")
                     cursor.execute("INSERT INTO employees (name, department) VALUES (?, ?)", ('Alice', 'Engineering'))
                     cursor.execute("INSERT INTO employees (name, department) VALUES (?, ?)", ('Bob', 'Marketing'))
                     conn_main.commit()
        except sqlite3.Error as e:
            logging.error(f"Error during example setup: {e}")
        finally:
            conn_main.close()

    logging.info("--- Example Query --- ")
    # Example query: Select all from employees table
    example_query = "SELECT * FROM employees;"
    employees_df = execute_query(example_query)

    if employees_df is not None:
        print("\nEmployees Data:")
        print(employees_df)
    else:
        print("\nFailed to retrieve employee data or table is empty.")

    # Example query with parameters
    logging.info("--- Example Query with Parameters --- ")
    param_query = "SELECT * FROM employees WHERE department = ?;"
    engineering_df = execute_query(param_query, params=('Engineering',)) # Note the trailing comma for a single-element tuple

    if engineering_df is not None:
        print("\nEngineering Department:")
        print(engineering_df)
    else:
        print("\nFailed to retrieve engineering data or department not found.")

    # Example usage for new functions
    logging.info("--- Example Performance Data Query ---")
    performance_data = get_performance_data(start_date='2024-01-01', end_date='2024-01-31')
    if performance_data is not None:
        print("\nPerformance Data (Jan 2024):")
        print(performance_data)
    else:
        print("\nFailed to retrieve performance data or table 'charged_hours' might not exist/be empty.")

    logging.info("--- Example Targets Data Query ---")
    # Create dummy targets data if table doesn't exist
    conn_targets = get_db_connection()
    if conn_targets:
        try:
            cursor = conn_targets.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='targets';")
            if not cursor.fetchone():
                logging.info("Creating dummy 'targets' table for example usage.")
                cursor.execute('''
                CREATE TABLE targets (
                    id INTEGER PRIMARY KEY,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    employee_id TEXT,
                    target_utilization REAL,
                    target_hours REAL
                )
                ''')
                # Add sample data
                cursor.execute("INSERT INTO targets (year, month, employee_id, target_utilization, target_hours) VALUES (?, ?, ?, ?, ?)", 
                               (2024, 1, 'emp1', 0.85, 150.0))
                cursor.execute("INSERT INTO targets (year, month, employee_id, target_utilization, target_hours) VALUES (?, ?, ?, ?, ?)", 
                               (2024, 1, 'emp2', 0.90, 160.0))
                conn_targets.commit()
        except sqlite3.Error as e:
            logging.error(f"Error during example targets setup: {e}")
        finally:
            conn_targets.close()
            
    targets_data = get_targets(year=2024, month=1)
    if targets_data is not None:
        print("\nTargets Data (Jan 2024):")
        print(targets_data)
    else:
        print("\nFailed to retrieve targets data or table 'targets' might not exist/be empty.")

    # Create dummy master_file data if table doesn't exist
    conn_master = get_db_connection()
    if conn_master:
        try:
            cursor = conn_master.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='master_file';")
            if not cursor.fetchone():
                logging.info("Creating dummy 'master_file' table for example usage.")
                cursor.execute('''
                CREATE TABLE master_file (
                    id INTEGER PRIMARY KEY,
                    employee_id TEXT,
                    employee_name TEXT,
                    segment TEXT,
                    practice TEXT,
                    title TEXT,
                    project_id TEXT,
                    project_name TEXT,
                    manager_id TEXT,
                    client_name TEXT
                    -- Add other relevant columns from your actual master file
                )
                ''')
                # Add sample data (can be expanded)
                cursor.execute("INSERT INTO master_file (employee_id, employee_name, segment, practice, title, project_id, project_name, manager_id, client_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                               ('emp1', 'Alice', 'SegmentA', 'Cloud', 'Consultant', 'projA', 'Project Alpha', 'mgr1', 'Client X'))
                cursor.execute("INSERT INTO master_file (employee_id, employee_name, segment, practice, title, project_id, project_name, manager_id, client_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                               ('emp2', 'Bob', 'SegmentB', 'Data', 'Senior Consultant', 'projB', 'Project Beta', 'mgr2', 'Client Y'))
                cursor.execute("INSERT INTO master_file (employee_id, employee_name, segment, practice, title, project_id, project_name, manager_id, client_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                               ('emp3', 'Charlie', 'SegmentA', 'Cloud', 'Manager', 'projA', 'Project Alpha', 'mgr1', 'Client X')) 
                conn_master.commit()
        except sqlite3.Error as e:
            logging.error(f"Error during example master_file setup: {e}")
        finally:
            conn_master.close()

    logging.info("--- Example Employee Data Query --- ")
    emp_data = get_employee_data(segment='SegmentA')
    if emp_data is not None:
        print("\nEmployee Data (SegmentA):")
        print(emp_data)
    else:
        print("\nFailed to retrieve employee data or master_file table might not exist/be empty.")

    logging.info("--- Example Project Data Query --- ")
    proj_data = get_project_data(project_id='projA')
    if proj_data is not None:
        print("\nProject Data (projA):")
        print(proj_data)
    else:
        print("\nFailed to retrieve project data or master_file table might not exist/be empty.")

    logging.info("--- Example Utilization Calculation --- ")
    # Example: Calculate utilization for emp1 in Jan 2024
    util_emp1 = calculate_utilization(start_date='2024-01-01', end_date='2024-01-31', employee_id='emp1')
    if util_emp1 is not None:
        print(f"\nUtilization for emp1 (Jan 2024): {util_emp1:.2f}")
    else:
        print("\nCould not calculate utilization for emp1 (Jan 2024). Check data.")

    # Example: Calculate overall utilization for Jan 2024
    util_overall = calculate_utilization(start_date='2024-01-01', end_date='2024-01-31')
    if util_overall is not None:
        print("\nOverall Utilization (Jan 2024):")
        print(util_overall)
    else:
        print("\nCould not calculate overall utilization (Jan 2024). Check data.") 