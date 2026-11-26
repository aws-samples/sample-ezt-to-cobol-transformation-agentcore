"""
Unit Tests for Feedback Analyzer Service

Tests the Feedback_Analyzer service with mocked LLM responses
for deterministic testing.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.services.analyzer import Feedback_Analyzer
from src.services.bre_extractor import BusinessRule, DataMapping, BREDocument


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

# Sample COBOL code
SAMPLE_COBOL_CODE = """
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


# Sample validation reports for testing
EXCELLENT_VALIDATION_REPORT = {
    'status': 'passed',
    'equivalence_score': 0.95,
    'validation_results': {
        'syntax_check': {'valid': True, 'errors': [], 'warnings': []},
        'structure_check': {'equivalent': True, 'score': 0.95, 'issues': []},
        'logic_check': {'equivalent': True, 'score': 1.0, 'differences': []},
        'data_flow_check': {'equivalent': True, 'score': 0.9, 'issues': []}
    },
    'findings': ['No issues found']
}

GOOD_VALIDATION_REPORT = {
    'status': 'passed',
    'equivalence_score': 0.75,
    'validation_results': {
        'syntax_check': {'valid': True, 'errors': [], 'warnings': ['Minor warning']},
        'structure_check': {'equivalent': True, 'score': 0.8, 'issues': ['Minor structure issue']},
        'logic_check': {'equivalent': True, 'score': 0.85, 'differences': []},
        'data_flow_check': {'equivalent': True, 'score': 0.8, 'issues': []}
    },
    'findings': ['Structure Issue: Minor structure issue']
}

FAIR_VALIDATION_REPORT = {
    'status': 'failed',
    'equivalence_score': 0.6,
    'validation_results': {
        'syntax_check': {'valid': True, 'errors': [], 'warnings': []},
        'structure_check': {'equivalent': False, 'score': 0.6, 'issues': ['Structure mismatch']},
        'logic_check': {'equivalent': False, 'score': 0.65, 'differences': ['Logic difference']},
        'data_flow_check': {'equivalent': True, 'score': 0.7, 'issues': []}
    },
    'findings': ['Structure Issue: Structure mismatch', 'Logic Difference: Logic difference']
}

POOR_VALIDATION_REPORT = {
    'status': 'failed',
    'equivalence_score': 0.3,
    'validation_results': {
        'syntax_check': {'valid': False, 'errors': ['Syntax error 1', 'Syntax error 2'], 'warnings': []},
        'structure_check': {'equivalent': False, 'score': 0.4, 'issues': ['Major structure issue']},
        'logic_check': {'equivalent': False, 'score': 0.3, 'differences': ['Major logic difference']},
        'data_flow_check': {'equivalent': False, 'score': 0.2, 'issues': ['Data flow broken']}
    },
    'findings': [
        'Syntax Error: Syntax error 1',
        'Syntax Error: Syntax error 2',
        'Structure Issue: Major structure issue',
        'Logic Difference: Major logic difference',
        'Data Flow Issue: Data flow broken'
    ]
}

VALIDATION_WITH_BRE_ISSUES = {
    'status': 'failed',
    'equivalence_score': 0.65,
    'validation_results': {
        'syntax_check': {'valid': True, 'errors': [], 'warnings': []},
        'structure_check': {'equivalent': True, 'score': 0.8, 'issues': []},
        'logic_check': {'equivalent': True, 'score': 0.75, 'differences': []},
        'data_flow_check': {'equivalent': True, 'score': 0.8, 'issues': []},
        'bre_coverage': {
            'coverage_score': 0.5,
            'implemented_rules': ['BR001'],
            'missing_rules': ['BR002', 'BR003'],
            'details': {'BR001': 'Implemented in MAIN-PROCEDURE'}
        }
    },
    'findings': ['Missing Business Rules: BR002, BR003']
}


# Mock LLM responses for BRE analysis
MOCK_BRE_ANALYSIS_GOOD = json.dumps({
    "overall_implementation_quality": 4,
    "rule_analysis": [
        {
            "rule_id": "BR001",
            "implemented": True,
            "location": "MAIN-PROCEDURE",
            "quality": 4,
            "deviations": [],
            "notes": "Well implemented"
        },
        {
            "rule_id": "BR002",
            "implemented": True,
            "location": "MAIN-PROCEDURE",
            "quality": 4,
            "deviations": [],
            "notes": "Correctly implemented"
        }
    ],
    "summary": "All business rules are well implemented"
})

MOCK_BRE_ANALYSIS_POOR = json.dumps({
    "overall_implementation_quality": 2,
    "rule_analysis": [
        {
            "rule_id": "BR001",
            "implemented": True,
            "location": "MAIN-PROCEDURE",
            "quality": 3,
            "deviations": ["Minor deviation"],
            "notes": "Partially implemented"
        },
        {
            "rule_id": "BR002",
            "implemented": False,
            "location": "N/A",
            "quality": 1,
            "deviations": ["Not implemented"],
            "notes": "Missing implementation"
        }
    ],
    "summary": "Some business rules are missing or poorly implemented"
})

# Mock LLM responses for code suggestions
MOCK_CODE_SUGGESTIONS = json.dumps([
    {
        "category": "Structure",
        "suggestion": "Add more comments to explain logic",
        "location": "PROCEDURE DIVISION",
        "priority": "medium",
        "example": "* This section adds two numbers"
    },
    {
        "category": "Naming",
        "suggestion": "Use more descriptive variable names",
        "location": "WORKING-STORAGE",
        "priority": "low",
        "example": "01  FIRST-INPUT-VALUE instead of INPUT1"
    },
    {
        "category": "Error Handling",
        "suggestion": "Add validation for numeric inputs",
        "location": "MAIN-PROCEDURE",
        "priority": "high",
        "example": "IF INPUT1 IS NUMERIC..."
    }
])

MOCK_CODE_SUGGESTIONS_EMPTY = json.dumps([])


class TestFeedbackAnalyzer:
    """Test suite for Feedback_Analyzer class."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        mock_client = Mock()
        mock_client.extract_json_from_response.side_effect = lambda response: response
        return mock_client
    
    @pytest.fixture
    def analyzer(self, mock_llm_client):
        """Create Feedback_Analyzer instance with mocked LLM client."""
        with patch('src.services.analyzer.SonnetClient', return_value=mock_llm_client):
            analyzer = Feedback_Analyzer('config/llm_config.yaml')
            return analyzer
    
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
            )
        ]
        
        return BREDocument(
            program_name="SAMPLE",
            business_rules=business_rules,
            data_mappings=data_mappings,
            summary="Sample program that adds two numbers"
        )

    
    # Test 1: Quality Assessment Categorization - Excellent
    def test_quality_assessment_excellent(self, analyzer, mock_llm_client):
        """Test quality assessment categorization for excellent translation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify quality assessment
        assert report['status'] == 'completed'
        assert report['quality_assessment']['quality_level'] == 'excellent'
        assert report['quality_assessment']['equivalence_score'] == 0.95
        assert report['quality_assessment']['passed_validation'] is True
        assert 'highly accurate' in report['quality_assessment']['description'].lower()
    
    # Test 2: Quality Assessment Categorization - Good
    def test_quality_assessment_good(self, analyzer, mock_llm_client):
        """Test quality assessment categorization for good translation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            GOOD_VALIDATION_REPORT
        )
        
        # Verify quality assessment
        assert report['status'] == 'completed'
        assert report['quality_assessment']['quality_level'] == 'good'
        assert report['quality_assessment']['equivalence_score'] == 0.75
        assert report['quality_assessment']['passed_validation'] is True
        assert 'acceptable' in report['quality_assessment']['description'].lower()
    
    # Test 3: Quality Assessment Categorization - Fair
    def test_quality_assessment_fair(self, analyzer, mock_llm_client):
        """Test quality assessment categorization for fair translation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            FAIR_VALIDATION_REPORT
        )
        
        # Verify quality assessment
        assert report['status'] == 'completed'
        assert report['quality_assessment']['quality_level'] == 'fair'
        assert report['quality_assessment']['equivalence_score'] == 0.6
        assert report['quality_assessment']['passed_validation'] is False
        assert 'moderate issues' in report['quality_assessment']['description'].lower()
    
    # Test 4: Quality Assessment Categorization - Poor
    def test_quality_assessment_poor(self, analyzer, mock_llm_client):
        """Test quality assessment categorization for poor translation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify quality assessment
        assert report['status'] == 'completed'
        assert report['quality_assessment']['quality_level'] == 'poor'
        assert report['quality_assessment']['equivalence_score'] == 0.3
        assert report['quality_assessment']['passed_validation'] is False
        assert 'significant issues' in report['quality_assessment']['description'].lower()

    
    # Test 5: Improvement Area Identification - Syntax Issues
    def test_improvement_areas_syntax(self, analyzer, mock_llm_client):
        """Test identification of syntax improvement areas."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify syntax improvement area identified
        improvement_areas = report['improvement_areas']
        syntax_area = next((area for area in improvement_areas if area['area'] == 'Syntax'), None)
        
        assert syntax_area is not None
        assert syntax_area['severity'] == 'high'
        assert syntax_area['priority'] == 1
        assert len(syntax_area['issues']) > 0
    
    # Test 6: Improvement Area Identification - Structure Issues
    def test_improvement_areas_structure(self, analyzer, mock_llm_client):
        """Test identification of structure improvement areas."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            FAIR_VALIDATION_REPORT
        )
        
        # Verify structure improvement area identified
        improvement_areas = report['improvement_areas']
        structure_area = next((area for area in improvement_areas if area['area'] == 'Structure'), None)
        
        assert structure_area is not None
        assert structure_area['severity'] == 'medium'
        assert 'Structure mismatch' in structure_area['issues']
    
    # Test 7: Improvement Area Identification - Logic Issues
    def test_improvement_areas_logic(self, analyzer, mock_llm_client):
        """Test identification of logic improvement areas."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            FAIR_VALIDATION_REPORT
        )
        
        # Verify logic improvement area identified
        improvement_areas = report['improvement_areas']
        logic_area = next((area for area in improvement_areas if area['area'] == 'Logic'), None)
        
        assert logic_area is not None
        assert logic_area['severity'] == 'high'
        assert logic_area['priority'] == 1
    
    # Test 8: Improvement Area Identification - Data Flow Issues
    def test_improvement_areas_data_flow(self, analyzer, mock_llm_client):
        """Test identification of data flow improvement areas."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify data flow improvement area identified
        improvement_areas = report['improvement_areas']
        data_flow_area = next((area for area in improvement_areas if area['area'] == 'Data Flow'), None)
        
        assert data_flow_area is not None
        assert data_flow_area['severity'] == 'medium'

    
    # Test 9: Improvement Area Identification - BRE Coverage Issues
    def test_improvement_areas_bre_coverage(self, analyzer, mock_llm_client):
        """Test identification of BRE coverage improvement areas."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            VALIDATION_WITH_BRE_ISSUES
        )
        
        # Verify BRE coverage improvement area identified
        improvement_areas = report['improvement_areas']
        bre_area = next((area for area in improvement_areas if area['area'] == 'Business Rules Coverage'), None)
        
        assert bre_area is not None
        assert bre_area['severity'] == 'high'
        assert bre_area['priority'] == 1
        assert 'BR002' in str(bre_area['issues'])
        assert 'BR003' in str(bre_area['issues'])
    
    # Test 10: Improvement Area Identification - No Issues
    def test_improvement_areas_none(self, analyzer, mock_llm_client):
        """Test that no improvement areas are identified for excellent translation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify no improvement areas identified
        improvement_areas = report['improvement_areas']
        assert len(improvement_areas) == 0
    
    # Test 11: Improvement Area Priority Sorting
    def test_improvement_areas_sorted_by_priority(self, analyzer, mock_llm_client):
        """Test that improvement areas are sorted by priority."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify improvement areas are sorted by priority
        improvement_areas = report['improvement_areas']
        if len(improvement_areas) > 1:
            for i in range(len(improvement_areas) - 1):
                assert improvement_areas[i]['priority'] <= improvement_areas[i + 1]['priority']

    
    # Test 12: Recommendations Generation - Syntax
    def test_recommendations_syntax(self, analyzer, mock_llm_client):
        """Test recommendations generation for syntax issues."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify syntax recommendations
        recommendations = report['recommendations']
        syntax_rec = next((rec for rec in recommendations if 'syntax' in rec.lower()), None)
        
        assert syntax_rec is not None
        assert 'fix' in syntax_rec.lower() or 'correct' in syntax_rec.lower()
    
    # Test 13: Recommendations Generation - Structure
    def test_recommendations_structure(self, analyzer, mock_llm_client):
        """Test recommendations generation for structure issues."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            FAIR_VALIDATION_REPORT
        )
        
        # Verify structure recommendations
        recommendations = report['recommendations']
        structure_rec = next((rec for rec in recommendations if 'structure' in rec.lower()), None)
        
        assert structure_rec is not None
        assert 'improve' in structure_rec.lower() or 'align' in structure_rec.lower()
    
    # Test 14: Recommendations Generation - Logic
    def test_recommendations_logic(self, analyzer, mock_llm_client):
        """Test recommendations generation for logic issues."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            FAIR_VALIDATION_REPORT
        )
        
        # Verify logic recommendations
        recommendations = report['recommendations']
        logic_rec = next((rec for rec in recommendations if 'logic' in rec.lower()), None)
        
        assert logic_rec is not None
        assert 'verify' in logic_rec.lower() or 'review' in logic_rec.lower()
    
    # Test 15: Recommendations Generation - Data Flow
    def test_recommendations_data_flow(self, analyzer, mock_llm_client):
        """Test recommendations generation for data flow issues."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify data flow recommendations
        recommendations = report['recommendations']
        data_flow_rec = next((rec for rec in recommendations if 'data flow' in rec.lower()), None)
        
        assert data_flow_rec is not None
        assert 'correct' in data_flow_rec.lower() or 'verify' in data_flow_rec.lower()

    
    # Test 16: Recommendations Generation - BRE Coverage
    def test_recommendations_bre_coverage(self, analyzer, mock_llm_client):
        """Test recommendations generation for BRE coverage issues."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            VALIDATION_WITH_BRE_ISSUES
        )
        
        # Verify BRE coverage recommendations
        recommendations = report['recommendations']
        bre_rec = next((rec for rec in recommendations if 'business rules' in rec.lower()), None)
        
        assert bre_rec is not None
        assert 'implement' in bre_rec.lower() or 'missing' in bre_rec.lower()
    
    # Test 17: Recommendations Generation - Low Score
    def test_recommendations_low_score(self, analyzer, mock_llm_client):
        """Test recommendations for low equivalence score."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify regeneration recommendation for low score
        recommendations = report['recommendations']
        regen_rec = next((rec for rec in recommendations if 'regenerat' in rec.lower()), None)
        
        assert regen_rec is not None
        assert 'low equivalence score' in regen_rec.lower()
    
    # Test 18: Quality Metrics Calculation - All Metrics
    def test_quality_metrics_calculation(self, analyzer, mock_llm_client):
        """Test calculation of all quality metrics."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify all quality metrics are present
        metrics = report['quality_metrics']
        assert 'equivalence_score' in metrics
        assert 'syntax_score' in metrics
        assert 'structure_score' in metrics
        assert 'logic_score' in metrics
        assert 'data_flow_score' in metrics
        assert 'overall_quality' in metrics
        
        # Verify metric values
        assert metrics['equivalence_score'] == 0.95
        assert metrics['syntax_score'] == 1.0
        assert metrics['structure_score'] == 0.95
        assert metrics['logic_score'] == 1.0
        assert metrics['data_flow_score'] == 0.9
        assert metrics['overall_quality'] == 'excellent'

    
    # Test 19: Quality Metrics - With BRE Coverage
    def test_quality_metrics_with_bre_coverage(self, analyzer, mock_llm_client):
        """Test quality metrics calculation with BRE coverage."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            VALIDATION_WITH_BRE_ISSUES
        )
        
        # Verify BRE coverage metric is present
        metrics = report['quality_metrics']
        assert 'bre_coverage_score' in metrics
        assert metrics['bre_coverage_score'] == 0.5
    
    # Test 20: Quality Metrics - Without BRE Coverage
    def test_quality_metrics_without_bre_coverage(self, analyzer, mock_llm_client):
        """Test quality metrics calculation without BRE coverage."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify BRE coverage metric is None when not available
        metrics = report['quality_metrics']
        assert metrics['bre_coverage_score'] is None
    
    # Test 21: BRE Implementation Analysis - Good Implementation
    def test_bre_analysis_good_implementation(self, analyzer, mock_llm_client, sample_bre_doc):
        """Test BRE implementation analysis with good implementation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_BRE_ANALYSIS_GOOD,
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis with BRE document
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT,
            bre_doc=sample_bre_doc
        )
        
        # Verify BRE analysis is present
        assert report['bre_analysis'] is not None
        assert report['bre_analysis']['overall_implementation_quality'] == 4
        assert len(report['bre_analysis']['rule_analysis']) == 2
        assert 'well implemented' in report['bre_analysis']['summary'].lower()
    
    # Test 22: BRE Implementation Analysis - Poor Implementation
    def test_bre_analysis_poor_implementation(self, analyzer, mock_llm_client, sample_bre_doc):
        """Test BRE implementation analysis with poor implementation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_BRE_ANALYSIS_POOR,
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis with BRE document
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            FAIR_VALIDATION_REPORT,
            bre_doc=sample_bre_doc
        )
        
        # Verify BRE analysis identifies issues
        assert report['bre_analysis'] is not None
        assert report['bre_analysis']['overall_implementation_quality'] == 2
        
        # Check for missing implementation
        rule_analysis = report['bre_analysis']['rule_analysis']
        br002 = next((rule for rule in rule_analysis if rule['rule_id'] == 'BR002'), None)
        assert br002 is not None
        assert br002['implemented'] is False

    
    # Test 23: BRE Implementation Analysis - Without BRE Document
    def test_bre_analysis_without_bre_doc(self, analyzer, mock_llm_client):
        """Test analysis without BRE document (no BRE analysis performed)."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis without BRE document
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify BRE analysis is None
        assert report['bre_analysis'] is None
    
    # Test 24: Code Suggestions Generation
    def test_code_suggestions_generation(self, analyzer, mock_llm_client):
        """Test code suggestions generation."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            GOOD_VALIDATION_REPORT
        )
        
        # Verify code suggestions are present
        assert 'code_suggestions' in report
        assert len(report['code_suggestions']) == 3
        
        # Verify suggestion structure
        for suggestion in report['code_suggestions']:
            assert 'category' in suggestion
            assert 'suggestion' in suggestion
            assert 'location' in suggestion
            assert 'priority' in suggestion
    
    # Test 25: Code Suggestions - Categories
    def test_code_suggestions_categories(self, analyzer, mock_llm_client):
        """Test code suggestions include various categories."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            GOOD_VALIDATION_REPORT
        )
        
        # Verify different categories are present
        suggestions = report['code_suggestions']
        categories = [s['category'] for s in suggestions]
        
        assert 'Structure' in categories
        assert 'Naming' in categories
        assert 'Error Handling' in categories
    
    # Test 26: Code Suggestions - Empty Response
    def test_code_suggestions_empty(self, analyzer, mock_llm_client):
        """Test code suggestions with empty LLM response."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS_EMPTY
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify empty suggestions list
        assert report['code_suggestions'] == []

    
    # Test 27: Summary Generation - Excellent Quality
    def test_summary_generation_excellent(self, analyzer, mock_llm_client):
        """Test summary generation for excellent quality."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify summary content
        summary = report['summary']
        assert 'EXCELLENT' in summary
        assert '0.95' in summary
        assert 'PASSED' in summary
        assert 'No significant issues' in summary
    
    # Test 28: Summary Generation - With Issues
    def test_summary_generation_with_issues(self, analyzer, mock_llm_client):
        """Test summary generation with improvement areas."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            POOR_VALIDATION_REPORT
        )
        
        # Verify summary includes issues
        summary = report['summary']
        assert 'POOR' in summary
        assert 'FAILED' in summary
        assert 'Areas Requiring Attention' in summary
    
    # Test 29: Error Handling - LLM Exception
    def test_error_handling_llm_exception(self, analyzer, mock_llm_client):
        """Test error handling when LLM raises exception."""
        # Setup mock to raise exception
        mock_llm_client.generate.side_effect = Exception("LLM API error")
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify error is handled
        assert report['status'] == 'error'
        assert 'error' in report
        # Raw exception text must not reach the caller (security review MF-8)
        assert 'LLM API error' not in report['error']
        assert 'Exception' in report['error']
    
    # Test 30: Error Handling - Invalid JSON in BRE Analysis
    def test_error_handling_invalid_bre_json(self, analyzer, mock_llm_client, sample_bre_doc):
        """Test error handling when BRE analysis returns invalid JSON."""
        # Setup mock to return invalid JSON
        mock_llm_client.generate.side_effect = [
            "This is not valid JSON",
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis with BRE document
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT,
            bre_doc=sample_bre_doc
        )
        
        # Verify fallback behavior for BRE analysis
        assert report['status'] == 'completed'
        assert report['bre_analysis'] is not None
        assert report['bre_analysis']['overall_implementation_quality'] == 0
        assert report['bre_analysis']['rule_analysis'] == []
        assert 'Failed to analyze' in report['bre_analysis']['summary']

    
    # Test 31: Error Handling - Invalid JSON in Code Suggestions
    def test_error_handling_invalid_suggestions_json(self, analyzer, mock_llm_client):
        """Test error handling when code suggestions return invalid JSON."""
        # Setup mock to return invalid JSON
        mock_llm_client.generate.side_effect = [
            "Not valid JSON at all"
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify fallback behavior for code suggestions
        assert report['status'] == 'completed'
        assert report['code_suggestions'] == []
    
    # Test 32: Error Handling - Non-Dict BRE Analysis Response
    def test_error_handling_non_dict_bre_response(self, analyzer, mock_llm_client, sample_bre_doc):
        """Test error handling when BRE analysis returns non-dict JSON."""
        # Setup mock to return list instead of dict
        mock_llm_client.generate.side_effect = [
            json.dumps(["not", "a", "dict"]),
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute analysis with BRE document
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT,
            bre_doc=sample_bre_doc
        )
        
        # Verify fallback behavior
        assert report['status'] == 'completed'
        assert report['bre_analysis']['overall_implementation_quality'] == 0
        assert report['bre_analysis']['rule_analysis'] == []
    
    # Test 33: Error Handling - Non-List Code Suggestions Response
    def test_error_handling_non_list_suggestions_response(self, analyzer, mock_llm_client):
        """Test error handling when code suggestions return non-list JSON."""
        # Setup mock to return dict instead of list
        mock_llm_client.generate.side_effect = [
            json.dumps({"not": "a list"})
        ]
        
        # Execute analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT
        )
        
        # Verify fallback behavior
        assert report['status'] == 'completed'
        assert report['code_suggestions'] == []
    
    # Test 34: Complete Analysis Flow
    def test_complete_analysis_flow(self, analyzer, mock_llm_client, sample_bre_doc):
        """Test complete analysis flow with all components."""
        # Setup mock responses
        mock_llm_client.generate.side_effect = [
            MOCK_BRE_ANALYSIS_GOOD,
            MOCK_CODE_SUGGESTIONS
        ]
        
        # Execute complete analysis
        report = analyzer.analyze(
            SAMPLE_ASM_CODE,
            SAMPLE_COBOL_CODE,
            EXCELLENT_VALIDATION_REPORT,
            bre_doc=sample_bre_doc
        )
        
        # Verify all components are present
        assert report['status'] == 'completed'
        assert 'quality_assessment' in report
        assert 'quality_metrics' in report
        assert 'improvement_areas' in report
        assert 'recommendations' in report
        assert 'code_suggestions' in report
        assert 'bre_analysis' in report
        assert 'summary' in report
        
        # Verify LLM was called twice (BRE analysis + code suggestions)
        assert mock_llm_client.generate.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
