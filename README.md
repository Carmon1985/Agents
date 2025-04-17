# Project: Agents - Resource Monitoring

This project implements a multi-agent system using AutoGen to monitor resource utilization based on data ingested from external sources.

## Features

*   **Data Ingestion:** Processes data from Excel files (Charged Hours, Master File, Targets) and loads it into a SQLite database.
*   **Database Schema:** Uses SQLite (`data/database.db`) with tables for `charged_hours`, `master_file`, and `targets`.
*   **Monitoring Agent:** An AutoGen agent that can query the database, calculate utilization for specific periods/employees, and compare against targets.
*   **Azure OpenAI Integration:** Uses Azure OpenAI for the LLM powering the agents.

## Project Structure

```
Agents/
├── data/
│   ├── database.db           # SQLite database (created by schema_setup)
│   ├── dummy_charged_hours.xlsx # Example source data
│   ├── dummy_master_file.xlsx   # Example source data
│   └── dummy_targets.xlsx       # Example source data
├── src/
│   ├── __init__.py
│   ├── agents/
│   │   ├── __init__.py
│   │   └── monitoring_agent.py # Main script for the monitoring agent
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base_processor.py     # Base class for data processors
│   │   ├── charged_hours_processor.py
│   │   ├── master_file_processor.py
│   │   ├── targets_processor.py
│   │   ├── schema_setup.py       # Script to create DB tables
│   │   ├── query_functions.py    # Functions used by agent to query DB
│   │   └── ingest_data.py        # Main script to run data ingestion
│   └── ui/                 # (Placeholder for potential UI components)
│       └── __init__.py
├── tests/                # Unit and integration tests
│   ├── __init__.py
│   ├── integration/
│   │   └── __init__.py
│   └── unit/
│       └── __init__.py
├── .env                  # Environment variables (Azure OpenAI keys, etc.)
├── .gitignore
├── README.md             # This file
├── requirements.txt      # Python dependencies (ensure this is created/updated)
├── tasks/                # Task management files (if using task-master)
│   └── tasks.json
└── ... (other config files)
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd Agents
    ```

2.  **Create and activate a virtual environment:** (Recommended)
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    *Make sure `requirements.txt` exists and is up-to-date.*
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    *   Create a `.env` file in the project root.
    *   Add your Azure OpenAI credentials:
        ```dotenv
        OPENAI_API_KEY="your_azure_openai_api_key"
        OPENAI_API_BASE="https://your_azure_resource_name.openai.azure.com/" # Your Azure Endpoint URL
        OPENAI_API_VERSION="your_api_version" # e.g., 2024-02-15-preview
        OPENAI_API_TYPE="azure"
        OPENAI_DEPLOYMENT_NAME="your_deployment_name" # The name you gave the model deployment in Azure
        ```

## Data Setup

1.  **Create Database Schema:**
    Run the setup script from the project root directory:
    ```bash
    python src/db/schema_setup.py
    ```
    This will create the `data/database.db` file and the necessary tables.

2.  **Prepare Source Files:**
    *   Place your source data Excel files in the `data/` directory.
    *   Ensure the filenames match those expected by `src/db/ingest_data.py` (e.g., `dummy_charged_hours.xlsx`, `dummy_master_file.xlsx`, `dummy_targets.xlsx`).
    *   **Crucially**, ensure the column headers within each Excel file match the expected names:
        *   `dummy_charged_hours.xlsx`: `Employee Identifier`, `Date Worked`, `Hours Charged`, `Project Code`, `Task Description`
        *   `dummy_master_file.xlsx`: `Employee Identifier`, `Date`, `Capacity Hours`, `Employee Name`, `Department`
        *   `dummy_targets.xlsx`: `Employee Identifier`, `Target Date`, `Target Utilization Pct`, `Notes`

3.  **Run Data Ingestion:**
    Run the ingestion script *as a module* from the project root directory:
    ```bash
    python -m src.db.ingest_data
    ```
    This will read the data from the Excel files, transform it, and load it into the `data/database.db` SQLite database.

## Running the Monitoring Agent

Once the database is populated, you can run the monitoring agent script *as a module* from the project root:

```bash
python -m src.agents.monitoring_agent
```

The script will initiate a chat, and the agent will use the `analyze_utilization` tool (which queries the database) based on the `initial_prompt` defined within the script.

## Development Notes

*   The system uses `task-master` for task management (see `tasks/tasks.json`).
*   Processors inherit from `src/db/base_processor.py`.
*   Logging is configured in various modules; check console output for details.

## 🌟 Features

- **Multi-Agent Architecture**
  - Monitoring Agent for real-time data analysis
  - User Proxy Agent for handling user interactions
  - Recommendation Agent for providing insights
  - Simulation Agent for what-if scenarios

- **Interactive Streamlit UI**
  - Real-time alerts and notifications
  - Data visualization dashboard
  - Interactive simulation interface
  - User-friendly configuration panel

- **Data Management**
  - SQLite database for efficient data storage
  - Automated data ingestion module (`src/db/data_ingestion.py` and specific processors like `ChargedHoursIngestion`, `MasterFileIngestion`, `MLPIngestion`)
  - Structured schema for monitoring data (`src/db/schema.sql`)
  - Tool functions for data manipulation

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Node.js (for task-master)
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Agents.git
   cd Agents
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Configuration

Configure the following in your `.env` file:

```env
# Required
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=your_api_base  # For Azure OpenAI
OPENAI_API_VERSION=2024-02-15
OPENAI_API_TYPE=azure
OPENAI_DEPLOYMENT_NAME=your_deployment

# Optional
MAX_TOKENS=4000
TEMPERATURE=0.7
```

## 📁 Project Structure

```
.
├── data/               # Data storage
├── docs/               # Documentation
├── notebooks/          # Jupyter notebooks
├── src/               # Source code
│   ├── db/            # Database modules
│   ├── ui/            # Streamlit UI components
│   └── utils/         # Utility functions
├── tests/             # Test files
│   ├── unit/          # Unit tests
│   └── integration/   # Integration tests
├── .env               # Environment variables
├── .gitignore         # Git ignore rules
├── README.md          # This file
└── requirements.txt   # Python dependencies
```

## 🔧 Usage

1. **Initialize Database:**
   Run the initialization script if the database doesn't exist or needs resetting:
   ```bash
   python src/db/initialize_db.py
   ```

2. **Prepare Source Data:**
   Place your source files (e.g., `charged_hours.csv`, `master_file.xlsx`, `mlp.xlsx`, `targets.csv`) in the `data/source/` directory (or configure paths in `src/db/data_ingestion.py`).

3. **Run Data Ingestion (Example for one processor):**
   You can run individual processors directly:
   ```bash
   python src/db/charged_hours_processor.py
   python src/db/master_file_processor.py
   python src/db/mlp_processor.py
   # python src/db/targets_processor.py  (Once implemented)
   ```
   (A main ingestion script calling all processors will likely be added later).

4. **Start the Streamlit application:**
   ```bash
   streamlit run src/ui/app.py
   ```

5. Access the UI at `http://localhost:8501`

6. Configure your monitoring parameters in the sidebar

7. View real-time monitoring data and alerts

## 🧪 Testing

Run the test suite:

```bash
pytest tests/
```

## 📚 Documentation

Additional documentation can be found in the `docs/` directory:
- API Reference
- Agent Architecture
- Database Schema
- UI Components

## 💾 Database Schema

The following diagram shows the relationships between the tables in the SQLite database (`data/operational_data.db`):

```mermaid
erDiagram
    employees {
        TEXT employee_id PK "Employee ID (e.g., Email)"
        TEXT employee_name NN "Full Name"
        TEXT status NN "Status (Active/Inactive)"
        REAL standard_hours_per_week "Standard Weekly Hours"
        TEXT employee_category "Category (Target Dimension)"
        TEXT employee_competency "Competency (Target Dimension)"
        TEXT employee_location "Location (Target Dimension)"
        TEXT employee_billing_rank "Billing Rank (Target Dimension)"
        TEXT department "Department/Practice"
        TEXT region "Region"
    }

    projects {
        TEXT project_id PK "Project ID (e.g., Code)"
        TEXT project_name NN "Project Name"
        TEXT project_status "Status"
        DATE project_start_date "Start Date"
        DATE project_end_date "End Date/Deadline"
        REAL total_budgeted_hours "Budgeted Hours"
        TEXT required_primary_skill "Required Skill"
        REAL target_resource_count "Target FTE"
    }

    charged_hours {
        INTEGER charge_id PK "Charge Entry ID"
        TEXT employee_id FK NN "Employee ID"
        TEXT project_id FK NN "Project ID"
        DATE charge_date NN "Date Worked"
        REAL charged_hours NN "Hours Charged"
    }

    targets {
        INTEGER target_year PK "Target Year"
        INTEGER target_month PK "Target Month (1-12)"
        TEXT employee_category PK "Category Dimension"
        TEXT employee_competency PK "Competency Dimension"
        TEXT employee_location PK "Location Dimension"
        TEXT employee_billing_rank PK "Billing Rank Dimension"
        REAL target_utilization_percentage "Target Utilization %"
        REAL target_charged_hours_per_fte "Target Charged Hours/FTE"
        REAL target_headcount_fte "Target Headcount FTE"
    }

    employees ||--o{ charged_hours : "charges time"
    projects ||--o{ charged_hours : "receives charges"
    
    %% Conceptual Link - Targets apply to aggregated hours/employees based on dimensions
    %% Mermaid doesn't directly support linking a composite key table based on multiple non-key fields in other tables easily.
    %% We represent the conceptual link via comments or potentially linking one dimension as representative.
    employees }|..|{ targets : "has target based on dimensions"

```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Microsoft AutoGen team for the multi-agent framework
- Streamlit team for the UI framework
- Task Master for development workflow management

# Agents Project

This project aims to build a system of autonomous agents using the AutoGen framework to monitor and analyze performance data based on charged hours, targets, and master file information.

## Project Status (as of [Current Date] - Please update)

The project has progressed through the initial setup, data ingestion, database tooling implementation, and the initial configuration of the first agent.

## Setup

1.  **Environment Variables:** Create a `.env` file in the root directory and configure your OpenAI API key and other settings:
    ```dotenv
    # Required
    OPENAI_API_KEY="your_openai_api_key_here"

    # Optional (Defaults shown, adjust if using Azure etc.)
    OPENAI_API_BASE="https://api.openai.com/v1"
    OPENAI_API_VERSION="2024-02-15"
    OPENAI_API_TYPE="open_ai"
    # MODEL="gpt-4"
    # MAX_TOKENS=4000
    # TEMPERATURE=0.7
    ```
2.  **Dependencies:** (TODO: Create `requirements.txt`) Install necessary Python packages (e.g., `pyautogen`, `pandas`, `python-dotenv`, `pytest`).
3.  **Database:** The application uses a SQLite database (`db/database.db`). The necessary tables (`charged_hours`, `targets`, `master_file`) are created/managed by the data ingestion processors and database tools.

## Directory Structure

```
├── .env                # Environment variables (API keys, config)
├── .gitignore          # Git ignore file
├── README.md           # This file
├── db/                 # Database files
│   └── database.db     # SQLite database
├── src/                # Source code
│   ├── agents/         # Agent implementations
│   │   ├── __init__.py
│   │   └── monitoring_agent.py # Initial setup for monitoring agent
│   ├── db/             # Database interaction logic
│   │   ├── __init__.py
│   │   ├── charged_hours_processor.py # Ingestion logic for charged hours
│   │   ├── master_file_processor.py  # Ingestion logic for master file data
│   │   ├── targets_processor.py     # Ingestion logic for targets
│   │   └── tools.py                 # Utility functions for DB querying/calculations
│   ├── ui/             # User interface components (if any)
│   │   └── __init__.py
│   └── utils/          # Utility functions
│       └── __init__.py
├── tasks/              # Task management files (generated by task-master)
│   ├── tasks.json      # Main task list
│   └── task_*.txt      # Individual task details
└── tests/              # Unit and integration tests
    ├── __init__.py
    └── unit/
        ├── __init__.py
        └── db/
            ├── __init__.py
            ├── test_charged_hours_processor.py
            ├── test_master_file_processor.py
            ├── test_targets_processor.py
            └── test_tools.py
```

## Implemented Components

### 1. Data Ingestion Processors (`src/db/*_processor.py`)

*   Classes responsible for reading source data files (e.g., Excel), transforming the data (cleaning, type conversion, renaming columns), and loading it into the corresponding database tables.
*   Includes error handling and logging.
*   Currently implemented for `charged_hours`, `master_file`, and `targets`.

### 2. Database Tools (`src/db/tools.py`)

*   Provides functions to interact with the SQLite database:
    *   `get_db_connection()`: Establishes connection.
    *   `execute_query()`: Executes arbitrary SQL queries and returns results as Pandas DataFrames.
    *   `get_performance_data()`: Retrieves charged hours data with filtering options.
    *   `get_targets()`: Retrieves target data with filtering options.
    *   `get_employee_data()`: Retrieves distinct employee details from the master file.
    *   `get_project_data()`: Retrieves distinct project details from the master file.
    *   `calculate_utilization()`: Calculates utilization based on charged and target hours.

### 3. Agents (`src/agents/`)

*   **Monitoring Agent (`monitoring_agent.py`):**
    *   Initial setup using `autogen.AssistantAgent`.
    *   Configured with a system prompt defining its role (querying, analysis, comparison, deviation detection, forecasting, alerting) and emphasizing the use of conversation history/memory.
    *   LLM configuration placeholder included.

### 4. Testing (`tests/`)

*   Unit tests using `pytest` are implemented for:
    *   Data Ingestion Processors (`test_*_processor.py`)
    *   Database Tools (`test_tools.py`)
*   Tests utilize fixtures and mocking (where appropriate) to ensure isolated testing of component logic.

### 5. Task Management (`tasks/`)

*   The project uses `task-master` (via `npx`) to manage the development workflow. Tasks are defined in `tasks.json` and detailed in individual `task_*.txt` files.

## Next Steps

*   Continue implementation of the Monitoring Agent (Task #5), focusing on data querying, comparison logic, and memory updates (Subtask 5.2).
*   Create `requirements.txt`.
*   Refine agent configurations and potentially implement more sophisticated memory mechanisms.