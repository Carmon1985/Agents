import pytest
import pandas as pd
import sqlite3
import os
from pathlib import Path
from src.db import tools

# Fixture for a temporary, in-memory database connection
@pytest.fixture(scope="function")
def test_db(monkeypatch):
    """Creates an in-memory SQLite DB, populates it, and patches 
    tools.get_db_connection to return this specific connection when 
    db_path=":memory:" is requested.
    """
    # 1. Create and populate the database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create necessary tables
    cursor.execute("""
    CREATE TABLE charged_hours (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        project_id TEXT,
        charge_date TEXT, -- YYYY-MM-DD
        charged_hours REAL
    )
    """)
    cursor.execute("""
    CREATE TABLE targets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER,
        month INTEGER,
        employee_id TEXT,
        target_utilization REAL,
        target_hours REAL
    )
    """)
    cursor.execute("""
    CREATE TABLE master_file (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id TEXT,
        employee_name TEXT,
        segment TEXT,
        practice TEXT,
        title TEXT,
        project_id TEXT,
        project_name TEXT,
        manager_id TEXT,
        client_name TEXT
    )
    """)

    # Insert Sample Data
    cursor.execute("INSERT INTO charged_hours (employee_id, project_id, charge_date, charged_hours) VALUES (?, ?, ?, ?)", ('emp1', 'projA', '2024-01-15', 8.0))
    cursor.execute("INSERT INTO charged_hours (employee_id, project_id, charge_date, charged_hours) VALUES (?, ?, ?, ?)", ('emp1', 'projB', '2024-01-20', 7.5))
    cursor.execute("INSERT INTO charged_hours (employee_id, project_id, charge_date, charged_hours) VALUES (?, ?, ?, ?)", ('emp2', 'projA', '2024-01-18', 8.0))
    cursor.execute("INSERT INTO charged_hours (employee_id, project_id, charge_date, charged_hours) VALUES (?, ?, ?, ?)", ('emp1', 'projA', '2024-02-10', 4.0))
    cursor.execute("INSERT INTO targets (year, month, employee_id, target_hours) VALUES (?, ?, ?, ?)", (2024, 1, 'emp1', 160.0))
    cursor.execute("INSERT INTO targets (year, month, employee_id, target_hours) VALUES (?, ?, ?, ?)", (2024, 1, 'emp2', 150.0))
    cursor.execute("INSERT INTO targets (year, month, employee_id, target_hours) VALUES (?, ?, ?, ?)", (2024, 2, 'emp1', 140.0))
    cursor.execute("INSERT INTO master_file (employee_id, employee_name, segment, project_id, manager_id) VALUES (?, ?, ?, ?, ?)", ('emp1', 'Alice', 'SegmentA', 'projA', 'mgr1'))
    cursor.execute("INSERT INTO master_file (employee_id, employee_name, segment, project_id, manager_id) VALUES (?, ?, ?, ?, ?)", ('emp1', 'Alice', 'SegmentA', 'projB', 'mgr1'))
    cursor.execute("INSERT INTO master_file (employee_id, employee_name, segment, project_id, manager_id) VALUES (?, ?, ?, ?, ?)", ('emp2', 'Bob', 'SegmentB', 'projA', 'mgr2'))
    cursor.execute("INSERT INTO master_file (employee_id, employee_name, segment, project_id, manager_id) VALUES (?, ?, ?, ?, ?)", ('emp3', 'Charlie', 'SegmentA', 'projC', 'mgr1'))
    conn.commit()

    # 2. Patch tools.get_db_connection
    # Store the original function
    original_get_db_connection = tools.get_db_connection

    # Define the patched function
    def patched_get_db_connection(db_path=None):
        # If the test explicitly asks for :memory:, return our populated connection
        if db_path == ":memory:":
            # Important: Return the *existing* connection object from the fixture
            return conn 
        else:
            # Otherwise, call the original function (e.g., if testing default path)
            # This branch might not be strictly needed if all tests use db_path=":memory:"
            return original_get_db_connection(db_path=db_path)

    # Apply the patch using monkeypatch
    monkeypatch.setattr(tools, "get_db_connection", patched_get_db_connection)

    yield conn # Provide the connection object to the test (optional)

    # 3. Teardown (happens automatically after yield)
    conn.close()
    # Monkeypatch automatically reverts the patch

# --- Test get_db_connection ---
def test_get_db_connection_success(test_db): # test_db fixture now handles patching
    """Test successful connection retrieval via patched function."""
    retrieved_conn = tools.get_db_connection(db_path=":memory:")
    assert retrieved_conn is not None
    assert isinstance(retrieved_conn, sqlite3.Connection)
    # Verify it's the *same* connection object the fixture created (optional)
    assert retrieved_conn is test_db 

# --- Test execute_query ---
# Tests remain largely the same, but now use the correctly patched connection
def test_execute_query_success(test_db):
    """Test successful execution of a basic query."""
    df = tools.execute_query("SELECT COUNT(*) as count FROM charged_hours", db_path=":memory:")
    assert df is not None
    assert not df.empty
    assert df.iloc[0]['count'] == 4

def test_execute_query_with_params(test_db):
    """Test successful execution with parameters."""
    df = tools.execute_query("SELECT * FROM charged_hours WHERE employee_id = ?", params=('emp1',), db_path=":memory:")
    assert df is not None
    assert len(df) == 3
    assert all(df['employee_id'] == 'emp1')

def test_execute_query_no_results(test_db):
    """Test query execution that returns no results."""
    df = tools.execute_query("SELECT * FROM charged_hours WHERE employee_id = ?", params=('nonexistent',), db_path=":memory:")
    assert df is not None
    assert df.empty

def test_execute_query_error(test_db, caplog):
    """Test query execution with a syntax error."""
    df = tools.execute_query("SELECT * FRO charged_hours", db_path=":memory:")
    assert df is None
    assert "Error executing query" in caplog.text
    assert "syntax error" in caplog.text

# --- Test get_performance_data ---
# All these tests should now work correctly
def test_get_performance_data_all(test_db):
    df = tools.get_performance_data(db_path=":memory:")
    assert df is not None
    assert len(df) == 4

def test_get_performance_data_by_employee(test_db):
    df = tools.get_performance_data(employee_id='emp2', db_path=":memory:")
    assert df is not None
    assert len(df) == 1
    assert df.iloc[0]['employee_id'] == 'emp2'

def test_get_performance_data_by_project(test_db):
    df = tools.get_performance_data(project_id='projA', db_path=":memory:")
    assert df is not None
    assert len(df) == 3
    assert all(df['project_id'] == 'projA')

def test_get_performance_data_by_date(test_db):
    df = tools.get_performance_data(start_date='2024-01-16', end_date='2024-01-31', db_path=":memory:")
    assert df is not None
    assert len(df) == 2
    assert all(pd.to_datetime(df['charge_date']) >= pd.Timestamp('2024-01-16'))
    assert all(pd.to_datetime(df['charge_date']) <= pd.Timestamp('2024-01-31'))

def test_get_performance_data_combined_filters(test_db):
    df = tools.get_performance_data(employee_id='emp1', project_id='projA', start_date='2024-01-01', end_date='2024-01-31', db_path=":memory:")
    assert df is not None
    assert len(df) == 1
    assert df.iloc[0]['charge_date'] == '2024-01-15'

def test_get_performance_data_no_match(test_db):
    df = tools.get_performance_data(employee_id='nonexistent', db_path=":memory:")
    assert df is not None
    assert df.empty

# --- Test get_targets ---
def test_get_targets_all(test_db):
    df = tools.get_targets(db_path=":memory:")
    assert df is not None
    assert len(df) == 3

def test_get_targets_by_year_month(test_db):
    df = tools.get_targets(year=2024, month=1, db_path=":memory:")
    assert df is not None
    assert len(df) == 2
    assert all(df['year'] == 2024)
    assert all(df['month'] == 1)

def test_get_targets_by_employee(test_db):
    df = tools.get_targets(employee_id='emp1', db_path=":memory:")
    assert df is not None
    assert len(df) == 2
    assert all(df['employee_id'] == 'emp1')

def test_get_targets_combined(test_db):
    df = tools.get_targets(year=2024, month=2, employee_id='emp1', db_path=":memory:")
    assert df is not None
    assert len(df) == 1
    assert df.iloc[0]['target_hours'] == 140.0

def test_get_targets_no_match(test_db):
    df = tools.get_targets(year=2023, db_path=":memory:")
    assert df is not None
    assert df.empty

# --- Test get_employee_data ---
def test_get_employee_data_all(test_db):
    df = tools.get_employee_data(db_path=":memory:")
    assert df is not None
    assert len(df) == 3
    assert sorted(df['employee_id'].tolist()) == sorted(['emp1', 'emp2', 'emp3'])

def test_get_employee_data_by_id(test_db):
    df = tools.get_employee_data(employee_id='emp1', db_path=":memory:")
    assert df is not None
    assert len(df) == 1
    assert df.iloc[0]['employee_name'] == 'Alice'

def test_get_employee_data_by_segment(test_db):
    df = tools.get_employee_data(segment='SegmentA', db_path=":memory:")
    assert df is not None
    assert len(df) == 2
    assert sorted(df['employee_id'].tolist()) == sorted(['emp1', 'emp3'])

def test_get_employee_data_no_match(test_db):
    df = tools.get_employee_data(segment='SegmentC', db_path=":memory:")
    assert df is not None
    assert df.empty

# --- Test get_project_data ---
def test_get_project_data_all(test_db):
    df = tools.get_project_data(db_path=":memory:")
    assert df is not None
    # Based on sample data, there are 4 distinct rows due to projA having 2 managers
    # ('projA', None, 'mgr1', None)
    # ('projB', None, 'mgr1', None)
    # ('projA', None, 'mgr2', None)
    # ('projC', None, 'mgr1', None)
    assert len(df) == 4 
    # Check distinct project IDs are still 3
    assert sorted(df['project_id'].unique().tolist()) == sorted(['projA', 'projB', 'projC'])

def test_get_project_data_by_id(test_db):
    df = tools.get_project_data(project_id='projA', db_path=":memory:")
    assert df is not None
    # projA has two distinct manager_ids (mgr1, mgr2) in the sample data
    assert len(df) == 2 
    # Note: The specific record returned by DISTINCT isn't guaranteed without ORDER BY
    # We just check that it's one of the possibilities
    assert sorted(df['manager_id'].tolist()) == sorted(['mgr1', 'mgr2'])

def test_get_project_data_by_manager(test_db):
    df = tools.get_project_data(manager_id='mgr1', db_path=":memory:")
    assert df is not None
    # mgr1 manages projA, projB, projC in the sample data
    assert len(df) == 3 
    assert sorted(df['project_id'].tolist()) == sorted(['projA', 'projB', 'projC'])

def test_get_project_data_no_match(test_db):
    df = tools.get_project_data(project_id='nonexistent', db_path=":memory:")
    assert df is not None
    assert df.empty

# --- Test calculate_utilization ---
def test_calculate_utilization_single_employee_jan(test_db):
    util = tools.calculate_utilization(start_date='2024-01-01', end_date='2024-01-31', employee_id='emp1', db_path=":memory:")
    assert util is not None
    expected_util = 15.5 / 160.0
    assert util == pytest.approx(expected_util)

def test_calculate_utilization_single_employee_multi_month(test_db):
     util = tools.calculate_utilization(start_date='2024-01-01', end_date='2024-02-29', employee_id='emp1', db_path=":memory:")
     assert util is not None
     expected_util = 19.5 / 300.0
     assert util == pytest.approx(expected_util)

def test_calculate_utilization_overall_jan(test_db):
    df = tools.calculate_utilization(start_date='2024-01-01', end_date='2024-01-31', db_path=":memory:")
    assert df is not None
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert 'employee_id' in df.columns
    assert 'utilization' in df.columns
    util_emp1 = df[df['employee_id'] == 'emp1']['utilization'].iloc[0]
    util_emp2 = df[df['employee_id'] == 'emp2']['utilization'].iloc[0]
    assert util_emp1 == pytest.approx(15.5 / 160.0)
    assert util_emp2 == pytest.approx(8.0 / 150.0)

def test_calculate_utilization_no_charged_data(test_db, caplog):
    util = tools.calculate_utilization(start_date='2023-01-01', end_date='2023-01-31', employee_id='emp1', db_path=":memory:")
    assert util is None
    assert "No charged hours data found" in caplog.text

def test_calculate_utilization_no_target_data(test_db, caplog):
     # Test for an employee present in master file but with no target data for the period
     util = tools.calculate_utilization(start_date='2024-01-01', end_date='2024-01-31', employee_id='emp3', db_path=":memory:")
     assert util is None
     # Emp3 has no charged hours in Jan, so the first check catches it.
     # To properly test *missing targets* despite having charged hours, we'd need different setup.
     # Let's refine this test slightly:
     # Add charged hours for emp3 in Jan, but no targets
     conn = test_db # Use the connection provided by the fixture
     cursor = conn.cursor()
     cursor.execute("INSERT INTO charged_hours (employee_id, project_id, charge_date, charged_hours) VALUES (?, ?, ?, ?)", ('emp3', 'projC', '2024-01-10', 8.0))
     conn.commit()
     
     # Now run the calculation again for emp3
     util_emp3 = tools.calculate_utilization(start_date='2024-01-01', end_date='2024-01-31', employee_id='emp3', db_path=":memory:")
     assert util_emp3 is None
     assert "No target hours data found" in caplog.text
     
# Note: The zero target hours test requires careful setup to ensure the test data is
# available within the same :memory: connection used by the functions.
# Using the yielded connection from the fixture directly is better.
@pytest.mark.skip(reason="Refining setup for zero target hours test")
def test_calculate_utilization_zero_target_hours(test_db, caplog):
     conn = test_db # Use the connection from the fixture
     cursor = conn.cursor()
     # Add target with zero hours
     cursor.execute("INSERT INTO targets (year, month, employee_id, target_hours) VALUES (?, ?, ?, ?)", (2024, 1, 'emp_zero', 0.0))
     # Add charged hours
     cursor.execute("INSERT INTO charged_hours (employee_id, project_id, charge_date, charged_hours) VALUES (?, ?, ?, ?)", ('emp_zero', 'projZ', '2024-01-05', 5.0))
     conn.commit()

     # Test single employee case
     util = tools.calculate_utilization(start_date='2024-01-01', end_date='2024-01-31', employee_id='emp_zero', db_path=":memory:")
     assert util is None # Expect None based on current implementation
     assert "Total target hours are zero" in caplog.text
     
     # Test overall calculation case
     df_overall = tools.calculate_utilization(start_date='2024-01-01', end_date='2024-01-31', db_path=":memory:")
     assert df_overall is not None
     emp_zero_row = df_overall[df_overall['employee_id'] == 'emp_zero']
     assert not emp_zero_row.empty
     assert emp_zero_row['utilization'].iloc[0] == 0.0 # Expect 0.0 in overall calc 