import unittest
import pandas as pd
from unittest.mock import patch, MagicMock
import os
import sqlite3

# Adjust import path as necessary
from src.db.targets_processor import TargetsIngestion

TEST_DB_PATH = ':memory:' # Use in-memory database for testing
DUMMY_SOURCE_FILE = 'dummy_targets.xlsx'

class TestTargetsIngestion(unittest.TestCase):

    def setUp(self):
        """Set up test methods."""
        self.processor = TargetsIngestion(source_file_path=DUMMY_SOURCE_FILE, db_path=TEST_DB_PATH)
        self.conn = sqlite3.connect(TEST_DB_PATH)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        """Clean up after test methods."""
        if self.conn:
            self.conn.close()
        # Clean up dummy file if created
        # if os.path.exists(DUMMY_SOURCE_FILE):
        #     os.remove(DUMMY_SOURCE_FILE)
        pass

    @patch('pandas.read_excel')
    def test_read_source_success(self, mock_read_excel):
        """Test successful reading of source data."""
        # Arrange
        sample_data = {
            'Target Year': [2024, 2024],
            'Target Month': [1, 1],
            'Employee Category': ['Dev', 'QA'],
            'Employee Competency': ['Backend', 'Automation'],
            'Employee Location': ['Office A', 'Office B'],
            'Employee Billing Rank': ['Senior', 'Mid'],
            'Target Utilization Percentage': [85.0, 80.0]
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

    @patch('pandas.read_excel', side_effect=FileNotFoundError)
    def test_read_source_file_not_found(self, mock_read_excel):
        """Test handling when the source file is not found."""
        with self.assertRaises(FileNotFoundError):
            self.processor.read_source()
        mock_read_excel.assert_called_once()
        
    @patch('pandas.read_excel')
    def test_read_source_missing_critical_column(self, mock_read_excel):
        """Test handling when a critical dimension column is missing."""
        # Arrange: Missing 'Employee Category'
        sample_data = {
            'Target Year': [2024],
            'Target Month': [1],
            # 'Employee Category': ['Dev'], # Missing!
            'Employee Competency': ['Backend'],
            'Employee Location': ['Office A'],
            'Employee Billing Rank': ['Senior'],
            'Target Utilization Percentage': [85.0]
        }
        mock_df = pd.DataFrame(sample_data)
        mock_read_excel.return_value = mock_df
        
        with self.assertRaisesRegex(ValueError, "missing critical dimension columns.*Employee Category"):
            self.processor.read_source()
            
    def test_transform_data_basic(self):
        """Test basic data transformations (types, cleaning)."""
        # Arrange
        raw_data = {
            'Target Year': ['2024', 2024],
            'Target Month': [1, '02'],
            'Employee Category': [' Dev ', 'QA'],
            'Employee Competency': ['Backend', ' Automation '],
            'Employee Location': ['OfficeA', 'OfficeB'],
            'Employee Billing Rank': [' Sr ', 'Mid'],
            'Target Utilization Percentage': ['85', 80.5],
            'Target Charged Hours per FTE': [None, '140']
        }
        self.processor.actual_columns = {k: self.processor.COLUMN_MAPPING[k] for k in raw_data.keys()}
        raw_df = pd.DataFrame(raw_data)
        
        # Act
        transformed_df = self.processor.transform_data(raw_df)
        
        # Assert
        self.assertEqual(transformed_df.iloc[0]['target_year'], 2024)
        self.assertEqual(transformed_df.iloc[1]['target_month'], 2)
        self.assertEqual(transformed_df.iloc[0]['employee_category'], 'Dev') # Check stripping
        self.assertEqual(transformed_df.iloc[1]['employee_competency'], 'Automation')
        self.assertEqual(transformed_df.iloc[0]['target_utilization_percentage'], 85.0) # Check numeric conversion
        self.assertEqual(transformed_df.iloc[1]['target_charged_hours_per_fte'], 140.0)
        self.assertTrue(pd.isna(transformed_df.iloc[0]['target_charged_hours_per_fte'])) # Check None handling
        self.assertIn('target_headcount_fte', transformed_df.columns) # Check missing optional col added
        self.assertTrue(pd.isna(transformed_df.iloc[0]['target_headcount_fte']))
        
    def test_transform_data_missing_critical(self):
        """Test dropping rows with missing critical dimension data."""
        # Arrange
        raw_data = {
            'Target Year': [2024, 2024, 2024, 2024],
            'Target Month': [1, None, 3, 4],
            'Employee Category': ['Dev', 'QA', ' ', 'Ops'], # Empty string counts as missing
            'Employee Competency': ['BE', 'Auto', 'Cloud', 'Support'],
            'Employee Location': ['A', 'B', 'C', 'D'],
            'Employee Billing Rank': ['Sr', 'Mid', 'Jr', 'Sr']
        }
        self.processor.actual_columns = {k: self.processor.COLUMN_MAPPING[k] for k in raw_data.keys()}
        raw_df = pd.DataFrame(raw_data)

        # Act
        transformed_df = self.processor.transform_data(raw_df)

        # Assert
        self.assertEqual(len(transformed_df), 2) # Rows with None month and empty category should be dropped
        self.assertEqual(transformed_df.iloc[0]['target_year'], 2024)
        self.assertEqual(transformed_df.iloc[1]['target_year'], 2024)
        self.assertEqual(transformed_df.iloc[0]['employee_category'], 'Dev')
        self.assertEqual(transformed_df.iloc[1]['employee_category'], 'Ops')
        
    @patch('pandas.DataFrame.to_sql')
    def test_load_to_db_success(self, mock_to_sql):
        """Test successful loading to the database."""
        # Arrange
        transformed_df = pd.DataFrame({
            'target_year': [2024], 'target_month': [1],
            'employee_category': ['Dev'], 'employee_competency': ['BE'],
            'employee_location': ['A'], 'employee_billing_rank': ['Sr']
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

    @patch('pandas.DataFrame.to_sql', side_effect=sqlite3.IntegrityError("Fake PK violation"))
    def test_load_to_db_integrity_error(self, mock_to_sql):
        """Test handling of database integrity errors (e.g., duplicate PK)."""
        # Arrange
        transformed_df = pd.DataFrame({'target_year': [2024], 'target_month': [1], 'employee_category':['Dev'], 'employee_competency':['BE'], 'employee_location':['A'], 'employee_billing_rank':['Sr']})
        self.processor.conn = MagicMock()
        
        # Act & Assert
        with self.assertRaises(sqlite3.IntegrityError):
            self.processor.load_to_db(transformed_df)
        mock_to_sql.assert_called_once()

if __name__ == '__main__':
    unittest.main() 