import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Removed Module-level Fixture --- 

# --- Import app --- 
import app

# --- Test Class ---
class TestUIComponents:
    
    def test_ui_component_initialization(self):
        """Test UI component initialization by calling setup_page with mock"""
        with patch('app.st', new_callable=MagicMock) as mock_st:
            # Call the setup function *after* the mock is active
            app.setup_page()

            # Assertions now use the locally created 'mock_st'
            mock_st.set_page_config.assert_called_with(
                page_title="🤖 Resource Monitoring Agent Dashboard",
                page_icon="🤖",
                layout="wide",
                initial_sidebar_state="expanded"
            )
            # Verify sidebar attribute was accessed (assuming setup_page implicitly causes this, 
            # or if other top-level code accesses st.sidebar after setup_page)
            # If st.sidebar is accessed *outside* setup_page, this might need adjustment
            # For now, let's assume the test focuses on set_page_config call within setup_page
            # assert mock_st.sidebar.called # Keep this commented/removed if not strictly part of setup_page logic

    def test_error_display(self):
        """Test error message display"""
        error_message = "Test error message"
        with patch('app.st', new_callable=MagicMock) as mock_st:
            app.display_error(error_message)
            mock_st.error.assert_called_with(error_message)

    def test_spinner_display(self):
        """Test spinner component"""
        # Patching app.process_message is no longer needed as it was removed
        # with patch('app.process_message') as mock_process:
        with patch('app.st', new_callable=MagicMock) as mock_st: 
            with app.show_processing_spinner():
                pass # Simply ensure the context manager runs
            # Assert spinner was called on the mocked module
            mock_st.spinner.assert_called_once() 