from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import engine as database
from app.generator import OpenAICompatibleGenerator, RuleBasedGenerator
from app.service import TextToSQLEngine

app = FastAPI(
    title="Self-Correcting Text-to-SQL Engine",
    description="Read-only Text-to-SQL with AST guardrails and typed execution-feedback repair.",
    version="1.0.0",
)
generator = OpenAICompatibleGenerator() if settings.llm_api_key else RuleBasedGenerator()
pipeline = TextToSQLEngine(database, generator=generator)


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class RepairEntry(BaseModel):
    attempt: int
    failure_type: str
    error_message: str


class QueryResponse(BaseModel):
    status: str
    final_sql: str
    results: list[dict[str, Any]]
    iterations: int
    repair_history: list[RepairEntry]


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with database.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return {"status": "unhealthy", "database": "unavailable"}
    return {"status": "healthy", "database": "connected"}


@app.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    outcome = pipeline.query(request.question)
    return QueryResponse(**outcome.__dict__)