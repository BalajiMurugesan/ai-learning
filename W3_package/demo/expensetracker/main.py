import os
import logging
import json
import sqlite3
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from pythonjsonlogger import jsonlogger

#import utils
# Use this command - uvicorn main:app --host 0.0.0.0 --port 8000 --reload

load_dotenv()

# Configure logging
# ==========================================
# CUSTOM JSON ARRAY LOGGING HANDLER
# ==========================================
class JSONArrayListHandler(logging.Handler):
    def __init__(self, filename="expenses_log.json"):
        """Initializes the custom handler with a target filename, 
        an empty list to store log records, and a JSON formatter."""
        super().__init__()
        self.filename = filename
        self.records = []  # In-memory storage for all captured log dictionaries
        
        # Sets up python-json-logger with standard timestamp, level, logger name, and message keys
        self.formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

    def emit(self, record):
        """Automatically called whenever a log message is generated. 
        Intercepts the log record, formats it into JSON, and appends it to memory."""
        try:
            # Format the log record into a JSON string using the JSON formatter
            formatted_msg = self.formatter.format(record)
            
            # Parse the JSON string back into a Python dictionary and store it in our list
            self.records.append(json.loads(formatted_msg))
        except Exception:
            # Standard Python logging error handler fallback if formatting fails
            self.handleError(record)

    def flush_to_file(self):
        """Dumps all collected log dictionaries from memory into the target file 
        as a properly structured and indented JSON array."""
        with open(self.filename, "a", encoding="utf-8") as f:
            # Serializes the Python list of dicts into a formatted JSON array with an indent of 4
            json.dump(self.records, f, indent=4, default=str)


# Configure logging and attach the custom handler
logger = logging.getLogger("expense_app")
logger.setLevel(logging.INFO)

# Instantiate the custom handler
json_handler = JSONArrayListHandler(filename="expenses_log.json")
logger.addHandler(json_handler)


client = AsyncOpenAI()

# Configuration defaults & Pricing (per million tokens)
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.0
INPUT_COST_PER_MILLION = 0.15   # $0.15 per million input tokens
OUTPUT_COST_PER_MILLION = 0.60  # $0.60 per million output tokens

app = FastAPI(
    title="My Personal Expense Tracker",
    description="API to extract structured expense details from natural language using OpenAI and store them in SQLite.",
    version="1.0.0"
)

# ==========================================
# REQUEST BODY MODEL
# ==========================================
class ExpenseRequest(BaseModel):
    user_input: str = Field(
        ...,
        example="I spent 500 INR on lunch today",
        description="Natural language expression of the expense",
    )

# ==========================================
# Token Telemetry & Cost Model (Pydantic)
# ==========================================
class TokenUsage(BaseModel):
    """Token consumption metrics and estimated cost."""
    prompt_tokens: int        # Number of tokens consumed by the input prompt/request
    completion_tokens: int    # Number of tokens generated in the model's response
    total_tokens: int         # Combined sum of prompt and completion tokens
    cost_usd: float = Field(..., description="Estimated cost in USD")


# ==========================================
# Structured Expense Record (Pydantic)
# ==========================================
class ExpenseSchema(BaseModel):
    transaction_date: date = Field(
        description="Date of the transaction mentioned in the input or inferred (YYYY-MM-DD format). If unknown, use today's date."
    )
    amount: float = Field(
        description="Numerical value of the expense amount"
    )
    currency: str = Field(
        description="Currency code or symbol, e.g., INR, USD, Rs, EUR"
    )
    transaction_type: str = Field(
        description="Category such as Travel Expense, Food Expense, Monthly Rent, Online Shopping, Utilities, Groceries, etc."
    )
    narrative: str = Field(
        description="A concise narrative or summary description of the expense"
    )

    @field_validator('transaction_date', mode='before')
    @classmethod
    def parse_date(cls, value):
        """Safely handles missing, unknown, or blank dates returned by the LLM 
        by falling back automatically to today's current date."""
        if isinstance(value, str) and (value.lower() == "unknown" or not value.strip()):
            return date.today()
        return value

# Response model combining extracted data and telemetry
class ExpenseResponse(BaseModel):
    extracted_expense: ExpenseSchema
    usage: TokenUsage


DB_NAME = "expenses.db"

# Method to initialize the database
def init_db():
    """Initializes the SQLite database and creates the expenses table synchronously."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date TEXT,
                amount REAL,
                currency TEXT,
                transaction_type TEXT,
                narrative TEXT,
                raw_input TEXT
            )
        """)
        conn.commit()
    logger.info("Database initialized and table created.")


# ==========================================
# Cost Calculation Utility Function
# ==========================================
def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculates total cost in USD based on token counts."""
    input_cost = (prompt_tokens / 1000000) * INPUT_COST_PER_MILLION
    output_cost = (completion_tokens / 1000000) * OUTPUT_COST_PER_MILLION
    return round(input_cost + output_cost, 7)


# ==========================================
# HELPER: BUILD MESSAGES PAYLOAD
# ==========================================
def build_messages(query: str):
    current_date_str = date.today().strftime("%Y-%m-%d")
    SYSTEM_PROMPT = f"""
    You are an expert financial assistant. Extract transaction details accurately from the user's natural language input and return a JSON object with these exact keys:
    
    1. 'transaction_date': String in YYYY-MM-DD format. 
        - CRITICAL RULE: The current absolute date is {current_date_str}. 
        - Resolve all relative terms ('today', 'yesterday', 'last night', 'this morning') strictly relative to {current_date_str}. 
        - Never use historical years (such as 2023 or 2024). If unknown, default to {current_date_str}.
    
    2. 'amount': Numerical float value of the expense.
    
    3. 'currency': Standardized ISO 4217 currency code (e.g., INR, USD, EUR). Convert symbols like 'Rs' or '₹' to 'INR'.
    
    4. 'transaction_type': Category (e.g., Travel Expense, Food Expense, Monthly Rent, Online Shopping).
    
    5. 'narrative': A concise summary description of the expense.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]


# =======================================
# Initiate Creation of Database
# =======================================
@app.on_event("startup")
def startup_event():
    init_db()

# =======================================
# Root call
# =======================================
@app.get("/")
async def root():
    return {"message": "Expense AI Application API is running! Check /docs for endpoints."}

# ==========================================
# Health Check Endpoint
# ==========================================
@app.get("/health", summary="Health Check")  # Maps an HTTP GET request to the '/health' route
async def health():
    """
    Lightweight health check endpoint used by monitoring systems, 
    load balancers, and container orchestrators (like Kubernetes or Docker) 
    to verify that the FastAPI service is running and responsive.
    """
    # Return a simple dictionary confirming the service status is operational
    return {"status": "ok"}

# ==========================================
# API ENDPOINT
# ==========================================
@app.post("/expenses/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(payload: ExpenseRequest):
    try:
        messages = build_messages(payload.user_input)

        # Call OpenAI Chat Completions API with streaming and usage options enabled
        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            temperature=DEFAULT_TEMPERATURE,
            stream=True,
            stream_options={"include_usage": True},
            response_format={"type": "json_object"},
        )

        full_content = ""
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        # Iterate through the async stream chunks
        async for chunk in response:
            # Accumulate content deltas
            if chunk.choices and chunk.choices[0].delta.content:
                full_content += chunk.choices[0].delta.content
            
            # Capture usage data sent in the final chunk (enabled by stream_options)
            if chunk.usage:
                prompt_tokens = chunk.usage.prompt_tokens
                completion_tokens = chunk.usage.completion_tokens
                total_tokens = chunk.usage.total_tokens

        # Parse the accumulated JSON string into the Pydantic model
        extracted_data = ExpenseSchema.model_validate_json(full_content)

        # Calculate cost
        cost = calculate_cost(prompt_tokens, completion_tokens)

        # Save to SQLite database
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                """
                INSERT INTO expenses (transaction_date, amount, currency, transaction_type, narrative, raw_input)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(extracted_data.transaction_date),
                    extracted_data.amount,
                    extracted_data.currency,
                    extracted_data.transaction_type,
                    extracted_data.narrative,
                    payload.user_input
                )
            )
            conn.commit()

        # Logging transaction and usage cost
        logger.info(
            "Successfully validated and saved expense asynchronously",
            extra={
                "category": extracted_data.transaction_type,
                "expense_amount": extracted_data.amount,
                "curr": extracted_data.currency,
                "tx_date": extracted_data.transaction_date,
                "prompt_tokens": prompt_tokens,
                "completion_tokens":completion_tokens,
                "cost_usd": cost,
                "default_model": DEFAULT_MODEL
            }
        )

        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=cost
        )

        json_handler.flush_to_file()

        return ExpenseResponse(
            extracted_expense=extracted_data,
            usage=token_usage
        )

    except Exception as e:
        logger.error(f"Error processing expense extraction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the expense: {str(e)}"
        )