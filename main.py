from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
import os
import re
from google import genai
from fastapi.staticfiles import StaticFiles
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# FastAPI app
app = FastAPI()

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic model for request
class QueryRequest(BaseModel):
    query: str

# Database connection
pool = None

def init_db_pool():
    global pool
    pool = SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT"),
        dbname=os.getenv("SUPABASE_DBNAME")
    )

@contextmanager
def get_db_connection():
    conn = None
    try:
        conn = pool.getconn()
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    finally:
        if conn:
            pool.putconn(conn)

# Initialize Google Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # Updated to match .env

# SQL generation prompt
SQL_PROMPT = """
You are an expert F1 statistician and SQL query generator.You have access to a database with the following tables and exact column definitions:
- Table: circuits
  - "circuitId" (TEXT, Primary Key)
  - "circuitRef" (TEXT, NOT NULL)
  - "name" (TEXT, NOT NULL)
  - "location" (TEXT)
  - "country" (TEXT)
  - "lat" (FLOAT)
  - "lng" (FLOAT)
  - "alt" (INTEGER)
  - "url" (TEXT)

- Table: constructors
  - "constructorId" (TEXT, Primary Key)
  - "constructorRef" (TEXT, NOT NULL)
  - "name" (TEXT, NOT NULL)
  - "nationality" (TEXT)
  - "url" (TEXT)

- Table: drivers
  - "driverId" (TEXT, Primary Key)
  - "driverRef" (TEXT, NOT NULL)
  - "number" (TEXT)
  - "code" (TEXT)
  - "forename" (TEXT, NOT NULL)
  - "surname" (TEXT, NOT NULL)
  - "dob" (DATE)
  - "nationality" (TEXT)
  - "url" (TEXT)

- Table: races
  - "raceId" (TEXT, Primary Key)
  - "year" (INTEGER, NOT NULL)
  - "round" (INTEGER, NOT NULL)
  - "circuitId" (TEXT, Foreign Key references circuits."circuitId")
  - "name" (TEXT, NOT NULL)
  - "date" (DATE, NOT NULL)
  - "time" (TEXT)
  - "url" (TEXT)

- Table: results
  - "resultId" (TEXT, Primary Key)
  - "raceId" (TEXT, Foreign Key references races."raceId")
  - "driverId" (TEXT, Foreign Key references drivers."driverId")
  - "constructorId" (TEXT, Foreign Key references constructors."constructorId")
  - "number" (INTEGER)
  - "grid" (TEXT)
  - "position" (TEXT)
  - "positionText" (TEXT)
  - "positionOrder" (INTEGER)
  - "points" (INTEGER)
  - "laps" (INTEGER)
  - "time" (TEXT)
  - "milliseconds" (TEXT)
  - "fastestLap" (TEXT)
  - "rank" (TEXT)
  - "fastestLapTime" (TEXT)
  - "fastestLapSpeed" (TEXT)
  - "statusId" (TEXT)

Rules:
**You will receive a natural language question about F1 data. Your task is to:**

1.  **Understand the user's intent.**
2.  **Translate the intent into a valid SQL query against the provided schema.**
- Return only one SQL query string, no explanations, markdown, or extra text.
- Enclose all column names in double quotes (e.g., results."driverId", drivers."surname").
- Generate a valid PostgreSQL SELECT query ONLY.
- Use exact column names as listed (e.g., results.driverId, not driver_id or driverId in other tables).
- Use correct join conditions based on foreign keys (e.g., results.driverId = drivers.driverId, not races.driverId).
- Use full table names (e.g., results, drivers) instead of aliases to avoid errors.
- Ensure the query is syntactically correct and executable.
- Return only the SQL query string, no explanations, markdown, or extra text.
- If the query is ambiguous, select relevant columns like drivers.forename, drivers.surname, races.name, races.date.
- driverId exists only in results and drivers; raceId exists only in results and races.
- If no valid query can be generated, return: SELECT drivers.forename, drivers.surname FROM drivers LIMIT 1;

Example:
SELECT drivers."forename", drivers."surname", races."name", races."date"
FROM results
JOIN drivers ON results."driverId" = drivers."driverId"
JOIN races ON results."raceId" = races."raceId"
WHERE drivers."surname" = 'Verstappen' AND races."year" = 2023 AND results."positionOrder" = 1;

Query: {query}
"""

def generate_sql_query(query: str) -> str:
    try:
        prompt = SQL_PROMPT.format(query=query)
        response = client.models.generate_content(
    model="gemini-2.0-flash", contents=prompt
)
        print(f"Raw LLM response : {response.text}")
        # Extract SQL query
        sql_query = response.text.strip()
        print(f"Raw SQL response: {sql_query}")
        # Clean up the SQL query
        sql_query = sql_query.split("SQL:")[-1].strip()
        if sql_query.startswith("```sql"):
            sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
        elif sql_query.startswith("```"):
            sql_query = sql_query.split("```")[1].strip()
        # Remove any leading/trailing whitespace
        sql_query = sql_query.strip()   
        if "```sql" in sql_query:
            sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql_query:
            sql_query = sql_query.split("```")[1].strip()
        print(f"Generated SQL: {sql_query}")
        return sql_query
    except Exception as e:
        print(f"Error generating SQL: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

def validate_sql_query(sql: str) -> bool:
    """Validate SQL query for security"""
    # Check for dangerous SQL commands
    dangerous_commands = [
        r'\bdrop\b', r'\bdelete\b', r'\btruncate\b', r'\balter\b',
        r'\binsert\b', r'\bupdate\b', r'\bcreate\b', r'\bexec\b',
        r'\bunion\b', r'\binto\b'
    ]
    if any(re.search(pattern, sql, re.IGNORECASE) for pattern in dangerous_commands):
        return False
        
    # Check if query starts with SELECT
    if not re.match(r"^\s*SELECT\b", sql, re.IGNORECASE):
        return False
        
    # Validate tables
    allowed_tables = {"circuits", "constructors", "drivers", "races", "results"}
    table_matches = re.findall(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)|JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql, re.IGNORECASE)
    tables = {match[0] or match[1] for match in table_matches}
    if not all(table.lower() in allowed_tables for table in tables):
        return False
        
    return True

@app.post("/query")
async def run_query(request: QueryRequest):
    try:
        # Generate SQL
        sql_query = generate_sql_query(request.query)
        
        # Validate query
        if not validate_sql_query(sql_query):
            raise HTTPException(status_code=400, detail="Invalid or unsafe SQL query")

        # Execute query with connection pooling
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_query)
                results = cur.fetchall()
                columns = [desc[0] for desc in cur.description]

        # Format results
        formatted_results = [dict(zip(columns, row)) for row in results]
        return {
            "query": request.query,
            "sql": sql_query,
            "results": formatted_results,
            "count": len(formatted_results)
        }
    except psycopg2.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """Initialize database pool when the application starts"""
    init_db_pool()
    logger.info("Application started, database pool initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Close all database connections when the application shuts down"""
    if pool:
        pool.closeall()
    logger.info("Application shutdown, database pool closed")
