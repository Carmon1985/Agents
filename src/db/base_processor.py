import pandas as pd
import logging
import sqlite3
import sys
import os
from abc import ABC, abstractmethod
from src.db.schema_setup import get_db_connection # Use the shared connection context manager

class BaseDataProcessor(ABC):
    """Abstract base class for data ingestion processors."""

    # Subclasses MUST define these class attributes
    EXPECTED_COLUMNS = []
    CRITICAL_SOURCE_COLUMNS = []
    COLUMN_MAPPING = {}
    TARGET_TABLE = ""

    def __init__(self, source_file_path: str, db_path: str):
        """Initializes the processor with source and database paths."""
        if not source_file_path or not db_path:
            raise ValueError("Source file path and database path cannot be empty.")
            
        self.source_file_path = source_file_path
        self.db_path = db_path # Stored but get_db_connection uses its own constant
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Initialized processor for source: {self.source_file_path}")

    def read_source(self) -> pd.DataFrame | None:
        """Reads the source XLSX file into a pandas DataFrame. Basic validation."""
        self.logger.info(f"Reading source file: {self.source_file_path}")
        try:
            # Assuming data is on the first sheet
            df = pd.read_excel(self.source_file_path, sheet_name=0)
            self.logger.info(f"Read {len(df)} rows from {self.source_file_path}")

            # --- Validation within read_source --- 
            if df.empty:
                self.logger.warning("Source file is empty.")
                return None # Return None if empty

            # Check for critical columns defined by the subclass
            missing_critical = [col for col in self.CRITICAL_SOURCE_COLUMNS if col not in df.columns]
            if missing_critical:
                 # Log error but return the df for transform_data to potentially handle
                 # Or raise ValueError here if critical columns MUST exist before transform
                 self.logger.error(f"Source file is missing critical columns: {missing_critical}. Transformation might fail.")
                 # raise ValueError(f"Source file {self.source_file_path} is missing critical columns: {missing_critical}")

            # Check if any expected columns are missing (warning)
            missing_expected = [col for col in self.EXPECTED_COLUMNS if col not in df.columns]
            if missing_expected:
                 self.logger.warning(f"Source file is missing some expected (non-critical) columns: {missing_expected}")
                 
            return df
        except FileNotFoundError:
            self.logger.error(f"Source file not found: {self.source_file_path}")
            return None # Return None on error
        except Exception as e:
            self.logger.error(f"Error reading source file {self.source_file_path}: {e}", exc_info=True)
            return None # Return None on error

    @abstractmethod
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame | None:
        """Transforms the raw DataFrame. Must be implemented by subclasses."""
        pass

    def load_to_db(self, df: pd.DataFrame) -> bool:
        """Loads the transformed DataFrame into the target SQLite table."""
        if df is None or df.empty:
            self.logger.warning("Transformed DataFrame is None or empty. No data to load.")
            return False
            
        # Ensure TARGET_TABLE is defined in the subclass
        if not self.TARGET_TABLE:
             self.logger.error("TARGET_TABLE class attribute not defined in subclass.")
             return False
             
        self.logger.info(f"Loading {len(df)} rows into table '{self.TARGET_TABLE}' using 'replace' strategy.")
        
        try:
            # Use the shared connection context manager
            with get_db_connection() as conn:
                df.to_sql(self.TARGET_TABLE, 
                          conn, 
                          if_exists='replace',  # Use replace to match test expectations
                          index=False
                         )
                self.logger.info(f"Successfully loaded data into '{self.TARGET_TABLE}'.")
                return True
        except sqlite3.IntegrityError as e:
            self.logger.error(f"Database integrity error during load into {self.TARGET_TABLE}: {e}. Check for duplicate primary/unique keys.")
            # Re-raise for tests to catch
            raise
        except Exception as e:
            self.logger.error(f"Error loading data into table '{self.TARGET_TABLE}': {e}", exc_info=True)
            return False # Indicate failure

    def process(self) -> bool:
        """Orchestrates the read, transform, and load process."""
        self.logger.info(f"Starting process for {self.source_file_path} -> {self.TARGET_TABLE}")
        df = None
        transformed_df = None
        try:
            df = self.read_source()
            if df is None:
                # Error logged in read_source
                self.logger.error("Process stopped: Failed to read source or source empty.")
                return False
                
            transformed_df = self.transform_data(df)
            if transformed_df is None:
                # Error should be logged in transform_data
                self.logger.error("Process stopped: Data transformation failed or returned None.")
                return False
                
            success = self.load_to_db(transformed_df)
            if success:
                 self.logger.info(f"Process completed successfully for {self.source_file_path}.")
            else:
                # Error logged in load_to_db
                self.logger.error(f"Process failed during database load for {self.source_file_path}.")
            return success
            
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during the process method: {e}", exc_info=True)
            return False 