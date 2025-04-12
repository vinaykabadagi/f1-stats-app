from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
import os
import re
from google import genai
from fastapi.staticfiles import StaticFiles
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
def get_db_connection():
    try:
        conn = psycopg2.connect(
            user=os.getenv("SUPABASE_USER"),
            password=os.getenv("SUPABASE_PASSWORD"),
            host=os.getenv("SUPABASE_HOST"),
            port=os.getenv("SUPABASE_PORT"),
            dbname=os.getenv("SUPABASE_DBNAME")
        )
        print("Database connection established")
        return conn
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# Hugging Face Inference API client
client = genai.Client(api_key=os.getenv("gemini_api_key"))

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

@app.post("/query")
async def run_query(request: QueryRequest):
    try:
        # Generate SQL
        sql_query = generate_sql_query(request.query)
        
        # Validate query
        if not re.match(r"^\s*SELECT\b", sql_query, re.IGNORECASE):
            
            raise HTTPException(status_code=400, detail="Only SELECT queries allowed")
        if any(dangerous in sql_query.lower() for dangerous in ["drop", "delete", "truncate", "alter", "insert", "update"]):
            raise HTTPException(status_code=400, detail="Unsafe SQL query detected")
        allowed_tables = {"circuits", "constructors", "drivers", "races", "results"}
        if not any(table in sql_query.lower() for table in allowed_tables):
            raise HTTPException(status_code=400, detail="Invalid table referenced")

        # Execute query
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql_query)
        results = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()

        # Format results
        formatted_results = [dict(zip(columns, row)) for row in results]
        return {"query": request.query, "sql": sql_query, "results": formatted_results}
    except psycopg2.Error as e:
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
