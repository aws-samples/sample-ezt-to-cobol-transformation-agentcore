"""
Unit Tests for Spec Generator Service

Tests the Functional Specification Generator service with mocked LLM responses
for deterministic testing.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.services.spec_generator import (
    SpecGenerator,
    FunctionalSpec
)
from src.services.bre_extractor import (
    BusinessRule,
    DataMapping,
    BREDocument
)


# Sample BRE document for testing
def create_sample_bre_doc():
    """Create a sample BRE document for testing."""
    business_rules = [
        BusinessRule(
            id="BR001",
            name="Calculate Total",
            description="Calculates total by adding two input values",
            purpose="Compute sum for financial calculation",
            inputs=["INPUT-AMOUNT-1", "INPUT-AMOUNT-2"],
            outputs=["TOTAL-AMOUNT"],
            logic="Add INPUT-AMOUNT-1 and INPUT-AMOUNT-2, store in TOTAL-AMOUNT",
            conditions=["Both inputs must be numeric", "Result must not overflow"],
            source_location={"line_start": 10, "line_end": 15}
        ),
        BusinessRule(
            id="BR002",
            name="Validate Amount",
            description="Validates that amount is within acceptable range",
            purpose="Ensure data quality",
            inputs=["TOTAL-AMOUNT"],
            outputs=["VALIDATION-FLAG"],
            logic="Check if TOTAL-AMOUNT is between 0 and 999999",
            conditions=["TOTAL-AMOUNT must be numeric"],
            source_location={"line_start": 16, "line_end": 20}
        )
    ]
    
    data_mappings = [
        DataMapping(
            source_field="R2",
            target_field="INPUT-AMOUNT-1",
            transformation="Load fullword from memory",
            validation_rules=["Must be numeric", "Must be positive"]
        ),
        DataMapping(
            source_field="R3",
            target_field="INPUT-AMOUNT-2",
            transformation="Load fullword from memory",
            validation_rules=["Must be numeric", "Must be positive"]
        ),
        DataMapping(
            source_field="R4",
            target_field="TOTAL-AMOUNT",
            transformation="Store fullword to memory",
            validation_rules=["Must be numeric"]
        )
    ]
    
    return BREDocument(
        program_name="CALCPROG",
        business_rules=business_rules,
        data_mappings=data_mappings,
        summary="Program calculates total of two amounts and validates the result"
    )


# Mock LLM response for data structures
MOCK_DATA_STRUCTURES_RESPONSE = json.dumps([
    {
        "name": "WORKING-STORAGE-SECTION",
        "fields": [
            {
                "name": "WS-INPUT-AMOUNT-1",
                "type": "PIC 9(7)V99",
                "description": "First input amount"
            },
            {
                "name": "WS-INPUT-AMOUNT-2",
                "type": "PIC 9(7)V99",
                "description": "Second input amount"
            },
            {
                "name": "WS-TOTAL-AMOUNT",
                "type": "PIC 9(8)V99",
                "description": "Calculated total amount"
            },
            {
                "name": "WS-VALIDATION-FLAG",
                "type": "PIC X",
                "description": "Validation result flag (Y/N)"
            }
        ]
    }
])


# Mock LLM response for process flows
MOCK_PROCESS_FLOWS_RESPONSE = json.dumps([
    {
        "step": 1,
        "name": "INITIALIZE-PROGRAM",
        "description": "Initialize working storage variables",
        "business_rules": []
    },
    {
        "step": 2,
        "name": "READ-INPUT-DATA",
        "description": "Read input amounts from data source",
        "business_rules": []
    },
    {
        "step": 3,
        "name": "CALCULATE-TOTAL",
        "description": "Add two input amounts to calculate total",
        "business_rules": ["BR001"]
    },
    {
        "step": 4,
        "name": "VALIDATE-AMOUNT",
        "description": "Validate total amount is within acceptable range",
        "business_rules": ["BR002"]
    },
    {
        "step": 5,
        "name": "WRITE-OUTPUT",
        "description": "Write results to output",
        "business_rules": []
    }
])


class TestSpecGenerator:
    """Test suite for SpecGenerator class."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        mock_client = Mock()
        mock_client.extract_json_from_response.side_effect = lambda response: response
        return mock_client
    
    @pytest.fixture
    def spec_generator(self, mock_llm_client):
        """Create SpecGenerator instance with mocked LLM client."""
        with patch('src.services.spec_generator.SonnetClient', return_value=mock_llm_client):
            generator = SpecGenerator('config/llm_config.yaml')
            return generator
    
    @pytest.fixture
    def sample_bre_doc(self):
        """Create a sample BRE document."""
        return create_sample_bre_doc()
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_generate_spec_success(self, spec_generator, mock_llm_client, sample_bre_doc):
        """Test successful specification generation with valid BRE document."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_DATA_STRUCTURES_RESPONSE,
            MOCK_PROCESS_FLOWS_RESPONSE
        ]
        
        # Execute generation
        spec = spec_generator.generate_spec(sample_bre_doc)
        
        # Verify results
        assert spec.program_name == "CALCPROG"
        assert spec.overview is not None
        assert len(spec.data_structures) == 1
        assert len(spec.process_flows) == 5
        assert len(spec.business_rules_coverage) == 2
        
        # Verify data structures
        data_section = spec.data_structures[0]
        assert data_section["name"] == "WORKING-STORAGE-SECTION"
        assert len(data_section["fields"]) == 4
        
        # Verify process flows
        first_step = spec.process_flows[0]
        assert first_step["step"] == 1
        assert first_step["name"] == "INITIALIZE-PROGRAM"
        
        # Verify business rules coverage
        assert "BR001" in spec.business_rules_coverage
        assert "BR002" in spec.business_rules_coverage
        
        # Verify LLM was called twice (once for data structures, once for process flows)
        assert mock_llm_client.generate.call_count == 2
    
    def test_generate_spec_with_invalid_data_structures_json(self, spec_generator, mock_llm_client, sample_bre_doc):
        """Test spec generation handles invalid data structures JSON gracefully."""
        # Setup mock to return invalid JSON for data structures
        mock_llm_client.generate.side_effect = [
            "This is not valid JSON",
            MOCK_PROCESS_FLOWS_RESPONSE
        ]
        
        # Execute generation - should not raise exception
        spec = spec_generator.generate_spec(sample_bre_doc)
        
        # Verify fallback behavior - default data structure
        assert spec.program_name == "CALCPROG"
        assert len(spec.data_structures) == 1
        assert spec.data_structures[0]["name"] == "WORKING-STORAGE-SECTION"
        assert spec.data_structures[0]["fields"] == []
        assert len(spec.process_flows) == 5
    
    def test_generate_spec_with_invalid_process_flows_json(self, spec_generator, mock_llm_client, sample_bre_doc):
        """Test spec generation handles invalid process flows JSON gracefully."""
        # Setup mock to return invalid JSON for process flows
        mock_llm_client.generate.side_effect = [
            MOCK_DATA_STRUCTURES_RESPONSE,
            "Invalid JSON for process flows"
        ]
        
        # Execute generation - should not raise exception
        spec = spec_generator.generate_spec(sample_bre_doc)
        
        # Verify fallback behavior - default process flow
        assert spec.program_name == "CALCPROG"
        assert len(spec.data_structures) == 1
        assert len(spec.process_flows) == 1
        assert spec.process_flows[0]["name"] == "MAIN-PROCEDURE"
    
    def test_generate_spec_with_non_list_data_structures(self, spec_generator, mock_llm_client, sample_bre_doc):
        """Test spec generation handles non-list data structures response."""
        # Setup mock to return non-list JSON
        mock_llm_client.generate.side_effect = [
            json.dumps({"not": "a list"}),
            MOCK_PROCESS_FLOWS_RESPONSE
        ]
        
        # Execute generation
        spec = spec_generator.generate_spec(sample_bre_doc)
        
        # Verify fallback behavior
        assert len(spec.data_structures) == 1
        assert spec.data_structures[0]["name"] == "WORKING-STORAGE-SECTION"
        assert spec.data_structures[0]["fields"] == []
    
    def test_generate_spec_with_non_list_process_flows(self, spec_generator, mock_llm_client, sample_bre_doc):
        """Test spec generation handles non-list process flows response."""
        # Setup mock to return non-list JSON
        mock_llm_client.generate.side_effect = [
            MOCK_DATA_STRUCTURES_RESPONSE,
            json.dumps({"not": "a list"})
        ]
        
        # Execute generation
        spec = spec_generator.generate_spec(sample_bre_doc)
        
        # Verify fallback behavior
        assert len(spec.process_flows) == 1
        assert spec.process_flows[0]["name"] == "MAIN-PROCEDURE"
    
    def test_generate_spec_with_llm_exception(self, spec_generator, mock_llm_client, sample_bre_doc):
        """Test spec generation handles LLM exceptions."""
        # Setup mock to raise exception
        mock_llm_client.generate.side_effect = Exception("LLM API error")
        
        # Execute generation - should raise exception
        with pytest.raises(Exception) as exc_info:
            spec_generator.generate_spec(sample_bre_doc)
        
        assert "LLM API error" in str(exc_info.value)
    
    def test_save_and_load_spec(self, spec_generator, temp_dir):
        """Test saving and loading functional specifications."""
        # Create a sample functional spec
        spec = FunctionalSpec(
            program_name="TESTPROG",
            overview="Test program overview",
            data_structures=[
                {
                    "name": "WORKING-STORAGE-SECTION",
                    "fields": [
                        {"name": "WS-FIELD1", "type": "PIC X(10)", "description": "Test field"}
                    ]
                }
            ],
            process_flows=[
                {
                    "step": 1,
                    "name": "MAIN-PROCESS",
                    "description": "Main processing",
                    "business_rules": ["BR001"]
                }
            ],
            business_rules_coverage={
                "BR001": "Covered in MAIN-PROCESS"
            }
        )
        
        # Save spec
        output_path = temp_dir / "test_spec.json"
        spec_generator.save_spec(spec, str(output_path))
        
        # Verify file was created
        assert output_path.exists()
        
        # Load spec
        loaded_spec = spec_generator.load_spec(str(output_path))
        
        # Verify loaded data matches original
        assert loaded_spec.program_name == "TESTPROG"
        assert loaded_spec.overview == "Test program overview"
        assert len(loaded_spec.data_structures) == 1
        assert len(loaded_spec.process_flows) == 1
        assert len(loaded_spec.business_rules_coverage) == 1
        
        # Verify data structure details
        assert loaded_spec.data_structures[0]["name"] == "WORKING-STORAGE-SECTION"
        assert len(loaded_spec.data_structures[0]["fields"]) == 1
        
        # Verify process flow details
        assert loaded_spec.process_flows[0]["step"] == 1
        assert loaded_spec.process_flows[0]["name"] == "MAIN-PROCESS"
        
        # Verify coverage details
        assert "BR001" in loaded_spec.business_rules_coverage
    
    def test_save_spec_creates_directories(self, spec_generator, temp_dir):
        """Test that save_spec creates parent directories if they don't exist."""
        # Create spec
        spec = FunctionalSpec(
            program_name="TEST",
            overview="Test",
            data_structures=[],
            process_flows=[],
            business_rules_coverage={}
        )
        
        # Save to nested path that doesn't exist
        nested_path = temp_dir / "phase2" / "specs" / "test.json"
        spec_generator.save_spec(spec, str(nested_path))
        
        # Verify file and directories were created
        assert nested_path.exists()
        assert nested_path.parent.exists()
    
    def test_load_spec_nonexistent_file(self, spec_generator):
        """Test loading spec from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            spec_generator.load_spec("nonexistent_spec.json")
    
    def test_design_data_structures_with_empty_bre(self, spec_generator, mock_llm_client):
        """Test data structure design with empty BRE document."""
        # Create empty BRE document
        empty_bre = BREDocument(
            program_name="EMPTY",
            business_rules=[],
            data_mappings=[],
            summary="Empty program"
        )
        
        # Setup mock response
        mock_llm_client.generate.side_effect = [
            json.dumps([{"name": "WORKING-STORAGE-SECTION", "fields": []}]),
            json.dumps([{"step": 1, "name": "MAIN-PROCEDURE", "description": "Main"}])
        ]
        
        # Execute generation
        spec = spec_generator.generate_spec(empty_bre)
        
        # Verify results
        assert spec.program_name == "EMPTY"
        assert len(spec.data_structures) == 1
        assert len(spec.business_rules_coverage) == 0
    
    def test_design_process_flows_with_multiple_rules(self, spec_generator, mock_llm_client):
        """Test process flow design with multiple business rules."""
        # Create BRE with multiple rules
        business_rules = [
            BusinessRule(
                id=f"BR{i:03d}",
                name=f"Rule {i}",
                description=f"Description {i}",
                purpose=f"Purpose {i}",
                inputs=[f"INPUT{i}"],
                outputs=[f"OUTPUT{i}"],
                logic=f"Logic {i}",
                conditions=[],
                source_location={}
            )
            for i in range(1, 6)
        ]
        
        bre_doc = BREDocument(
            program_name="MULTI",
            business_rules=business_rules,
            data_mappings=[],
            summary="Multiple rules"
        )
        
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_DATA_STRUCTURES_RESPONSE,
            json.dumps([
                {"step": i, "name": f"STEP-{i}", "description": f"Step {i}", "business_rules": [f"BR{i:03d}"]}
                for i in range(1, 6)
            ])
        ]
        
        # Execute generation
        spec = spec_generator.generate_spec(bre_doc)
        
        # Verify multiple process flows
        assert len(spec.process_flows) == 5
        assert spec.process_flows[0]["step"] == 1
        assert spec.process_flows[4]["step"] == 5
        
        # Verify all rules are covered
        assert len(spec.business_rules_coverage) == 5
        for i in range(1, 6):
            assert f"BR{i:03d}" in spec.business_rules_coverage
    
    def test_create_coverage_map(self, spec_generator, sample_bre_doc):
        """Test business rules coverage map creation."""
        coverage = spec_generator._create_coverage_map(sample_bre_doc)
        
        # Verify all business rules are in coverage map
        assert len(coverage) == 2
        assert "BR001" in coverage
        assert "BR002" in coverage
        
        # Verify coverage descriptions
        assert "Covered" in coverage["BR001"]
        assert "Covered" in coverage["BR002"]
    
    def test_generate_overview(self, spec_generator, sample_bre_doc):
        """Test overview generation."""
        data_structures = [
            {"name": "WORKING-STORAGE-SECTION", "fields": [{"name": "FIELD1"}]}
        ]
        process_flows = [
            {"step": 1, "name": "STEP1"},
            {"step": 2, "name": "STEP2"}
        ]
        
        overview = spec_generator._generate_overview(sample_bre_doc, data_structures, process_flows)
        
        # Verify overview contains key information
        assert "CALCPROG" in overview
        assert "2" in overview  # 2 business rules
        assert "1" in overview  # 1 data structure
        assert "2" in overview  # 2 process steps
        assert sample_bre_doc.summary in overview
    
    def test_functional_spec_dataclass(self):
        """Test FunctionalSpec dataclass creation."""
        spec = FunctionalSpec(
            program_name="TEST",
            overview="Test overview",
            data_structures=[{"name": "SECTION1"}],
            process_flows=[{"step": 1}],
            business_rules_coverage={"BR001": "Covered"}
        )
        
        assert spec.program_name == "TEST"
        assert spec.overview == "Test overview"
        assert len(spec.data_structures) == 1
        assert len(spec.process_flows) == 1
        assert len(spec.business_rules_coverage) == 1
    
    def test_generate_spec_with_complex_data_mappings(self, spec_generator, mock_llm_client):
        """Test spec generation with complex data mappings."""
        # Create BRE with complex mappings
        data_mappings = [
            DataMapping(
                source_field=f"R{i}",
                target_field=f"FIELD-{i}",
                transformation=f"Transform {i}",
                validation_rules=[f"Rule {i}"]
            )
            for i in range(1, 11)
        ]
        
        bre_doc = BREDocument(
            program_name="COMPLEX",
            business_rules=[],
            data_mappings=data_mappings,
            summary="Complex mappings"
        )
        
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_DATA_STRUCTURES_RESPONSE,
            MOCK_PROCESS_FLOWS_RESPONSE
        ]
        
        # Execute generation
        spec = spec_generator.generate_spec(bre_doc)
        
        # Verify generation succeeded
        assert spec.program_name == "COMPLEX"
        assert len(spec.data_structures) > 0
    
    def test_generate_spec_with_special_characters_in_fields(self, spec_generator, mock_llm_client):
        """Test spec generation with special characters in field names."""
        # Create BRE with special characters
        business_rules = [
            BusinessRule(
                id="BR001",
                name="Special Rule",
                description="Rule with special chars",
                purpose="Test",
                inputs=["INPUT-FIELD-1", "INPUT_FIELD_2", "INPUT.FIELD.3"],
                outputs=["OUTPUT-RESULT"],
                logic="Process special fields",
                conditions=[],
                source_location={}
            )
        ]
        
        bre_doc = BREDocument(
            program_name="SPECIAL",
            business_rules=business_rules,
            data_mappings=[],
            summary="Special characters test"
        )
        
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_DATA_STRUCTURES_RESPONSE,
            MOCK_PROCESS_FLOWS_RESPONSE
        ]
        
        # Execute generation - should handle special characters
        spec = spec_generator.generate_spec(bre_doc)
        
        # Verify generation succeeded
        assert spec.program_name == "SPECIAL"
        assert len(spec.business_rules_coverage) == 1
    
    def test_generate_spec_preserves_business_rule_order(self, spec_generator, mock_llm_client):
        """Test that spec generation preserves business rule order."""
        # Create BRE with ordered rules
        business_rules = [
            BusinessRule(
                id=f"BR{i:03d}",
                name=f"Rule {i}",
                description="",
                purpose="",
                inputs=[],
                outputs=[],
                logic="",
                conditions=[],
                source_location={}
            )
            for i in range(1, 11)
        ]
        
        bre_doc = BREDocument(
            program_name="ORDERED",
            business_rules=business_rules,
            data_mappings=[],
            summary="Ordered rules"
        )
        
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_DATA_STRUCTURES_RESPONSE,
            MOCK_PROCESS_FLOWS_RESPONSE
        ]
        
        # Execute generation
        spec = spec_generator.generate_spec(bre_doc)
        
        # Verify all rules are covered
        assert len(spec.business_rules_coverage) == 10
        
        # Verify rule IDs are present
        for i in range(1, 11):
            assert f"BR{i:03d}" in spec.business_rules_coverage


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
