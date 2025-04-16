import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
import os
import sqlite3

from src.db.master_file_processor import MasterFileIngestion

TEST_DB_PATH = ':memory:'
DUMMY_SOURCE_FILE = 'dummy_master_file.xlsx'

class TestMasterFileIngestion(unittest.TestCase):

    def setUp(self):
        """Set up test methods."""
        self.processor = MasterFileIngestion(source_file_path=DUMMY_SOURCE_FILE, db_path=TEST_DB_PATH)
        self.conn = sqlite3.connect(TEST_DB_PATH)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        """Clean up after test methods."""
        if self.conn:
            self.conn.close()
        pass

    @patch('pandas.read_excel')
    def test_read_source_success(self, mock_read_excel):
        """Test successful reading of source data with standard columns."""
        # Arrange
        sample_data = {
            'Employee Identifier': ['emp1', 'emp2'],
            'Employee Name': ['Alice', 'Bob'],
            'Status': ['Active', 'Inactive'],
            'Standard Hours Per Week': [40, 37.5],
            'Employee Category': ['Dev', 'Support'],
            'Employee Competency': ['Backend', 'Tier 1'],
            'Employee Location': ['Office A', 'Remote'],
            'Employee Billing Rank': ['Senior', 'Junior']
        }
        mock_df = pd.DataFrame(sample_data)
        mock_read_excel.return_value = mock_df
        
        # Act
        df = self.processor.read_source()
        
        # Assert
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        mock_read_excel.assert_called_once_with(DUMMY_SOURCE_FILE, sheet_name=0)
        self.assertTrue(all(col in self.processor.actual_columns for col in sample_data.keys()))
        
    @patch('pandas.read_excel')
    def test_read_source_success_alternative_names(self, mock_read_excel):
        """Test successful reading using alternative column names."""
        # Arrange
        sample_data = {
            'Employee Identifier': ['emp1'],
            'Employee Name': ['Alice'],
            'Status': ['Active'],
            'Effective STD Hrs per Week': [40], # Alternative name
            'Primary Skill Group': ['Backend'], # Alternative name
            'Office': ['Office A'], # Alternative name
            'Grade': ['Senior'] # Alternative name
        }
        mock_df = pd.DataFrame(sample_data)
        mock_read_excel.return_value = mock_df
        
        # Act
        df = self.processor.read_source()
        
        # Assert
        self.assertIsNotNone(df)
        mock_read_excel.assert_called_once_with(DUMMY_SOURCE_FILE, sheet_name=0)
        # Check that the mapping worked
        self.assertIn('Effective STD Hrs per Week', self.processor.actual_columns)
        self.assertEqual(self.processor.actual_columns['Effective STD Hrs per Week'], 'standard_hours_per_week')
        self.assertIn('Primary Skill Group', self.processor.actual_columns)
        self.assertEqual(self.processor.actual_columns['Primary Skill Group'], 'employee_competency')
        
    @patch('pandas.read_excel', side_effect=FileNotFoundError)
    def test_read_source_file_not_found(self, mock_read_excel):
        """Test handling when the source file is not found."""
        with self.assertRaises(FileNotFoundError):
            self.processor.read_source()
        mock_read_excel.assert_called_once()

    @patch('pandas.read_excel')
    def test_read_source_missing_critical_column(self, mock_read_excel):
        """Test handling when a critical column like Status is missing."""
        # Arrange: Missing 'Status'
        sample_data = {
            'Employee Identifier': ['emp1'],
            'Employee Name': ['Alice'] 
            # 'Status': ['Active'], # Missing!
        }
        mock_df = pd.DataFrame(sample_data)
        mock_read_excel.return_value = mock_df
        
        with self.assertRaisesRegex(ValueError, "missing critical columns:.*Status"):
            self.processor.read_source()
            
    def test_transform_data_basic(self):
        """Test basic transformations (renaming, types, stripping)."""
        # Arrange
        raw_data = {
            'Employee Identifier': [' emp1 ', 'emp2'],
            'Employee Name': [' Alice ', ' Bob '],
            'Status': [' Active ', 'Inactive'],
            'Standard Hours Per Week': ['40', 37.5],
            'Employee Category': [' Dev ', None],
            'Primary Skill Group': ['Backend', ' Support '], # Use alternative name
        }
        # Simulate actual columns found
        self.processor.actual_columns = {
            'Employee Identifier': 'employee_id', 'Employee Name': 'employee_name',
            'Status': 'status', 'Standard Hours Per Week': 'standard_hours_per_week',
            'Employee Category': 'employee_category', 'Primary Skill Group': 'employee_competency'
        }
        raw_df = pd.DataFrame(raw_data)
        
        # Act
        transformed_df = self.processor.transform_data(raw_df)
        
        # Assert
        self.assertEqual(len(transformed_df), 2)
        self.assertEqual(transformed_df.iloc[0]['employee_id'], 'emp1') # Check stripping
        self.assertEqual(transformed_df.iloc[0]['employee_name'], 'Alice')
        self.assertEqual(transformed_df.iloc[0]['status'], 'Active')
        self.assertEqual(transformed_df.iloc[0]['standard_hours_per_week'], 40.0)
        self.assertEqual(transformed_df.iloc[1]['standard_hours_per_week'], 37.5)
        self.assertEqual(transformed_df.iloc[0]['employee_category'], 'Dev') # Check stripping
        self.assertIsNone(transformed_df.iloc[1]['employee_category']) # Check None -> None (updated logic)
        self.assertEqual(transformed_df.iloc[0]['employee_competency'], 'Backend') # Check renaming
        self.assertEqual(transformed_df.iloc[1]['employee_competency'], 'Support') # Check stripping
        self.assertIn('employee_location', transformed_df.columns) # Check missing cols added
        self.assertIsNone(transformed_df.iloc[0]['employee_location'])
        
    def test_transform_data_missing_critical(self):
        """Test dropping rows with missing critical data."""
        # Arrange
        raw_data = {
            'Employee Identifier': ['emp1', None, 'emp3', ' '], # None and whitespace ID
            'Employee Name': ['Alice', 'Bob', None, 'Charlie'], # None Name
            'Status': ['Active', 'Active', 'Active', 'Active']
        }
        self.processor.actual_columns = {k: self.processor.COLUMN_MAPPING[k] for k in raw_data.keys()}
        raw_df = pd.DataFrame(raw_data)
        
        # Act
        transformed_df = self.processor.transform_data(raw_df)
        
        # Assert
        self.assertEqual(len(transformed_df), 1) # Only first row should remain
        self.assertEqual(transformed_df.iloc[0]['employee_id'], 'emp1')

    @patch('pandas.DataFrame.to_sql')
    def test_load_to_db_success(self, mock_to_sql):
        """Test successful loading."""
        # Arrange
        transformed_df = pd.DataFrame({'employee_id': ['emp1'], 'employee_name': ['Alice'], 'status': ['Active']})
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

    @patch('pandas.DataFrame.to_sql', side_effect=sqlite3.IntegrityError("Fake PK violation"))
    def test_load_to_db_integrity_error(self, mock_to_sql):
        """Test handling PK integrity errors."""
        # Arrange
        transformed_df = pd.DataFrame({'employee_id': ['emp1'], 'employee_name': ['Alice'], 'status': ['Active']})
        self.processor.conn = MagicMock()
        
        # Act & Assert
        with self.assertRaises(sqlite3.IntegrityError):
            self.processor.load_to_db(transformed_df)
        mock_to_sql.assert_called_once()

if __name__ == '__main__':
    unittest.main() 