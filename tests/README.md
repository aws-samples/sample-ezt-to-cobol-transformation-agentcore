# Test Suite for ASM-to-COBOL BRE Translation

This directory contains unit and integration tests for the BRE-based ASM-to-COBOL translation system.

## Running Tests

### Run all tests
```bash
python -m pytest tests/
```

### Run specific test file
```bash
python -m pytest tests/test_bre_extractor.py -v
```

### Run with coverage
```bash
PYTHONPATH=src python -m pytest tests/ --cov=services --cov=llm --cov=utils --cov-report=term-missing
```

### Run specific test class or method
```bash
python -m pytest tests/test_bre_extractor.py::TestBREExtractor::test_extract_bre_success -v
```

## Test Structure

### test_bre_extractor.py
Tests for the Business Rules Extraction service:
- ✅ Extract BRE with sample Assembly code
- ✅ Save/load BRE documents
- ✅ Mock LLM responses for deterministic testing
- ✅ Error handling (invalid JSON, missing fields, LLM exceptions)
- ✅ Data structure validation (BusinessRule, DataMapping, BREDocument)
- ✅ Edge cases (empty code, multiple rules)

**Coverage: 93%**

### test_spec_generator.py
Tests for the Functional Specification Generator service:
- ✅ Generate spec with sample BRE documents
- ✅ Test data structure design from business rules
- ✅ Test process flow design from business rules
- ✅ Test business rules coverage mapping
- ✅ Save/load functional specifications
- ✅ Mock LLM responses for deterministic testing
- ✅ Error handling (invalid JSON, non-list responses, LLM exceptions)
- ✅ Data structure validation (FunctionalSpec dataclass)
- ✅ Edge cases (empty BRE, multiple rules, special characters)
- ✅ Overview generation
- ✅ Directory creation for nested paths

**Coverage: 93%**

## Test Fixtures

### Mock Data
- `SAMPLE_ASM_CODE`: Sample Assembly code for testing
- `MOCK_BUSINESS_RULES_RESPONSE`: Mock LLM response for business rules
- `MOCK_DATA_MAPPINGS_RESPONSE`: Mock LLM response for data mappings

### Fixtures
- `mock_llm_client`: Mocked SonnetClient for deterministic testing
- `bre_extractor`: BREExtractor instance with mocked dependencies
- `temp_dir`: Temporary directory for file I/O tests

## Testing Best Practices

1. **Mock LLM Calls**: All tests mock the LLM client to avoid actual API calls
2. **Deterministic Results**: Tests use fixed mock responses for reproducibility
3. **Error Handling**: Tests verify graceful handling of errors and edge cases
4. **File I/O**: Tests use temporary directories to avoid polluting the workspace
5. **Coverage**: Aim for >90% code coverage for all services

## Adding New Tests

When adding tests for new services:

1. Create a new test file: `test_<service_name>.py`
2. Import the service with proper path handling:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
   from services.<service_name> import ServiceClass
   ```
3. Mock external dependencies (LLM client, file I/O)
4. Test happy path, error cases, and edge cases
5. Verify code coverage is >90%

## Test Categories

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions (coming soon)
- **Error Handling Tests**: Verify graceful error handling
- **Edge Case Tests**: Test boundary conditions and unusual inputs

## Dependencies

Install the pinned test dependencies with:

```bash
python -m pip install -r requirements-dev.txt
```

- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `unittest.mock` - Mocking framework (built-in)

Exact versions are pinned in [`requirements-dev.txt`](../requirements-dev.txt).

## Notes

- Tests use `PYTHONPATH=src` to properly resolve imports
- Mock responses are defined as JSON strings for realistic testing
- Temporary directories are automatically cleaned up after tests
- All tests should be independent and not rely on external state
