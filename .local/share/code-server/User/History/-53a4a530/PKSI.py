import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
#import utils

# ==========================================
# FastAPI Application Initialization
# ==========================================
# This instantiates the core FastAPI app, configuring metadata 
# that automatically populates the interactive Swagger UI (/docs) 
# and ReDoc (/redoc) documentation endpoints.
# run using uvicorn main:app --host 0.0.0.0 --port 8000 --reload
app = FastAPI(
    title="OpenAI Async FastAPI Service",
    description="FastAPI service with token usage and cost tracking.",
    version="4.2.0"
)

# Initialize the official Async OpenAI client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configuration defaults & Pricing (per million tokens)
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TEMPERATURE = 0.7
SYSTEM_PROMPT = "You are a helpful assistant. Restrict your response to a maximum of 20 words."

INPUT_COST_PER_MILLION = 0.15   # $0.15 per million input tokens
OUTPUT_COST_PER_MILLION = 0.60  # $0.60 per million output tokens


# ==========================================
# Pydantic Models (Question & Answer)
# ==========================================

# ==========================================
# Input Data Validation Model (Pydantic)
# ==========================================
class Question(BaseModel):
    """Input model containing only the user query."""

    # 'query' is a required string field.
    # '...' (ellipsis) inside Field() marks this field as mandatory (no default value allowed).
    # 'description' provides metadata that automatically populates the interactive Swagger UI (/docs).
    query: str = Field(..., description="User question")

# ==========================================
# Token Telemetry & Cost Model (Pydantic)
# ==========================================
class TokenUsage(BaseModel):
    """Token consumption metrics and estimated cost."""  # Class docstring summarizing the telemetry schema
    
    prompt_tokens: int        # Number of tokens consumed by the input prompt/request
    completion_tokens: int    # Number of tokens generated in the model's response
    total_tokens: int         # Combined sum of prompt and completion tokens
    
    # 'cost_usd' tracks the calculated financial cost.
    # '...' marks it as a required field, and 'description' populates the Swagger UI (/docs) metadata.
    cost_usd: float = Field(..., description="Estimated cost in USD")


# ==========================================
# Standardized Output Response Model (Pydantic)
# ==========================================
class Answer(BaseModel):
    """Standardized output model for non-streaming responses."""  # Class docstring summarizing the response payload
    
    # 'model' is a required string field indicating which OpenAI model processed the request (e.g., "gpt-4o-mini").
    model: str = Field(..., description="The model used for generation")
    
    # 'response' is a required string field containing the actual generated text returned by the model.
    response: str = Field(..., description="The generated response/answer")
    
    # 'usage' is an optional field of type 'TokenUsage'. 
    # It defaults to None if token telemetry is not present or disabled for the request.
    usage: Optional[TokenUsage] = Field(None, description="Token usage details")


# ==========================================
# Cost Calculation Utility Function
# ==========================================
def calculate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    """Calculates total cost in USD based on token counts."""
    
    # Calculate input token cost: 
    # Divide prompt tokens by 1 million, then multiply by the configured input cost rate.
    input_cost = (prompt_tokens / 1000000) * INPUT_COST_PER_MILLION
    
    # Calculate output token cost: 
    # Divide completion tokens by 1 million, then multiply by the configured output cost rate.
    output_cost = (completion_tokens / 1000_000) * OUTPUT_COST_PER_MILLION
    
    # Combine input and output costs, rounding to 7 decimal places 
    # to maintain high precision for micro-transactions and small token counts.
    return round(input_cost + output_cost, 7)


def build_messages(query: str):
    """Helper to construct the prompt with system instructions."""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query}
    ]

# ==========================================
# OpenAI Streaming Generator Function
# ==========================================
async def generate_openai_stream(query: str):
    """Helper generator function to stream chunks safely and publish usage at the end."""
    try:
        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=build_messages(query),
            temperature=DEFAULT_TEMPERATURE,
            stream=True,
            stream_options={"include_usage": True}
        )
        
        async for chunk in response:
            if chunk.usage is not None:
                usage_data = chunk.usage
                cost = calculate_cost(usage_data.prompt_tokens, usage_data.completion_tokens)
                yield f"\n\n[Usage Stats] Prompt Tokens: {usage_data.prompt_tokens} | Completion Tokens: {usage_data.completion_tokens} | Total Tokens: {usage_data.total_tokens} | Estimated Cost: ${cost:.6f}"
                break

            if chunk.choices and len(chunk.choices) > 0:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
                    
    except Exception as e:
        yield f"\n[Error: {str(e)}]"



# ==========================================
# 1. GET Method
# ==========================================

@app.get("/")
async def root():
    return {"message": "AI Application API is running! Check /docs for endpoints."}

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
# GET Generation Endpoint
# ==========================================
@app.get("/generate/get", response_model=Answer, summary="Generate answer using GET")
async def generate_get(
    query: str = Query(..., description="The user query"),  # Required query string parameter from URL
    stream: bool = Query(False, description="Enable streaming response")  # Optional flag to toggle streaming mode
):
    """
    **GET Endpoint**: Takes only a `query` string parameter.
    """
    try:
        # Branch 1: Handle streaming response if 'stream=true' is passed
        if stream:
            return StreamingResponse(
                generate_openai_stream(query),
                media_type="text/plain"  # Plain text stream format for typewriter UI rendering
            )
        
        # Branch 2: Handle standard (non-streaming) JSON response
        else:
            # Request a standard completion from the OpenAI async client
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=build_messages(query),
                temperature=DEFAULT_TEMPERATURE
            )
            
            # Extract token usage telemetry from the API response object
            usage_data = response.usage
            usage_obj = None
            
            if usage_data:
                # Compute cost in USD using prompt and completion token totals
                cost = calculate_cost(usage_data.prompt_tokens, usage_data.completion_tokens)
                # Construct the structured TokenUsage Pydantic sub-model
                usage_obj = TokenUsage(
                    prompt_tokens=usage_data.prompt_tokens,
                    completion_tokens=usage_data.completion_tokens,
                    total_tokens=usage_data.total_tokens,
                    cost_usd=cost
                )

            # Return the finalized response formatted against the 'Answer' Pydantic model
            return Answer(
                model=DEFAULT_MODEL,
                response=response.choices[0].message.content,
                usage=usage_obj
            )
            
    except Exception as e:
        # Catch any unexpected runtime errors and raise a standardized HTTP 500 error
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# 2. POST Method
# ==========================================


@app.post("/generate/post", response_model=Answer, summary="Generate answer using POST")
async def generate_post(
    question: Question,  # Automatically validates incoming JSON body against the 'Question' Pydantic model
    stream: bool = Query(False, description="Enable streaming response")  # Optional query param to toggle streaming mode
):
    """
    **POST Endpoint**: Accepts a JSON body with only the `query` field.
    """
    try:
        # Branch 1: Handle streaming response if 'stream=true' query parameter is provided
        if stream:
            return StreamingResponse(
                generate_openai_stream(question.query),
                media_type="text/plain"  # Plain text stream format for typewriter UI consumption
            )
        
        # Branch 2: Handle standard (non-streaming) JSON response
        else:
            # Send an asynchronous completion request to OpenAI using the validated query text
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=build_messages(question.query),
                temperature=DEFAULT_TEMPERATURE
            )
            
            # Extract token usage telemetry returned from the OpenAI response
            usage_data = response.usage
            usage_obj = None
            
            if usage_data:
                # Calculate estimated cost in USD based on input/output token counts
                cost = calculate_cost(usage_data.prompt_tokens, usage_data.completion_tokens)
                # Build the structured TokenUsage Pydantic model object
                usage_obj = TokenUsage(
                    prompt_tokens=usage_data.prompt_tokens,
                    completion_tokens=usage_data.completion_tokens,
                    total_tokens=usage_data.total_tokens,
                    cost_usd=cost
                )

            # Return the final structured answer matching the 'Answer' response model
            return Answer(
                model=DEFAULT_MODEL,
                response=response.choices[0].message.content,
                usage=usage_obj
            )
            
    except Exception as e:
        # Catch any unexpected runtime errors and raise an HTTP 500 error with the exception details
        raise HTTPException(status_code=500, detail=str(e))
