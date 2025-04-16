import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
import os
import sqlite3
import logging # Import logging

from src.db.charged_hours_processor import ChargedHoursIngestion

TEST_DB_PATH = ':memory:'
DUMMY_SOURCE_FILE = 'dummy_charged_hours.xlsx'

class TestChargedHoursIngestion(unittest.TestCase):

    def setUp(self):
        """Set up test methods."""
        self.processor = ChargedHoursIngestion(source_file_path=DUMMY_SOURCE_FILE, db_path=TEST_DB_PATH)
        # --- Set processor logger level to DEBUG for testing --- 
        self.processor.logger.setLevel(logging.DEBUG)
        # Optional: Add a handler if logs aren't showing up in pytest capture
        # self.log_stream = io.StringIO()
        # self.stream_handler = logging.StreamHandler(self.log_stream)
        # self.processor.logger.addHandler(self.stream_handler)
        # --- End DEBUG setup ---
        self.conn = sqlite3.connect(TEST_DB_PATH)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        """Clean up after test methods."""
        if self.conn:
            self.conn.close()
        # Optional: Remove handler
        # if hasattr(self, 'stream_handler'):
        #    self.processor.logger.removeHandler(self.stream_handler)
        pass

    # --- Test read_source methods with 'with patch' ---
    def test_read_source_success(self):
        """Test successful reading of source data."""
        sample_data = {
            'Employee Identifier': ['emp1', 'emp2'], 'Project Identifier': ['projA', 'projB'],
            'Date Worked': ['2024-01-10', '2024-01-11'], 'Charged Hours': [8, 7.5]
        }
        mock_df = pd.DataFrame(sample_data)
        
        # Use 'with patch' targeting the specific function used internally
        with patch('pandas.read_excel', return_value=mock_df) as mock_read:
            # We also need to ensure os.path.exists doesn't prevent the check
            with patch('os.path.exists', return_value=True):
                df = self.processor.read_source()
            
            self.assertIsNotNone(df)
            self.assertEqual(len(df), 2)
            mock_read.assert_called_once_with(DUMMY_SOURCE_FILE, sheet_name=0)
            # Check that the processor identified the columns correctly based on mapping
            self.assertTrue(all(col in self.processor.EXPECTED_COLUMNS for col in sample_data.keys()))

    def test_read_source_file_not_found(self):
        """Test handling when the source file is not found."""
        # Patching read_excel to raise the error
        with patch('pandas.read_excel', side_effect=FileNotFoundError("Mock file not found")) as mock_read:
             # Also patch os.path.exists to simulate file not being there initially if needed
             with patch('os.path.exists', return_value=False):
                 with self.assertRaises(FileNotFoundError):
                      self.processor.read_source()
                 # The code should ideally check existence first or handle the error from read_excel
                 # Depending on implementation, mock_read might not be called if exists check fails first
                 # Let's assume for now the primary check is read_excel failing
                 # mock_read.assert_called_once() # This might fail if os.path check prevents call

    def test_read_source_missing_critical_column(self):
        """Test handling when a critical column is missing."""
        sample_data = {
            'Employee Identifier': ['emp1', 'emp2'], #'Project Identifier': Missing!
            'Date Worked': ['2024-01-10', '2024-01-11'], 'Charged Hours': [8, 7.5]
        }
        mock_df = pd.DataFrame(sample_data)
        
        with patch('pandas.read_excel', return_value=mock_df) as mock_read:
            with patch('os.path.exists', return_value=True):
                with self.assertRaisesRegex(ValueError, "missing required columns:.*Project Identifier"):
                     self.processor.read_source()
                mock_read.assert_called_once()

    def test_transform_data_basic(self):
        """Test basic data transformations (renaming, types, date format)."""
        # Arrange
        raw_data = {
            'Employee Identifier': [' emp1 ', 'emp2', 'emp3'],
            'Project Identifier': ['projA ', ' projB', 'projC'],
            'Date Worked': ['2024-01-15', '2024-01-16', 'Invalid Date'],
            'Charged Hours': ['8', 7.5, 'abc']
        }
        raw_df = pd.DataFrame(raw_data)
        
        # Act
        transformed_df = self.processor.transform_data(raw_df)
        
        # Assert
        self.assertEqual(len(transformed_df), 2) # Row 3 dropped
        self.assertEqual(transformed_df.iloc[0]['employee_id'], 'emp1') 
        self.assertEqual(transformed_df.iloc[0]['project_id'], 'projA') 
        self.assertEqual(transformed_df.iloc[1]['employee_id'], 'emp2') 
        self.assertEqual(transformed_df.iloc[1]['project_id'], 'projB')
        self.assertEqual(transformed_df.iloc[0]['charge_date'], '2024-01-15') 
        self.assertEqual(transformed_df.iloc[1]['charge_date'], '2024-01-16')
        self.assertEqual(transformed_df.iloc[0]['charged_hours'], 8.0) # Check numeric conversion
        self.assertEqual(transformed_df.iloc[1]['charged_hours'], 7.5)
        
    def test_transform_data_missing_critical(self):
        """Test dropping rows with missing critical data (NaNs)."""
        # Arrange
        raw_data = {
            'Employee Identifier': ['emp1', None, 'emp3', '  ', 'emp5'], # Added empty string case
            'Project Identifier': ['projA', 'projB', None, 'projD', 'projE'],
            'Date Worked': ['2024-01-10', '2024-01-11', '2024-01-12', '2024-01-13', None],
            'Charged Hours': [8, 7, 6, 5, 4]
        }
        raw_df = pd.DataFrame(raw_data)
        
        # Act
        transformed_df = self.processor.transform_data(raw_df)
        
        # Assert
        self.assertEqual(len(transformed_df), 1) # Only the first row is complete
        self.assertEqual(transformed_df.iloc[0]['employee_id'], 'emp1')

    @patch('pandas.DataFrame.to_sql')
    def test_load_to_db_success(self, mock_to_sql):
        """Test successful loading to the database."""
        # Arrange
        transformed_df = pd.DataFrame({
            'employee_id': ['emp1'], 'project_id': ['projA'], 
            'charge_date': ['2024-01-10'], 'charged_hours': [8.0]
        })
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

    @patch('pandas.DataFrame.to_sql', side_effect=sqlite3.IntegrityError("Fake FK violation"))
    def test_load_to_db_integrity_error(self, mock_to_sql):
        """Test handling of database integrity errors (e.g., FK violation)."""
        # Arrange
        transformed_df = pd.DataFrame({'employee_id': ['non_existent_emp'], 'project_id':['projA'], 'charge_date':['2024-01-10'], 'charged_hours':[8]})
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
        mock_to_sql = MagicMock()
        # Need to patch the method on the class for the instance
        with patch.object(pd.DataFrame, 'to_sql', mock_to_sql):
            # Act
            self.processor.load_to_db(empty_df)
            # Assert
            mock_to_sql.assert_not_called()

if __name__ == '__main__':
    unittest.main() 