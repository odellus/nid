#!/usr/bin/env python3
"""Helper script to view terminal logs."""

import os
import sys
from pathlib import Path

log_dir = Path.home() / ".cache" / "crow-mcp" / "logs"

if not log_dir.exists():
    print("No logs directory found. Run a terminal command first.")
    sys.exit(1)

log_files = sorted(log_dir.glob("terminal_*.log"), reverse=True)

if not log_files:
    print("No log files found. Run a terminal command first.")
    sys.exit(1)

print(f"Found {len(log_files)} log files:\n")
for i, log_file in enumerate(log_files[:5]):  # Show last 5
    size = os.path.getsize(log_file)
    mtime = os.path.getmtime(log_file)
    from datetime import datetime
    timestamp = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
    print(f"{i+1}. {log_file.name} ({size} bytes, {timestamp})")

print(f"\nMost recent log file: {log_files[0]}")
print(f"View with: cat {log_files[0]}")
print(f"Tail with: tail -f {log_files[0]}")
print(f"Less with: less {log_files[0]}")
