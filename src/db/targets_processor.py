import pandas as pd
import logging
import os
import sqlite3

from .data_ingestion import DataIngestion, DEFAULT_FILE_PATHS, DEFAULT_DB_PATH

class TargetsIngestion(DataIngestion):
    """
    Concrete implementation for ingesting Targets data.
    Reads from an XLSX file, transforms the data based on defined dimensions
    and metrics, and loads it into the 'targets' table.
    """

    # Define source column names and their target DB column names
    COLUMN_MAPPING = {
        'Target Year': 'target_year',
        'Target Month': 'target_month',
        'Employee Category': 'employee_category',
        'Employee Competency': 'employee_competency',
        'Employee Location': 'employee_location',
        'Employee Billing Rank': 'employee_billing_rank',
        'Target Utilization Percentage': 'target_utilization_percentage',
        'Target Charged Hours per FTE': 'target_charged_hours_per_fte', # Optional
        'Target Headcount (FTE)': 'target_headcount_fte' # Optional
    }
    
    # All dimension columns are critical as they form the composite PK
    CRITICAL_SOURCE_COLUMNS = [
        'Target Year', 
        'Target Month', 
        'Employee Category', 
        'Employee Competency', 
        'Employee Location', 
        'Employee Billing Rank'
    ]
    
    TARGET_TABLE = 'targets'

    def read_source(self) -> pd.DataFrame:
        """Reads the Targets XLSX file (first sheet) into a pandas DataFrame."""
        try:
            # Read from Excel file, assuming data is on the first sheet
            df = pd.read_excel(self.source_file_path, sheet_name=0)
            self.logger.info(f"Read {len(df)} rows from {self.source_file_path}")

            # Find actual columns present in the source file
            self.actual_columns = {k: v for k, v in self.COLUMN_MAPPING.items() if k in df.columns}
            if not self.actual_columns:
                 raise ValueError(f"Source file {self.source_file_path} contains none of the expected Targets columns.")

            # Check if all critical dimension columns are present
            missing_critical = [col for col in self.CRITICAL_SOURCE_COLUMNS if col not in self.actual_columns]
            if missing_critical:
                 raise ValueError(f"Source file {self.source_file_path} is missing critical dimension columns required for primary key: {missing_critical}")

            return df
        except FileNotFoundError:
            self.logger.error(f"Source file not found: {self.source_file_path}")
            raise
        except Exception as e:
            # Catch broader exceptions that might occur with Excel reading (e.g., xlrd missing, file corruption)
            self.logger.error(f"Error reading Excel file {self.source_file_path}: {e}")
            raise

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms the raw Targets data."""
        self.logger.debug("Starting Targets data transformation...")
        
        # Select only the columns found in the source file
        source_cols_to_use = list(self.actual_columns.keys())
        df_selected = df[source_cols_to_use].copy()

        # Rename columns based on the mapping
        rename_map = {k: v for k, v in self.actual_columns.items()}
        df_transformed = df_selected.rename(columns=rename_map)
        self.logger.debug("Renamed columns.")

        # --- Data Type Conversion and Cleaning ---
        # Convert year and month to integers
        for col in ['target_year', 'target_month']:
            if col in df_transformed.columns:
                # Use Int64 to handle potential NaNs before dropping
                df_transformed[col] = pd.to_numeric(df_transformed[col], errors='coerce').astype('Int64')
                self.logger.debug(f"Converted {col} to integer.")

        # Convert dimension columns to strings and strip whitespace, handling None/NaN
        dimension_cols = ['employee_category', 'employee_competency', 'employee_location', 'employee_billing_rank']
        for col in dimension_cols:
             if col in df_transformed.columns:
                 df_transformed[col] = df_transformed[col].fillna('__NA__').astype(str).str.strip()
                 df_transformed[col] = df_transformed[col].replace({'': None, 'None': None, 'nan': None, 'NaT': None, '__NA__': None})
        self.logger.debug("Cleaned dimension string columns.")
                 
        # Convert target metric columns to numeric (REAL)
        metric_cols = ['target_utilization_percentage', 'target_charged_hours_per_fte', 'target_headcount_fte']
        for col in metric_cols:
            if col in df_transformed.columns:
                df_transformed[col] = pd.to_numeric(df_transformed[col], errors='coerce')
                self.logger.debug(f"Converted {col} to numeric.")

        # --- Handle missing critical values (PK components) --- 
        initial_rows = len(df_transformed)
        critical_db_cols = [
            'target_year', 'target_month', 'employee_category', 
            'employee_competency', 'employee_location', 'employee_billing_rank'
        ]
        # Drop rows where any critical column is None/NaT AFTER conversions and cleaning
        df_transformed.dropna(subset=critical_db_cols, inplace=True)
        
        final_rows = len(df_transformed)
        if initial_rows != final_rows:
            self.logger.warning(f"Dropped {initial_rows - final_rows} rows due to missing critical dimension data required for primary key. ")

        # --- Final Schema Alignment ---
        expected_db_cols = list(self.COLUMN_MAPPING.values())
        for col in expected_db_cols:
            if col not in df_transformed.columns:
                df_transformed[col] = None # Add missing optional metric columns
                self.logger.debug(f"Added missing target column '{col}' with None values.")
        
        # Ensure final integer types for PK after dropping NaNs
        for col in ['target_year', 'target_month']:
             if col in df_transformed.columns:
                 df_transformed[col] = df_transformed[col].astype(int)
                 
        # Reorder columns
        df_transformed = df_transformed[expected_db_cols]

        self.logger.info("Targets data transformation completed.")
        return df_transformed

    def load_to_db(self, df: pd.DataFrame):
        """Loads the transformed Targets data into the SQLite targets table."""
        if df.empty:
            self.logger.warning("Transformed Targets DataFrame is empty. No data to load.")
            return
            
        self.logger.info(f"Loading {len(df)} rows into table '{self.TARGET_TABLE}' using 'replace' strategy.")
        
        try:
            df.to_sql(self.TARGET_TABLE, 
                      self.conn, 
                      if_exists='replace', 
                      index=False, # Crucial for composite primary key
                     )
            self.logger.info(f"Successfully loaded data into '{self.TARGET_TABLE}'.")
        except sqlite3.IntegrityError as e:
            # This would likely indicate duplicate dimension combinations in the source file
            self.logger.error(f"Database integrity error during load: {e}. Possible duplicate dimension combinations (Year, Month, Category, etc.) in source data?")
            raise
        except Exception as e:
            self.logger.error(f"Error loading data into table '{self.TARGET_TABLE}': {e}")
            raise

# Allow running this processor directly
if __name__ == '__main__':
    logging.info("Running Targets Ingestion Processor directly...")
    # Adjusted to expect .xlsx by default
    source_path = DEFAULT_FILE_PATHS.get('targets') 
    db_path = DEFAULT_DB_PATH
    
    if not source_path:
        logging.error("Default path for 'targets' not found.")
    # Update the expected extension in the check and error message
    elif not os.path.exists(source_path) or not source_path.endswith('.xlsx'): 
         logging.error(f"Source Excel file not found at expected path: {source_path}. Ensure it ends with .xlsx")
    else:
        processor = TargetsIngestion(source_file_path=source_path, db_path=db_path)
        processor.process()
        logging.info("Targets Ingestion Processor finished.") 