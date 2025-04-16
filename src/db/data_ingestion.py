import sqlite3
import pandas as pd
import os
import logging
from abc import ABC, abstractmethod

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(module)s] - %(message)s')

# --- Configuration Defaults ---
# Assumes source files are in a 'data/source' directory relative to project root
DEFAULT_SOURCE_DIR = os.path.join('data', 'source')
DEFAULT_DB_PATH = os.path.join('data', 'operational_data.db')

# Define expected source filenames (can be overridden)
DEFAULT_FILE_PATHS = {
    'charged_hours': os.path.join(DEFAULT_SOURCE_DIR, 'charged_hours.csv'),
    'master_file': os.path.join(DEFAULT_SOURCE_DIR, 'master_file.xlsx'),
    'mlp': os.path.join(DEFAULT_SOURCE_DIR, 'mlp.xlsx'),
    'targets': os.path.join(DEFAULT_SOURCE_DIR, 'targets.csv')
}
# --- End Configuration ---

class DataIngestion(ABC):
    """
    Abstract Base Class for data ingestion processes.
    Provides a framework for reading, transforming, and loading data
    from a specific source file into the SQLite database.
    """

    def __init__(self, source_file_path: str, db_path: str = DEFAULT_DB_PATH):
        """
        Initializes the DataIngestion process.

        Args:
            source_file_path (str): Path to the source data file (CSV or XLSX).
            db_path (str): Path to the SQLite database file.
        """
        if not os.path.exists(source_file_path):
            logging.warning(f"Source file not found at initialization: {source_file_path}")
            # We might still proceed if the file is expected to be generated later,
            # but log a warning.
            # raise FileNotFoundError(f"Source file not found: {source_file_path}")
        
        self.source_file_path = source_file_path
        self.db_path = db_path
        self.logger = logging.getLogger(self.__class__.__name__) # Logger specific to the subclass
        self.conn = None
        self.cursor = None

    def _connect_db(self):
        """Establishes a connection to the SQLite database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Enable foreign key support
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.cursor = self.conn.cursor()
            self.logger.debug(f"Successfully connected to database: {self.db_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Error connecting to database {self.db_path}: {e}")
            raise # Re-raise the exception to halt processing if connection fails

    def _close_db(self):
        """Closes the database connection if it's open."""
        if self.conn:
            try:
                self.conn.commit() # Ensure any pending changes are committed
                self.conn.close()
                self.logger.debug("Database connection closed.")
            except sqlite3.Error as e:
                self.logger.error(f"Error closing database connection: {e}")
            finally:
                self.conn = None
                self.cursor = None

    @abstractmethod
    def read_source(self) -> pd.DataFrame:
        """
        Reads the source data file (CSV or XLSX) into a pandas DataFrame.
        Specific implementation depends on the file type and structure.
        Should handle potential file reading errors.

        Returns:
            pd.DataFrame: DataFrame containing the source data.
                         Returns an empty DataFrame or raises error on failure.
        """
        pass

    @abstractmethod
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transforms the raw data from the DataFrame.
        This includes cleaning, renaming columns, type conversions,
        handling missing values, and any other necessary transformations
        to match the database schema.

        Args:
            df (pd.DataFrame): The raw DataFrame read from the source.

        Returns:
            pd.DataFrame: The transformed DataFrame ready for loading.
        """
        pass

    @abstractmethod
    def load_to_db(self, df: pd.DataFrame):
        """
        Loads the transformed data from the DataFrame into the appropriate
        SQLite database table.
        Should handle potential database errors (e.g., constraint violations).
        Consider strategies for handling existing data (e.g., replace, append, update).

        Args:
            df (pd.DataFrame): The transformed DataFrame.
        """
        pass

    def process(self):
        """
        Orchestrates the full ingestion process: connect, read, transform, load, close.
        """
        self.logger.info(f"Starting ingestion process for: {os.path.basename(self.source_file_path)}")
        raw_df = None
        transformed_df = None
        try:
            self._connect_db()
            
            self.logger.info(f"Reading source file: {self.source_file_path}")
            raw_df = self.read_source()
            if raw_df is None or raw_df.empty:
                 self.logger.warning("No data read from source. Skipping transform and load.")
                 return # Exit early if no data

            self.logger.info(f"Transforming data ({len(raw_df)} rows)...")
            transformed_df = self.transform_data(raw_df)
            if transformed_df is None or transformed_df.empty:
                 self.logger.warning("No data after transformation. Skipping load.")
                 return # Exit early if no data

            self.logger.info(f"Loading data ({len(transformed_df)} rows) to database...")
            self.load_to_db(transformed_df)
            
            self.logger.info(f"Successfully completed ingestion for: {os.path.basename(self.source_file_path)}")

        except FileNotFoundError:
            self.logger.error(f"Source file not found during processing: {self.source_file_path}")
        except sqlite3.Error as e:
            self.logger.error(f"Database error during processing: {e}")
            # Attempt to rollback if there was an error during load
            if self.conn:
                try:
                    self.conn.rollback()
                    self.logger.info("Database transaction rolled back due to error.")
                except sqlite3.Error as rb_e:
                    self.logger.error(f"Error during rollback: {rb_e}")
        except Exception as e:
            # Catch any other unexpected errors during the process
            self.logger.exception(f"An unexpected error occurred during processing: {e}") # Use exc_info=True
        finally:
            self._close_db()


# Example Usage (Conceptual - will be implemented in subclasses)
if __name__ == '__main__':
    logging.info("DataIngestion base framework loaded. Run specific processor scripts.")
    # Example:
    # from charged_hours_processor import ChargedHoursIngestion # Assuming this exists
    # charged_hours_processor = ChargedHoursIngestion(DEFAULT_FILE_PATHS['charged_hours'])
    # charged_hours_processor.process() 