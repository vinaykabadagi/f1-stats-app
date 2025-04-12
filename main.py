from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
import os
import re
from google import genai
from fastapi.staticfiles import StaticFiles
from typing import List, Dict, Any, Optional
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import redis.asyncio as redis

# Load environment variables
load_dotenv()

# FastAPI app
app = FastAPI(title="F1 Stats API",
             description="API for querying Formula 1 statistics",
             version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("ALLOWED_ORIGINS", "https://f1-stats-app.onrender.com")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Create connection pool
try:
    connection_pool = pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        user=os.getenv("SUPABASE_USER"),
        password=os.getenv("SUPABASE_PASSWORD"),
        host=os.getenv("SUPABASE_HOST"),
        port=os.getenv("SUPABASE_PORT"),
        dbname=os.getenv("SUPABASE_DBNAME")
    )
except Exception as e:
    print(f"Failed to create connection pool: {e}")
    raise

class QueryRequest(BaseModel):
    query: str

def get_db_connection():
    try:
        conn = connection_pool.getconn()
        return conn
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Database connection error",
                "error": str(e)
            }
        )

# Custom error handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail if isinstance(exc.detail, str) else exc.detail.get("message"),
            "details": exc.detail if isinstance(exc.detail, dict) else None
        }
    )

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
            model="gemini-2.0-flash", 
            contents=prompt
        )
        
        if not response or not response.text:
            raise ValueError("No response from LLM")
            
        sql_query = response.text.strip()
        
        # Clean up the SQL query
        sql_query = sql_query.split("SQL:")[-1].strip()
        if "```" in sql_query:
            sql_query = re.search(r"```(?:sql)?(.*?)```", sql_query, re.DOTALL)
            if sql_query:
                sql_query = sql_query.group(1).strip()
            
        if not sql_query:
            raise ValueError("Failed to generate valid SQL query")
            
        return sql_query
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Failed to generate SQL query",
                "error": str(e)
            }
        )

# Initialize Redis for rate limiting
@app.on_event("startup")
async def startup():
    try:
        # Get Redis URL from environment variable (Render provides this)
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(redis_url, decode_responses=True)
        await FastAPILimiter.init(redis_client)
    except Exception as e:
        print(f"Warning: Rate limiting is disabled - Redis connection failed: {e}")
        # Continue without rate limiting if Redis is not available
        pass

# Add rate limiting to the query endpoint, but make it optional
async def get_rate_limiter():
    if FastAPILimiter._redis:  # Only apply rate limiting if Redis is connected
        return RateLimiter(times=10, seconds=60)
    return None

@app.post("/query")
async def run_query(
    request: QueryRequest,
    rate_limit: Optional[Any] = Depends(get_rate_limiter)
) -> Dict[str, Any]:
    try:
        # Input validation
        if not request.query.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Query cannot be empty",
                    "error": "Invalid input"
                }
            )

        # Generate SQL
        sql_query = generate_sql_query(request.query)
        
        # Validate query for security
        sql_lower = sql_query.lower()
        if not re.match(r"^\s*SELECT\b", sql_lower):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Only SELECT queries are allowed",
                    "error": "Security violation"
                }
            )
            
        dangerous_keywords = ["drop", "delete", "truncate", "alter", "insert", "update"]
        if any(keyword in sql_lower for keyword in dangerous_keywords):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Unsafe SQL query detected",
                    "error": "Security violation"
                }
            )

        allowed_tables = {"circuits", "constructors", "drivers", "races", "results"}
        if not any(table in sql_lower for table in allowed_tables):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Invalid table referenced",
                    "error": "Security violation"
                }
            )

        # Execute query with pagination
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql_query)
            results = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            formatted_results = [dict(zip(columns, row)) for row in results]
            
            return {
                "query": request.query,
                "sql": sql_query,
                "results": formatted_results,
                "count": len(formatted_results)
            }
        finally:
            cur.close()
            connection_pool.putconn(conn)
            
    except psycopg2.Error as e:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Database error",
                "error": str(e)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Internal server error",
                "error": str(e)
            }
        )

# Cleanup connection pool when app stops
@app.on_event("shutdown")
async def shutdown():
    if connection_pool:
        connection_pool.closeall()
