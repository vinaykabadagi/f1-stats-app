# F1 Stats App

An interactive Formula 1 statistics application that allows users to query F1 data using natural language and visualize the results.

## Features

- Natural language to SQL query conversion
- Real-time data visualization using Chart.js
- Interactive data tables
- Export results to CSV
- Secure query execution with SQL injection prevention
- Connection pooling for better performance
- Error handling and user feedback
- Responsive design

## Prerequisites

- Python 3.x
- PostgreSQL database
- Node.js (optional, for development)

## Installation

1. Clone the repository
2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
SUPABASE_USER=your_db_user
SUPABASE_PASSWORD=your_db_password
SUPABASE_HOST=your_db_host
SUPABASE_PORT=your_db_port
SUPABASE_DBNAME=your_db_name
gemini_api_key=your_gemini_api_key
```

## Running the Application

1. Start the FastAPI server:
```bash
uvicorn main:app --reload
```

2. Open your browser and navigate to:
```
http://localhost:8000/static/index.html
```

## Usage

1. Enter a natural language query about F1 statistics in the input field
2. Click "Submit" or press Enter
3. View the generated SQL and results table
4. Explore the data visualization (if applicable)
5. Export results to CSV if needed

## Example Queries

- Show me points scored by each constructor in 2023
- Who had the most fastest laps in 2023?
- Show me all Monaco Grand Prix winners
- Compare Hamilton and Verstappen's points in 2021
- Which drivers scored points in every race of 2023?

## API Reference

### POST /query

Accepts natural language queries and returns F1 statistics.

Request body:
```json
{
    "query": "string"
}
```

Response:
```json
{
    "query": "string",
    "sql": "string",
    "results": array,
    "count": number
}
```

## Security

- SQL injection prevention
- Input validation
- Query type restrictions (SELECT only)
- Table access restrictions

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request