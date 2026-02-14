"""
Database schema for MCP Testing - Local LLM first persistence layer.

This module defines SQLAlchemy models for:
1. PROMPTS table - Versioned system prompt templates
2. SESSIONS table - The "DNA" of the agent (KV cache anchor)
3. EVENTS table - The "Wide" transcript (all conversation turns)
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    create_engine,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Prompt(Base):
    """System prompt templates - versioned, reusable"""

    __tablename__ = "prompts"

    id = Column(
        Text, primary_key=True, doc="Unique prompt ID (e.g., 'crow-v1', 'crow-minimal')"
    )
    name = Column(Text, nullable=False, doc="Display name")
    template = Column(Text, nullable=False, doc="Jinja2 template content")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship to sessions
    sessions = relationship("Session", back_populates="prompt")

    def __repr__(self) -> str:
        return f"<Prompt(id='{self.id}', name='{self.name}')>"


class Session(Base):
    """
    The "DNA" of the agent. This table anchors your KV cache.
    If a row exists with a specific hash, your local engine can skip the prefill.
    """

    __tablename__ = "sessions"

    session_id = Column(
        Text, primary_key=True, doc="Unique hash of prompt_id + prompt_args + tools"
    )
    prompt_id = Column(
        Text, ForeignKey("prompts.id"), nullable=True, doc="Reference to prompt template"
    )
    prompt_args = Column(
        JSON, nullable=True, doc="Arguments used to render the prompt template"
    )
    system_prompt = Column(
        Text, nullable=False, doc="The rendered system prompt (cached for reconstruction)"
    )
    tool_definitions = Column(
        JSON, nullable=False, doc="Full JSON schemas of all available MCP tools"
    )
    request_params = Column(
        JSON, nullable=False, doc="temperature, top_p, max_tokens, etc."
    )
    model_identifier = Column(
        Text,
        nullable=False,
        doc="Exact model version (e.g., 'glm-4.7' or 'llama-3-70b')",
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="When this agent configuration was first used",
    )

    # Relationships
    prompt = relationship("Prompt", back_populates="sessions")
    events = relationship(
        "Event", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Session(session_id='{self.session_id}', model='{self.model_identifier}')>"


class Event(Base):
    """
    The "Wide" transcript. Every row is a single turn.
    Captures thinking, speaking, and acting without needing to join multiple tables.
    """

    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Unique event ID")
    session_id = Column(
        Text,
        ForeignKey("sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        doc="Links back to static session config",
    )
    conv_index = Column(Integer, nullable=False, doc="Linear order of the conversation")
    timestamp = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        doc="Precise timing for latency and log-order analysis",
    )
    role = Column(
        Text, nullable=False, doc="user, assistant, tool, or custom tool_assistant"
    )
    content = Column(
        Text, nullable=True, doc="User: input; Assistant: verbal; Tool: JSON result"
    )
    reasoning_content = Column(
        Text, nullable=True, doc="Internal 'Thinking' tokens (hidden from user)"
    )
    tool_call_id = Column(
        Text, nullable=True, doc="Unique ID linking Assistant's intent to Tool's result"
    )
    tool_call_name = Column(
        Text, nullable=True, doc="Name of the function being executed"
    )
    tool_arguments = Column(
        JSON, nullable=True, doc="Arguments the model generated for the tool"
    )
    prompt_tokens = Column(
        Integer, nullable=True, doc="Input token count from API usage"
    )
    completion_tokens = Column(
        Integer, nullable=True, doc="Output token count from API usage"
    )
    total_tokens = Column(
        Integer, nullable=True, doc="Total token count from API usage"
    )
    event_metadata = Column(
        JSON, nullable=True, doc="Finish reasons, local GPU stats, or other metadata"
    )

    # Relationship to session
    session = relationship("Session", back_populates="events")

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, session_id='{self.session_id}', role='{self.role}', conv_index={self.conv_index})>"


def create_database(db_path: str = "sqlite:///mcp_testing.db") -> None:
    """
    Create the database and tables.

    Args:
        db_path: Database connection string (default: SQLite in current directory)
    """
    engine = create_engine(db_path)
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    create_database()
