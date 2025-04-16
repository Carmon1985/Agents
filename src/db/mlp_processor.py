import pandas as pd
import logging
import os
import sqlite3

from .data_ingestion import DataIngestion, DEFAULT_FILE_PATHS, DEFAULT_DB_PATH

class MLPIngestion(DataIngestion):
    """
    Concrete implementation for ingesting MLP (Master List of Projects) data.
    Reads from an XLSX file, transforms the data, and loads it into the
    'projects' table in the SQLite database.
    """

    # Define potential source column names and their target DB column names
    COLUMN_MAPPING = {
        'Project Identifier': 'project_id',
        'Project Name': 'project_name',
        'Project Status': 'project_status',
        'Project Start Date': 'project_start_date',
        'Project End Date': 'project_end_date', # Prioritize this
        'Overall Deadline Date': 'project_end_date', # Alternative
        'Total Budgeted Hours': 'total_budgeted_hours',
        'Required Primary Skill Category': 'required_primary_skill',
        'Target Resource Count (FTE)': 'target_resource_count'
    }
    
    CRITICAL_SOURCE_COLUMNS = [
        'Project Identifier', 
        'Project Name'
    ]
    
    TARGET_TABLE = 'projects'

    def read_source(self) -> pd.DataFrame:
        """Reads the MLP XLSX file into a pandas DataFrame."""
        try:
            df = pd.read_excel(self.source_file_path, sheet_name=0)
            self.logger.info(f"Read {len(df)} rows from {self.source_file_path}")

            # Find actual columns present in the source
            self.actual_columns = {k: v for k, v in self.COLUMN_MAPPING.items() if k in df.columns}
            if not self.actual_columns:
                 raise ValueError(f"Source file {self.source_file_path} contains none of the expected MLP columns.")

            # Check for critical columns
            missing_critical = [col for col in self.CRITICAL_SOURCE_COLUMNS if col not in self.actual_columns]
            if missing_critical:
                 raise ValueError(f"Source file {self.source_file_path} is missing critical MLP columns: {missing_critical}")

            return df
        except FileNotFoundError:
            self.logger.error(f"Source file not found: {self.source_file_path}")
            raise
        except Exception as e:
            self.logger.error(f"Error reading Excel file {self.source_file_path}: {e}")
            raise

    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transforms the raw MLP data."""
        self.logger.debug("Starting MLP data transformation...")
        
        # Select and rename columns
        source_cols_to_use = list(self.actual_columns.keys())
        df_selected = df[source_cols_to_use].copy()
        rename_map = {k: v for k, v in self.actual_columns.items()}
        df_transformed = df_selected.rename(columns=rename_map)
        self.logger.debug("Renamed columns.")

        # --- Data Type Conversion and Cleaning ---
        # Dates - Handle NaT before formatting
        for date_col in ['project_start_date', 'project_end_date']:
            if date_col in df_transformed.columns:
                df_transformed[date_col] = pd.to_datetime(df_transformed[date_col], errors='coerce')
                # Explicitly convert to string *after* to_datetime, handling NaT
                df_transformed[date_col] = df_transformed[date_col].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
                self.logger.debug(f"Processed and formatted {date_col} to string.")

        # Numeric
        for num_col in ['total_budgeted_hours', 'target_resource_count']:
            if num_col in df_transformed.columns:
                df_transformed[num_col] = pd.to_numeric(df_transformed[num_col], errors='coerce')
                self.logger.debug(f"Converted {num_col} to numeric.")
                
        # Ensure critical IDs/Names are strings and stripped, converting empty/None to actual None
        critical_str_cols = ['project_id', 'project_name']
        for col in critical_str_cols:
             if col in df_transformed.columns:
                 # Apply robust cleaning: fillna first for astype, strip, replace common invalid strings
                 df_transformed[col] = df_transformed[col].fillna('__NA__').astype(str).str.strip()
                 df_transformed[col] = df_transformed[col].replace({'': None, 'None': None, 'nan': None, 'NaT': None, '__NA__': None})
        self.logger.debug("Cleaned and standardized critical string columns.")

        # Convert other text fields to strings, converting empty to None
        for col in ['project_status', 'required_primary_skill']:
            if col in df_transformed.columns:
                 df_transformed[col] = df_transformed[col].fillna('__NA__').astype(str).str.strip()
                 df_transformed[col] = df_transformed[col].replace({'': None, 'None': None, 'nan': None, 'NaT': None, '__NA__': None})
        self.logger.debug("Cleaned and standardized other text columns.")

        # --- Handle missing values --- 
        initial_rows = len(df_transformed)
        # Drop rows where critical columns are None AFTER cleaning
        df_transformed.dropna(subset=critical_str_cols, inplace=True)
        
        final_rows = len(df_transformed)
        if initial_rows != final_rows:
            self.logger.warning(f"Dropped {initial_rows - final_rows} rows due to missing critical MLP data (Project ID or Name). ")

        # --- Final Schema Alignment ---
        expected_db_cols = [
            'project_id', 'project_name', 'project_status', 'project_start_date',
            'project_end_date', 'total_budgeted_hours', 'required_primary_skill',
            'target_resource_count'
        ]
        for col in expected_db_cols:
            if col not in df_transformed.columns:
                df_transformed[col] = None
                self.logger.debug(f"Added missing target column '{col}' with None values.")
                
        df_transformed = df_transformed[expected_db_cols]

        self.logger.info("MLP data transformation completed.")
        return df_transformed

    def load_to_db(self, df: pd.DataFrame):
        """Loads the transformed MLP data into the SQLite projects table."""
        if df.empty:
            self.logger.warning("Transformed MLP DataFrame is empty. No data to load.")
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
            self.logger.error(f"Database integrity error during load: {e}. Possible duplicate Project IDs?")
            raise
        except Exception as e:
            self.logger.error(f"Error loading data into table '{self.TARGET_TABLE}': {e}")
            raise

# Allow running this processor directly
if __name__ == '__main__':
    logging.info("Running MLP Ingestion Processor directly...")
    source_path = DEFAULT_FILE_PATHS.get('mlp')
    db_path = DEFAULT_DB_PATH
    
    if not source_path:
        logging.error("Default path for 'mlp' not found.")
    elif not os.path.exists(source_path):
         logging.error(f"Source file not found at default path: {source_path}.")
    else:
        processor = MLPIngestion(source_file_path=source_path, db_path=db_path)
        processor.process()
        logging.info("MLP Ingestion Processor finished.") 