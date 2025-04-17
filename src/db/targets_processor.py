import pandas as pd
import logging
import os
import sqlite3
import sys
from src.db.schema_setup import get_db_connection # Import the shared connection function
from .base_processor import BaseDataProcessor # Assuming a base class exists

# Add logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

from .data_ingestion import DataIngestion, DEFAULT_FILE_PATHS, DEFAULT_DB_PATH

# Define expected columns and renaming map to match dummy_targets.xlsx headers
EXPECTED_COLUMNS = [
    'Employee Identifier',
    'Target Date',
    'Target Utilization Pct',
    'Notes'
]
CRITICAL_SOURCE_COLUMNS = [
    'Employee Identifier',
    'Target Date',
    'Target Utilization Pct'
]
COLUMN_MAPPING = {
    'Employee Identifier': 'employee_id',
    'Target Date': 'date',
    'Target Utilization Pct': 'target_utilization',
    'Notes': 'notes'
}

class TargetsIngestion(BaseDataProcessor):
    """Handles ingestion of Targets data from XLSX to SQLite."""

    # Define constants specific to this processor
    EXPECTED_COLUMNS = EXPECTED_COLUMNS
    CRITICAL_SOURCE_COLUMNS = CRITICAL_SOURCE_COLUMNS
    COLUMN_MAPPING = COLUMN_MAPPING
    TARGET_TABLE = 'targets'

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

        # 1. Handle Dates ('Target Date')
        date_col = 'Target Date'
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
            self.logger.error(f"Critical date column '{date_col}' not found.")
            return None

        # 2. Handle Numeric Types ('Target Utilization Pct')
        numeric_col = 'Target Utilization Pct'
        if numeric_col in df.columns:
            try:
                df[numeric_col] = pd.to_numeric(df[numeric_col], errors='coerce')
                # Validate range (e.g., 0-100)
                # Check for NaN before comparison
                valid_range_mask = df[numeric_col].between(0, 100, inclusive='both')
                if not df[numeric_col].isna().all() and not valid_range_mask[~df[numeric_col].isna()].all():
                     self.logger.warning(f"Column '{numeric_col}' contains values outside the 0-100 range.")
                     # Decide if invalid values should be dropped or capped
                     # df.loc[~valid_range_mask, numeric_col] = None # Option: Set invalid to NaN
                     # df[numeric_col] = df[numeric_col].clip(0, 100) # Option: Cap values
                original_count = len(df)
                df.dropna(subset=[numeric_col], inplace=True) # Drop rows where conversion failed (NaN)
                if len(df) < original_count:
                    self.logger.warning(f"Dropped {original_count - len(df)} rows due to invalid numeric format or out-of-range values in '{numeric_col}'.")
                self.logger.debug(f"Successfully converted '{numeric_col}' to numeric.")
            except Exception as e:
                 self.logger.error(f"Error converting column '{numeric_col}' to numeric: {e}", exc_info=True)
                 return None
        else:
             self.logger.error(f"Critical numeric column '{numeric_col}' not found.")
             return None

        # 3. Handle String Types
        string_cols = ['Employee Identifier', 'Notes']
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna('')
            else:
                 if col in self.EXPECTED_COLUMNS and col not in self.CRITICAL_SOURCE_COLUMNS:
                    self.logger.warning(f"Expected string column '{col}' not found.")

        # 4. Rename columns
        df_renamed = df.rename(columns=self.COLUMN_MAPPING)
        self.logger.debug(f"Columns renamed using mapping: {self.COLUMN_MAPPING}")

        # 5. Select final columns based on the target DB schema
        final_columns = [db_col for db_col in self.COLUMN_MAPPING.values() if db_col in df_renamed.columns]
        df_final = df_renamed[final_columns]
        self.logger.debug(f"Selected final columns for DB: {final_columns}")

        self.logger.info("Data transformation completed successfully.")
        return df_final

# Main execution block
if __name__ == "__main__":
    logger.info("[targets_processor] - Running Targets Ingestion Processor directly...")

    # --- Argument Handling ---
    input_file_path = None
    if len(sys.argv) > 1:
        input_file_path = sys.argv[1]
        logger.info(f"Input file path provided via argument: {input_file_path}")
    else:
        default_path = os.path.join("data", "source", "targets.xlsx") # Define default
        logger.warning(f"No input file path provided via argument. Using default: {default_path}")
        input_file_path = default_path
        
    db_path = DEFAULT_DB_PATH
    logger.info(f"Using database path: {db_path}")

    if not os.path.exists(input_file_path):
        logger.error(f"Source Excel file not found at path: {input_file_path}. Please provide a valid path.")
        sys.exit(1)
        
    # Instantiate and run the processor (using only expected init args)
    processor = TargetsIngestion(
        source_file_path=input_file_path, 
        db_path=db_path
    )
    # Use the correct method name
    processor.process()
    logger.info("Targets Ingestion Processor finished.") 