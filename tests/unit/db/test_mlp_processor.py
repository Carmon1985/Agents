import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
import os
import sqlite3

# Assuming the structure allows this import. Adjust if necessary.
from src.db.mlp_processor import MLPIngestion

# Define paths relative to the test file or use absolute paths based on a known root
# For simplicity, we might mock file existence or use temporary files in real tests
TEST_DB_PATH = ':memory:' # Use in-memory database for testing
DUMMY_SOURCE_FILE = 'dummy_mlp.xlsx'

class TestMLPIngestion(unittest.TestCase):

    def setUp(self):
        """Set up for test methods."""
        # Create a dummy source file for tests that need it
        # In a real scenario, use a predefined test file or mock pd.read_excel
        # For now, just ensure the path exists conceptually for the constructor
        # self.create_dummy_excel(DUMMY_SOURCE_FILE)
        self.processor = MLPIngestion(source_file_path=DUMMY_SOURCE_FILE, db_path=TEST_DB_PATH)
        
        # Setup in-memory database and schema if needed for load tests
        self.conn = sqlite3.connect(TEST_DB_PATH)
        self.cursor = self.conn.cursor()
        # You might want to execute the actual schema or a simplified version
        # For now, we'll assume the table might not exist for some tests

    def tearDown(self):
        """Clean up after test methods."""
        # Close the DB connection
        if self.conn:
            self.conn.close()
        # Remove dummy file if created
        # if os.path.exists(DUMMY_SOURCE_FILE):
        #     os.remove(DUMMY_SOURCE_FILE)
        pass
        
    # --- Placeholder: Helper to create dummy excel --- 
    # def create_dummy_excel(self, filepath):
    #     # In a real test, create an Excel file with sample data
    #     # df = pd.DataFrame({ ... })
    #     # df.to_excel(filepath, index=False)
    #     # For now, just create an empty file to satisfy os.path check if not mocked
    #     # open(filepath, 'a').close() 
    #     pass

    @patch('pandas.read_excel') # Mock the pandas read function
    def test_read_source_success(self, mock_read_excel):
        """Test successful reading of source data."""
        # Arrange: Configure the mock to return a sample DataFrame
        sample_data = {
            'Project Identifier': ['P101', 'P102'],
            'Project Name': ['Project Alpha', 'Project Beta'],
            'Project Status': ['Active', 'Closed'],
            # ... add other required columns
        }
        mock_df = pd.DataFrame(sample_data)
        mock_read_excel.return_value = mock_df
        
        # Act
        df = self.processor.read_source()
        
        # Assert
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        mock_read_excel.assert_called_once_with(DUMMY_SOURCE_FILE, sheet_name=0)
        # Add more assertions based on expected columns found
        self.assertIn('Project Identifier', self.processor.actual_columns)
        
    @patch('pandas.read_excel', side_effect=FileNotFoundError)
    def test_read_source_file_not_found(self, mock_read_excel):
        """Test handling when the source file is not found."""
        # Act & Assert
        with self.assertRaises(FileNotFoundError):
            self.processor.read_source()
        mock_read_excel.assert_called_once()

    @patch('pandas.read_excel')
    def test_read_source_missing_critical_column(self, mock_read_excel):
        """Test handling when a critical column is missing."""
        # Arrange: Mock DataFrame missing 'Project Name'
        sample_data = {
            'Project Identifier': ['P101', 'P102'], 
             # 'Project Name': ['Project Alpha', 'Project Beta'], # Missing!
            'Project Status': ['Active', 'Closed']
        }
        mock_df = pd.DataFrame(sample_data)
        mock_read_excel.return_value = mock_df
        
        # Act & Assert
        with self.assertRaisesRegex(ValueError, "missing critical MLP columns:.*Project Name"):
            self.processor.read_source()

    def test_transform_data_basic(self):
        """Test basic data transformations (renaming, types)."""
        # Arrange: Create a sample input DataFrame
        raw_data = {
            'Project Identifier': [' P101 ', 'P102', 'P103'],
            'Project Name': [' Alpha ', ' Beta ', ' Gamma '],
            'Project Status': ['Active', 'Planning', None],
            'Project Start Date': ['2023-01-15', '2024-02-20', 'Invalid Date'],
            'Total Budgeted Hours': [1000, '500.5', None]
        }
        # Simulate actual columns found during read_source
        self.processor.actual_columns = {k: self.processor.COLUMN_MAPPING[k] for k in raw_data.keys()}
        raw_df = pd.DataFrame(raw_data)
        
        # Act
        transformed_df = self.processor.transform_data(raw_df)
        
        # Assert
        self.assertIn('project_id', transformed_df.columns)
        self.assertIn('project_start_date', transformed_df.columns)
        self.assertEqual(transformed_df.iloc[0]['project_id'], 'P101') # Check stripping
        self.assertEqual(transformed_df.iloc[0]['project_start_date'], '2023-01-15')
        self.assertIsNone(transformed_df.iloc[2]['project_start_date']) # Check date error handling
        self.assertEqual(transformed_df.iloc[1]['total_budgeted_hours'], 500.5) # Check numeric conversion
        self.assertTrue(pd.isna(transformed_df.iloc[2]['total_budgeted_hours'])) # Check numeric error handling
        # Add more assertions for type conversions, renaming, etc.
        
    def test_transform_data_missing_critical(self):
        """Test dropping rows with missing critical data."""
         # Arrange: Create a sample input DataFrame
        raw_data = {
            'Project Identifier': ['P101', None, 'P103', ' '],
            'Project Name': ['Alpha', 'Beta', 'Gamma', 'Delta'],
            'Project Status': ['Active', 'Planning', 'Closed', 'Active']
        }
        self.processor.actual_columns = {k: self.processor.COLUMN_MAPPING[k] for k in raw_data.keys()}
        raw_df = pd.DataFrame(raw_data)
        
        # Act
        transformed_df = self.processor.transform_data(raw_df)
        
        # Assert
        self.assertEqual(len(transformed_df), 2) # Rows with None and empty string ID should be dropped
        self.assertEqual(transformed_df.iloc[0]['project_id'], 'P101')
        self.assertEqual(transformed_df.iloc[1]['project_id'], 'P103')
        
    @patch('pandas.DataFrame.to_sql')
    def test_load_to_db_success(self, mock_to_sql):
        """Test successful loading to the database."""
        # Arrange
        transformed_data = {
             'project_id': ['P101', 'P102'],
             'project_name': ['Alpha', 'Beta']
             # ... other columns matching schema
        }
        transformed_df = pd.DataFrame(transformed_data)
        # Simulate DB connection being established by process()
        self.processor.conn = MagicMock()
        
        # Act
        self.processor.load_to_db(transformed_df)
        
        # Assert
        mock_to_sql.assert_called_once_with(
            self.processor.TARGET_TABLE,
            self.processor.conn,
            if_exists='replace',
            index=False
        )

    @patch('pandas.DataFrame.to_sql', side_effect=sqlite3.IntegrityError("Fake integrity error"))
    def test_load_to_db_integrity_error(self, mock_to_sql):
        """Test handling of database integrity errors during load."""
        # Arrange
        transformed_df = pd.DataFrame({'project_id': ['P101'], 'project_name':['Alpha']})
        self.processor.conn = MagicMock()
        
        # Act & Assert
        with self.assertRaises(sqlite3.IntegrityError):
             self.processor.load_to_db(transformed_df)
        mock_to_sql.assert_called_once()

    def test_load_to_db_empty_dataframe(self):
        """Test that loading is skipped for an empty DataFrame."""
        # Arrange
        empty_df = pd.DataFrame()
        self.processor.conn = MagicMock()
        # Mock the to_sql method to ensure it's not called
        self.processor.conn.cursor().execute = MagicMock()
        pd.DataFrame.to_sql = MagicMock()

        # Act
        self.processor.load_to_db(empty_df)

        # Assert
        pd.DataFrame.to_sql.assert_not_called()

    # --- Integration-style test for the process method (Optional) ---
    # @patch('src.db.mlp_processor.MLPIngestion.read_source')
    # @patch('src.db.mlp_processor.MLPIngestion.transform_data')
    # @patch('src.db.mlp_processor.MLPIngestion.load_to_db')
    # @patch('src.db.mlp_processor.MLPIngestion._connect_db')
    # @patch('src.db.mlp_processor.MLPIngestion._close_db')
    # def test_process_full_flow(self, mock_close, mock_connect, mock_load, mock_transform, mock_read):
    #     """Test the overall process orchestration."""
    #     # Arrange
    #     mock_read.return_value = pd.DataFrame({'Project Identifier': ['P101']}) # Dummy non-empty
    #     mock_transform.return_value = pd.DataFrame({'project_id': ['P101']}) # Dummy non-empty
    #     
    #     # Act
    #     self.processor.process()
    #     
    #     # Assert
    #     mock_connect.assert_called_once()
    #     mock_read.assert_called_once()
    #     mock_transform.assert_called_once()
    #     mock_load.assert_called_once()
    #     mock_close.assert_called_once()

if __name__ == '__main__':
    unittest.main() 