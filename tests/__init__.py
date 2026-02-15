"""
Test suite for Crow Agent.

This test suite follows a multi-level testing strategy:

1. **Unit Tests** (`tests/unit/`)
   - Fast, isolated tests
   - Test individual functions and classes
   - Mock all external dependencies

2. **Integration Tests** (`tests/integration/`)
   - Test component interactions
   - Use real database (temporary)
   - Test resource lifecycle

3. **End-to-End Tests** (`tests/e2e/`)
   - Test complete user flows
   - Full stack integration
   - Real-world scenarios

## Running Tests

Run all tests:
```bash
pytest
```

Run specific test levels:
```bash
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
```

Run with markers:
```bash
pytest -m unit
pytest -m "not slow"
```

Run with coverage:
```bash
pytest --cov=src/crow --cov-report=html
```
"""

__test__ = True
