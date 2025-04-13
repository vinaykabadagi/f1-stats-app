# F1 Stats App

An interactive Formula 1 statistics application that allows users to query F1 data using natural language through an intuitive web interface.

## Features

- Natural language to SQL query conversion using Google's Gemini AI
- Real-time SQL query generation and execution
- Interactive data tables with responsive design
- Query debouncing for better performance
- Connection pooling for efficient database management
- Comprehensive SQL injection prevention
- Automatic loading states and error handling
- F1-themed modern UI design

## Tech Stack

- Backend: FastAPI + Python 3.x
- Database: PostgreSQL (via Supabase)
- AI: Google Gemini API
- Frontend: Vanilla JavaScript with modern ES6+ features
- Styling: Custom CSS with responsive design

## Prerequisites

- Python 3.x
- PostgreSQL database (Supabase account)
- Google Gemini API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd f1-stats-app
```

2. Create a virtual environment and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
SUPABASE_USER=your_db_user
SUPABASE_PASSWORD=your_db_password
SUPABASE_HOST=your_db_host
SUPABASE_PORT=5432
SUPABASE_DBNAME=your_db_name
GEMINI_API_KEY=your_gemini_api_key
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

1. Enter a natural language query in the text area
2. The query will be automatically processed after typing (with debouncing)
3. View the generated SQL query in the code section
4. See the results in a responsive table format
5. Error messages will be displayed if something goes wrong

## Example Queries

- "Who won the most races in 2023?"
- "Show me all Monaco Grand Prix winners"
- "Compare Hamilton and Verstappen's points in 2021"
- "Which drivers scored points in every race of 2023?"
- "Show me the fastest lap times at Silverstone"

## Database Schema

The application uses the following tables:
- `circuits`: Track information and locations
- `constructors`: F1 teams/constructors
- `drivers`: Driver information
- `races`: Race event details
- `results`: Race results and statistics

## API Endpoints

### POST /query
Converts natural language to SQL and returns F1 statistics.

Request:
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

## Security Features

- SQL injection prevention through query validation
- Input sanitization and validation
- Query type restrictions (SELECT only)
- Table access restrictions
- Connection pooling with automatic cleanup
- Error logging and handling

## Error Handling

- Invalid query detection
- Database connection error handling
- AI model error handling
- Frontend error display with user-friendly messages
- Comprehensive server-side logging

## Development

The application uses:
- FastAPI for efficient API handling
- Pydantic for data validation
- psycopg2 connection pooling for database efficiency
- Google Gemini AI for natural language processing
- Modern JavaScript with async/await patterns
- CSS custom properties for theming