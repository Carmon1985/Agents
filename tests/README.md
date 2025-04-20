# Chat Functionality Testing

This directory contains automated tests for the chat functionality in the Resource Monitoring application. The tests verify the proper behavior of the chat interface, including agent interactions, responses to various user queries, and error handling.

## Test Structure

- **test_chat_functionality.py**: Unit tests for individual components of the chat system
- **test_chat_e2e.py**: End-to-end tests for complete conversation flows
- **run_chat_tests.py**: Script to run all tests and generate reports

## Prerequisites

Make sure you have the required dependencies installed:

```bash
pip install pytest pytest-html
```

## Running Tests

### Running Individual Test Files

To run a specific test file:

```bash
pytest tests/test_chat_functionality.py -v
pytest tests/test_chat_e2e.py -v
```

### Running All Tests with Report Generation

To run all chat tests and generate a summary report:

```bash
python tests/run_chat_tests.py
```

### Additional Options

The test runner supports several options:

```bash
python tests/run_chat_tests.py --help

# Options:
# --report-dir REPORT_DIR  Directory to save test reports
# --verbose, -v            Enable verbose output
# --junit                  Generate JUnit XML reports
# --html                   Generate HTML report
# --filter FILTER          Filter tests by name pattern
```

Examples:

```bash
# Run tests with verbose output
python tests/run_chat_tests.py -v

# Generate HTML reports
python tests/run_chat_tests.py --html

# Run only tests containing "greeting" in the name
python tests/run_chat_tests.py --filter greeting
```

## Test Cases

The tests cover various conversation scenarios:

1. **Simple Greetings**: Test the system's response to basic greetings
2. **Out-of-Domain Queries**: Test rejection of non-resource related queries (weather, news, etc.)
3. **Agent Specialization**: Test that appropriate specialist agents respond to relevant queries
4. **Multi-turn Conversations**: Test complete conversation flows with multiple interactions
5. **Complex Queries**: Test queries that engage multiple specialist agents
6. **Error Handling**: Test graceful handling of error conditions

## Adding New Tests

To add new test cases:

1. For unit tests, add new test functions to `test_chat_functionality.py`
2. For conversation flows, add new test cases to the `TEST_CASES` list in `test_chat_e2e.py`

## Test Reports

Reports are saved to the `test_reports` directory by default. Each test run generates:

- A JSON file with detailed results
- A text summary file
- HTML reports (if enabled)
- JUnit XML reports (if enabled)

## Mocking Strategy

The tests use mock objects to simulate:

1. Streamlit session state and UI components
2. Azure OpenAI API calls
3. Autogen agent interactions
4. Chat message processing

This allows testing the chat functionality without requiring real OpenAI API keys or a running Streamlit application. 