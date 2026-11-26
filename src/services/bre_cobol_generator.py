"""
BRE-based COBOL Generator

Generates COBOL code from BRE and functional specifications.
Replaces the IR-based generation approach.
"""

import logging
from typing import Dict, Any

from src.llm.client import SonnetClient
from src.utils.file_handler import FileHandler
from src.services.bre_extractor import BREDocument
from src.services.spec_generator import FunctionalSpec


class BRECOBOLGenerator:
    """Generates COBOL code from BRE and functional specifications."""
    
    def __init__(self, config_path: str):
        """Initialize BRE-based COBOL generator."""
        self.config_path = config_path
        self.llm_client = SonnetClient(config_path)
        self.file_handler = FileHandler()
        self.logger = logging.getLogger(__name__)
    
    def generate_cobol(self, asm_code: str, bre_doc: BREDocument, 
                      spec: FunctionalSpec) -> str:
        """
        Generate COBOL code from source using BRE and specifications.
        
        Args:
            asm_code: Original Easytrieve source code
            bre_doc: Business rules extraction document
            spec: Functional specification
            
        Returns:
            Generated COBOL code
        """
        self.logger.info(f"Generating COBOL for {spec.program_name}")
        
        try:
            # Build context for COBOL generation
            context = self._build_generation_context(asm_code, bre_doc, spec)
            
            # Add BRE metadata to context for header generation
            context['bre_count'] = len(bre_doc.business_rules)
            context['mapping_count'] = len(bre_doc.data_mappings)
            
            # Generate COBOL using LLM
            cobol_code = self._generate_with_llm(context)
            
            self.logger.info("COBOL generation successful")
            return cobol_code
            
        except Exception as e:
            self.logger.error(f"COBOL generation failed: {str(e)}")
            raise
    
    def _build_generation_context(self, asm_code: str, bre_doc: BREDocument,
                                  spec: FunctionalSpec) -> Dict[str, Any]:
        """Build comprehensive context for COBOL generation."""
        return {
            'program_name': spec.program_name,
            'asm_code': asm_code,
            'business_rules': [
                {
                    'id': rule.id,
                    'name': rule.name,
                    'logic': rule.logic,
                    'inputs': rule.inputs,
                    'outputs': rule.outputs,
                    'conditions': rule.conditions
                }
                for rule in bre_doc.business_rules
            ],
            'data_mappings': [
                {
                    'source': mapping.source_field,
                    'target': mapping.target_field,
                    'transformation': mapping.transformation
                }
                for mapping in bre_doc.data_mappings
            ],
            'data_structures': spec.data_structures,
            'process_flows': spec.process_flows,
            'overview': spec.overview
        }
    
    def _generate_with_llm(self, context: Dict[str, Any]) -> str:
        """Generate COBOL code using LLM with BRE context."""
        prompt = f"""Generate well-structured, compilable COBOL code based on this Easytrieve program analysis.

Program: {context['program_name']}

Overview:
{context['overview']}

Business Rules:
{self._format_business_rules(context['business_rules'])}

Data Mappings:
{self._format_data_mappings(context['data_mappings'])}

Data Structures:
{self._format_data_structures(context['data_structures'])}

Process Flow:
{self._format_process_flows(context['process_flows'])}

Original Easytrieve Source Code (for reference):
{context['asm_code']}

Generate complete COBOL code that:
1. Implements ALL business rules listed above — every single one must be traceable in the code
2. Uses the defined data structures with EXACT field sizes matching the Easytrieve source
3. Follows the process flow precisely as defined in the specification
4. Applies all data transformations faithfully
5. Includes proper error handling
6. Follows COBOL best practices

CRITICAL EQUIVALENCE REQUIREMENTS (these directly affect validation scoring):
- Match Easytrieve field sizes EXACTLY (e.g., if EZT defines a field as 20 A, use PIC X(20))
- Match Easytrieve record lengths EXACTLY (e.g., if EZT FILE has FB(80 80), use RECORD CONTAINS 80)
- PIC clauses MUST have enough decimal positions for the VALUE
- Every statement must be properly terminated with a period where required
- Every IF must have a matching END-IF
- Every PERFORM UNTIL must have a matching END-PERFORM
- Map Easytrieve data types faithfully:
  - A (alphanumeric) → PIC X(n)
  - N (numeric) → PIC 9(n)
  - P (packed decimal) → PIC S9(n)V9(d) COMP-3
  - B (binary) → PIC S9(n) COMP
- Do NOT add extra validation or features not present in the Easytrieve source
- Do NOT change data flow patterns — preserve the original logic
- Ensure the COBOL program is COMPLETE — include ALL paragraphs referenced by PERFORM statements

EASYTRIEVE-TO-COBOL CONVERSION PATTERNS (use these exact patterns):
1. FILE declaration → SELECT/ASSIGN + FD entry with matching record layout
2. JOB INPUT(file) → OPEN INPUT, READ loop with AT END, CLOSE
3. PUT file → WRITE record
4. PRINT report → DISPLAY or WRITE to report file
5. IF/END-IF → IF/END-IF with same conditions
6. SEQUENCE field → SORT verb with SD work file
7. CONTROL field → Control-break logic (compare previous vs current value)
8. SUM accumulation → ADD field TO accumulator
9. REPORT TITLE → Header line formatting
10. REPORT LINE → Detail line formatting

CRITICAL FORMATTING REQUIREMENTS:
1. DO NOT include any explanatory text, introductions, or conclusions.
2. Return ONLY the COBOL code itself.
3. Strict Column Alignment:
   - Column 7: Indicator area (* for comments, - for continuation).
   - Area A (Cols 8-11): Division/Section headers, Paragraphs, Level 01, Level 77.
   - Area B (Cols 12-72): All levels 05-49, Level 88, and all Procedure Division logic.
   - Margin: NO code or comments must exceed Column 72.
4. Level Numbering:
   - Use 01 for top-level items in Area A.
   - Use 05, 10, 15, etc. for subordinate items in Area B (indented by 4 spaces per level).
   - Use 88 for condition names.
5. Visual Alignment of WORKING-STORAGE:
   - Vertically align all PIC clauses to start at exactly Column 40.
   - Vertically align all VALUE clauses to start at exactly Column 56.
6. Data Precision:
   - Map Easytrieve types to appropriate COBOL types.
   - Ensure numeric fields are signed (S9) if the source logic allows negative values.
7. Add blank lines between logical sections and after each 01-level data group.

COMMENT REQUIREMENTS:
1. Start with a header comment block:
000100*****************************************************************
000200* Program: {context['program_name']:<54} *
000300* Generated from Easytrieve using BRE-based transformation      *
000400* Business Rules: {context['bre_count']:<44} *
000500* Data Mappings: {context['mapping_count']:<45} *
000600*****************************************************************
2. Add comment blocks before each SECTION and major paragraph.
3. Comment format: Column 7 has '*', columns 8-72 contain the comment text.
4. Include single-line comments explaining:
   - What each section/paragraph does.
   - Which business rules it implements (reference BR001, BR002, etc.).

CRITICAL: Return ONLY the COBOL code. Do not include markdown formatting or "Here is the code". 
Start directly with the header comment block.
The generated COBOL MUST be syntactically valid — no incomplete statements, no missing periods, no unclosed IF/PERFORM blocks.
Every paragraph referenced in a PERFORM statement MUST be implemented.
"""
        cobol_code = self.llm_client.generate(prompt)
        
        # Remove any introductory text that the LLM might add
        cobol_code = self._remove_llm_preamble(cobol_code)
        
        # Post-process to ensure proper formatting (this adds sequence numbers)
        cobol_code = self._ensure_proper_formatting(cobol_code)
        
        return cobol_code
    
    def _format_business_rules(self, rules: list) -> str:
        """Format business rules for prompt."""
        formatted = []
        for rule in rules:
            formatted.append(f"""
{rule['id']}: {rule['name']}
Logic: {rule['logic']}
Inputs: {', '.join(rule['inputs'])}
Outputs: {', '.join(rule['outputs'])}
Conditions: {', '.join(rule['conditions'])}
""")
        return '\n'.join(formatted)
    
    def _format_data_mappings(self, mappings: list) -> str:
        """Format data mappings for prompt."""
        formatted = []
        for mapping in mappings:
            formatted.append(
                f"{mapping['source']} -> {mapping['target']}: {mapping['transformation']}"
            )
        return '\n'.join(formatted)
    
    def _format_data_structures(self, structures: list) -> str:
        """Format data structures for prompt."""
        import json
        return json.dumps(structures, indent=2)
    
    def _format_process_flows(self, flows: list) -> str:
        """Format process flows for prompt."""
        formatted = []
        for flow in flows:
            formatted.append(
                f"Step {flow['step']}: {flow['name']} - {flow['description']}"
            )
        return '\n'.join(formatted)
    
    def _remove_llm_preamble(self, cobol_code: str) -> str:
        """
        Remove any introductory text that the LLM might add before the actual COBOL code.
        
        Common patterns to remove:
        - "Here's the COBOL code..."
        - "Based on the specifications..."
        - "I've generated the following COBOL code..."
        - Any text before the first COBOL division or comment block
        """
        import re
        
        # Strip leading/trailing whitespace
        cobol_code = cobol_code.strip()
        
        # Pattern to find the start of actual COBOL code
        # Look for: comment blocks (lines starting with *), or IDENTIFICATION/ENVIRONMENT/DATA/PROCEDURE DIVISION
        cobol_start_patterns = [
            r'^\s*\*+',  # Comment block starting with asterisks
            r'^\s*IDENTIFICATION\s+DIVISION',
            r'^\s*ENVIRONMENT\s+DIVISION',
            r'^\s*DATA\s+DIVISION',
            r'^\s*PROCEDURE\s+DIVISION',
        ]
        lines = cobol_code.split('\n')
        
        # Return the first COBOL-looking line. A matched line can be index 0,
        # so a numeric sentinel would incorrectly continue scanning.
        for index, line in enumerate(lines):
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in cobol_start_patterns):
                if index:
                    self.logger.info(f"Removed {index} lines of LLM preamble text")
                return '\n'.join(lines[index:])

        return cobol_code
    
    def _ensure_proper_formatting(self, cobol_code: str) -> str:
        """
        Ensure COBOL code follows proper formatting standards.
        - 80 character lines
        - Code starts at column 8
        - Comments at column 7
        - Sequence numbers in columns 1-6
        
        This method ALWAYS strips any existing sequence numbers and regenerates them
        to ensure consistent formatting.
        """
        lines = cobol_code.split('\n')
        formatted_lines = []
        line_number = 100  # Start sequence numbering at 100
        
        for line in lines:
            # Strip any existing sequence numbers (first 6 characters if they're digits)
            if len(line) >= 6 and line[:6].strip().isdigit():
                line = line[6:]  # Remove the sequence number area
            
            # Handle empty lines
            if not line.strip():
                formatted_line = f"{line_number:06d}" + ' ' * 74
                formatted_lines.append(formatted_line)
                line_number += 100
                continue
            
            # Determine the indicator character (column 7)
            indicator = ' '  # Default to space
            content_start = 0
            
            if len(line) > 0:
                # Check if first character is an indicator
                if line[0] in ('*', '-'):
                    indicator = line[0]
                    content_start = 1
                elif len(line) > 1 and line[0] == ' ' and line[1] in ('*', '-'):
                    indicator = line[1]
                    content_start = 2
                elif line[0] == ' ':
                    # Leading space, content starts after it
                    content_start = 1
            
            # Extract the actual content (everything after indicator)
            content = line[content_start:].rstrip()
            
            # Fix single-digit level numbers and condition names
            import re
            # Check if line starts with a single digit followed by space(s)
            match = re.match(r'^(\d)(\s+)(.+)', content)
            if match:
                digit = match.group(1)
                spaces = match.group(2)
                rest = match.group(3)
                
                # If it's "8" and the rest starts with uppercase (likely condition name), make it "88"
                if digit == '8' and rest and rest[0].isupper():
                    content = '88' + spaces + rest
                # Otherwise, pad single digit to 2 digits (5 -> 05, etc.)
                elif digit != '8':
                    content = '0' + digit + spaces + rest
            
            # Build the formatted line: sequence (6) + indicator (1) + content (up to 73)
            formatted_line = f"{line_number:06d}{indicator}{content[:73]}"
            
            # Pad to exactly 80 characters
            formatted_line = formatted_line.ljust(80)
            
            formatted_lines.append(formatted_line)
            line_number += 100
        
        return '\n'.join(formatted_lines)
    
    def save_cobol(self, cobol_code: str, output_path: str) -> None:
        """Save generated COBOL code to file."""
        self.file_handler.write_file(output_path, cobol_code)
        self.logger.info(f"COBOL code saved to {output_path}")
