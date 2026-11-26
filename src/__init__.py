# ASM to COBOL Translation Package

__version__ = '1.0.0'
__author__ = 'ASM-to-COBOL Translation System'
__description__ = 'AI-powered Assembly to COBOL translation tool'

# Main services
from .services.bre_extractor import BREExtractor
from .services.spec_generator import SpecGenerator
from .services.bre_cobol_generator import BRECOBOLGenerator
from .services.validator import Code_Validator
from .services.analyzer import Feedback_Analyzer
from .llm.client import SonnetClient
from .utils.config_manager import ConfigManager, ConfigurationError

__all__ = [
    'BREExtractor', 'SpecGenerator', 'BRECOBOLGenerator', 
    'Code_Validator', 'Feedback_Analyzer',
    'SonnetClient', 'ConfigManager', 'ConfigurationError'
]