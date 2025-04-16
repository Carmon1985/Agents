import pandas as pd
import logging
import os
import sqlite3

# Assuming data_ingestion.py is in the same directory or Python path is configured
from .data_ingestion import DataIngestion, DEFAULT_FILE_PATHS, DEFAULT_DB_PATH

class ChargedHoursIngestion(DataIngestion):
    """
    Concrete implementation for ingesting Charged Hours data.
    Reads from a CSV file, transforms the data, and loads it into the
    'charged_hours' table in the SQLite database.
    """

    EXPECTED_COLUMNS = [
        'Employee Identifier', 
        'Project Identifier', 
        'Date Worked', 
        'Charged Hours'
        # 'Employee Name' and 'Project Name' are ignored as per PRD schema need
    ]
    
    TARGET_TABLE = 'charged_hours'

    def read_source(self) -> pd.DataFrame:
        """Reads the Charged Hours XLSX file (first sheet) into a pandas DataFrame."""
        try:
            df = pd.read_excel(self.source_file_path, sheet_name=0)
            self.logger.info(f"Read {len(df)} rows from {self.source_file_path}")
            missing_cols = [col for col in self.EXPECTED_COLUMNS if col not in df.columns]
            if missing_cols:
                self.logger.error(f"Missing expected columns in source file: {missing_cols}")
                raise ValueError(f"Source file {self.source_file_path} is missing required columns: {missing_cols}")
            return df
        except FileNotFoundError:
            self.logger.error(f"Source file not found: {self.source_file_path}")
            raise 
        except Exception as e:
            self.logger.error(f"Error reading Excel file {self.source_file_path}: {e}")
            raise 

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms the raw Charged Hours data."""
        self.logger.debug("Starting data transformation...")
        
        # Select only expected columns first to avoid issues with extra cols
        df_transformed = df[self.EXPECTED_COLUMNS].copy()

        # --- Data Type Conversion (BEFORE renaming) --- 
        # Explicitly infer datetime format
        df_transformed['Date Worked'] = pd.to_datetime(df_transformed['Date Worked'], infer_datetime_format=True, errors='coerce')
        # Convert Charged Hours
        df_transformed['Charged Hours'] = pd.to_numeric(df_transformed['Charged Hours'], errors='coerce')
        self.logger.debug("Converted source data types for date (inferring format) and hours.")

        # --- Rename Columns --- 
        df_transformed.rename(columns={
            'Employee Identifier': 'employee_id',
            'Project Identifier': 'project_id',
            'Date Worked': 'charge_date',
            'Charged Hours': 'charged_hours'
        }, inplace=True)
        self.logger.debug("Renamed columns.")

        # --- Clean IDs (Convert to string, strip, replace specific non-values with None) ---
        for col in ['employee_id', 'project_id']:
            if col in df_transformed.columns:
                df_transformed[col] = df_transformed[col].fillna('__NA__').astype(str).str.strip()
                df_transformed[col] = df_transformed[col].replace(
                    {'': None, 'None': None, 'nan': None, 'NaT': None, '<NA>': None, '__NA__': None}
                )
        self.logger.debug("Cleaned and standardized ID columns.")

        # --- Handle missing/invalid values --- 
        initial_rows = len(df_transformed)
        critical_cols = ['employee_id', 'project_id', 'charge_date', 'charged_hours']
        
        # Log check BEFORE dropna
        null_check_before = df_transformed[critical_cols].isnull().sum()
        self.logger.debug(f"Null check BEFORE dropna:\n{null_check_before}")
        rows_to_be_dropped = df_transformed[df_transformed[critical_cols].isnull().any(axis=1)]
        if not rows_to_be_dropped.empty:
             self.logger.debug(f"Rows potentially being dropped by dropna:\n{rows_to_be_dropped}")

        # Drop rows where ANY critical column is None/NaT/NaN
        df_transformed.dropna(subset=critical_cols, inplace=True)
        
        final_rows = len(df_transformed)
        if initial_rows != final_rows:
            self.logger.warning(f"Dropped {initial_rows - final_rows} rows due to missing/invalid critical values.")
        
        # Log check AFTER dropna
        null_check_after = df_transformed[critical_cols].isnull().sum()
        self.logger.debug(f"Null check AFTER dropna:\n{null_check_after}")

        # --- Final Formatting --- 
        if not df_transformed.empty:
            # Ensure date column exists and format it
            if 'charge_date' in df_transformed.columns:
                 # It should be datetime already if not NaT, format directly
                 df_transformed['charge_date'] = df_transformed['charge_date'].dt.strftime('%Y-%m-%d')
                 self.logger.debug("Formatted charge_date as YYYY-MM-DD string.")

        self.logger.info("Data transformation completed.")
        return df_transformed

    def load_to_db(self, df: pd.DataFrame):
        """Loads the transformed Charged Hours data into the SQLite database."""
        if df.empty:
            self.logger.warning("Transformed DataFrame is empty. No data to load.")
            return
            
        self.logger.info(f"Loading {len(df)} rows into table '{self.TARGET_TABLE}' using 'replace' strategy.")
        
        try:
            df.to_sql(self.TARGET_TABLE, 
                      self.conn, 
                      if_exists='replace', 
                      index=False,
                     )
            self.logger.info(f"Successfully loaded data into '{self.TARGET_TABLE}'.")
        except sqlite3.IntegrityError as e:
            self.logger.error(f"Database integrity error during load: {e}. Check foreign key references (employee_id, project_id). Ensure referenced employees/projects exist.")
            raise # Re-raise to be caught by the main process method for rollback
        except Exception as e:
            self.logger.error(f"Error loading data into table '{self.TARGET_TABLE}': {e}")
            raise # Re-raise

# Allow running this processor directly for testing or manual execution
if __name__ == '__main__':
    logging.info("Running Charged Hours Ingestion Processor directly...")
    
    # Use default paths defined in the base class config
    source_path = DEFAULT_FILE_PATHS.get('charged_hours')
    db_path = DEFAULT_DB_PATH
    
    if not source_path:
        logging.error("Default path for 'charged_hours' not found in configuration.")
    elif not os.path.exists(source_path) or not source_path.endswith('.xlsx'):
         logging.error(f"Source Excel file not found at default path: {source_path}. Ensure it ends with .xlsx")
    else:
        processor = ChargedHoursIngestion(source_file_path=source_path, db_path=db_path)
        processor.process() 
        logging.info("Charged Hours Ingestion Processor finished.") 