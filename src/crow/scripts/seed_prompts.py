#!/usr/bin/env python
"""
Seed the database with initial prompt templates.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from crow.agent import create_database, Prompt
from crow.agent.db import Session as SQLAlchemySession
from sqlalchemy import create_engine


def seed_prompts(db_path: str = "sqlite:///mcp_testing.db"):
    """
    Seed the prompts table with initial templates.
    
    Args:
        db_path: Database connection string
    """
    # Create database if it doesn't exist
    create_database(db_path)
    
    # Get database session
    from sqlalchemy.orm import Session as ORMSession
    engine = create_engine(db_path)
    db = ORMSession(engine)
    
    try:
        # Check if prompts already exist
        existing = db.query(Prompt).first()
        if existing:
            print("Prompts already seeded")
            return
        
        # Load system prompt template
        prompt_path = Path(__file__).parent.parent / "agent" / "prompts" / "system_prompt.jinja2"
        with open(prompt_path) as f:
            template = f.read()
        
        # Create prompt record
        prompt = Prompt(
            id="crow-v1",
            name="Crow Default",
            template=template
        )
        db.add(prompt)
        
        # Create a minimal prompt variant
        minimal_prompt = Prompt(
            id="crow-minimal",
            name="Crow Minimal",
            template="You are Crow, a helpful AI assistant."
        )
        db.add(minimal_prompt)
        
        db.commit()
        print("✓ Seeded prompts table with default templates")
    finally:
        db.close()


if __name__ == "__main__":
    seed_prompts()
