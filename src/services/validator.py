"""
Code Validator Service

Validates functional equivalence between Easytrieve and generated COBOL code.
Uses BRE and functional specifications for validation.
"""

import json
import logging
from typing import Dict, Any, List

from src.llm.client import SonnetClient
from src.utils.file_handler import FileHandler


class Code_Validator:
    """Validates functional equivalence between Easytrieve and COBOL."""
    
    def __init__(self, config_path: str):
        """Initialize validator with configuration."""
        self.config_path = config_path
        self.llm_client = SonnetClient(config_path)
        self.file_handler = FileHandler()
        self.logger = logging.getLogger(__name__)
    
    def validate(self, asm_code: str, cobol_code: str, 
                 bre_doc: Any = None, spec: Any = None) -> Dict[str, Any]:
        """
        Validate functional equivalence between Easytrieve and COBOL.
        
        Args:
            asm_code: Original Easytrieve source code
            cobol_code: Generated COBOL code
            bre_doc: Optional BRE document for enhanced validation
            spec: Optional functional specification for enhanced validation
            
        Returns:
            Validation report with equivalence score and findings
        """
        self.logger.info("Starting validation")

        if not cobol_code.strip():
            validation_results = {
                'syntax_check': {
                    'valid': False,
                    'errors': ['COBOL code is empty'],
                    'warnings': [],
                },
                'structure_check': {'equivalent': False, 'score': 0.0, 'issues': []},
                'logic_check': {'equivalent': False, 'score': 0.0, 'differences': []},
                'data_flow_check': {'equivalent': False, 'score': 0.0, 'issues': []},
            }
            return {
                'status': 'failed',
                'equivalence_score': 0.0,
                'validation_results': validation_results,
                'findings': self._generate_findings(validation_results),
                'recommendations': self._generate_recommendations(validation_results),
            }
        
        try:
            # Perform validation checks
            validation_results = {
                'syntax_check': self._check_syntax(cobol_code),
                'structure_check': self._check_structure(asm_code, cobol_code),
                'logic_check': self._check_logic_equivalence(asm_code, cobol_code),
                'data_flow_check': self._check_data_flow(asm_code, cobol_code)
            }
            
            # If BRE and spec provided, do enhanced validation
            if bre_doc and spec:
                validation_results['bre_coverage'] = self._check_bre_coverage(
                    cobol_code, bre_doc
                )
                validation_results['spec_compliance'] = self._check_spec_compliance(
                    cobol_code, spec
                )
            
            # Calculate overall equivalence score
            equivalence_score = self._calculate_equivalence_score(validation_results)
            
            # Generate detailed findings
            findings = self._generate_findings(validation_results)
            
            report = {
                'status': 'passed' if equivalence_score >= 0.7 else 'failed',
                'equivalence_score': equivalence_score,
                'validation_results': validation_results,
                'findings': findings,
                'recommendations': self._generate_recommendations(validation_results)
            }
            
            self.logger.info(f"Validation completed: {report['status']} (score: {equivalence_score:.2f})")
            return report
            
        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return {
                'status': 'error',
                'error': f"Validation failed ({type(e).__name__}). See the server logs.",
                'equivalence_score': 0.0
            }
    
    def _check_syntax(self, cobol_code: str) -> Dict[str, Any]:
        """Check COBOL syntax validity."""
        prompt = f"""Analyze this COBOL code for syntax errors.

COBOL Code:
{cobol_code}

Check for:
1. Proper IDENTIFICATION DIVISION structure
2. Valid DATA DIVISION declarations
3. Correct PROCEDURE DIVISION syntax
4. Proper statement termination
5. Valid COBOL keywords and clauses

IMPORTANT CLASSIFICATION RULES:
- Only report as "errors" things that would cause a COBOL compiler to REJECT the code
- These are WARNINGS, not errors:
  * Moving COMP/BINARY fields to display fields (COBOL handles this automatically)
  * Moving alphanumeric to numeric fields (COBOL performs implicit conversion)
  * Using CONTINUE statements
  * Using GO TO statements
  * Obsolete clauses (SOURCE-COMPUTER, OBJECT-COMPUTER)
  * PIC clause size being larger than necessary
  * Hard-coded string lengths in reference modification
- True errors include: missing periods, unclosed IF/PERFORM, invalid keywords, incomplete statements

IMPORTANT: Respond with ONLY the following JSON object, no other text:
{{
  "valid": true/false,
  "errors": ["list of actual compiler-rejecting syntax errors only"],
  "warnings": ["list of warnings and style issues"]
}}
"""
        
        response = self.llm_client.generate(prompt)
        
        # Log raw response for debugging parse failures
        self.logger.debug(f"Syntax check raw response length: {len(response)}")
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Handle empty response
        if not json_str or not json_str.strip():
            self.logger.warning("Syntax check returned empty response. LLM may have run out of tokens.")
            return {
                'valid': False,
                'errors': ['Syntax check returned empty response - prompt may exceed token limits'],
                'warnings': []
            }
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Provide defaults for missing fields
            return {
                'valid': result.get('valid', False),
                'errors': result.get('errors', ['Failed to validate syntax']),
                'warnings': result.get('warnings', [])
            }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse syntax check JSON: {str(e)}. Using error fallback.")
            return {
                'valid': False,
                'errors': [f'Failed to parse syntax check response: {str(e)}'],
                'warnings': []
            }
        except Exception as e:
            self.logger.warning(f"Unexpected error in syntax check: {str(e)}. Using error fallback.")
            return {
                'valid': False,
                'errors': [f'Unexpected error in syntax check ({type(e).__name__}). See the server logs.'],
                'warnings': []
            }
    
    def _check_structure(self, asm_code: str, cobol_code: str) -> Dict[str, Any]:
        """Check structural equivalence between Easytrieve and COBOL."""
        prompt = f"""Compare the structure of Easytrieve and COBOL code.

Easytrieve Source Code:
{asm_code}

COBOL Code:
{cobol_code}

Analyze:
1. Are all Easytrieve sections represented in COBOL?
2. Is the program flow preserved?
3. Are all FILE declarations mapped to COBOL FD entries?

SCORING GUIDELINES (score 0.0-1.0):
- These are EXPECTED differences between Easytrieve and COBOL and should NOT reduce the score:
  * Implicit file handling (JOB INPUT) vs explicit OPEN/READ/CLOSE
  * PRINT/REPORT vs DISPLAY or WRITE statements
  * SEQUENCE keyword vs SORT verb
  * CONTROL keyword vs manual control-break logic
  * Concise EZT syntax vs verbose COBOL divisions
- Score 0.90-1.0: All business logic sections are represented, program flow is preserved
- Score 0.80-0.89: Minor structural differences but all functionality is present
- Score 0.70-0.79: Some sections missing or significantly restructured
- Score below 0.70: Major sections missing or program flow broken
- Only penalize for MISSING functionality, not for different implementation approaches

IMPORTANT: Respond with ONLY the following JSON object, no other text:
{{
  "equivalent": true/false,
  "score": 0.0-1.0,
  "issues": ["list of structural differences"]
}}
"""
        
        response = self.llm_client.generate(prompt)
        
        # Log raw response for debugging parse failures
        self.logger.debug(f"Structure check raw response length: {len(response)}")
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Handle empty response
        if not json_str or not json_str.strip():
            self.logger.warning("Structure check returned empty response. LLM may have run out of tokens.")
            return {
                'equivalent': False,
                'score': 0.0,
                'issues': ['Structure check returned empty response - prompt may exceed token limits']
            }
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Provide defaults for missing fields
            return {
                'equivalent': result.get('equivalent', False),
                'score': result.get('score', 0.0),
                'issues': result.get('issues', ['Failed to validate structure'])
            }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse structure check JSON: {str(e)}. Using error fallback.")
            return {
                'equivalent': False,
                'score': 0.0,
                'issues': [f'Failed to parse structure check response: {str(e)}']
            }
        except Exception as e:
            self.logger.warning(f"Unexpected error in structure check: {str(e)}. Using error fallback.")
            return {
                'equivalent': False,
                'score': 0.0,
                'issues': [f'Unexpected error in structure check ({type(e).__name__}). See the server logs.']
            }
    
    def _check_logic_equivalence(self, asm_code: str, cobol_code: str) -> Dict[str, Any]:
        """Check logical equivalence of operations."""
        prompt = f"""Verify that COBOL implements the same logic as the Easytrieve source.

Easytrieve Source Code:
{asm_code}

COBOL Code:
{cobol_code}

Check:
1. Are conditional checks (IF/ELSE/END-IF) equivalent?
2. Are calculations performed correctly?
3. Are loops and iterations equivalent?
4. Is error handling preserved?
5. Are all JOB processing steps represented?

SCORING GUIDELINES (score 0.0-1.0):
- These are EXPECTED differences between Easytrieve and COBOL and should NOT reduce the score:
  * Implicit JOB INPUT loop vs explicit OPEN/READ/CLOSE with PERFORM UNTIL
  * PRINT report vs DISPLAY or WRITE statements
  * Easytrieve SUM accumulation vs explicit ADD statements
  * SEQUENCE/CONTROL vs SORT verb and manual control-break logic
  * Concise EZT expressions vs verbose COBOL COMPUTE/IF statements
- Score 0.90-1.0: All business logic is correctly implemented, calculations produce same results
- Score 0.80-0.89: Minor differences in edge case handling but core logic is correct
- Score 0.70-0.79: Some calculations may differ in precision or some logic paths missing
- Score below 0.70: Major logic errors or missing critical calculations
- Focus on FUNCTIONAL equivalence (same inputs produce same outputs), not implementation similarity

IMPORTANT: Respond with ONLY the following JSON object, no other text:
{{
  "equivalent": true/false,
  "score": 0.0-1.0,
  "differences": ["list of logic differences"]
}}
"""
        
        response = self.llm_client.generate(prompt)
        
        # Log raw response for debugging parse failures
        self.logger.debug(f"Logic check raw response length: {len(response)}")
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Handle empty response
        if not json_str or not json_str.strip():
            self.logger.warning("Logic check returned empty response. LLM may have run out of tokens.")
            return {
                'equivalent': False,
                'score': 0.0,
                'differences': ['Logic check returned empty response - prompt may exceed token limits']
            }
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Provide defaults for missing fields
            return {
                'equivalent': result.get('equivalent', False),
                'score': result.get('score', 0.0),
                'differences': result.get('differences', ['Failed to validate logic'])
            }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse logic check JSON: {str(e)}. Using error fallback.")
            return {
                'equivalent': False,
                'score': 0.0,
                'differences': [f'Failed to parse logic check response: {str(e)}']
            }
        except Exception as e:
            self.logger.warning(f"Unexpected error in logic check: {str(e)}. Using error fallback.")
            return {
                'equivalent': False,
                'score': 0.0,
                'differences': [f'Unexpected error in logic check ({type(e).__name__}). See the server logs.']
            }
    
    def _check_data_flow(self, asm_code: str, cobol_code: str) -> Dict[str, Any]:
        """Check data flow equivalence."""
        prompt = f"""Verify data flow equivalence between Easytrieve and COBOL.

Easytrieve Source Code:
{asm_code}

COBOL Code:
{cobol_code}

Check:
1. Are field-to-variable mappings correct?
2. Is data transformation logic preserved?
3. Are input/output operations equivalent?

SCORING GUIDELINES (score 0.0-1.0):
- These are EXPECTED differences between Easytrieve and COBOL and should NOT reduce the score:
  * Easytrieve field definitions mapped to COBOL PIC clauses
  * Easytrieve A type → PIC X, N type → PIC 9, P type → COMP-3
  * Implicit file I/O (JOB INPUT) vs explicit OPEN/READ/WRITE/CLOSE
  * Easytrieve PUT vs COBOL WRITE
  * Different variable naming conventions
  * Easytrieve automatic type conversion vs explicit COBOL MOVE
- Score 0.90-1.0: All data flows correctly mapped, field sizes appropriate, I/O preserved
- Score 0.80-0.89: Minor field size differences but data integrity maintained
- Score 0.70-0.79: Some data precision differences or missing data transformations
- Score below 0.70: Major data flow errors or missing I/O operations
- Focus on whether the same data reaches the same destinations with correct values

IMPORTANT: Respond with ONLY the following JSON object, no other text:
{{
  "equivalent": true/false,
  "score": 0.0-1.0,
  "issues": ["list of data flow issues"]
}}
"""
        
        response = self.llm_client.generate(prompt)
        
        # Log raw response for debugging parse failures
        self.logger.debug(f"Data flow check raw response length: {len(response)}")
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Handle empty response
        if not json_str or not json_str.strip():
            self.logger.warning("Data flow check returned empty response. LLM may have run out of tokens.")
            return {
                'equivalent': False,
                'score': 0.0,
                'issues': ['Data flow check returned empty response - prompt may exceed token limits']
            }
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Provide defaults for missing fields
            return {
                'equivalent': result.get('equivalent', False),
                'score': result.get('score', 0.0),
                'issues': result.get('issues', ['Failed to validate data flow'])
            }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse data flow check JSON: {str(e)}. Using error fallback.")
            return {
                'equivalent': False,
                'score': 0.0,
                'issues': [f'Failed to parse data flow check response: {str(e)}']
            }
        except Exception as e:
            self.logger.warning(f"Unexpected error in data flow check: {str(e)}. Using error fallback.")
            return {
                'equivalent': False,
                'score': 0.0,
                'issues': [f'Unexpected error in data flow check ({type(e).__name__}). See the server logs.']
            }
    
    def _check_bre_coverage(self, cobol_code: str, bre_doc: Any) -> Dict[str, Any]:
        """Check if COBOL implements all business rules from BRE."""
        business_rules = [
            {
                'id': rule.id,
                'name': rule.name,
                'logic': rule.logic
            }
            for rule in bre_doc.business_rules
        ]
        
        prompt = f"""Verify that COBOL code implements all business rules.

Business Rules:
{json.dumps(business_rules, indent=2)}

COBOL Code:
{cobol_code}

For each business rule, check if it's implemented in COBOL.

IMPORTANT: Respond with ONLY the following JSON object, no other text:
{{
  "coverage_score": 0.0-1.0,
  "implemented_rules": ["BR001", "BR002"],
  "missing_rules": ["BR003"],
  "details": {{"BR001": "Implemented in MAIN-PROCEDURE"}}
}}
"""
        
        response = self.llm_client.generate(prompt)
        
        # Log raw response for debugging parse failures
        self.logger.debug(f"BRE coverage check raw response length: {len(response)}")
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Handle empty response
        if not json_str or not json_str.strip():
            self.logger.warning("BRE coverage check returned empty response.")
            return {
                'coverage_score': 0.0,
                'implemented_rules': [],
                'missing_rules': [rule['id'] for rule in business_rules],
                'details': {}
            }
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Provide defaults for missing fields
            return {
                'coverage_score': result.get('coverage_score', 0.0),
                'implemented_rules': result.get('implemented_rules', []),
                'missing_rules': result.get('missing_rules', [rule['id'] for rule in business_rules]),
                'details': result.get('details', {})
            }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse BRE coverage JSON: {str(e)}. Using error fallback.")
            return {
                'coverage_score': 0.0,
                'implemented_rules': [],
                'missing_rules': [rule['id'] for rule in business_rules],
                'details': {}
            }
        except Exception as e:
            self.logger.warning(f"Unexpected error in BRE coverage check: {str(e)}. Using error fallback.")
            return {
                'coverage_score': 0.0,
                'implemented_rules': [],
                'missing_rules': [rule['id'] for rule in business_rules],
                'details': {}
            }
    
    def _check_spec_compliance(self, cobol_code: str, spec: Any) -> Dict[str, Any]:
        """Check if COBOL complies with functional specification."""
        prompt = f"""Verify COBOL code compliance with functional specification.

Specification Overview:
{spec.overview}

Data Structures Required:
{json.dumps(spec.data_structures, indent=2)}

Process Flows Required:
{json.dumps(spec.process_flows, indent=2)}

COBOL Code:
{cobol_code}

Check:
1. Are all required data structures defined?
2. Does the code follow the specified process flow?
3. Are all functions implemented?

SCORING GUIDELINES (score 0.0-1.0):
- These are EXPECTED differences and should NOT reduce the score:
  * COMP-3 and PACKED-DECIMAL are synonymous in COBOL
  * Using PIC S9 instead of PIC 9 (signed vs unsigned) is acceptable
  * Combining multiple specification steps into fewer paragraphs is acceptable if logic is preserved
  * Additional working storage fields not in spec are acceptable if they support the logic
  * Different field sizes are acceptable if they can hold the required data range
- Score 0.90-1.0: All data structures present, process flow followed, all functions implemented
- Score 0.80-0.89: Minor deviations but all functionality is present
- Score 0.70-0.79: Some functions missing or process flow significantly altered
- Score below 0.70: Major spec violations or missing critical functionality

IMPORTANT: Respond with ONLY the following JSON object, no other text:
{{
  "compliant": true/false,
  "score": 0.0-1.0,
  "issues": ["list of compliance issues"]
}}
"""
        
        response = self.llm_client.generate(prompt)
        
        # Log raw response for debugging parse failures
        self.logger.debug(f"Spec compliance check raw response length: {len(response)}")
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Handle empty response
        if not json_str or not json_str.strip():
            self.logger.warning("Spec compliance check returned empty response.")
            return {
                'compliant': False,
                'score': 0.0,
                'issues': ['Spec compliance check returned empty response - prompt may exceed token limits']
            }
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Provide defaults for missing fields
            return {
                'compliant': result.get('compliant', False),
                'score': result.get('score', 0.0),
                'issues': result.get('issues', ['Failed to validate spec compliance'])
            }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse spec compliance JSON: {str(e)}. Using error fallback.")
            return {
                'compliant': False,
                'score': 0.0,
                'issues': [f'Failed to parse compliance check response: {str(e)}']
            }
        except Exception as e:
            self.logger.warning(f"Unexpected error in spec compliance check: {str(e)}. Using error fallback.")
            return {
                'compliant': False,
                'score': 0.0,
                'issues': [f'Unexpected error in spec compliance check ({type(e).__name__}). See the server logs.']
            }
    
    def _calculate_equivalence_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate overall equivalence score from validation results."""
        scores = []
        
        # Syntax check (weight: 0.2) - graduated scoring
        syntax_result = validation_results['syntax_check']
        if syntax_result.get('valid', False):
            scores.append(0.2)
        else:
            # Graduated: reduce score based on number of errors
            error_count = len(syntax_result.get('errors', []))
            if error_count == 0:
                scores.append(0.2)
            elif error_count <= 2:
                scores.append(0.15)
            elif error_count <= 5:
                scores.append(0.10)
            else:
                scores.append(0.05)
        
        # Structure check (weight: 0.2)
        structure_score = validation_results['structure_check'].get('score', 0.0)
        scores.append(structure_score * 0.2)
        
        # Logic check (weight: 0.3)
        logic_score = validation_results['logic_check'].get('score', 0.0)
        scores.append(logic_score * 0.3)
        
        # Data flow check (weight: 0.3)
        data_flow_score = validation_results['data_flow_check'].get('score', 0.0)
        scores.append(data_flow_score * 0.3)
        
        # BRE coverage (bonus if available)
        if 'bre_coverage' in validation_results:
            bre_score = validation_results['bre_coverage'].get('coverage_score', 0.0)
            scores.append(bre_score * 0.1)
        
        # Spec compliance (bonus if available)
        if 'spec_compliance' in validation_results:
            spec_score = validation_results['spec_compliance'].get('score', 0.0)
            scores.append(spec_score * 0.1)
        
        return sum(scores)
    
    def _generate_findings(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate list of findings from validation results."""
        findings = []
        
        # Syntax findings
        syntax = validation_results['syntax_check']
        if not syntax.get('valid', False):
            findings.extend([f"Syntax Error: {err}" for err in syntax.get('errors', [])])
        
        # Structure findings
        structure = validation_results['structure_check']
        if not structure.get('equivalent', False):
            findings.extend([f"Structure Issue: {issue}" for issue in structure.get('issues', [])])
        
        # Logic findings
        logic = validation_results['logic_check']
        if not logic.get('equivalent', False):
            findings.extend([f"Logic Difference: {diff}" for diff in logic.get('differences', [])])
        
        # Data flow findings
        data_flow = validation_results['data_flow_check']
        if not data_flow.get('equivalent', False):
            findings.extend([f"Data Flow Issue: {issue}" for issue in data_flow.get('issues', [])])
        
        # BRE coverage findings
        if 'bre_coverage' in validation_results:
            bre = validation_results['bre_coverage']
            if bre.get('missing_rules'):
                findings.append(f"Missing Business Rules: {', '.join(bre['missing_rules'])}")
        
        # Spec compliance findings
        if 'spec_compliance' in validation_results:
            spec = validation_results['spec_compliance']
            if not spec.get('compliant', False):
                findings.extend([f"Spec Compliance: {issue}" for issue in spec.get('issues', [])])
        
        return findings if findings else ['No issues found']
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations for improvement."""
        recommendations = []
        
        # Syntax recommendations
        syntax = validation_results['syntax_check']
        if syntax.get('warnings'):
            recommendations.append("Review and address syntax warnings")
        
        # Structure recommendations
        structure = validation_results['structure_check']
        if structure.get('score', 1.0) < 0.8:
            recommendations.append("Review program structure alignment with Easytrieve source")
        
        # Logic recommendations
        logic = validation_results['logic_check']
        if logic.get('score', 1.0) < 0.8:
            recommendations.append("Verify conditional logic and calculations")
        
        # BRE recommendations
        if 'bre_coverage' in validation_results:
            bre = validation_results['bre_coverage']
            if bre.get('coverage_score', 1.0) < 1.0:
                recommendations.append("Implement missing business rules")
        
        return recommendations if recommendations else ['Code meets validation criteria']
