import sqlite3
import logging
import os
from contextlib import contextmanager

DATABASE_PATH = 'data/database.db'
DATA_DIR = 'data'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    """Provides a database connection, ensuring the data directory exists."""
    conn = None
    try:
        # Ensure the data directory exists
        os.makedirs(DATA_DIR, exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        logger.info(f"Database connection established to {DATABASE_PATH}")
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")

def create_tables():
    """Creates the necessary tables in the SQLite database if they don't exist."""
    table_creation_commands = [
        """
        CREATE TABLE IF NOT EXISTS charged_hours (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            date TEXT NOT NULL, -- Format YYYY-MM-DD
            charged_hours REAL NOT NULL,
            project_code TEXT,
            task_description TEXT,
            UNIQUE(employee_id, date, project_code) -- Example unique constraint
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS master_file (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            date TEXT NOT NULL, -- Assuming capacity can vary monthly/daily, format YYYY-MM-DD
            employee_name TEXT,
            department TEXT,
            capacity_hours REAL NOT NULL, -- Total available hours for the period
            UNIQUE(employee_id, date) -- Ensure one capacity entry per employee per date
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            date TEXT NOT NULL, -- Target period start date, format YYYY-MM-DD
            target_utilization REAL NOT NULL, -- Target utilization percentage (e.g., 85.0 for 85%)
            notes TEXT,
            UNIQUE(employee_id, date)
        );
        """
    ]

    index_creation_commands = [
        "CREATE INDEX IF NOT EXISTS idx_charged_hours_date ON charged_hours (date);",
        "CREATE INDEX IF NOT EXISTS idx_charged_hours_employee ON charged_hours (employee_id);",
        "CREATE INDEX IF NOT EXISTS idx_master_file_date ON master_file (date);",
        "CREATE INDEX IF NOT EXISTS idx_master_file_employee ON master_file (employee_id);",
        "CREATE INDEX IF NOT EXISTS idx_targets_date ON targets (date);",
        "CREATE INDEX IF NOT EXISTS idx_targets_employee ON targets (employee_id);"
    ]

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            logger.info("Creating tables...")
            for command in table_creation_commands:
                cursor.execute(command)
                logger.debug(f"Executed: {command.strip().splitlines()[0]}...")
            logger.info("Tables created successfully (if they didn't exist).")

            logger.info("Creating indexes...")
            for command in index_creation_commands:
                cursor.execute(command)
                logger.debug(f"Executed: {command}")
            logger.info("Indexes created successfully (if they didn't exist).")

            conn.commit()
            logger.info("Database schema setup complete.")

    except sqlite3.Error as e:
        logger.error(f"Database schema creation error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during schema setup: {e}")

if __name__ == "__main__":
    create_tables() 