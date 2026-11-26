"""
Feedback Analyzer Service

Analyzes validation results and provides detailed feedback and improvement suggestions.
"""

import json
import logging
from typing import Dict, Any, List

from src.llm.client import SonnetClient
from src.utils.file_handler import FileHandler


class Feedback_Analyzer:
    """Analyzes validation results and provides actionable feedback."""
    
    def __init__(self, config_path: str):
        """Initialize analyzer with configuration."""
        self.config_path = config_path
        self.llm_client = SonnetClient(config_path)
        self.file_handler = FileHandler()
        self.logger = logging.getLogger(__name__)
    
    def analyze(self, asm_code: str, cobol_code: str, 
                validation_report: Dict[str, Any],
                bre_doc: Any = None) -> Dict[str, Any]:
        """
        Analyze validation results and provide detailed feedback.
        
        Args:
            asm_code: Original Easytrieve source code
            cobol_code: Generated COBOL code
            validation_report: Validation report from Code_Validator
            bre_doc: Optional BRE document for enhanced analysis
            
        Returns:
            Analysis report with feedback and improvement suggestions
        """
        self.logger.info("Starting feedback analysis")
        
        try:
            # Analyze validation results
            quality_assessment = self._assess_quality(validation_report)
            
            # Identify improvement areas
            improvement_areas = self._identify_improvements(
                asm_code, cobol_code, validation_report
            )
            
            # Generate specific recommendations
            recommendations = self._generate_detailed_recommendations(
                validation_report, improvement_areas
            )
            
            # Analyze BRE implementation if available
            bre_analysis = None
            if bre_doc:
                bre_analysis = self._analyze_bre_implementation(
                    cobol_code, bre_doc, validation_report
                )
            
            # Generate code improvement suggestions
            code_suggestions = self._generate_code_suggestions(
                cobol_code, validation_report
            )
            
            # Calculate overall quality metrics
            quality_metrics = self._calculate_quality_metrics(
                validation_report, quality_assessment
            )
            
            report = {
                'status': 'completed',
                'quality_assessment': quality_assessment,
                'quality_metrics': quality_metrics,
                'improvement_areas': improvement_areas,
                'recommendations': recommendations,
                'code_suggestions': code_suggestions,
                'bre_analysis': bre_analysis,
                'summary': self._generate_summary(
                    quality_assessment, improvement_areas
                )
            }
            
            self.logger.info("Feedback analysis completed")
            return report
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            return {
                'status': 'error',
                'error': f"Analysis failed ({type(e).__name__}). See the server logs."
            }
    
    def _assess_quality(self, validation_report: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall quality of the translation."""
        equivalence_score = validation_report.get('equivalence_score', 0.0)
        
        # Determine quality level
        if equivalence_score >= 0.9:
            quality_level = 'excellent'
            description = 'Translation is highly accurate with minimal issues'
        elif equivalence_score >= 0.7:
            quality_level = 'good'
            description = 'Translation is acceptable with some minor issues'
        elif equivalence_score >= 0.5:
            quality_level = 'fair'
            description = 'Translation has moderate issues requiring attention'
        else:
            quality_level = 'poor'
            description = 'Translation has significant issues requiring major revision'
        
        return {
            'quality_level': quality_level,
            'description': description,
            'equivalence_score': equivalence_score,
            'passed_validation': validation_report.get('status') == 'passed'
        }
    
    def _identify_improvements(self, asm_code: str, cobol_code: str,
                               validation_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify specific areas for improvement."""
        improvements = []
        
        validation_results = validation_report.get('validation_results', {})
        
        # Check syntax issues
        syntax = validation_results.get('syntax_check', {})
        if not syntax.get('valid', False):
            improvements.append({
                'area': 'Syntax',
                'severity': 'high',
                'issues': syntax.get('errors', []),
                'priority': 1
            })
        
        # Check structure issues
        structure = validation_results.get('structure_check', {})
        if structure.get('score', 1.0) < 0.8:
            improvements.append({
                'area': 'Structure',
                'severity': 'medium',
                'issues': structure.get('issues', []),
                'priority': 2
            })
        
        # Check logic issues
        logic = validation_results.get('logic_check', {})
        if logic.get('score', 1.0) < 0.8:
            improvements.append({
                'area': 'Logic',
                'severity': 'high',
                'issues': logic.get('differences', []),
                'priority': 1
            })
        
        # Check data flow issues
        data_flow = validation_results.get('data_flow_check', {})
        if data_flow.get('score', 1.0) < 0.8:
            improvements.append({
                'area': 'Data Flow',
                'severity': 'medium',
                'issues': data_flow.get('issues', []),
                'priority': 2
            })
        
        # Check BRE coverage
        if 'bre_coverage' in validation_results:
            bre = validation_results['bre_coverage']
            if bre.get('missing_rules'):
                improvements.append({
                    'area': 'Business Rules Coverage',
                    'severity': 'high',
                    'issues': [f"Missing rules: {', '.join(bre['missing_rules'])}"],
                    'priority': 1
                })
        
        # Sort by priority
        improvements.sort(key=lambda x: x['priority'])
        
        return improvements
    
    def _generate_detailed_recommendations(self, validation_report: Dict[str, Any],
                                          improvement_areas: List[Dict[str, Any]]) -> List[str]:
        """Generate detailed, actionable recommendations."""
        recommendations = []
        
        for area in improvement_areas:
            if area['area'] == 'Syntax':
                recommendations.append(
                    "Fix syntax errors: Review COBOL syntax rules and correct "
                    "invalid statements, missing periods, or incorrect keywords"
                )
            
            elif area['area'] == 'Structure':
                recommendations.append(
                    "Improve structure alignment: Ensure COBOL program structure "
                    "mirrors Easytrieve sections and maintains proper division organization"
                )
            
            elif area['area'] == 'Logic':
                recommendations.append(
                    "Verify logic equivalence: Review conditional statements, "
                    "calculations, and loops to ensure they match Easytrieve behavior"
                )
            
            elif area['area'] == 'Data Flow':
                recommendations.append(
                    "Correct data flow: Verify register-to-variable mappings and "
                    "ensure data transformations preserve original semantics"
                )
            
            elif area['area'] == 'Business Rules Coverage':
                recommendations.append(
                    "Implement missing business rules: Add code sections to implement "
                    "all extracted business rules from the BRE document"
                )
        
        # Add general recommendations
        equivalence_score = validation_report.get('equivalence_score', 0.0)
        if equivalence_score < 0.7:
            recommendations.append(
                "Consider regenerating COBOL: Low equivalence score suggests "
                "significant issues - review BRE and specifications before regenerating"
            )
        
        return recommendations
    
    def _analyze_bre_implementation(self, cobol_code: str, bre_doc: Any,
                                   validation_report: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze how well business rules are implemented in COBOL."""
        prompt = f"""Analyze how business rules are implemented in COBOL code.

Business Rules:
{json.dumps([{
    'id': rule.id,
    'name': rule.name,
    'logic': rule.logic,
    'conditions': rule.conditions
} for rule in bre_doc.business_rules], indent=2)}

COBOL Code:
{cobol_code}

For each business rule, analyze:
1. Is it implemented correctly?
2. Where is it implemented (procedure name)?
3. Are there any deviations from the rule logic?
4. Quality of implementation (1-5 scale)

Return JSON:
{{
  "overall_implementation_quality": 1-5,
  "rule_analysis": [
    {{
      "rule_id": "BR001",
      "implemented": true/false,
      "location": "PROCEDURE-NAME",
      "quality": 1-5,
      "deviations": ["list of deviations"],
      "notes": "implementation notes"
    }}
  ],
  "summary": "overall summary"
}}
"""
        
        response = self.llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Validate structure
            if not isinstance(result, dict):
                self.logger.warning("BRE analysis response is not a dict, using default")
                return {
                    'overall_implementation_quality': 0,
                    'rule_analysis': [],
                    'summary': 'Failed to analyze BRE implementation'
                }
            # Provide defaults for missing fields
            return {
                'overall_implementation_quality': result.get('overall_implementation_quality', 0),
                'rule_analysis': result.get('rule_analysis', []),
                'summary': result.get('summary', 'Failed to analyze BRE implementation')
            }
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse BRE analysis JSON: {str(e)}. Using error fallback.")
            return {
                'overall_implementation_quality': 0,
                'rule_analysis': [],
                'summary': f'Failed to analyze BRE implementation: {str(e)}'
            }
        except Exception as e:
            self.logger.warning(f"Unexpected error in BRE analysis: {str(e)}. Using error fallback.")
            return {
                'overall_implementation_quality': 0,
                'rule_analysis': [],
                'summary': f'Unexpected error in BRE analysis ({type(e).__name__}). See the server logs.'
            }
    
    def _generate_code_suggestions(self, cobol_code: str,
                                  validation_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate specific code improvement suggestions."""
        prompt = f"""Analyze this COBOL code and provide specific improvement suggestions.

COBOL Code:
{cobol_code}

Validation Issues:
{json.dumps(validation_report.get('findings', []), indent=2)}

Provide specific suggestions for:
1. Code structure improvements
2. Better variable naming
3. Enhanced error handling
4. Performance optimizations
5. COBOL best practices

Return JSON array:
[
  {{
    "category": "Structure|Naming|Error Handling|Performance|Best Practices",
    "suggestion": "specific suggestion",
    "location": "where to apply (line/section)",
    "priority": "high|medium|low",
    "example": "code example if applicable"
  }}
]
"""
        
        response = self.llm_client.generate(prompt)
        
        # Extract JSON from response (handles markdown code blocks)
        json_str = self.llm_client.extract_json_from_response(response)
        
        # Parse JSON response with robust error handling
        try:
            result = json.loads(json_str)
            # Validate structure
            if not isinstance(result, list):
                self.logger.warning("Code suggestions response is not a list, returning empty list")
                return []
            return result
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse code suggestions JSON: {str(e)}. Returning empty list as fallback.")
            return []
        except Exception as e:
            self.logger.warning(f"Unexpected error parsing code suggestions: {str(e)}. Returning empty list as fallback.")
            return []
    
    def _calculate_quality_metrics(self, validation_report: Dict[str, Any],
                                   quality_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate detailed quality metrics."""
        validation_results = validation_report.get('validation_results', {})
        
        return {
            'equivalence_score': validation_report.get('equivalence_score', 0.0),
            'syntax_score': 1.0 if validation_results.get('syntax_check', {}).get('valid', False) else 0.0,
            'structure_score': validation_results.get('structure_check', {}).get('score', 0.0),
            'logic_score': validation_results.get('logic_check', {}).get('score', 0.0),
            'data_flow_score': validation_results.get('data_flow_check', {}).get('score', 0.0),
            'bre_coverage_score': validation_results.get('bre_coverage', {}).get('coverage_score', 0.0) if 'bre_coverage' in validation_results else None,
            'spec_compliance_score': validation_results.get('spec_compliance', {}).get('score', 0.0) if 'spec_compliance' in validation_results else None,
            'overall_quality': quality_assessment['quality_level']
        }
    
    def _generate_summary(self, quality_assessment: Dict[str, Any],
                         improvement_areas: List[Dict[str, Any]]) -> str:
        """Generate executive summary of the analysis."""
        summary_parts = [
            f"Quality Assessment: {quality_assessment['quality_level'].upper()}",
            f"Equivalence Score: {quality_assessment['equivalence_score']:.2f}",
            f"Validation Status: {'PASSED' if quality_assessment['passed_validation'] else 'FAILED'}",
            "",
            quality_assessment['description']
        ]
        
        if improvement_areas:
            summary_parts.append("")
            summary_parts.append(f"Areas Requiring Attention: {len(improvement_areas)}")
            for area in improvement_areas[:3]:  # Top 3 priorities
                summary_parts.append(f"  - {area['area']} ({area['severity']} severity)")
        else:
            summary_parts.append("")
            summary_parts.append("No significant issues identified.")
        
        return '\n'.join(summary_parts)
