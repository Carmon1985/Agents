# Multi-Agent Monitoring System

A sophisticated monitoring system powered by AutoGen multi-agent architecture and Streamlit UI. The system uses multiple AI agents to monitor, analyze, and provide recommendations based on data inputs.

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