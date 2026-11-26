"""
Unit Tests for Code Validator Service

Tests the Code_Validator service with mocked LLM responses
for deterministic testing.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.services.validator import Code_Validator
from src.services.bre_extractor import BusinessRule, DataMapping, BREDocument
from src.services.spec_generator import FunctionalSpec


# Sample Assembly code for testing
SAMPLE_ASM_CODE = """
         TITLE 'SAMPLE PROGRAM'
SAMPLE   CSECT
         STM   14,12,12(13)
         L     2,INPUT1
         L     3,INPUT2
         AR    2,3
         ST    2,RESULT
         LM    14,12,12(13)
         BR    14
INPUT1   DC    F'100'
INPUT2   DC    F'200'
RESULT   DS    F
         END   SAMPLE
"""

# Sample good COBOL code (functionally equivalent)
GOOD_COBOL_CODE = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  INPUT1      PIC 9(8) VALUE 100.
       01  INPUT2      PIC 9(8) VALUE 200.
       01  RESULT      PIC 9(8).
       
       PROCEDURE DIVISION.
       MAIN-PROCEDURE.
           ADD INPUT1 TO INPUT2 GIVING RESULT.
           STOP RUN.
"""

# Sample bad COBOL code (not equivalent)
BAD_COBOL_CODE = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  INPUT1      PIC 9(8) VALUE 100.
       01  RESULT      PIC 9(8).
       
       PROCEDURE DIVISION.
       MAIN-PROCEDURE.
           MOVE INPUT1 TO RESULT.
           STOP RUN.
"""

# Mock LLM responses for validation checks
MOCK_SYNTAX_VALID = json.dumps({
    "valid": True,
    "errors": [],
    "warnings": []
})

MOCK_SYNTAX_INVALID = json.dumps({
    "valid": False,
    "errors": ["Missing END PROGRAM statement", "Invalid PIC clause"],
    "warnings": ["Consider using COMP-3 for numeric fields"]
})

MOCK_STRUCTURE_EQUIVALENT = json.dumps({
    "equivalent": True,
    "score": 0.95,
    "issues": []
})

MOCK_STRUCTURE_NOT_EQUIVALENT = json.dumps({
    "equivalent": False,
    "score": 0.6,
    "issues": ["Missing data initialization section", "Program flow differs"]
})

MOCK_LOGIC_EQUIVALENT = json.dumps({
    "equivalent": True,
    "score": 1.0,
    "differences": []
})

MOCK_LOGIC_NOT_EQUIVALENT = json.dumps({
    "equivalent": False,
    "score": 0.5,
    "differences": ["Addition operation missing", "Only one input used"]
})

MOCK_DATA_FLOW_EQUIVALENT = json.dumps({
    "equivalent": True,
    "score": 0.9,
    "issues": []
})

MOCK_DATA_FLOW_NOT_EQUIVALENT = json.dumps({
    "equivalent": False,
    "score": 0.4,
    "issues": ["INPUT2 not mapped", "Register R3 not used"]
})

MOCK_BRE_COVERAGE_FULL = json.dumps({
    "coverage_score": 1.0,
    "implemented_rules": ["BR001", "BR002"],
    "missing_rules": [],
    "details": {
        "BR001": "Implemented in MAIN-PROCEDURE",
        "BR002": "Implemented in MAIN-PROCEDURE"
    }
})

MOCK_BRE_COVERAGE_PARTIAL = json.dumps({
    "coverage_score": 0.5,
    "implemented_rules": ["BR001"],
    "missing_rules": ["BR002"],
    "details": {
        "BR001": "Implemented in MAIN-PROCEDURE"
    }
})

MOCK_SPEC_COMPLIANT = json.dumps({
    "compliant": True,
    "score": 1.0,
    "issues": []
})

MOCK_SPEC_NOT_COMPLIANT = json.dumps({
    "compliant": False,
    "score": 0.6,
    "issues": ["Missing data structure WORK-AREA", "Process flow not followed"]
})


class TestCodeValidator:
    """Test suite for Code_Validator class."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        mock_client = Mock()
        mock_client.extract_json_from_response.side_effect = lambda response: response
        return mock_client
    
    @pytest.fixture
    def validator(self, mock_llm_client):
        """Create Code_Validator instance with mocked LLM client."""
        with patch('src.services.validator.SonnetClient', return_value=mock_llm_client):
            validator = Code_Validator('config/llm_config.yaml')
            return validator
    
    @pytest.fixture
    def sample_bre_doc(self):
        """Create a sample BRE document for testing."""
        business_rules = [
            BusinessRule(
                id="BR001",
                name="Add Two Numbers",
                description="Adds INPUT1 and INPUT2",
                purpose="Calculate sum",
                inputs=["INPUT1", "INPUT2"],
                outputs=["RESULT"],
                logic="Add INPUT1 and INPUT2, store in RESULT",
                conditions=["Both inputs must be valid"],
                source_location={"line_start": 5, "line_end": 8}
            ),
            BusinessRule(
                id="BR002",
                name="Store Result",
                description="Store calculation result",
                purpose="Persist result",
                inputs=["RESULT"],
                outputs=["RESULT"],
                logic="Store result to memory",
                conditions=["Result must be numeric"],
                source_location={"line_start": 8, "line_end": 9}
            )
        ]
        
        data_mappings = [
            DataMapping(
                source_field="R2",
                target_field="INPUT1",
                transformation="Load fullword",
                validation_rules=["Must be numeric"]
            ),
            DataMapping(
                source_field="R3",
                target_field="INPUT2",
                transformation="Load fullword",
                validation_rules=["Must be numeric"]
            )
        ]
        
        return BREDocument(
            program_name="SAMPLE",
            business_rules=business_rules,
            data_mappings=data_mappings,
            summary="Sample program that adds two numbers"
        )

    @pytest.fixture
    def sample_spec(self):
        """Create a sample functional specification for testing."""
        return FunctionalSpec(
            program_name="SAMPLE",
            overview="Program to add two numbers",
            data_structures=[
                {
                    "name": "INPUT1",
                    "type": "PIC 9(8)",
                    "description": "First input value"
                },
                {
                    "name": "INPUT2",
                    "type": "PIC 9(8)",
                    "description": "Second input value"
                },
                {
                    "name": "RESULT",
                    "type": "PIC 9(8)",
                    "description": "Sum of inputs"
                }
            ],
            process_flows=[
                {
                    "step": 1,
                    "action": "Load INPUT1 and INPUT2",
                    "implements": "BR001"
                },
                {
                    "step": 2,
                    "action": "Add values",
                    "implements": "BR001"
                },
                {
                    "step": 3,
                    "action": "Store result",
                    "implements": "BR002"
                }
            ],
            business_rules_coverage={
                "BR001": "Steps 1-2",
                "BR002": "Step 3"
            }
        )
    
    def test_validate_good_translation(self, validator, mock_llm_client):
        """Test validation with a known good translation."""
        # Setup mock responses for all validation checks
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify validation passed
        assert report['status'] == 'passed'
        assert report['equivalence_score'] >= 0.7
        
        # Verify all checks passed
        assert report['validation_results']['syntax_check']['valid'] is True
        assert report['validation_results']['structure_check']['equivalent'] is True
        assert report['validation_results']['logic_check']['equivalent'] is True
        assert report['validation_results']['data_flow_check']['equivalent'] is True
        
        # Verify findings
        assert 'No issues found' in report['findings']
        
        # Verify LLM was called 4 times (syntax, structure, logic, data flow)
        assert mock_llm_client.generate.call_count == 4
    
    def test_validate_bad_translation(self, validator, mock_llm_client):
        """Test validation with a known bad translation."""
        # Setup mock responses indicating problems
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_NOT_EQUIVALENT,
            MOCK_LOGIC_NOT_EQUIVALENT,
            MOCK_DATA_FLOW_NOT_EQUIVALENT
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, BAD_COBOL_CODE)
        
        # Verify validation failed
        assert report['status'] == 'failed'
        assert report['equivalence_score'] < 0.7
        
        # Verify checks found issues
        assert report['validation_results']['structure_check']['equivalent'] is False
        assert report['validation_results']['logic_check']['equivalent'] is False
        assert report['validation_results']['data_flow_check']['equivalent'] is False
        
        # Verify findings contain issues
        assert len(report['findings']) > 1
        assert any('Structure Issue' in finding for finding in report['findings'])
        assert any('Logic Difference' in finding for finding in report['findings'])
        assert any('Data Flow Issue' in finding for finding in report['findings'])

    def test_validate_with_syntax_errors(self, validator, mock_llm_client):
        """Test validation with syntax errors in COBOL."""
        # Setup mock responses with syntax errors
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_INVALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify syntax check failed
        assert report['validation_results']['syntax_check']['valid'] is False
        
        # Verify syntax errors are in findings
        assert any('Syntax Error' in finding for finding in report['findings'])
        assert any('Missing END PROGRAM' in finding for finding in report['findings'])
        
        # Note: Status might still be 'passed' if other scores compensate for syntax failure
    
    def test_equivalence_score_calculation(self, validator, mock_llm_client):
        """Test equivalence score calculation with various check results."""
        # Setup mock responses with specific scores
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,  # 0.2 weight
            json.dumps({"equivalent": True, "score": 0.8, "issues": []}),  # 0.8 * 0.2 = 0.16
            json.dumps({"equivalent": True, "score": 0.9, "differences": []}),  # 0.9 * 0.3 = 0.27
            json.dumps({"equivalent": True, "score": 1.0, "issues": []})  # 1.0 * 0.3 = 0.30
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Expected score: 0.2 + 0.16 + 0.27 + 0.30 = 0.93
        assert report['equivalence_score'] >= 0.9
        assert report['status'] == 'passed'
    
    def test_validate_with_bre_coverage(self, validator, mock_llm_client, sample_bre_doc, sample_spec):
        """Test validation with BRE coverage checking (requires both BRE and spec)."""
        # Setup mock responses including BRE coverage
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT,
            MOCK_BRE_COVERAGE_FULL,
            MOCK_SPEC_COMPLIANT
        ]
        
        # Execute validation with BRE document and spec (both required)
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify BRE coverage was checked
        assert 'bre_coverage' in report['validation_results']
        assert report['validation_results']['bre_coverage']['coverage_score'] == 1.0
        assert len(report['validation_results']['bre_coverage']['implemented_rules']) == 2
        assert len(report['validation_results']['bre_coverage']['missing_rules']) == 0
        
        # Verify LLM was called 6 times (4 standard + 2 enhanced)
        assert mock_llm_client.generate.call_count == 6
    
    def test_validate_with_partial_bre_coverage(self, validator, mock_llm_client, sample_bre_doc, sample_spec):
        """Test validation with partial BRE coverage (requires both BRE and spec)."""
        # Setup mock responses with partial BRE coverage
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT,
            MOCK_BRE_COVERAGE_PARTIAL,
            MOCK_SPEC_COMPLIANT
        ]
        
        # Execute validation with both BRE and spec
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify partial coverage detected
        assert report['validation_results']['bre_coverage']['coverage_score'] == 0.5
        assert 'BR002' in report['validation_results']['bre_coverage']['missing_rules']
        
        # Verify findings include missing rules
        assert any('Missing Business Rules' in finding for finding in report['findings'])
        assert any('BR002' in finding for finding in report['findings'])

    def test_validate_with_spec_compliance(self, validator, mock_llm_client, sample_bre_doc, sample_spec):
        """Test validation with spec compliance checking (requires both BRE and spec)."""
        # Setup mock responses including spec compliance
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT,
            MOCK_BRE_COVERAGE_FULL,
            MOCK_SPEC_COMPLIANT
        ]
        
        # Execute validation with both BRE and spec
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify spec compliance was checked
        assert 'spec_compliance' in report['validation_results']
        assert report['validation_results']['spec_compliance']['compliant'] is True
        assert report['validation_results']['spec_compliance']['score'] == 1.0
    
    def test_validate_with_spec_non_compliance(self, validator, mock_llm_client, sample_bre_doc, sample_spec):
        """Test validation with spec non-compliance (requires both BRE and spec)."""
        # Setup mock responses with spec issues
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT,
            MOCK_BRE_COVERAGE_FULL,
            MOCK_SPEC_NOT_COMPLIANT
        ]
        
        # Execute validation with both BRE and spec
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify non-compliance detected
        assert report['validation_results']['spec_compliance']['compliant'] is False
        assert report['validation_results']['spec_compliance']['score'] == 0.6
        
        # Verify findings include spec issues
        assert any('Spec Compliance' in finding for finding in report['findings'])
    
    def test_validate_with_both_bre_and_spec(self, validator, mock_llm_client, 
                                             sample_bre_doc, sample_spec):
        """Test validation with both BRE and spec provided."""
        # Setup mock responses for all checks
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT,
            MOCK_BRE_COVERAGE_FULL,
            MOCK_SPEC_COMPLIANT
        ]
        
        # Execute validation with both BRE and spec
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify both enhanced checks were performed
        assert 'bre_coverage' in report['validation_results']
        assert 'spec_compliance' in report['validation_results']
        
        # Verify high equivalence score with bonuses
        assert report['equivalence_score'] >= 0.9
        assert report['status'] == 'passed'
        
        # Verify LLM was called 6 times (4 standard + 2 enhanced)
        assert mock_llm_client.generate.call_count == 6
    
    def test_validate_with_llm_exception(self, validator, mock_llm_client):
        """Test validation handles LLM exceptions gracefully."""
        # Setup mock to raise exception
        mock_llm_client.generate.side_effect = Exception("LLM API error")
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify error is handled
        assert report['status'] == 'error'
        assert 'error' in report
        # Raw exception text must not reach the caller (security review MF-8)
        assert 'LLM API error' not in report['error']
        assert 'Exception' in report['error']
        assert report['equivalence_score'] == 0.0

    def test_validate_with_invalid_json_response(self, validator, mock_llm_client):
        """Test validation handles invalid JSON responses gracefully."""
        # Setup mock to return invalid JSON
        mock_llm_client.generate.side_effect = [
            "This is not valid JSON",
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT
        ]
        
        # Execute validation - should not raise exception
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify fallback behavior for syntax check
        assert report['validation_results']['syntax_check']['valid'] is False
        assert len(report['validation_results']['syntax_check']['errors']) > 0
    
    def test_validate_with_missing_json_fields(self, validator, mock_llm_client):
        """Test validation handles missing fields in JSON responses."""
        # Setup mock with incomplete JSON
        incomplete_syntax = json.dumps({"valid": True})  # Missing errors and warnings
        incomplete_structure = json.dumps({"equivalent": True})  # Missing score and issues
        
        mock_llm_client.generate.side_effect = [
            incomplete_syntax,
            incomplete_structure,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify defaults are used for missing fields
        assert 'errors' in report['validation_results']['syntax_check']
        assert 'warnings' in report['validation_results']['syntax_check']
        assert 'score' in report['validation_results']['structure_check']
        assert 'issues' in report['validation_results']['structure_check']
    
    def test_recommendations_generation(self, validator, mock_llm_client):
        """Test recommendations are generated based on validation results."""
        # Setup mock responses with various issues
        mock_llm_client.generate.side_effect = [
            json.dumps({"valid": True, "errors": [], "warnings": ["Warning 1"]}),
            json.dumps({"equivalent": True, "score": 0.75, "issues": []}),
            json.dumps({"equivalent": True, "score": 0.7, "differences": []}),
            MOCK_DATA_FLOW_EQUIVALENT
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify recommendations are generated
        assert 'recommendations' in report
        assert len(report['recommendations']) > 0
        
        # Check for specific recommendations based on scores
        recommendations_text = ' '.join(report['recommendations'])
        assert 'syntax warnings' in recommendations_text.lower() or \
               'structure' in recommendations_text.lower() or \
               'logic' in recommendations_text.lower()
    
    def test_findings_generation_with_no_issues(self, validator, mock_llm_client):
        """Test findings generation when no issues are found."""
        # Setup mock responses with all checks passing
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify findings indicate no issues
        assert 'No issues found' in report['findings']

    def test_findings_generation_with_multiple_issues(self, validator, mock_llm_client):
        """Test findings generation with multiple types of issues."""
        # Setup mock responses with various issues
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_INVALID,
            MOCK_STRUCTURE_NOT_EQUIVALENT,
            MOCK_LOGIC_NOT_EQUIVALENT,
            MOCK_DATA_FLOW_NOT_EQUIVALENT
        ]
        
        # Execute validation
        report = validator.validate(SAMPLE_ASM_CODE, BAD_COBOL_CODE)
        
        # Verify multiple types of findings
        findings_text = ' '.join(report['findings'])
        assert 'Syntax Error' in findings_text
        assert 'Structure Issue' in findings_text
        assert 'Logic Difference' in findings_text
        assert 'Data Flow Issue' in findings_text
    
    def test_equivalence_score_threshold(self, validator, mock_llm_client):
        """Test that equivalence score threshold of 0.7 determines pass/fail."""
        # Test case: Score at threshold (0.7)
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,  # 0.2
            json.dumps({"equivalent": True, "score": 0.5, "issues": []}),  # 0.5 * 0.2 = 0.1
            json.dumps({"equivalent": True, "score": 0.5, "differences": []}),  # 0.5 * 0.3 = 0.15
            json.dumps({"equivalent": True, "score": 0.85, "issues": []})  # 0.85 * 0.3 = 0.255
        ]
        # Total: 0.2 + 0.1 + 0.15 + 0.255 = 0.705
        
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        assert report['equivalence_score'] >= 0.7
        assert report['status'] == 'passed'
    
    def test_equivalence_score_below_threshold(self, validator, mock_llm_client):
        """Test that score below 0.7 results in failed status."""
        # Setup mock responses for low scores
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,  # 0.2
            json.dumps({"equivalent": False, "score": 0.5, "issues": ["issue1"]}),  # 0.5 * 0.2 = 0.1
            json.dumps({"equivalent": False, "score": 0.4, "differences": ["diff1"]}),  # 0.4 * 0.3 = 0.12
            json.dumps({"equivalent": False, "score": 0.3, "issues": ["issue2"]})  # 0.3 * 0.3 = 0.09
        ]
        # Total: 0.2 + 0.1 + 0.12 + 0.09 = 0.51
        
        report = validator.validate(SAMPLE_ASM_CODE, BAD_COBOL_CODE)
        assert report['equivalence_score'] < 0.7
        assert report['status'] == 'failed'
    
    def test_bre_coverage_bonus_score(self, validator, mock_llm_client, sample_bre_doc, sample_spec):
        """Test that BRE coverage adds bonus to equivalence score (requires both BRE and spec)."""
        # Setup mock responses with base score + BRE bonus
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,  # 0.2
            json.dumps({"equivalent": True, "score": 0.8, "issues": []}),  # 0.8 * 0.2 = 0.16
            json.dumps({"equivalent": True, "score": 0.8, "differences": []}),  # 0.8 * 0.3 = 0.24
            json.dumps({"equivalent": True, "score": 0.8, "issues": []}),  # 0.8 * 0.3 = 0.24
            MOCK_BRE_COVERAGE_FULL,  # 1.0 * 0.1 = 0.1 bonus
            MOCK_SPEC_COMPLIANT  # 1.0 * 0.1 = 0.1 bonus
        ]
        # Total: 0.2 + 0.16 + 0.24 + 0.24 + 0.1 + 0.1 = 0.94
        
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify bonus was applied
        assert report['equivalence_score'] >= 0.9
        assert report['status'] == 'passed'

    def test_spec_compliance_bonus_score(self, validator, mock_llm_client, sample_bre_doc, sample_spec):
        """Test that spec compliance adds bonus to equivalence score (requires both BRE and spec)."""
        # Setup mock responses with base score + spec bonus
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,  # 0.2
            json.dumps({"equivalent": True, "score": 0.8, "issues": []}),  # 0.8 * 0.2 = 0.16
            json.dumps({"equivalent": True, "score": 0.8, "differences": []}),  # 0.8 * 0.3 = 0.24
            json.dumps({"equivalent": True, "score": 0.8, "issues": []}),  # 0.8 * 0.3 = 0.24
            MOCK_BRE_COVERAGE_FULL,  # 1.0 * 0.1 = 0.1 bonus
            MOCK_SPEC_COMPLIANT  # 1.0 * 0.1 = 0.1 bonus
        ]
        # Total: 0.2 + 0.16 + 0.24 + 0.24 + 0.1 + 0.1 = 0.94
        
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify bonus was applied
        assert report['equivalence_score'] >= 0.9
        assert report['status'] == 'passed'
    
    def test_both_bonuses_applied(self, validator, mock_llm_client, 
                                  sample_bre_doc, sample_spec):
        """Test that both BRE and spec bonuses can be applied together."""
        # Setup mock responses with base score + both bonuses
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,  # 0.2
            json.dumps({"equivalent": True, "score": 0.7, "issues": []}),  # 0.7 * 0.2 = 0.14
            json.dumps({"equivalent": True, "score": 0.7, "differences": []}),  # 0.7 * 0.3 = 0.21
            json.dumps({"equivalent": True, "score": 0.7, "issues": []}),  # 0.7 * 0.3 = 0.21
            MOCK_BRE_COVERAGE_FULL,  # 1.0 * 0.1 = 0.1 bonus
            MOCK_SPEC_COMPLIANT  # 1.0 * 0.1 = 0.1 bonus
        ]
        # Total: 0.2 + 0.14 + 0.21 + 0.21 + 0.1 + 0.1 = 0.96
        
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=sample_bre_doc,
            spec=sample_spec
        )
        
        # Verify both bonuses were applied
        assert report['equivalence_score'] >= 0.95
        assert report['status'] == 'passed'
    
    def test_syntax_check_failure_affects_score(self, validator, mock_llm_client):
        """Test that syntax check failure significantly impacts score."""
        # Setup mock with syntax failure but other checks passing
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_INVALID,  # 0.0 (failed)
            MOCK_STRUCTURE_EQUIVALENT,  # 0.95 * 0.2 = 0.19
            MOCK_LOGIC_EQUIVALENT,  # 1.0 * 0.3 = 0.3
            MOCK_DATA_FLOW_EQUIVALENT  # 0.9 * 0.3 = 0.27
        ]
        # Total: 0.0 + 0.19 + 0.3 + 0.27 = 0.76
        
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Even with other checks passing, syntax failure reduces score
        assert report['validation_results']['syntax_check']['valid'] is False
        # But might still pass if other scores are high enough
        assert report['equivalence_score'] >= 0.7
    
    def test_empty_cobol_code(self, validator, mock_llm_client):
        """Test validation with empty COBOL code."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            json.dumps({"valid": False, "errors": ["Empty code"], "warnings": []}),
            json.dumps({"equivalent": False, "score": 0.0, "issues": ["No code"]}),
            json.dumps({"equivalent": False, "score": 0.0, "differences": ["No logic"]}),
            json.dumps({"equivalent": False, "score": 0.0, "issues": ["No data flow"]})
        ]
        
        # Execute validation with empty COBOL
        report = validator.validate(SAMPLE_ASM_CODE, "")
        
        # Verify validation failed
        assert report['status'] == 'failed'
        assert report['equivalence_score'] == 0.0

    def test_bre_coverage_with_no_business_rules(self, validator, mock_llm_client, sample_spec):
        """Test BRE coverage check with empty business rules list (requires both BRE and spec)."""
        # Create BRE doc with no business rules
        empty_bre_doc = BREDocument(
            program_name="EMPTY",
            business_rules=[],
            data_mappings=[],
            summary="Empty program"
        )
        
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT,
            json.dumps({
                "coverage_score": 1.0,
                "implemented_rules": [],
                "missing_rules": [],
                "details": {}
            }),
            MOCK_SPEC_COMPLIANT
        ]
        
        # Execute validation with both BRE and spec
        report = validator.validate(
            SAMPLE_ASM_CODE,
            GOOD_COBOL_CODE,
            bre_doc=empty_bre_doc,
            spec=sample_spec
        )
        
        # Verify coverage is 100% when there are no rules to implement
        assert report['validation_results']['bre_coverage']['coverage_score'] == 1.0
        assert len(report['validation_results']['bre_coverage']['missing_rules']) == 0
    
    def test_validate_without_bre_or_spec(self, validator, mock_llm_client):
        """Test validation without BRE or spec (basic validation only)."""
        # Setup mock responses for basic checks only
        mock_llm_client.generate.side_effect = [
            MOCK_SYNTAX_VALID,
            MOCK_STRUCTURE_EQUIVALENT,
            MOCK_LOGIC_EQUIVALENT,
            MOCK_DATA_FLOW_EQUIVALENT
        ]
        
        # Execute validation without BRE or spec
        report = validator.validate(SAMPLE_ASM_CODE, GOOD_COBOL_CODE)
        
        # Verify only basic checks were performed
        assert 'syntax_check' in report['validation_results']
        assert 'structure_check' in report['validation_results']
        assert 'logic_check' in report['validation_results']
        assert 'data_flow_check' in report['validation_results']
        assert 'bre_coverage' not in report['validation_results']
        assert 'spec_compliance' not in report['validation_results']
        
        # Verify LLM was called 4 times (basic checks only)
        assert mock_llm_client.generate.call_count == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
