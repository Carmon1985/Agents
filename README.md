# Resource Monitoring Agent

## Overview
An intelligent agent-based system for monitoring and analyzing resource utilization, built with Python and Streamlit. The agent provides interactive chat-based interface for querying resource data and generating insights.

## Recent Updates
- Enhanced UI with improved message display and timestamps
- Added clear conversation functionality
- Improved error handling and message formatting
- Streamlined chat interface with better user feedback
- Enhanced tool execution feedback with loading indicators
- Added comprehensive example queries in the sidebar

## Features
- Interactive chat interface for resource queries
- Real-time resource utilization analysis
- Data visualization capabilities
- Historical data analysis
- Forecasting capabilities
- Error handling and graceful degradation
- Clear conversation history option
- Timestamped messages
- Loading indicators for tool execution

## Setup
1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env`:
```
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.openai.com/v1  # Change if using Azure
OPENAI_API_VERSION=2024-02-15
OPENAI_API_TYPE=open_ai
```

4. Run the application:
```bash
streamlit run app.py
```

## Usage
1. Start the application
2. Use the chat interface to:
   - Query resource utilization
   - Generate forecasts
   - Analyze historical data
   - View visualizations
3. Example queries are provided in the sidebar
4. Use the "Clear Conversation" button to reset the chat

## Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key
- `OPENAI_API_BASE`: API endpoint (default: OpenAI, can be changed for Azure)
- `OPENAI_API_VERSION`: API version
- `OPENAI_API_TYPE`: API type (open_ai or azure)
- `MODEL`: Model name (optional)
- `MAX_TOKENS`: Maximum tokens (optional)
- `TEMPERATURE`: Temperature setting (optional)

## Project Structure
```
.
├── src/
│   ├── agents/
│   │   └── monitoring_agent.py
│   ├── db/
│   │   ├── charged_hours_processor.py
│   │   ├── master_file_processor.py
│   │   └── targets_processor.py
│   ├── ui/
│   └── utils/
├── tests/
│   ├── unit/
│   └── integration/
├── app.py
├── requirements.txt
└── .env
```

## Testing
Run tests using:
```bash
python -m pytest tests/
```

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License
[MIT License](LICENSE)