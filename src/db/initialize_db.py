import sqlite3
import os
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define database and schema paths relative to the project root
# Assumes the script is run from the project root or the paths are adjusted accordingly
DATABASE_PATH = os.path.join('data', 'operational_data.db')
SCHEMA_PATH = os.path.join('src', 'db', 'schema.sql')


def initialize_database(db_path=DATABASE_PATH, schema_path=SCHEMA_PATH):
    """
    Initializes the SQLite database by creating it if it doesn't exist
    and executing the schema definition script.

    Args:
        db_path (str): The path to the SQLite database file.
        schema_path (str): The path to the SQL schema definition file.
    """
    logging.info(f"Attempting to initialize database at: {db_path}")
    db_dir = os.path.dirname(db_path)

    # Ensure the data directory exists
    try:
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            logging.info(f"Created directory: {db_dir}")
    except OSError as e:
        logging.error(f"Error creating directory {db_dir}: {e}")
        return

    # Check if schema file exists
    if not os.path.exists(schema_path):
        logging.error(f"Schema file not found at: {schema_path}")
        return

    conn = None
    try:
        # Connect to the database (this will create the file if it doesn't exist)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        logging.info(f"Successfully connected to database: {db_path}")

        # Read the schema SQL script
        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        # Execute the entire schema script
        # Using executescript allows multiple SQL statements separated by semicolons
        cursor.executescript(schema_sql)
        conn.commit()
        logging.info(f"Successfully executed schema from: {schema_path}")

    except sqlite3.Error as e:
        logging.error(f"Database error during initialization: {e}")
        # Consider rolling back if partial changes occurred, though executescript is often atomic
        # if conn:
        #     conn.rollback()
    except IOError as e:
        logging.error(f"Error reading schema file {schema_path}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("Database connection closed.")

if __name__ == '__main__':
    # This allows the script to be run directly for initialization
    logging.info("Running database initialization script directly...")
    # Adjust paths if running directly from src/db might change the relative root
    # For simplicity, assume it's run from the project root for now.
    # If needed, calculate project root dynamically:
    # PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    # db_path_abs = os.path.join(PROJECT_ROOT, DATABASE_PATH)
    # schema_path_abs = os.path.join(PROJECT_ROOT, SCHEMA_PATH)
    # initialize_database(db_path_abs, schema_path_abs)
    initialize_database()
    logging.info("Database initialization script finished.") 