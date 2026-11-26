"""
Business Rules Extraction Service

Extracts business rules from Easytrieve code using BRE methodology.
BRE serves as the intermediate representation for EZT-to-COBOL transformation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from html import escape

from src.llm.client import SonnetClient
from src.utils.file_handler import FileHandler


def _e(value) -> str:
    """HTML-escape a value. LLM output is derived from untrusted source files."""
    return escape(str(value), quote=True)


@dataclass
class BusinessRule:
    """Represents an extracted business rule."""
    id: str
    name: str
    description: str
    purpose: str
    inputs: List[str]
    outputs: List[str]
    logic: str
    conditions: List[str]
    source_location: Dict[str, Any]


@dataclass
class DataMapping:
    """Represents data transformation mapping."""
    source_field: str
    target_field: str
    transformation: str
    validation_rules: List[str]


@dataclass
class BREDocument:
    """Complete BRE document for a source file."""
    program_name: str
    business_rules: List[BusinessRule]
    data_mappings: List[DataMapping]
    summary: str


class BREExtractor:
    """Extracts Business Rules from Easytrieve code."""
    
    def __init__(self, config_path: str):
        """Initialize BRE extractor with configuration."""
        self.config_path = config_path
        self.llm_client = SonnetClient(config_path)
        self.file_handler = FileHandler()
        self.logger = logging.getLogger(__name__)
        
    def extract_bre(self, asm_code: str, program_name: str) -> BREDocument:
        """
        Extract business rules from source code.
        
        Args:
            asm_code: Easytrieve source code
            program_name: Name of the program
            
        Returns:
            BREDocument containing extracted business rules
        """
        self.logger.info(f"Extracting BRE from {program_name}")
        
        try:
            # Extract business rules
            business_rules = self._extract_business_rules(asm_code, program_name)
            
            # Extract data mappings
            data_mappings = self._extract_data_mappings(asm_code, program_name)
            
            # Generate summary
            summary = self._generate_summary(business_rules, data_mappings)
            
            bre_doc = BREDocument(
                program_name=program_name,
                business_rules=business_rules,
                data_mappings=data_mappings,
                summary=summary
            )
            
            self.logger.info(f"Successfully extracted {len(business_rules)} business rules")
            return bre_doc
            
        except Exception as e:
            self.logger.error(f"BRE extraction failed: {str(e)}")
            raise
    
    def _extract_business_rules(self, asm_code: str, program_name: str) -> List[BusinessRule]:
        """Extract business rules using LLM."""
        prompt = f"""Analyze this Easytrieve source code and extract ALL business rules at a granular level.

Easytrieve Source Code:
{asm_code}

IMPORTANT: Extract EVERY business rule, not just high-level or major rules. Include:
- Every conditional check (IF/THEN, comparisons, branch logic)
- Every calculation and arithmetic operation
- Every data validation rule
- Every data transformation
- Every business decision point
- Every loop and iteration logic
- Every error handling rule
- Every state change or flag setting
- Every accumulation or aggregation
- Every formatting or conversion rule

For each business rule (no matter how small), identify:
1. Name and description
2. Purpose (what business need it serves)
3. Input data fields
4. Output data fields
5. Logic description in natural language
6. Conditions that trigger the rule

Return a JSON array of ALL business rules with this structure:
[
  {{
    "id": "BR001",
    "name": "Rule name",
    "description": "What the rule does",
    "purpose": "Business purpose",
    "inputs": ["field1", "field2"],
    "outputs": ["result1"],
    "logic": "Natural language description of the logic",
    "conditions": ["condition1", "condition2"],
    "source_location": {{"line_start": 10, "line_end": 20}}
  }}
]

Extract rules at multiple levels of granularity:
- High-level business processes (e.g., "Calculate Employee Pay")
- Mid-level operations (e.g., "Calculate Overtime Pay", "Apply Tax Bracket")
- Low-level checks (e.g., "Validate Hours <= 80", "Check if Medical Insurance Selected")

DO NOT limit yourself to major rules only. Extract EVERY distinct business logic operation.
IMPORTANT: Respond with ONLY the JSON array, no other text before or after it.
"""
        
        response = self.llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        try:
            json_str = self.llm_client.extract_json_from_response(response)
        except ValueError as e:
            self.logger.warning(f"Failed to extract JSON from business rules response: {str(e)}. Returning empty list as fallback.")
            return []
        
        # Parse JSON response with robust error handling
        try:
            rules_data = json.loads(json_str)
            business_rules = [
                BusinessRule(
                    id=rule.get('id', f'BR{i+1:03d}'),
                    name=rule.get('name', 'Unknown Rule'),
                    description=rule.get('description', ''),
                    purpose=rule.get('purpose', ''),
                    inputs=rule.get('inputs', []),
                    outputs=rule.get('outputs', []),
                    logic=rule.get('logic', ''),
                    conditions=rule.get('conditions', []),
                    source_location=rule.get('source_location', {})
                )
                for i, rule in enumerate(rules_data)
            ]
            return business_rules
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse business rules JSON: {str(e)}. Returning empty list as fallback.")
            return []
        except (KeyError, TypeError) as e:
            self.logger.warning(f"Invalid business rules data structure: {str(e)}. Returning empty list as fallback.")
            return []
    
    def _extract_data_mappings(self, asm_code: str, program_name: str) -> List[DataMapping]:
        """Extract data transformation mappings using LLM."""
        prompt = f"""Analyze this Easytrieve source code and identify data transformations.

Easytrieve Source Code:
{asm_code}

For each data transformation, identify:
1. Source data field
2. Target data field
3. Transformation logic
4. Validation rules applied

Return a JSON array of data mappings:
[
  {{
    "source_field": "INPUT-FIELD",
    "target_field": "OUTPUT-FIELD",
    "transformation": "Description of transformation",
    "validation_rules": ["Must be positive", "Max 9999999"]
  }}
]
IMPORTANT: Respond with ONLY the JSON array, no other text before or after it.
"""
        
        response = self.llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        try:
            json_str = self.llm_client.extract_json_from_response(response)
        except ValueError as e:
            self.logger.warning(f"Failed to extract JSON from data mappings response: {str(e)}. Returning empty list as fallback.")
            return []
        
        # Parse JSON response with robust error handling
        try:
            mappings_data = json.loads(json_str)
            data_mappings = [
                DataMapping(
                    source_field=mapping.get('source_field', 'UNKNOWN'),
                    target_field=mapping.get('target_field', 'UNKNOWN'),
                    transformation=mapping.get('transformation', ''),
                    validation_rules=mapping.get('validation_rules', [])
                )
                for mapping in mappings_data
            ]
            return data_mappings
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse data mappings JSON: {str(e)}. Returning empty list as fallback.")
            return []
        except (KeyError, TypeError) as e:
            self.logger.warning(f"Invalid data mappings structure: {str(e)}. Returning empty list as fallback.")
            return []
    
    def _generate_summary(self, business_rules: List[BusinessRule], 
                         data_mappings: List[DataMapping]) -> str:
        """Generate summary of extracted BRE."""
        return f"""Business Rules Extraction Summary:
- Total Business Rules: {len(business_rules)}
- Total Data Mappings: {len(data_mappings)}
- Key Rules: {', '.join([rule.name for rule in business_rules[:3]])}
"""
    
    def save_bre(self, bre_doc: BREDocument, output_path: str) -> None:
        """Save BRE document to JSON file."""
        bre_dict = {
            'program_name': bre_doc.program_name,
            'business_rules': [asdict(rule) for rule in bre_doc.business_rules],
            'data_mappings': [asdict(mapping) for mapping in bre_doc.data_mappings],
            'summary': bre_doc.summary
        }
        
        self.file_handler.write_json(output_path, bre_dict)
        self.logger.info(f"BRE saved to {output_path}")
    
    def save_bre_html(self, bre_doc: BREDocument, output_path: str) -> None:
        """Save BRE document as HTML for better visualization."""
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <title>BRE Report - {_e(bre_doc.program_name)}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 2.5em;
        }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary h2 {{
            color: #667eea;
            margin-top: 0;
        }}
        .summary pre {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #667eea;
            overflow-x: auto;
        }}
        .section {{
            background: white;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #667eea;
            margin-top: 0;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .rule-card {{
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
        }}
        .rule-card h3 {{
            color: #764ba2;
            margin-top: 0;
        }}
        .rule-id {{
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .field-label {{
            font-weight: bold;
            color: #555;
            margin-top: 15px;
            margin-bottom: 5px;
        }}
        .field-value {{
            color: #333;
            padding-left: 10px;
        }}
        .list-item {{
            background: white;
            padding: 8px 12px;
            margin: 5px 0;
            border-radius: 4px;
            border-left: 3px solid #764ba2;
        }}
        .mapping-card {{
            background: #f8f9fa;
            border-left: 4px solid #28a745;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 5px;
        }}
        .mapping-arrow {{
            color: #28a745;
            font-size: 1.5em;
            font-weight: bold;
            margin: 0 10px;
        }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin-top: 20px;
        }}
        .stat-box {{
            text-align: center;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 8px;
            flex: 1;
            margin: 0 10px;
        }}
        .stat-number {{
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .empty-state {{
            text-align: center;
            padding: 40px;
            color: #999;
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Business Rules Extraction Report</h1>
        <p style="font-size: 1.2em; margin: 0;">Program: <strong>{_e(bre_doc.program_name)}</strong></p>
    </div>

    <div class="summary">
        <h2>📊 Summary</h2>
        <pre>{_e(bre_doc.summary)}</pre>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-label">Business Rules</div>
                <div class="stat-number">{len(bre_doc.business_rules)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Data Mappings</div>
                <div class="stat-number">{len(bre_doc.data_mappings)}</div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>📋 Business Rules</h2>
"""
        
        if bre_doc.business_rules:
            for rule in bre_doc.business_rules:
                html_content += f"""
        <div class="rule-card">
            <span class="rule-id">{_e(rule.id)}</span>
            <h3>{_e(rule.name)}</h3>
            
            <div class="field-label">Description:</div>
            <div class="field-value">{_e(rule.description)}</div>
            
            <div class="field-label">Purpose:</div>
            <div class="field-value">{_e(rule.purpose)}</div>
            
            <div class="field-label">Logic:</div>
            <div class="field-value">{_e(rule.logic)}</div>
            
            <div class="field-label">Inputs:</div>
            <div class="field-value">
"""
                for inp in rule.inputs:
                    html_content += f'                <div class="list-item">{_e(inp)}</div>\n'
                
                html_content += """            </div>
            
            <div class="field-label">Outputs:</div>
            <div class="field-value">
"""
                for out in rule.outputs:
                    html_content += f'                <div class="list-item">{_e(out)}</div>\n'
                
                html_content += """            </div>
            
            <div class="field-label">Conditions:</div>
            <div class="field-value">
"""
                for cond in rule.conditions:
                    html_content += f'                <div class="list-item">{_e(cond)}</div>\n'
                
                html_content += """            </div>
        </div>
"""
        else:
            html_content += """
        <div class="empty-state">
            <p>No business rules extracted. The Assembly code may not contain explicit business logic patterns.</p>
        </div>
"""
        
        html_content += """
    </div>

    <div class="section">
        <h2>🔄 Data Mappings</h2>
"""
        
        if bre_doc.data_mappings:
            for mapping in bre_doc.data_mappings:
                html_content += f"""
        <div class="mapping-card">
            <div style="display: flex; align-items: center;">
                <strong>{_e(mapping.source_field)}</strong>
                <span class="mapping-arrow">→</span>
                <strong>{_e(mapping.target_field)}</strong>
            </div>
            
            <div class="field-label">Transformation:</div>
            <div class="field-value">{_e(mapping.transformation)}</div>
            
            <div class="field-label">Validation Rules:</div>
            <div class="field-value">
"""
                for rule in mapping.validation_rules:
                    html_content += f'                <div class="list-item">{_e(rule)}</div>\n'
                
                html_content += """            </div>
        </div>
"""
        else:
            html_content += """
        <div class="empty-state">
            <p>No data mappings extracted. The Assembly code may not contain explicit data transformation patterns.</p>
        </div>
"""
        
        html_content += """
    </div>

    <footer style="text-align: center; padding: 20px; color: #999; margin-top: 40px;">
        <p>Generated by ASM-to-COBOL BRE Pipeline</p>
    </footer>
</body>
</html>
"""
        
        # Write HTML file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"BRE HTML report saved to {output_path}")
    
    def load_bre(self, bre_path: str) -> BREDocument:
        """Load BRE document from JSON file."""
        bre_dict = self.file_handler.read_json(bre_path)
        
        business_rules = [
            BusinessRule(**rule) for rule in bre_dict['business_rules']
        ]
        data_mappings = [
            DataMapping(**mapping) for mapping in bre_dict['data_mappings']
        ]
        
        return BREDocument(
            program_name=bre_dict['program_name'],
            business_rules=business_rules,
            data_mappings=data_mappings,
            summary=bre_dict['summary']
        )
