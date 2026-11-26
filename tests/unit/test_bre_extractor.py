"""
Unit Tests for BRE Extractor Service

Tests the Business Rules Extraction service with mocked LLM responses
for deterministic testing.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.services.bre_extractor import (
    BREExtractor,
    BusinessRule,
    DataMapping,
    BREDocument
)


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


# Mock LLM response for business rules extraction
MOCK_BUSINESS_RULES_RESPONSE = json.dumps([
    {
        "id": "BR001",
        "name": "Add Two Numbers",
        "description": "Adds two input values and stores the result",
        "purpose": "Calculate sum of two numeric inputs",
        "inputs": ["INPUT1", "INPUT2"],
        "outputs": ["RESULT"],
        "logic": "Load INPUT1 into register 2, load INPUT2 into register 3, add them, store in RESULT",
        "conditions": ["Both inputs must be valid"],
        "source_location": {"line_start": 8, "line_end": 13}
    }
])


# Mock LLM response for data mappings extraction
MOCK_DATA_MAPPINGS_RESPONSE = json.dumps([
    {
        "source_field": "R2",
        "target_field": "INPUT1",
        "transformation": "Load fullword from memory",
        "validation_rules": ["Must be numeric"]
    },
    {
        "source_field": "R3",
        "target_field": "INPUT2",
        "transformation": "Load fullword from memory",
        "validation_rules": ["Must be numeric"]
    },
    {
        "source_field": "R2",
        "target_field": "RESULT",
        "transformation": "Store fullword to memory",
        "validation_rules": ["Must be numeric"]
    }
])


class TestBREExtractor:
    """Test suite for BREExtractor class."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        mock_client = Mock()
        mock_client.extract_json_from_response.side_effect = lambda response: response
        return mock_client
    
    @pytest.fixture
    def bre_extractor(self, mock_llm_client):
        """Create BREExtractor instance with mocked LLM client."""
        with patch('src.services.bre_extractor.SonnetClient', return_value=mock_llm_client):
            extractor = BREExtractor('config/llm_config.yaml')
            return extractor
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    def test_extract_bre_success(self, bre_extractor, mock_llm_client):
        """Test successful BRE extraction with valid Assembly code."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_BUSINESS_RULES_RESPONSE,
            MOCK_DATA_MAPPINGS_RESPONSE
        ]
        
        # Execute extraction
        bre_doc = bre_extractor.extract_bre(SAMPLE_ASM_CODE, "SAMPLE")
        
        # Verify results
        assert bre_doc.program_name == "SAMPLE"
        assert len(bre_doc.business_rules) == 1
        assert len(bre_doc.data_mappings) == 3
        assert bre_doc.summary is not None
        
        # Verify business rule details
        rule = bre_doc.business_rules[0]
        assert rule.id == "BR001"
        assert rule.name == "Add Two Numbers"
        assert "INPUT1" in rule.inputs
        assert "INPUT2" in rule.inputs
        assert "RESULT" in rule.outputs
        
        # Verify data mapping details
        mapping = bre_doc.data_mappings[0]
        assert mapping.source_field == "R2"
        assert mapping.target_field == "INPUT1"
        
        # Verify LLM was called twice (once for rules, once for mappings)
        assert mock_llm_client.generate.call_count == 2
    
    def test_extract_bre_with_invalid_json_response(self, bre_extractor, mock_llm_client):
        """Test BRE extraction handles invalid JSON gracefully."""
        # Setup mock to return invalid JSON
        mock_llm_client.generate.side_effect = [
            "This is not valid JSON",
            MOCK_DATA_MAPPINGS_RESPONSE
        ]
        
        # Execute extraction - should not raise exception
        bre_doc = bre_extractor.extract_bre(SAMPLE_ASM_CODE, "SAMPLE")
        
        # Verify fallback behavior - empty business rules
        assert bre_doc.program_name == "SAMPLE"
        assert len(bre_doc.business_rules) == 0
        assert len(bre_doc.data_mappings) == 3
    
    def test_extract_bre_with_missing_fields(self, bre_extractor, mock_llm_client):
        """Test BRE extraction handles missing fields in JSON response."""
        # Setup mock with incomplete data
        incomplete_rules = json.dumps([
            {
                "id": "BR001",
                "name": "Incomplete Rule"
                # Missing other required fields
            }
        ])
        
        mock_llm_client.generate.side_effect = [
            incomplete_rules,
            MOCK_DATA_MAPPINGS_RESPONSE
        ]
        
        # Execute extraction
        bre_doc = bre_extractor.extract_bre(SAMPLE_ASM_CODE, "SAMPLE")
        
        # Verify defaults are used for missing fields
        assert len(bre_doc.business_rules) == 1
        rule = bre_doc.business_rules[0]
        assert rule.id == "BR001"
        assert rule.name == "Incomplete Rule"
        assert rule.description == ""
        assert rule.inputs == []
        assert rule.outputs == []
    
    def test_extract_bre_with_llm_exception(self, bre_extractor, mock_llm_client):
        """Test BRE extraction handles LLM exceptions."""
        # Setup mock to raise exception
        mock_llm_client.generate.side_effect = Exception("LLM API error")
        
        # Execute extraction - should raise exception
        with pytest.raises(Exception) as exc_info:
            bre_extractor.extract_bre(SAMPLE_ASM_CODE, "SAMPLE")
        
        assert "LLM API error" in str(exc_info.value)
    
    def test_save_and_load_bre(self, bre_extractor, temp_dir):
        """Test saving and loading BRE documents."""
        # Create a sample BRE document
        business_rules = [
            BusinessRule(
                id="BR001",
                name="Test Rule",
                description="Test description",
                purpose="Test purpose",
                inputs=["INPUT1"],
                outputs=["OUTPUT1"],
                logic="Test logic",
                conditions=["condition1"],
                source_location={"line_start": 1, "line_end": 10}
            )
        ]
        
        data_mappings = [
            DataMapping(
                source_field="R1",
                target_field="FIELD1",
                transformation="Test transformation",
                validation_rules=["rule1"]
            )
        ]
        
        bre_doc = BREDocument(
            program_name="TEST",
            business_rules=business_rules,
            data_mappings=data_mappings,
            summary="Test summary"
        )
        
        # Save BRE document
        output_path = temp_dir / "test_bre.json"
        bre_extractor.save_bre(bre_doc, str(output_path))
        
        # Verify file was created
        assert output_path.exists()
        
        # Load BRE document
        loaded_bre = bre_extractor.load_bre(str(output_path))
        
        # Verify loaded data matches original
        assert loaded_bre.program_name == "TEST"
        assert len(loaded_bre.business_rules) == 1
        assert len(loaded_bre.data_mappings) == 1
        assert loaded_bre.summary == "Test summary"
        
        # Verify business rule details
        loaded_rule = loaded_bre.business_rules[0]
        assert loaded_rule.id == "BR001"
        assert loaded_rule.name == "Test Rule"
        assert loaded_rule.inputs == ["INPUT1"]
        
        # Verify data mapping details
        loaded_mapping = loaded_bre.data_mappings[0]
        assert loaded_mapping.source_field == "R1"
        assert loaded_mapping.target_field == "FIELD1"
    
    def test_save_bre_creates_directories(self, bre_extractor, temp_dir):
        """Test that save_bre creates parent directories if they don't exist."""
        # Create BRE document
        bre_doc = BREDocument(
            program_name="TEST",
            business_rules=[],
            data_mappings=[],
            summary="Test"
        )
        
        # Save to nested path that doesn't exist
        nested_path = temp_dir / "phase1" / "bre" / "test.json"
        bre_extractor.save_bre(bre_doc, str(nested_path))
        
        # Verify file and directories were created
        assert nested_path.exists()
        assert nested_path.parent.exists()
    
    def test_load_bre_nonexistent_file(self, bre_extractor):
        """Test loading BRE from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            bre_extractor.load_bre("nonexistent_file.json")
    
    def test_extract_data_mappings_with_invalid_json(self, bre_extractor, mock_llm_client):
        """Test data mappings extraction handles invalid JSON gracefully."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_BUSINESS_RULES_RESPONSE,
            "Invalid JSON for mappings"
        ]
        
        # Execute extraction
        bre_doc = bre_extractor.extract_bre(SAMPLE_ASM_CODE, "SAMPLE")
        
        # Verify fallback behavior - empty data mappings
        assert len(bre_doc.business_rules) == 1
        assert len(bre_doc.data_mappings) == 0
    
    def test_generate_summary(self, bre_extractor):
        """Test summary generation."""
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
            for i in range(1, 6)
        ]
        
        data_mappings = [
            DataMapping(
                source_field=f"R{i}",
                target_field=f"FIELD{i}",
                transformation="",
                validation_rules=[]
            )
            for i in range(1, 4)
        ]
        
        summary = bre_extractor._generate_summary(business_rules, data_mappings)
        
        # Verify summary contains counts
        assert "5" in summary  # 5 business rules
        assert "3" in summary  # 3 data mappings
        assert "Rule 1" in summary or "Rule 2" in summary or "Rule 3" in summary
    
    def test_business_rule_dataclass(self):
        """Test BusinessRule dataclass creation."""
        rule = BusinessRule(
            id="BR001",
            name="Test Rule",
            description="Test description",
            purpose="Test purpose",
            inputs=["INPUT1", "INPUT2"],
            outputs=["OUTPUT1"],
            logic="Test logic",
            conditions=["condition1", "condition2"],
            source_location={"line_start": 10, "line_end": 20}
        )
        
        assert rule.id == "BR001"
        assert rule.name == "Test Rule"
        assert len(rule.inputs) == 2
        assert len(rule.outputs) == 1
        assert len(rule.conditions) == 2
    
    def test_data_mapping_dataclass(self):
        """Test DataMapping dataclass creation."""
        mapping = DataMapping(
            source_field="R1",
            target_field="TOTAL-AMOUNT",
            transformation="Convert binary to decimal",
            validation_rules=["Must be positive", "Max 9999999"]
        )
        
        assert mapping.source_field == "R1"
        assert mapping.target_field == "TOTAL-AMOUNT"
        assert len(mapping.validation_rules) == 2
    
    def test_bre_document_dataclass(self):
        """Test BREDocument dataclass creation."""
        doc = BREDocument(
            program_name="SAMPLE",
            business_rules=[],
            data_mappings=[],
            summary="Test summary"
        )
        
        assert doc.program_name == "SAMPLE"
        assert isinstance(doc.business_rules, list)
        assert isinstance(doc.data_mappings, list)
        assert doc.summary == "Test summary"
    
    def test_extract_bre_with_empty_assembly_code(self, bre_extractor, mock_llm_client):
        """Test BRE extraction with empty Assembly code."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            json.dumps([]),
            json.dumps([])
        ]
        
        # Execute extraction
        bre_doc = bre_extractor.extract_bre("", "EMPTY")
        
        # Verify results
        assert bre_doc.program_name == "EMPTY"
        assert len(bre_doc.business_rules) == 0
        assert len(bre_doc.data_mappings) == 0
    
    def test_extract_bre_with_multiple_rules(self, bre_extractor, mock_llm_client):
        """Test BRE extraction with multiple business rules."""
        # Setup mock with multiple rules
        multiple_rules = json.dumps([
            {
                "id": "BR001",
                "name": "Rule 1",
                "description": "First rule",
                "purpose": "Purpose 1",
                "inputs": ["INPUT1"],
                "outputs": ["OUTPUT1"],
                "logic": "Logic 1",
                "conditions": ["condition1"],
                "source_location": {"line_start": 1, "line_end": 5}
            },
            {
                "id": "BR002",
                "name": "Rule 2",
                "description": "Second rule",
                "purpose": "Purpose 2",
                "inputs": ["INPUT2"],
                "outputs": ["OUTPUT2"],
                "logic": "Logic 2",
                "conditions": ["condition2"],
                "source_location": {"line_start": 6, "line_end": 10}
            },
            {
                "id": "BR003",
                "name": "Rule 3",
                "description": "Third rule",
                "purpose": "Purpose 3",
                "inputs": ["INPUT3"],
                "outputs": ["OUTPUT3"],
                "logic": "Logic 3",
                "conditions": ["condition3"],
                "source_location": {"line_start": 11, "line_end": 15}
            }
        ])
        
        mock_llm_client.generate.side_effect = [
            multiple_rules,
            MOCK_DATA_MAPPINGS_RESPONSE
        ]
        
        # Execute extraction
        bre_doc = bre_extractor.extract_bre(SAMPLE_ASM_CODE, "MULTI")
        
        # Verify multiple rules were extracted
        assert len(bre_doc.business_rules) == 3
        assert bre_doc.business_rules[0].id == "BR001"
        assert bre_doc.business_rules[1].id == "BR002"
        assert bre_doc.business_rules[2].id == "BR003"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
