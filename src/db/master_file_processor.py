import pandas as pd
import logging
import os
import sqlite3

from .data_ingestion import DataIngestion, DEFAULT_FILE_PATHS, DEFAULT_DB_PATH

class MasterFileIngestion(DataIngestion):
    """
    Concrete implementation for ingesting Employee Master File data.
    Reads from an XLSX file, transforms the data, and loads it into the
    'employees' table in the SQLite database.
    """

    # Define potential source column names and their target DB column names
    # Prioritize names based on likelihood or preference if multiple source names map to one target
    COLUMN_MAPPING = {
        'Employee Identifier': 'employee_id',
        'Employee Name': 'employee_name',
        'Status': 'status',
        'Standard Hours Per Week': 'standard_hours_per_week', # Prioritize this
        'Effective STD Hrs per Week': 'standard_hours_per_week', # Alternative
        'Employee Category': 'employee_category',
        'Employee Competency': 'employee_competency', # Prioritize this
        'Primary Skill Group': 'employee_competency', # Alternative
        'Employee Location': 'employee_location', # Prioritize this
        'Office': 'employee_location', # Alternative
        'Employee Billing Rank': 'employee_billing_rank', # Prioritize this
        'Level': 'employee_billing_rank', # Alternative
        'Grade': 'employee_billing_rank', # Alternative
        'Department': 'department', # Prioritize this
        'Practice Area': 'department', # Alternative
        'Region': 'region'
    }
    
    CRITICAL_SOURCE_COLUMNS = [
        'Employee Identifier', 
        'Employee Name', 
        'Status'
    ]
    
    TARGET_TABLE = 'employees'

    def read_source(self) -> pd.DataFrame:
        """Reads the Master File XLSX file into a pandas DataFrame."""
        try:
            # Assuming data is on the first sheet
            df = pd.read_excel(self.source_file_path, sheet_name=0)
            self.logger.info(f"Read {len(df)} rows from {self.source_file_path}")

            # Find which of the potential source columns actually exist in the DataFrame
            self.actual_columns = {k: v for k, v in self.COLUMN_MAPPING.items() if k in df.columns}
            if not self.actual_columns:
                 raise ValueError(f"Source file {self.source_file_path} contains none of the expected columns.")

            # Check if critical columns are present among the found columns
            missing_critical = [col for col in self.CRITICAL_SOURCE_COLUMNS if col not in self.actual_columns]
            if missing_critical:
                 raise ValueError(f"Source file {self.source_file_path} is missing critical columns: {missing_critical}")

            return df
        except FileNotFoundError:
            self.logger.error(f"Source file not found: {self.source_file_path}")
            raise
        except Exception as e:
            self.logger.error(f"Error reading Excel file {self.source_file_path}: {e}")
            raise

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms the raw Master File data."""
        self.logger.debug("Starting data transformation...")
        
        # Select only the columns found in the source file
        source_cols_to_use = list(self.actual_columns.keys())
        df_selected = df[source_cols_to_use].copy()

        # Rename columns based on the mapping derived in read_source
        rename_map = {k: v for k, v in self.actual_columns.items()}
        df_transformed = df_selected.rename(columns=rename_map)
        self.logger.debug("Renamed columns.")

        # --- Data Type Conversion and Cleaning ---
        # Convert standard_hours_per_week to numeric if the column exists
        if 'standard_hours_per_week' in df_transformed.columns:
            df_transformed['standard_hours_per_week'] = pd.to_numeric(df_transformed['standard_hours_per_week'], errors='coerce')
            self.logger.debug("Converted standard_hours_per_week to numeric.")
            
        # Clean ALL string columns (critical and optional) robustly first
        string_cols = [
            'employee_id', 'employee_name', 'status', 'employee_category',
            'employee_competency', 'employee_location', 'employee_billing_rank',
            'department', 'region'
        ]
        for col in string_cols:
            if col in df_transformed.columns:
                # Use fillna before astype, then strip and replace invalid/empty strings with None
                df_transformed[col] = df_transformed[col].fillna('__NA__').astype(str).str.strip()
                df_transformed[col] = df_transformed[col].replace(
                    {'': None, 'None': None, 'nan': None, 'NaT': None, '<NA>': None, '__NA__': None}
                )
        self.logger.debug("Cleaned and standardized all potential string columns.")

        # --- Handle missing values --- 
        initial_rows = len(df_transformed)
        critical_str_cols = ['employee_id', 'employee_name', 'status']
        # Drop rows where ANY critical column is None (after cleaning)
        df_transformed.dropna(subset=critical_str_cols, inplace=True)

        final_rows = len(df_transformed)
        if initial_rows != final_rows:
            self.logger.warning(f"Dropped {initial_rows - final_rows} rows due to missing critical data (ID, Name, or Status). ")

        # --- Final Schema Alignment ---
        # Ensure all target columns exist, adding any missing ones with None/NULL values
        expected_db_cols = [
            'employee_id', 'employee_name', 'status', 'standard_hours_per_week', 
            'employee_category', 'employee_competency', 'employee_location', 
            'employee_billing_rank', 'department', 'region'
        ]
        for col in expected_db_cols:
            if col not in df_transformed.columns:
                df_transformed[col] = None
                self.logger.debug(f"Added missing target column '{col}' with None values.")
                
        # Reorder columns to match the canonical schema order (optional but good practice)
        df_transformed = df_transformed[expected_db_cols]

        self.logger.info("Data transformation completed.")
        return df_transformed

    def load_to_db(self, df: pd.DataFrame):
        """Loads the transformed Master File data into the SQLite employees table."""
        if df.empty:
            self.logger.warning("Transformed DataFrame is empty. No data to load.")
            return
            
        self.logger.info(f"Loading {len(df)} rows into table '{self.TARGET_TABLE}' using 'replace' strategy.")
        
        try:
            df.to_sql(self.TARGET_TABLE, 
                      self.conn, 
                      if_exists='replace', 
                      index=False
                     )
            self.logger.info(f"Successfully loaded data into '{self.TARGET_TABLE}'.")
        except sqlite3.IntegrityError as e:
            # Primary key violations (duplicate employee_id) might occur if source isn't clean
            self.logger.error(f"Database integrity error during load: {e}. Possible duplicate Employee IDs in source data?")
            raise
        except Exception as e:
            self.logger.error(f"Error loading data into table '{self.TARGET_TABLE}': {e}")
            raise

# Allow running this processor directly
if __name__ == '__main__':
    logging.info("Running Master File Ingestion Processor directly...")
    source_path = DEFAULT_FILE_PATHS.get('master_file')
    db_path = DEFAULT_DB_PATH
    
    if not source_path:
        logging.error("Default path for 'master_file' not found.")
    elif not os.path.exists(source_path):
         logging.error(f"Source file not found at default path: {source_path}.")
    else:
        processor = MasterFileIngestion(source_file_path=source_path, db_path=db_path)
        processor.process()
        logging.info("Master File Ingestion Processor finished.") 