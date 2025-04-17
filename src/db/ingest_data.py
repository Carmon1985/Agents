import logging
import os
import sys
import time # Import time for basic duration logging

# ---- ADDED: Explicit start print ----
print("Starting ingestion script...")

# Configure logging (ensure level is appropriate, e.g., INFO or DEBUG)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

# Import processor classes
try:
    print("Importing processors using absolute paths from src...")
    from src.db.base_processor import BaseDataProcessor
    from src.db.charged_hours_processor import ChargedHoursIngestion
    from src.db.master_file_processor import MasterFileIngestion
    from src.db.targets_processor import TargetsIngestion
    print("Processors imported successfully.")
except ImportError as e:
    logger.error(f"Failed to import processor classes: {e}", exc_info=True) # Log traceback
    print(f"ERROR: Failed to import processor classes: {e}")
    logger.error("Ensure you are running this script from the project root directory or the src directory is in your PYTHONPATH.")
    exit(1)

# Define paths
DATA_DIR = 'data'
DATABASE_PATH = os.path.join(DATA_DIR, 'database.db')
CHARGED_HOURS_FILE = os.path.join(DATA_DIR, 'dummy_charged_hours.xlsx')
MASTER_FILE_FILE = os.path.join(DATA_DIR, 'dummy_master_file.xlsx')
TARGETS_FILE = os.path.join(DATA_DIR, 'dummy_targets.xlsx')

def run_single_ingestion(ProcessorClass: type[BaseDataProcessor], source_file: str, db_path: str) -> bool:
    """Runs the ingestion process for a single processor class and handles logging."""
    processor_name = ProcessorClass.__name__
    logger.info(f"[{processor_name}] Processing source: {source_file}")
    print(f"Processing {processor_name} from: {source_file}")
    start_time = time.time()
    success = False
    try:
        processor = ProcessorClass(source_file, db_path)
        print(f"  [{processor_name}] Running process()...")
        
        # --- Detailed steps (assuming process calls read, transform, load) ---
        # 1. Read Source
        df_read = processor.read_source()
        if df_read is None:
            logger.error(f"  [{processor_name}] Failed to read source file or file is empty.")
            return False # Stop if read fails
        rows_read = len(df_read)
        logger.info(f"  [{processor_name}] Read {rows_read} rows from source.")
        
        # 2. Transform Data
        df_transformed = processor.transform_data(df_read)
        if df_transformed is None:
            logger.error(f"  [{processor_name}] Data transformation failed.")
            return False # Stop if transform fails
        rows_transformed = len(df_transformed)
        logger.info(f"  [{processor_name}] Transformed {rows_transformed} rows successfully.")
        if rows_read != rows_transformed:
            logger.warning(f"  [{processor_name}] Row count changed during transformation ({rows_read} -> {rows_transformed}). Check logs for details.")
            
        # 3. Load to DB
        load_success = processor.load_to_db(df_transformed)
        if load_success:
            logger.info(f"  [{processor_name}] Successfully loaded {rows_transformed} rows into DB table '{processor.TARGET_TABLE}'.")
        else:
            logger.error(f"  [{processor_name}] Failed to load data into DB table '{processor.TARGET_TABLE}'.")
            
        success = load_success # Overall success depends on loading

    except Exception as e:
        logger.error(f"[{processor_name}] Exception during processing: {e}", exc_info=True)
        print(f"ERROR processing {processor_name}: {e}")
        success = False
        
    end_time = time.time()
    duration = end_time - start_time
    status_msg = "SUCCESS" if success else "FAILED"
    logger.info(f"[{processor_name}] Processing {status_msg} in {duration:.2f} seconds.")
    print(f"  [{processor_name}] Process finished. Success: {success}")
    print("-" * 30)
    return success

def run_ingestion():
    """Runs the ingestion process for all data sources."""
    overall_start_time = time.time()
    logger.info("--- Starting Full Data Ingestion Process ---")
    print("--- Starting Full Data Ingestion Process ---")
    
    # List of processors to run
    processors_to_run = [
        (ChargedHoursIngestion, CHARGED_HOURS_FILE),
        (MasterFileIngestion, MASTER_FILE_FILE),
        (TargetsIngestion, TARGETS_FILE),
    ]
    
    results = []
    for Processor, source_file in processors_to_run:
        result = run_single_ingestion(Processor, source_file, DATABASE_PATH)
        results.append(result)
        
    overall_success = all(results)
    overall_end_time = time.time()
    overall_duration = overall_end_time - overall_start_time
    
    if overall_success:
        logger.info(f"--- Full Data Ingestion Process Completed Successfully in {overall_duration:.2f}s ---")
        print(f"--- Full Data Ingestion Process Completed Successfully in {overall_duration:.2f}s ---")
    else:
        logger.warning(f"--- Full Data Ingestion Process Completed with Errors in {overall_duration:.2f}s ---")
        print(f"--- Full Data Ingestion Process Completed with Errors in {overall_duration:.2f}s ---")

if __name__ == "__main__":
    # Ensure the data directory exists before trying to read from it
    print(f"Checking if data directory '{DATA_DIR}' exists...")
    if not os.path.isdir(DATA_DIR):
        logger.error(f"Data directory '{DATA_DIR}' not found. Please create it and add the necessary dummy Excel files:")
        print(f"ERROR: Data directory '{DATA_DIR}' not found.")
        logger.error(f" - {CHARGED_HOURS_FILE}")
        logger.error(f" - {MASTER_FILE_FILE}")
        logger.error(f" - {TARGETS_FILE}")
        exit(1)
    print(f"Data directory found. Running ingestion...")
    run_ingestion()

# ---- ADDED: Explicit end print ----
print("Ingestion script finished.") 