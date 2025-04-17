import pandas as pd
import logging
import os
import sqlite3
import sys
from src.db.schema_setup import get_db_connection # Import the shared connection function
from .base_processor import BaseDataProcessor # Assuming a base class exists

# Assuming data_ingestion.py is in the same directory or Python path is configured
try:
    # This works when run as module: python -m src.db.charged_hours_processor ...
    from .data_ingestion import DataIngestion, DEFAULT_DB_PATH
except ImportError:
    # This works when run as script: python src/db/charged_hours_processor.py ...
    # Requires src/ to be in PYTHONPATH or run from root with src/ prepended
    from data_ingestion import DataIngestion, DEFAULT_DB_PATH

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class ChargedHoursIngestion(BaseDataProcessor):
    """Handles ingestion of Charged Hours data from XLSX to SQLite."""

    # Define source columns expected in the Excel file
    EXPECTED_COLUMNS = [
        'Employee Identifier', # Changed from 'Employee ID'
        'Date Worked',         # Changed from 'Date'
        'Hours Charged',       # Changed from 'Charged Hours'
        'Project Code',
        'Task Description'
    ]
    # Define columns critical for validation
    CRITICAL_SOURCE_COLUMNS = [
        'Employee Identifier',
        'Date Worked',
        'Hours Charged'
    ]
    # Map source columns to database columns
    COLUMN_MAPPING = {
        'Employee Identifier': 'employee_id',
        'Date Worked': 'date',
        'Hours Charged': 'charged_hours',
        'Project Code': 'project_code',
        'Task Description': 'task_description'
    }
    # Define the target database table
    TARGET_TABLE = 'charged_hours'

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms the raw DataFrame: parses dates, converts types, renames columns."""
        if df is None:
            self.logger.warning("Input DataFrame for transformation is None.")
            return None

        self.logger.info(f"Starting transformation for {self.__class__.__name__}...")

        # Ensure critical columns are present before proceeding
        missing_critical = [col for col in self.CRITICAL_SOURCE_COLUMNS if col not in df.columns]
        if missing_critical:
            self.logger.error(f"Critical columns missing for transformation: {missing_critical}")
            # Optionally, raise an error or return None depending on desired behavior
            # raise ValueError(f"Critical columns missing: {missing_critical}")
            return None

        # 1. Handle Dates ('Date Worked')
        date_col = 'Date Worked' # Use the correct source column name
        try:
            # Convert to datetime objects, coercing errors to NaT (Not a Time)
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce', infer_datetime_format=True)
            # Drop rows where date conversion failed
            original_count = len(df)
            df.dropna(subset=[date_col], inplace=True)
            if len(df) < original_count:
                 self.logger.warning(f"Dropped {original_count - len(df)} rows due to invalid date formats in '{date_col}'.")
            # Format dates as YYYY-MM-DD strings for SQLite compatibility
            df[date_col] = df[date_col].dt.strftime('%Y-%m-%d')
            self.logger.debug(f"Successfully parsed and formatted '{date_col}'.")
        except KeyError:
             self.logger.error(f"Date column '{date_col}' not found in DataFrame.")
             return None
        except Exception as e:
            self.logger.error(f"Error processing date column '{date_col}': {e}", exc_info=True)
            return None

        # 2. Handle Numeric Types ('Hours Charged')
        numeric_col = 'Hours Charged' # Use the correct source column name
        if numeric_col in df.columns:
            try:
                df[numeric_col] = pd.to_numeric(df[numeric_col], errors='coerce')
                # Optional: Handle negative values if needed
                if (df[numeric_col] < 0).any():
                    self.logger.warning(f"Column '{numeric_col}' contains negative values.")
                # Drop rows where numeric conversion failed
                original_count = len(df)
                df.dropna(subset=[numeric_col], inplace=True)
                if len(df) < original_count:
                    self.logger.warning(f"Dropped {original_count - len(df)} rows due to invalid numeric format in '{numeric_col}'.")
                self.logger.debug(f"Successfully converted '{numeric_col}' to numeric.")
            except Exception as e:
                 self.logger.error(f"Error converting column '{numeric_col}' to numeric: {e}", exc_info=True)
                 # Decide how to handle: return None, drop column, fill with 0?
                 return None # Safest default
        else:
            self.logger.warning(f"Numeric column '{numeric_col}' not found, skipping conversion.")

        # 3. Handle String Types (and fill NaNs)
        string_cols = ['Employee Identifier', 'Project Code', 'Task Description']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna('') # Ensure string type, fill missing
            else:
                 self.logger.warning(f"Expected string column '{col}' not found.")

        # 4. Rename columns to match DB schema using COLUMN_MAPPING
        df_renamed = df.rename(columns=self.COLUMN_MAPPING)
        self.logger.debug(f"Columns renamed using mapping: {self.COLUMN_MAPPING}")

        # 5. Select only the columns defined in the mapping's values (target DB columns)
        final_columns = [db_col for db_col in self.COLUMN_MAPPING.values() if db_col in df_renamed.columns]
        df_final = df_renamed[final_columns]
        self.logger.debug(f"Selected final columns for DB: {final_columns}")

        self.logger.info("Data transformation completed successfully.")
        return df_final

# Main execution block (optional, for direct testing)
if __name__ == "__main__":
    # Example of how to run this processor directly
    logging.basicConfig(level=logging.DEBUG) # Set to DEBUG for detailed logs
    logger = logging.getLogger(__name__)
    logger.info("Running ChargedHoursIngestion directly for testing...")

    # Create dummy data file path and DB path
    # IMPORTANT: Replace with actual paths to your dummy files for testing
    dummy_source_file = 'data/dummy_charged_hours.xlsx' # Path to your test Excel file
    dummy_db_file = 'data/test_database.db'           # Path to a test database file

    # Ensure dummy file exists (basic check)
    import os
    if not os.path.exists(dummy_source_file):
         logger.error(f"Dummy source file not found: {dummy_source_file}")
         sys.exit(1)

    # Create an instance of the processor
    processor = ChargedHoursIngestion(source_file_path=dummy_source_file, db_path=dummy_db_file)

    # Run the process method (assuming it's defined in BaseDataProcessor)
    logger.info("Calling processor.process()...")
    try:
        success = processor.process() # process() likely calls read_source, transform_data, load_to_db
        if success:
            logger.info("Direct test run completed successfully.")
        else:
            logger.error("Direct test run failed.")
    except AttributeError:
        logger.error("The 'process' method might be missing (potentially in BaseDataProcessor).")
        logger.error("Cannot run direct test without a .process() method.")
    except Exception as e:
        logger.error(f"An error occurred during direct test run: {e}", exc_info=True)