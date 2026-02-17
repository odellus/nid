"""
Crow Builtin MCP Server

Combines all builtin tools into one MCP server:
- file_editor: View, create, edit files
- web_search: Search the web via SearXNG
- fetch: Fetch and parse web pages

This is the default MCP server for crow agents.
"""

import base64
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

import charset_normalizer
import markdownify
import readabilipy.simple_json
from binaryornot.check import is_binary
from cachetools import LRUCache
from fastmcp import FastMCP
from httpx import AsyncClient
from pydantic import BaseModel

from crow_mcp.server import mcp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
