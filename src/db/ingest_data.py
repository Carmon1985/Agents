import logging
import os
import sys # Added for explicit prints

# ---- ADDED: Explicit start print ----
print("Starting ingestion script...")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout) # Ensure logging goes to stdout
logger = logging.getLogger(__name__)

# Import processor classes using absolute imports from src
try:
    print("Importing processors using absolute paths from src...")
    # Use absolute imports assuming script is run as module from root
    from src.db.charged_hours_processor import ChargedHoursIngestion
    from src.db.master_file_processor import MasterFileIngestion
    from src.db.targets_processor import TargetsIngestion
    print("Processors imported successfully.")
except ImportError as e:
    logger.error(f"Failed to import processor classes: {e}")
    print(f"ERROR: Failed to import processor classes: {e}")
    logger.error("Ensure you are running this script from the project root directory or the src directory is in your PYTHONPATH.")
    exit(1)

# Define paths
DATA_DIR = 'data'
DATABASE_PATH = os.path.join(DATA_DIR, 'database.db') # Define DB Path
CHARGED_HOURS_FILE = os.path.join(DATA_DIR, 'dummy_charged_hours.xlsx')
MASTER_FILE_FILE = os.path.join(DATA_DIR, 'dummy_master_file.xlsx')
TARGETS_FILE = os.path.join(DATA_DIR, 'dummy_targets.xlsx')

def run_ingestion():
    """Runs the ingestion process for all data sources with explicit error catching and prints."""
    ingestion_success = True # Track overall success

    logger.info("--- Starting Data Ingestion Process ---")
    print("--- Starting Data Ingestion Process ---")

    # --- Ingest Charged Hours ---
    logger.info(f"Processing Charged Hours from: {CHARGED_HOURS_FILE}")
    print(f"Processing Charged Hours from: {CHARGED_HOURS_FILE}")
    try:
        # Pass both file path and db path
        charged_hours_ingestor = ChargedHoursIngestion(CHARGED_HOURS_FILE, DATABASE_PATH)
        print("  Running Charged Hours process()...")
        success = charged_hours_ingestor.process()
        print(f"  Charged Hours process() returned: {success}")
        if success:
            logger.info("Charged Hours ingestion completed successfully.")
        else:
            logger.error("Charged Hours ingestion failed (processor returned False).")
            ingestion_success = False
    except Exception as e:
        logger.error(f"Exception during Charged Hours ingestion: {e}", exc_info=True)
        print(f"ERROR processing Charged Hours: {e}")
        ingestion_success = False
    print("-" * 20) # Separator

    # --- Ingest Master File ---
    logger.info(f"Processing Master File from: {MASTER_FILE_FILE}")
    print(f"Processing Master File from: {MASTER_FILE_FILE}")
    try:
        # Pass both file path and db path
        master_file_ingestor = MasterFileIngestion(MASTER_FILE_FILE, DATABASE_PATH)
        print("  Running Master File process()...")
        success = master_file_ingestor.process()
        print(f"  Master File process() returned: {success}")
        if success:
            logger.info("Master File ingestion completed successfully.")
        else:
            logger.error("Master File ingestion failed (processor returned False).")
            ingestion_success = False
    except Exception as e:
        logger.error(f"Exception during Master File ingestion: {e}", exc_info=True)
        print(f"ERROR processing Master File: {e}")
        ingestion_success = False
    print("-" * 20) # Separator

    # --- Ingest Targets ---
    logger.info(f"Processing Targets from: {TARGETS_FILE}")
    print(f"Processing Targets from: {TARGETS_FILE}")
    try:
        # Pass both file path and db path
        targets_ingestor = TargetsIngestion(TARGETS_FILE, DATABASE_PATH)
        print("  Running Targets process()...")
        success = targets_ingestor.process()
        print(f"  Targets process() returned: {success}")
        if success:
            logger.info("Targets ingestion completed successfully.")
        else:
            logger.error("Targets ingestion failed (processor returned False).")
            ingestion_success = False
    except Exception as e:
        logger.error(f"Exception during Targets ingestion: {e}", exc_info=True)
        print(f"ERROR processing Targets: {e}")
        ingestion_success = False
    print("-" * 20) # Separator

    if ingestion_success:
        logger.info("--- Data Ingestion Process Completed Successfully ---")
        print("--- Data Ingestion Process Completed Successfully ---")
    else:
        logger.warning("--- Data Ingestion Process Completed with Errors ---")
        print("--- Data Ingestion Process Completed with Errors ---")

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