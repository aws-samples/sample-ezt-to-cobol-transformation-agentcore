"""
Unit Tests for BRE COBOL Generator Service

Tests the COBOL generation service with mocked LLM responses
for deterministic testing.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.services.bre_cobol_generator import BRECOBOLGenerator
from src.services.bre_extractor import BusinessRule, DataMapping, BREDocument
from src.services.spec_generator import FunctionalSpec


# Sample Assembly code for testing
SAMPLE_ASM_CODE = """
         TITLE 'SAMPLE PROGRAM'
SAMPLE   CSECT
         STM   14,12,12(13)
         LR    12,15
         USING SAMPLE,12
         
* Load input values
         L     2,INPUT1
         L     3,INPUT2
         
* Add values
         AR    2,3
         ST    2,RESULT
         
* Return
         LM    14,12,12(13)
         BR    14
         
INPUT1   DC    F'100'
INPUT2   DC    F'200'
RESULT   DS    F
         END   SAMPLE
"""


# Sample BRE document for testing
SAMPLE_BRE_DOC = BREDocument(
    program_name="SAMPLE",
    business_rules=[
        BusinessRule(
            id="BR001",
            name="Add Two Numbers",
            description="Adds two input values and stores the result",
            purpose="Calculate sum of two numeric inputs",
            inputs=["INPUT1", "INPUT2"],
            outputs=["RESULT"],
            logic="Load INPUT1 into register 2, load INPUT2 into register 3, add them, store in RESULT",
            conditions=["Both inputs must be valid"],
            source_location={"line_start": 8, "line_end": 13}
        )
    ],
    data_mappings=[
        DataMapping(
            source_field="R2",
            target_field="INPUT1",
            transformation="Load fullword from memory",
            validation_rules=["Must be numeric"]
        ),
        DataMapping(
            source_field="R3",
            target_field="INPUT2",
            transformation="Load fullword from memory",
            validation_rules=["Must be numeric"]
        ),
        DataMapping(
            source_field="R2",
            target_field="RESULT",
            transformation="Store fullword to memory",
            validation_rules=["Must be numeric"]
        )
    ],
    summary="Program adds two numbers"
)


# Sample functional specification for testing
SAMPLE_SPEC = FunctionalSpec(
    program_name="SAMPLE",
    overview="This program adds two numeric inputs and stores the result",
    data_structures=[
        {
            "level": "01",
            "name": "INPUT-DATA",
            "fields": [
                {"level": "05", "name": "INPUT1", "pic": "9(9)", "usage": "COMP"},
                {"level": "05", "name": "INPUT2", "pic": "9(9)", "usage": "COMP"}
            ]
        },
        {
            "level": "01",
            "name": "OUTPUT-DATA",
            "fields": [
                {"level": "05", "name": "RESULT", "pic": "9(9)", "usage": "COMP"}
            ]
        }
    ],
    process_flows=[
        {
            "step": 1,
            "name": "Initialize",
            "description": "Initialize program variables"
        },
        {
            "step": 2,
            "name": "Load Inputs",
            "description": "Load INPUT1 and INPUT2 values"
        },
        {
            "step": 3,
            "name": "Calculate Sum",
            "description": "Add INPUT1 and INPUT2, store in RESULT"
        },
        {
            "step": 4,
            "name": "Return",
            "description": "Return to caller"
        }
    ],
    business_rules_coverage={
        "BR001": "Implemented in Calculate Sum procedure"
    }
)


# Mock COBOL code response from LLM
MOCK_COBOL_RESPONSE = """* ****************************************************************
* Program: SAMPLE
* Generated from Easytrieve using BRE-based transformation
* Business Rules: 1
* Data Mappings: 3
* ****************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAMPLE.
       
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  INPUT-DATA.
           05  INPUT1          PIC 9(9) COMP.
           05  INPUT2          PIC 9(9) COMP.
       01  OUTPUT-DATA.
           05  RESULT          PIC 9(9) COMP.
       
       PROCEDURE DIVISION.
       MAIN-LOGIC.
           PERFORM INITIALIZE-PROGRAM.
           PERFORM LOAD-INPUTS.
           PERFORM CALCULATE-SUM.
           PERFORM RETURN-TO-CALLER.
           STOP RUN.
       
       INITIALIZE-PROGRAM.
           MOVE ZERO TO RESULT.
       
       LOAD-INPUTS.
           MOVE 100 TO INPUT1.
           MOVE 200 TO INPUT2.
       
       CALCULATE-SUM.
      * Business Rule BR001: Add Two Numbers
           ADD INPUT1 TO INPUT2 GIVING RESULT.
       
       RETURN-TO-CALLER.
           GOBACK.
"""


class TestBRECOBOLGenerator:
    """Test suite for BRECOBOLGenerator class."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        mock_client = Mock()
        mock_client.extract_json_from_response.side_effect = lambda response: response
        return mock_client
    
    @pytest.fixture
    def cobol_generator(self, mock_llm_client):
        """Create BRECOBOLGenerator instance with mocked LLM client."""
        with patch('src.services.bre_cobol_generator.SonnetClient', return_value=mock_llm_client):
            generator = BRECOBOLGenerator('config/llm_config.yaml')
            return generator
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_generate_cobol_success(self, cobol_generator, mock_llm_client):
        """Test successful COBOL generation with valid inputs."""
        # Setup mock response
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_code = cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            SAMPLE_BRE_DOC,
            SAMPLE_SPEC
        )
        
        # Verify COBOL code was generated
        assert cobol_code is not None
        assert len(cobol_code) > 0
        
        # Verify traceability header was added
        assert "Program: SAMPLE" in cobol_code
        assert "Generated from Easytrieve using BRE-based transformation" in cobol_code
        assert "Business Rules: 1" in cobol_code
        assert "Data Mappings: 3" in cobol_code
        
        # Verify COBOL content is present
        assert "IDENTIFICATION DIVISION" in cobol_code
        assert "DATA DIVISION" in cobol_code
        assert "PROCEDURE DIVISION" in cobol_code
        
        # Verify LLM was called once
        assert mock_llm_client.generate.call_count == 1
    
    def test_generate_cobol_syntax_validity(self, cobol_generator, mock_llm_client):
        """Test that generated COBOL has valid syntax structure."""
        # Setup mock response
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_code = cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            SAMPLE_BRE_DOC,
            SAMPLE_SPEC
        )
        
        # Verify COBOL divisions are present
        assert "IDENTIFICATION DIVISION" in cobol_code
        assert "PROGRAM-ID" in cobol_code
        assert "DATA DIVISION" in cobol_code
        assert "WORKING-STORAGE SECTION" in cobol_code
        assert "PROCEDURE DIVISION" in cobol_code
        
        # Verify data structures are defined
        assert "INPUT-DATA" in cobol_code
        assert "OUTPUT-DATA" in cobol_code
        assert "PIC" in cobol_code
        
        # Verify procedures are defined
        assert "MAIN-LOGIC" in cobol_code or "PERFORM" in cobol_code
    
    def test_generate_cobol_traceability_comments(self, cobol_generator, mock_llm_client):
        """Test that traceability comments are properly generated."""
        # Setup mock response
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_code = cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            SAMPLE_BRE_DOC,
            SAMPLE_SPEC
        )
        
        # Verify traceability header
        assert cobol_code.splitlines()[0].startswith("000100*")
        assert "Program: SAMPLE" in cobol_code
        assert "Generated from Easytrieve using BRE-based transformation" in cobol_code
        
        # Verify business rules count
        assert "Business Rules: 1" in cobol_code
        
        # Verify data mappings count
        assert "Data Mappings: 3" in cobol_code
        
        # Verify header appears at the beginning
        lines = cobol_code.split('\n')
        header_found = False
        for i, line in enumerate(lines[:10]):  # Check first 10 lines
            if "Program: SAMPLE" in line:
                header_found = True
                break
        assert header_found, "Traceability header should appear at the beginning"
    
    def test_generate_cobol_with_multiple_business_rules(self, cobol_generator, mock_llm_client):
        """Test COBOL generation with multiple business rules."""
        # Create BRE with multiple rules
        multi_rule_bre = BREDocument(
            program_name="MULTI",
            business_rules=[
                BusinessRule(
                    id="BR001",
                    name="Validate Input",
                    description="Validate input values",
                    purpose="Ensure data quality",
                    inputs=["INPUT1"],
                    outputs=["VALID-FLAG"],
                    logic="Check if INPUT1 is positive",
                    conditions=["INPUT1 > 0"],
                    source_location={"line_start": 1, "line_end": 5}
                ),
                BusinessRule(
                    id="BR002",
                    name="Calculate Total",
                    description="Calculate total amount",
                    purpose="Sum all inputs",
                    inputs=["INPUT1", "INPUT2"],
                    outputs=["TOTAL"],
                    logic="Add INPUT1 and INPUT2",
                    conditions=["Both inputs valid"],
                    source_location={"line_start": 6, "line_end": 10}
                ),
                BusinessRule(
                    id="BR003",
                    name="Format Output",
                    description="Format output for display",
                    purpose="Present results",
                    inputs=["TOTAL"],
                    outputs=["DISPLAY-TOTAL"],
                    logic="Convert to display format",
                    conditions=["TOTAL calculated"],
                    source_location={"line_start": 11, "line_end": 15}
                )
            ],
            data_mappings=[],
            summary="Multi-rule program"
        )
        
        multi_spec = FunctionalSpec(
            program_name="MULTI",
            overview="Multi-rule program",
            data_structures=[],
            process_flows=[],
            business_rules_coverage={}
        )
        
        # Setup mock response
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_code = cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            multi_rule_bre,
            multi_spec
        )
        
        # Verify the prompt carries the count that the generated header must show.
        prompt = mock_llm_client.generate.call_args.args[0]
        assert "Business Rules: 3" in prompt
    
    def test_generate_cobol_with_llm_exception(self, cobol_generator, mock_llm_client):
        """Test COBOL generation handles LLM exceptions."""
        # Setup mock to raise exception
        mock_llm_client.generate.side_effect = Exception("LLM API error")
        
        # Execute generation - should raise exception
        with pytest.raises(Exception) as exc_info:
            cobol_generator.generate_cobol(
                SAMPLE_ASM_CODE,
                SAMPLE_BRE_DOC,
                SAMPLE_SPEC
            )
        
        assert "LLM API error" in str(exc_info.value)
    
    def test_generate_cobol_with_empty_bre(self, cobol_generator, mock_llm_client):
        """Test COBOL generation with empty BRE document."""
        # Create empty BRE
        empty_bre = BREDocument(
            program_name="EMPTY",
            business_rules=[],
            data_mappings=[],
            summary="Empty program"
        )
        
        empty_spec = FunctionalSpec(
            program_name="EMPTY",
            overview="Empty program",
            data_structures=[],
            process_flows=[],
            business_rules_coverage={}
        )
        
        # Setup mock response
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_code = cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            empty_bre,
            empty_spec
        )
        
        # Verify generation succeeds with empty inputs
        assert cobol_code is not None
        prompt = mock_llm_client.generate.call_args.args[0]
        assert "Business Rules: 0" in prompt
        assert "Data Mappings: 0" in prompt
    
    def test_save_cobol(self, cobol_generator, temp_dir):
        """Test saving COBOL code to file."""
        # Create sample COBOL code
        cobol_code = MOCK_COBOL_RESPONSE
        
        # Save to file
        output_path = temp_dir / "sample.cbl"
        cobol_generator.save_cobol(cobol_code, str(output_path))
        
        # Verify file was created
        assert output_path.exists()
        
        # Verify content matches
        with open(output_path, 'r') as f:
            saved_content = f.read()
        assert saved_content == cobol_code
    
    def test_save_cobol_creates_directories(self, cobol_generator, temp_dir):
        """Test that save_cobol creates parent directories if they don't exist."""
        # Create sample COBOL code
        cobol_code = MOCK_COBOL_RESPONSE
        
        # Save to nested path that doesn't exist
        nested_path = temp_dir / "phase3" / "cobol" / "sample.cbl"
        cobol_generator.save_cobol(cobol_code, str(nested_path))
        
        # Verify file and directories were created
        assert nested_path.exists()
        assert nested_path.parent.exists()
    
    def test_build_generation_context(self, cobol_generator):
        """Test building generation context from inputs."""
        # Execute context building (private method, but testing for completeness)
        context = cobol_generator._build_generation_context(
            SAMPLE_ASM_CODE,
            SAMPLE_BRE_DOC,
            SAMPLE_SPEC
        )
        
        # Verify context structure
        assert context['program_name'] == "SAMPLE"
        assert 'asm_code' in context
        assert 'business_rules' in context
        assert 'data_mappings' in context
        assert 'data_structures' in context
        assert 'process_flows' in context
        assert 'overview' in context
        
        # Verify business rules are formatted correctly
        assert len(context['business_rules']) == 1
        assert context['business_rules'][0]['id'] == "BR001"
        assert context['business_rules'][0]['name'] == "Add Two Numbers"
        
        # Verify data mappings are formatted correctly
        assert len(context['data_mappings']) == 3
        assert context['data_mappings'][0]['source'] == "R2"
        assert context['data_mappings'][0]['target'] == "INPUT1"
    
    def test_format_business_rules(self, cobol_generator):
        """Test formatting business rules for prompt."""
        rules = [
            {
                'id': 'BR001',
                'name': 'Test Rule',
                'logic': 'Test logic',
                'inputs': ['INPUT1', 'INPUT2'],
                'outputs': ['OUTPUT1'],
                'conditions': ['condition1', 'condition2']
            }
        ]
        
        formatted = cobol_generator._format_business_rules(rules)
        
        # Verify formatting
        assert 'BR001' in formatted
        assert 'Test Rule' in formatted
        assert 'Test logic' in formatted
        assert 'INPUT1' in formatted
        assert 'INPUT2' in formatted
        assert 'OUTPUT1' in formatted
        assert 'condition1' in formatted
    
    def test_format_data_mappings(self, cobol_generator):
        """Test formatting data mappings for prompt."""
        mappings = [
            {
                'source': 'R1',
                'target': 'FIELD1',
                'transformation': 'Load from memory'
            },
            {
                'source': 'R2',
                'target': 'FIELD2',
                'transformation': 'Store to memory'
            }
        ]
        
        formatted = cobol_generator._format_data_mappings(mappings)
        
        # Verify formatting
        assert 'R1 -> FIELD1' in formatted
        assert 'Load from memory' in formatted
        assert 'R2 -> FIELD2' in formatted
        assert 'Store to memory' in formatted
    
    def test_format_data_structures(self, cobol_generator):
        """Test formatting data structures for prompt."""
        structures = [
            {
                "level": "01",
                "name": "TEST-DATA",
                "fields": [
                    {"level": "05", "name": "FIELD1", "pic": "X(10)"}
                ]
            }
        ]
        
        formatted = cobol_generator._format_data_structures(structures)
        
        # Verify JSON formatting
        assert '"level"' in formatted or "'level'" in formatted
        assert 'TEST-DATA' in formatted
        assert 'FIELD1' in formatted
    
    def test_format_process_flows(self, cobol_generator):
        """Test formatting process flows for prompt."""
        flows = [
            {
                'step': 1,
                'name': 'Initialize',
                'description': 'Initialize variables'
            },
            {
                'step': 2,
                'name': 'Process',
                'description': 'Process data'
            }
        ]
        
        formatted = cobol_generator._format_process_flows(flows)
        
        # Verify formatting
        assert 'Step 1' in formatted
        assert 'Initialize' in formatted
        assert 'Initialize variables' in formatted
        assert 'Step 2' in formatted
        assert 'Process' in formatted
    
    def test_remove_llm_preamble(self, cobol_generator):
        """Test that text before the first COBOL line is removed."""
        cobol_with_preamble = """Here is the generated COBOL program:

       IDENTIFICATION DIVISION.
       PROGRAM-ID. TEST.
       PROCEDURE DIVISION.
           STOP RUN."""

        cleaned_cobol = cobol_generator._remove_llm_preamble(cobol_with_preamble)

        assert cleaned_cobol.startswith("       IDENTIFICATION DIVISION.")
        assert "Here is the generated COBOL program" not in cleaned_cobol
        assert "PROGRAM-ID. TEST" in cleaned_cobol
    
    def test_generate_cobol_with_complex_data_structures(self, cobol_generator, mock_llm_client):
        """Test COBOL generation with complex nested data structures."""
        # Create spec with complex data structures
        complex_spec = FunctionalSpec(
            program_name="COMPLEX",
            overview="Complex data structures",
            data_structures=[
                {
                    "level": "01",
                    "name": "CUSTOMER-RECORD",
                    "fields": [
                        {"level": "05", "name": "CUSTOMER-ID", "pic": "9(10)"},
                        {
                            "level": "05",
                            "name": "CUSTOMER-NAME",
                            "fields": [
                                {"level": "10", "name": "FIRST-NAME", "pic": "X(20)"},
                                {"level": "10", "name": "LAST-NAME", "pic": "X(30)"}
                            ]
                        },
                        {
                            "level": "05",
                            "name": "CUSTOMER-ADDRESS",
                            "fields": [
                                {"level": "10", "name": "STREET", "pic": "X(50)"},
                                {"level": "10", "name": "CITY", "pic": "X(30)"},
                                {"level": "10", "name": "ZIP", "pic": "9(5)"}
                            ]
                        }
                    ]
                }
            ],
            process_flows=[],
            business_rules_coverage={}
        )
        
        # Setup mock response
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_code = cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            SAMPLE_BRE_DOC,
            complex_spec
        )
        
        # Verify generation succeeds with complex structures
        assert cobol_code is not None
        assert len(cobol_code) > 0
    
    def test_generate_cobol_with_multiple_process_flows(self, cobol_generator, mock_llm_client):
        """Test COBOL generation with multiple process flow steps."""
        # Create spec with multiple process flows
        multi_flow_spec = FunctionalSpec(
            program_name="MULTIFLOW",
            overview="Multiple process flows",
            data_structures=[],
            process_flows=[
                {"step": 1, "name": "Initialize", "description": "Initialize program"},
                {"step": 2, "name": "Validate", "description": "Validate inputs"},
                {"step": 3, "name": "Process", "description": "Process data"},
                {"step": 4, "name": "Calculate", "description": "Perform calculations"},
                {"step": 5, "name": "Format", "description": "Format output"},
                {"step": 6, "name": "Write", "description": "Write results"},
                {"step": 7, "name": "Cleanup", "description": "Cleanup resources"}
            ],
            business_rules_coverage={}
        )
        
        # Setup mock response
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_code = cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            SAMPLE_BRE_DOC,
            multi_flow_spec
        )
        
        # Verify generation succeeds with multiple flows
        assert cobol_code is not None
        assert len(cobol_code) > 0
    
    def test_generate_cobol_prompt_includes_all_context(self, cobol_generator, mock_llm_client):
        """Test that the LLM prompt includes all necessary context."""
        # Setup mock to capture the prompt
        mock_llm_client.generate.return_value = MOCK_COBOL_RESPONSE
        
        # Execute generation
        cobol_generator.generate_cobol(
            SAMPLE_ASM_CODE,
            SAMPLE_BRE_DOC,
            SAMPLE_SPEC
        )
        
        # Get the prompt that was sent to LLM
        call_args = mock_llm_client.generate.call_args
        prompt = call_args[0][0]
        
        # Verify prompt includes all necessary sections
        assert "Program: SAMPLE" in prompt
        assert "Overview:" in prompt
        assert "Business Rules:" in prompt
        assert "Data Mappings:" in prompt
        assert "Data Structures:" in prompt
        assert "Process Flow:" in prompt
        assert "Original Easytrieve Source Code" in prompt
        assert "well-structured, compilable COBOL" in prompt
        
        # Verify specific content is included
        assert "BR001" in prompt
        assert "Add Two Numbers" in prompt
        assert "INPUT1" in prompt
        assert "INPUT2" in prompt
        assert "RESULT" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
