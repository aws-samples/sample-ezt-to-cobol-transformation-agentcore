# Test Suite Documentation

This document explains all tests in the ASM-to-COBOL BRE translation system.

## Test Organization

Tests are organized into two categories:

- **Unit Tests** (`tests/unit/`): Test individual components in isolation with mocked dependencies
- **Integration Tests** (`tests/integration/`): Test the complete pipeline end-to-end

## Running Tests

### Run All Tests
```bash
python -m pytest tests/
```

### Run Unit Tests Only
```bash
python -m pytest tests/unit/
```

### Run Integration Tests Only
```bash
python -m pytest tests/integration/
```

### Run Specific Test File
```bash
python -m pytest tests/unit/test_bre_extractor.py -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=src --cov-report=html
```

### Run Specific Test
```bash
python -m pytest tests/unit/test_bre_extractor.py::TestBREExtractor::test_extract_bre_success -v
```

## Unit Tests

### test_analyzer.py

Tests the Feedback Analyzer service that provides quality assessment and recommendations.

**What it tests:**
- Quality assessment categorization (excellent/good/fair/poor)
- Improvement area identification (syntax, structure, logic, data flow, BRE coverage)
- Recommendations generation based on validation results
- Quality metrics calculation
- BRE implementation analysis
- Code suggestions generation

**Key test cases:**
- Quality levels based on equivalence scores
- Identification of specific improvement areas
- Priority sorting of improvement areas
- BRE coverage analysis with good/poor implementations
- Code suggestions with various categories
- Executive summary generation

**Coverage:** 93%

**How to run:**
```bash
python -m pytest tests/unit/test_analyzer.py -v
```

---

### test_bre_cobol_generator.py

Tests the COBOL code generation service that creates COBOL from BRE and functional specifications.

**What it tests:**
- COBOL code generation from BRE and spec
- Syntax validity of generated COBOL
- Traceability comments in generated code
- Handling of multiple business rules
- Handling of complex data structures
- Error handling for LLM failures
- File saving and directory creation

**Key test cases:**
- Successful COBOL generation with valid inputs
- COBOL syntax structure validation
- Traceability header generation
- Multiple business rules handling
- Complex nested data structures
- Empty BRE document handling
- LLM exception handling
- Prompt context completeness

**Coverage:** 90%

**How to run:**
```bash
python -m pytest tests/unit/test_bre_cobol_generator.py -v
```

---

### test_bre_extractor.py

Tests the Business Rules Extraction service that extracts business rules and data mappings from Assembly code.

**What it tests:**
- BRE extraction from Assembly code
- Business rules identification
- Data mappings extraction
- JSON parsing and error handling
- File I/O operations (save/load)
- Handling of invalid LLM responses

**Key test cases:**
- Successful BRE extraction with valid Assembly
- Invalid JSON response handling
- Missing fields in JSON responses
- LLM exception handling
- Save and load BRE documents
- Directory creation for nested paths
- Empty Assembly code handling
- Multiple business rules extraction

**Coverage:** 95%

**How to run:**
```bash
python -m pytest tests/unit/test_bre_extractor.py -v
```

---

### test_spec_generator.py

Tests the Functional Specification Generator that creates COBOL specifications from BRE documents.

**What it tests:**
- Functional specification generation from BRE
- Data structure design
- Process flow design
- Business rules coverage mapping
- JSON parsing and error handling
- File I/O operations

**Key test cases:**
- Successful spec generation with valid BRE
- Invalid data structures JSON handling
- Invalid process flows JSON handling
- Non-list response handling
- LLM exception handling
- Save and load specifications
- Empty BRE document handling
- Multiple business rules handling
- Special characters in field names
- Business rule order preservation

**Coverage:** 92%

**How to run:**
```bash
python -m pytest tests/unit/test_spec_generator.py -v
```

---

### test_validator.py

Tests the Code Validator service that performs multi-level validation of generated COBOL code.

**What it tests:**
- Syntax validation
- Structure comparison
- Logic equivalence checking
- Data flow verification
- BRE coverage checking
- Spec compliance checking
- Equivalence score calculation
- Findings and recommendations generation

**Key test cases:**
- Good translation validation (high scores)
- Bad translation validation (low scores)
- Syntax error detection
- Equivalence score calculation with various inputs
- BRE coverage with full/partial implementation
- Spec compliance checking
- Bonus score application (BRE + Spec)
- Score threshold testing (0.7 pass/fail)
- Invalid JSON response handling
- Empty COBOL code handling

**Coverage:** 94%

**How to run:**
```bash
python -m pytest tests/unit/test_validator.py -v
```

## Integration Tests

### test_integration.py

Tests the complete pipeline end-to-end with real and mocked scenarios.

**What it tests:**
- Complete pipeline with sample files
- All phases executing in sequence
- Artifact generation and content quality
- Batch processing of multiple files
- Error handling and isolation
- Summary report accuracy

**Key test cases:**
- Complete pipeline with real Amazon Bedrock (requires credentials)
- Complete pipeline with mocked LLM responses
- Artifact content quality validation
- Pipeline error handling with invalid input
- Batch processing with multiple files
- Batch processing with failures (error isolation)
- Summary report accuracy

**Coverage:** Integration tests focus on workflow validation rather than code coverage

**How to run:**
```bash
# Run all integration tests
python -m pytest tests/integration/ -v

# Skip tests requiring AWS credentials
python -m pytest tests/integration/ -v -k "not real"

# Run only tests with AWS credentials
python -m pytest tests/integration/ -v -k "real"
```

**Note:** Some integration tests require valid Amazon Bedrock credentials and will be skipped if not available.

## Test Fixtures and Mocks

### Common Fixtures

- **mock_llm_client**: Mocked SonnetClient for deterministic testing
- **temp_dir**: Temporary directory for file I/O tests
- **sample_bre_doc**: Sample BRE document with business rules
- **sample_spec**: Sample functional specification
- **sample_asm_code**: Sample Assembly code for testing
- **sample_cobol_code**: Sample COBOL code for testing

### Mock Data

All unit tests use mocked LLM responses to avoid actual API calls:

- **MOCK_BUSINESS_RULES_RESPONSE**: Mock JSON for business rules
- **MOCK_DATA_MAPPINGS_RESPONSE**: Mock JSON for data mappings
- **MOCK_DATA_STRUCTURES_RESPONSE**: Mock JSON for data structures
- **MOCK_PROCESS_FLOWS_RESPONSE**: Mock JSON for process flows
- **MOCK_COBOL_RESPONSE**: Mock COBOL code
- **MOCK_SYNTAX_VALID/INVALID**: Mock syntax validation results
- **MOCK_STRUCTURE_EQUIVALENT**: Mock structure comparison results
- **MOCK_LOGIC_EQUIVALENT**: Mock logic equivalence results
- **MOCK_DATA_FLOW_EQUIVALENT**: Mock data flow verification results

## Test Coverage Summary

| Component | Coverage | Test File |
|-----------|----------|-----------|
| BRE Extractor | 95% | test_bre_extractor.py |
| Spec Generator | 92% | test_spec_generator.py |
| COBOL Generator | 90% | test_bre_cobol_generator.py |
| Validator | 94% | test_validator.py |
| Analyzer | 93% | test_analyzer.py |
| **Overall** | **92%** | Current unit tests |

## Testing Best Practices

1. **Mock External Dependencies**: All unit tests mock the LLM client to avoid actual API calls
2. **Deterministic Results**: Tests use fixed mock responses for reproducibility
3. **Error Handling**: Tests verify graceful handling of errors and edge cases
4. **File I/O**: Tests use temporary directories to avoid polluting the workspace
5. **Independence**: Each test is independent and doesn't rely on external state
6. **Coverage**: Aim for >90% code coverage for all services

## Adding New Tests

When adding tests for new services:

1. **Create test file**: `tests/unit/test_<service_name>.py`
2. **Import with proper path**:
   ```python
   from src.services.<service_name> import ServiceClass
   ```
3. **Mock external dependencies** (LLM client, file I/O)
4. **Test happy path, error cases, and edge cases**
5. **Verify code coverage is >90%**

## Continuous Integration

Tests are designed to run in CI/CD pipelines:

- **Fast execution**: Unit tests complete in seconds
- **No external dependencies**: All external services are mocked
- **Deterministic**: Same inputs always produce same outputs
- **Isolated**: Tests don't interfere with each other

## Troubleshooting Tests

### Import Errors

If you see `ModuleNotFoundError`, ensure you're running from the project root:

```bash
cd /path/to/asm-to-cobol
python -m pytest tests/
```

### AWS Credential Errors in Integration Tests

Integration tests requiring AWS credentials will be automatically skipped if credentials are not available. To run them:

1. Configure AWS credentials (see main README.md)
2. Run tests with: `python -m pytest tests/integration/ -v`

### Coverage Report Not Generated

Install the pinned test dependencies (includes pytest-cov):

```bash
python -m pip install -r requirements-dev.txt
```

Then run with coverage:

```bash
python -m pytest tests/ --cov=src --cov-report=html
```

View the report by opening `htmlcov/index.html` in your browser.

## Dependencies

- `pytest` - Testing framework
- `pytest-cov` - Coverage reporting
- `unittest.mock` - Mocking framework (built-in)
- `boto3` - AWS SDK (for integration tests)

Exact versions are pinned in [`requirements-dev.txt`](../requirements-dev.txt) and [`requirements.txt`](../requirements.txt).

## Notes

- All tests use `PYTHONPATH=src` to properly resolve imports
- Mock responses are defined as JSON strings for realistic testing
- Temporary directories are automatically cleaned up after tests
- Integration tests can run with or without AWS credentials
- Test execution time: Unit tests ~10s, Integration tests ~30s (with mocks)
