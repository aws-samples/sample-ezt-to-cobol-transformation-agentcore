"""
Functional Specification Generator

Generates functional specifications from BRE documents.
"""

import json
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

from src.llm.client import SonnetClient
from src.utils.file_handler import FileHandler
from src.services.bre_extractor import BREDocument


@dataclass
class FunctionalSpec:
    """Functional specification for COBOL generation."""
    program_name: str
    overview: str
    data_structures: List[Dict[str, Any]]
    process_flows: List[Dict[str, Any]]
    business_rules_coverage: Dict[str, str]


class SpecGenerator:
    """Generates functional specifications from BRE."""
    
    def __init__(self, config_path: str):
        """Initialize spec generator with configuration."""
        self.config_path = config_path
        self.llm_client = SonnetClient(config_path)
        self.file_handler = FileHandler()
        self.logger = logging.getLogger(__name__)
    
    def generate_spec(self, bre_doc: BREDocument) -> FunctionalSpec:
        """
        Generate functional specification from BRE document.
        
        Args:
            bre_doc: BRE document containing business rules
            
        Returns:
            FunctionalSpec for COBOL generation
        """
        self.logger.info(f"Generating functional spec for {bre_doc.program_name}")
        
        try:
            # Generate data structures
            data_structures = self._design_data_structures(bre_doc)
            
            # Generate process flows
            process_flows = self._design_process_flows(bre_doc)
            
            # Create business rules coverage map
            coverage = self._create_coverage_map(bre_doc)
            
            # Generate overview
            overview = self._generate_overview(bre_doc, data_structures, process_flows)
            
            spec = FunctionalSpec(
                program_name=bre_doc.program_name,
                overview=overview,
                data_structures=data_structures,
                process_flows=process_flows,
                business_rules_coverage=coverage
            )
            
            self.logger.info(f"Successfully generated functional spec")
            return spec
            
        except Exception as e:
            self.logger.error(f"Spec generation failed: {str(e)}")
            raise
    
    def _design_data_structures(self, bre_doc: BREDocument) -> List[Dict[str, Any]]:
        """Design COBOL data structures from BRE."""
        # Collect all data fields from business rules and mappings
        all_fields = set()
        for rule in bre_doc.business_rules:
            # Handle inputs and outputs which might be lists
            if isinstance(rule.inputs, list):
                all_fields.update(rule.inputs)
            else:
                all_fields.add(rule.inputs)
            
            if isinstance(rule.outputs, list):
                all_fields.update(rule.outputs)
            else:
                all_fields.add(rule.outputs)
        
        for mapping in bre_doc.data_mappings:
            # Handle source and target fields which might be lists or strings
            if isinstance(mapping.source_field, list):
                all_fields.update(mapping.source_field)
            else:
                all_fields.add(mapping.source_field)
            
            if isinstance(mapping.target_field, list):
                all_fields.update(mapping.target_field)
            else:
                all_fields.add(mapping.target_field)
        
        prompt = f"""Design COBOL data structures for this program.

Business Rules Summary:
{bre_doc.summary}

Data Fields Identified:
{', '.join(all_fields)}

Data Mappings:
{json.dumps([asdict(m) for m in bre_doc.data_mappings], indent=2)}

Create COBOL-compatible data structures with:
1. Field names (COBOL naming conventions)
2. Data types (PIC clauses)
3. Field sizes
4. Grouping (01, 05 levels)

Return JSON array:
[
  {{
    "name": "WORKING-STORAGE-SECTION",
    "fields": [
      {{"name": "WS-FIELD-NAME", "type": "PIC X(10)", "description": "Field purpose"}}
    ]
  }}
]
IMPORTANT: Respond with ONLY the JSON array, no other text before or after it.
"""
        
        response = self.llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Parse JSON response with robust error handling
        try:
            data_structures = json.loads(json_str)
            # Validate structure
            if not isinstance(data_structures, list):
                self.logger.warning("Data structures response is not a list, using default")
                return [{"name": "WORKING-STORAGE-SECTION", "fields": []}]
            return data_structures
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse data structures JSON: {str(e)}. Using default structure as fallback.")
            return [{"name": "WORKING-STORAGE-SECTION", "fields": []}]
        except Exception as e:
            self.logger.warning(f"Unexpected error parsing data structures: {str(e)}. Using default structure as fallback.")
            return [{"name": "WORKING-STORAGE-SECTION", "fields": []}]
    
    def _design_process_flows(self, bre_doc: BREDocument) -> List[Dict[str, Any]]:
        """Design process flows from business rules."""
        prompt = f"""Design the process flow for this COBOL program.

Business Rules:
{json.dumps([asdict(r) for r in bre_doc.business_rules], indent=2)}

Create a structured process flow showing:
1. Main procedure steps
2. Decision points (based on business rules)
3. Data processing steps
4. Error handling

Return JSON array of process steps:
[
  {{
    "step": 1,
    "name": "INITIALIZE-PROGRAM",
    "description": "Initialize working storage variables",
    "business_rules": ["BR001"]
  }}
]
IMPORTANT: Respond with ONLY the JSON array, no other text before or after it.
"""
        
        response = self.llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Parse JSON response with robust error handling
        try:
            process_flows = json.loads(json_str)
            # Validate structure
            if not isinstance(process_flows, list):
                self.logger.warning("Process flows response is not a list, using default")
                return [{"step": 1, "name": "MAIN-PROCEDURE", "description": "Main processing"}]
            return process_flows
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse process flows JSON: {str(e)}. Using default flow as fallback.")
            return [{"step": 1, "name": "MAIN-PROCEDURE", "description": "Main processing"}]
        except Exception as e:
            self.logger.warning(f"Unexpected error parsing process flows: {str(e)}. Using default flow as fallback.")
            return [{"step": 1, "name": "MAIN-PROCEDURE", "description": "Main processing"}]
    
    def _create_coverage_map(self, bre_doc: BREDocument) -> Dict[str, str]:
        """Create mapping of business rules to spec sections."""
        coverage = {}
        for rule in bre_doc.business_rules:
            coverage[rule.id] = f"Covered in process flow and data structures"
        return coverage
    
    def _generate_overview(self, bre_doc: BREDocument, 
                          data_structures: List[Dict[str, Any]],
                          process_flows: List[Dict[str, Any]]) -> str:
        """Generate overview of the functional specification."""
        return f"""Functional Specification for {bre_doc.program_name}

This specification defines the COBOL program structure based on extracted business rules.

Business Rules: {len(bre_doc.business_rules)}
Data Structures: {len(data_structures)}
Process Steps: {len(process_flows)}

{bre_doc.summary}
"""
    
    def save_spec(self, spec: FunctionalSpec, output_path: str) -> None:
        """Save functional specification to JSON file."""
        spec_dict = asdict(spec)
        self.file_handler.write_json(output_path, spec_dict)
        self.logger.info(f"Functional spec saved to {output_path}")
    
    def load_spec(self, spec_path: str) -> FunctionalSpec:
        """Load functional specification from JSON file."""
        spec_dict = self.file_handler.read_json(spec_path)
        return FunctionalSpec(**spec_dict)
