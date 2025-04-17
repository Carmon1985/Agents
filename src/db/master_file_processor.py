import pandas as pd
import logging
import sqlite3
import sys
from .base_processor import BaseDataProcessor # Assuming a base class exists

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

class MasterFileIngestion(BaseDataProcessor):
    """Handles ingestion of Master File data (capacity, employee info) from XLSX to SQLite."""

    # Define source columns expected in the Excel file
    # Adjusted based on previous errors and schema_setup
    EXPECTED_COLUMNS = [
        'Employee Identifier', # Changed from 'Employee ID'
        'Date',                # Keep as 'Date' if this is the source column
        'Capacity Hours',
        'Employee Name',
        'Department',
        # 'Status' # Include if actually present and needed, otherwise remove
    ]
    # Define columns critical for validation
    CRITICAL_SOURCE_COLUMNS = [
        'Employee Identifier',
        'Date',
        'Capacity Hours'
        # Add 'Status' here ONLY if it's truly critical and expected
    ]
    # Map source columns to database columns
    COLUMN_MAPPING = {
        'Employee Identifier': 'employee_id',
        'Date': 'date',
        'Capacity Hours': 'capacity_hours',
        'Employee Name': 'employee_name',
        'Department': 'department'
        # 'Status': 'status' # Add mapping ONLY if 'status' column exists in DB schema
    }
    # Define the target database table
    TARGET_TABLE = 'master_file'

    # --- The conflicting __init__, validate_data, save_to_db, process methods are removed --- 
    # --- Assuming they are handled by BaseDataProcessor or were incorrect additions ---

    # Keep the original read_source if it existed, or rely on BaseDataProcessor
    # def read_source(self) -> pd.DataFrame:
    #     """Reads the Master File XLSX file into a pandas DataFrame."""
    #     # ... (Implementation likely involves pd.read_excel(self.source_file_path)) ...
    #     # Check for critical columns here as per the ValueError
    #     df = super().read_source()
    #     missing_critical = [col for col in self.CRITICAL_SOURCE_COLUMNS if col not in df.columns]
    #     if missing_critical:
    #          raise ValueError(f"Source file {self.source_file_path} is missing critical columns: {missing_critical}")
    #     return df

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms the raw DataFrame: parses dates, converts types, renames columns."""
        if df is None:
            self.logger.warning("Input DataFrame for transformation is None.")
            return None

        self.logger.info(f"Starting transformation for {self.__class__.__name__}...")

        # Ensure critical columns are present
        missing_critical = [col for col in self.CRITICAL_SOURCE_COLUMNS if col not in df.columns]
        if missing_critical:
            self.logger.error(f"Critical columns missing for transformation: {missing_critical}")
            return None

        # 1. Handle Dates ('Date')
        date_col = 'Date'
        if date_col in df.columns:
            try:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce', infer_datetime_format=True)
                original_count = len(df)
                df.dropna(subset=[date_col], inplace=True)
                if len(df) < original_count:
                    self.logger.warning(f"Dropped {original_count - len(df)} rows due to invalid date formats in '{date_col}'.")
                df[date_col] = df[date_col].dt.strftime('%Y-%m-%d')
                self.logger.debug(f"Successfully parsed and formatted '{date_col}'.")
            except Exception as e:
                self.logger.error(f"Error processing date column '{date_col}': {e}", exc_info=True)
                return None
        else:
            # This check might be redundant if Date is in CRITICAL_SOURCE_COLUMNS
            self.logger.error(f"Critical date column '{date_col}' not found.")
            return None

        # 2. Handle Numeric Types ('Capacity Hours')
        numeric_col = 'Capacity Hours'
        if numeric_col in df.columns:
            try:
                df[numeric_col] = pd.to_numeric(df[numeric_col], errors='coerce')
                if (df[numeric_col] <= 0).any():
                    self.logger.warning(f"Column '{numeric_col}' contains non-positive values.")
                original_count = len(df)
                df.dropna(subset=[numeric_col], inplace=True)
                if len(df) < original_count:
                     self.logger.warning(f"Dropped {original_count - len(df)} rows due to invalid numeric format in '{numeric_col}'.")
                self.logger.debug(f"Successfully converted '{numeric_col}' to numeric.")
            except Exception as e:
                 self.logger.error(f"Error converting column '{numeric_col}' to numeric: {e}", exc_info=True)
                 return None
        else:
             # This check might be redundant if Capacity Hours is critical
             self.logger.error(f"Critical numeric column '{numeric_col}' not found.")
             return None

        # 3. Handle String Types
        string_cols = ['Employee Identifier', 'Employee Name', 'Department'] # Add 'Status' if needed
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna('')
            else:
                # Log warning only if column is expected but not critical
                if col in self.EXPECTED_COLUMNS and col not in self.CRITICAL_SOURCE_COLUMNS:
                    self.logger.warning(f"Expected string column '{col}' not found.")

        # 4. Rename columns
        df_renamed = df.rename(columns=self.COLUMN_MAPPING)
        self.logger.debug(f"Columns renamed using mapping: {self.COLUMN_MAPPING}")

        # 5. Select final columns
        final_columns = [db_col for db_col in self.COLUMN_MAPPING.values() if db_col in df_renamed.columns]
        df_final = df_renamed[final_columns]
        self.logger.debug(f"Selected final columns for DB: {final_columns}")

        self.logger.info("Data transformation completed successfully.")
        return df_final

    # Keep the original load_to_db if it existed, or rely on BaseDataProcessor
    # def load_to_db(self, df: pd.DataFrame) -> bool:
    #    return super().load_to_db(df)

# Main execution block (for direct testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info("Running MasterFileIngestion directly for testing...")

    dummy_source_file = 'data/dummy_master_file.xlsx'
    dummy_db_file = 'data/test_database.db'

    import os
    if not os.path.exists(dummy_source_file):
         logger.error(f"Dummy source file not found: {dummy_source_file}")
         sys.exit(1)

    processor = MasterFileIngestion(source_file_path=dummy_source_file, db_path=dummy_db_file)

    logger.info("Calling processor.process()...")
    try:
        # Assuming process() exists in BaseDataProcessor
        success = processor.process()
        if success:
            logger.info("Direct test run completed successfully.")
        else:
            logger.error("Direct test run failed.")
    except AttributeError:
         logger.error("The 'process' method might be missing (potentially in BaseDataProcessor).")
    except Exception as e:
        logger.error(f"An error occurred during direct test run: {e}", exc_info=True)