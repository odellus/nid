"""
Configuration settings for NID Agent.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
ZAI_API_KEY = os.getenv("ZAI_API_KEY")
ZAI_BASE_URL = os.getenv("ZAI_BASE_URL")

# Model Configuration
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "glm-5")

# Database Configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", "sqlite:///mcp_testing.db")

# MCP Configuration
DEFAULT_MCP_PATH = os.getenv("DEFAULT_MCP_PATH", "src/nid/mcp/search.py")
