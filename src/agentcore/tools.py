"""
Strands Agents Tool Wrappers

Thin @tool wrappers around existing pipeline services for AgentCore.
Each tool accepts/returns JSON strings at the boundary.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, asdict
from pathlib import PurePosixPath
from typing import Dict, Any, Optional, Tuple

from strands import tool

from src.agentcore.observability import PipelineObserver
from src.services.bre_extractor import BREExtractor, BREDocument, BusinessRule, DataMapping
from src.services.spec_generator import SpecGenerator, FunctionalSpec
from src.services.bre_cobol_generator import BRECOBOLGenerator
from src.services.validator import Code_Validator
from src.services.analyzer import Feedback_Analyzer
from src.utils.s3_storage import S3StorageHandler, SourceTooLargeError


logger = logging.getLogger(__name__)

# Module-level service instances (initialized once via _init_services)
_services: Dict[str, Any] = {}
_observer: PipelineObserver | None = None


@dataclass
class ToolErrorResponse:
    """Structured error response returned by tools on failure."""
    error: bool = True
    error_type: str = ""
    message: str = ""
    phase: str = ""


ALLOWED_PREFIX = "input/"
ALLOWED_EXTENSIONS = {".ezt": "Easytrieve", ".asm": "ASM"}
_PROGRAM_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class InputValidationError(ValueError):
    """Raised for caller-supplied input that fails validation (safe to return)."""


def _validate_source_key(s3_key: str, expected_type: Optional[str] = None) -> Tuple[str, str]:
    """Validate an S3 source key and return (program_name, source_type).

    Only .ezt and .asm files under the input/ prefix are accepted, so the agent
    cannot be prompted into reading other objects in the bucket (for example
    previously generated outputs).
    """
    if not isinstance(s3_key, str) or not s3_key.startswith(ALLOWED_PREFIX):
        raise InputValidationError("Source key must be under the input/ prefix.")
    path = PurePosixPath(s3_key)
    if ".." in path.parts or "//" in s3_key:
        raise InputValidationError("Source key must not contain '..' or empty segments.")
    source_type = ALLOWED_EXTENSIONS.get(path.suffix.lower())
    if source_type is None:
        raise InputValidationError("Only .ezt and .asm source files are supported.")
    if expected_type and source_type != expected_type:
        raise InputValidationError(f"Expected a {expected_type} file, got {path.suffix}.")
    if not _PROGRAM_NAME_RE.match(path.stem):
        raise InputValidationError("File name must be 1-64 letters, digits, '_' or '-'.")
    return path.stem, source_type


def _output_prefix(program_name: str, source_type: str, s3_key: str) -> str:
    """Return a deterministic, collision-resistant prefix for pipeline artifacts."""
    source_key_hash = hashlib.sha256(s3_key.encode("utf-8")).hexdigest()[:12]
    return f"outputs/{program_name}-{source_type.lower()}-{source_key_hash}"


def _init_services(config_path: str = "config/llm_config.yaml") -> None:
    """Initialize all service instances once at startup."""
    global _services, _observer
    logger.info("Initializing pipeline services...")
    _services["bre_extractor"] = BREExtractor(config_path)
    _services["spec_generator"] = SpecGenerator(config_path)
    _services["cobol_generator"] = BRECOBOLGenerator(config_path)
    _services["validator"] = Code_Validator(config_path)
    _services["analyzer"] = Feedback_Analyzer(config_path)
    _observer = PipelineObserver()
    logger.info("All pipeline services initialized")


def _error_response(phase: str, exc: Exception) -> str:
    """Build a JSON error response string.

    The full error is logged server-side. Only messages written by this project
    are returned to the caller; SDK error text can contain account IDs, role
    names, and bucket names.
    """
    logger.error("Tool phase %s failed", phase, exc_info=True)
    if isinstance(exc, (InputValidationError, FileNotFoundError, SourceTooLargeError)):
        message = str(exc)
    else:
        message = "Internal error while running this phase. See the server logs."
    resp = ToolErrorResponse(
        error=True,
        error_type=type(exc).__name__,
        message=message,
        phase=phase,
    )
    return json.dumps(asdict(resp))


def _reconstruct_bre(data: dict) -> BREDocument:
    """Reconstruct a BREDocument from a dict."""
    return BREDocument(
        program_name=data["program_name"],
        business_rules=[BusinessRule(**r) for r in data["business_rules"]],
        data_mappings=[DataMapping(**m) for m in data["data_mappings"]],
        summary=data["summary"],
    )


def _reconstruct_spec(data: dict) -> FunctionalSpec:
    """Reconstruct a FunctionalSpec from a dict."""
    return FunctionalSpec(**data)


@tool
def extract_bre(asm_code: str, program_name: str) -> str:
    """Extract business rules from source code. Returns BRE document as JSON string."""
    try:
        with _observer.phase_context("extract_bre", program_name):
            bre_doc = _services["bre_extractor"].extract_bre(asm_code, program_name)
            return json.dumps({
                "program_name": bre_doc.program_name,
                "business_rules": [asdict(r) for r in bre_doc.business_rules],
                "data_mappings": [asdict(m) for m in bre_doc.data_mappings],
                "summary": bre_doc.summary,
            })
    except Exception as e:
        return _error_response("extract_bre", e)


@tool
def generate_spec(bre_json: str) -> str:
    """Generate functional specification from BRE document. Returns spec as JSON string."""
    try:
        bre_data = json.loads(bre_json)
        bre_doc = _reconstruct_bre(bre_data)
        with _observer.phase_context("generate_spec", bre_doc.program_name):
            spec = _services["spec_generator"].generate_spec(bre_doc)
            return json.dumps(asdict(spec))
    except Exception as e:
        return _error_response("generate_spec", e)


@tool
def generate_cobol(asm_code: str, bre_json: str, spec_json: str) -> str:
    """Generate COBOL code from source, BRE, and spec. Returns COBOL source code."""
    try:
        bre_doc = _reconstruct_bre(json.loads(bre_json))
        spec = _reconstruct_spec(json.loads(spec_json))
        with _observer.phase_context("generate_cobol", spec.program_name):
            cobol_code = _services["cobol_generator"].generate_cobol(asm_code, bre_doc, spec)
            return cobol_code
    except Exception as e:
        return _error_response("generate_cobol", e)


@tool
def validate_translation(asm_code: str, cobol_code: str, bre_json: str, spec_json: str) -> str:
    """Validate translation accuracy. Returns validation report as JSON string."""
    try:
        bre_doc = _reconstruct_bre(json.loads(bre_json))
        spec = _reconstruct_spec(json.loads(spec_json))
        with _observer.phase_context("validate_translation", spec.program_name):
            report = _services["validator"].validate(asm_code, cobol_code, bre_doc, spec)
            return json.dumps(report)
    except Exception as e:
        return _error_response("validate_translation", e)


@tool
def analyze_results(asm_code: str, cobol_code: str, validation_json: str, bre_json: str) -> str:
    """Analyze results and generate feedback. Returns analysis report as JSON string."""
    try:
        bre_doc = _reconstruct_bre(json.loads(bre_json))
        validation_report = json.loads(validation_json)
        with _observer.phase_context("analyze_results", bre_doc.program_name):
            analysis = _services["analyzer"].analyze(asm_code, cobol_code, validation_report, bre_doc)
            return json.dumps(analysis)
    except Exception as e:
        return _error_response("analyze_results", e)


@tool
def process_asm_from_s3(s3_key: str) -> str:
    """Read an ASM file from S3 and run the full 5-phase pipeline.

    Args:
        s3_key: S3 object key for the ASM file, e.g. 'input/asm/sample.asm'

    Returns:
        JSON string with pipeline results including BRE, spec, COBOL, validation, and analysis.
    """
    return _run_pipeline_from_s3(s3_key, "ASM")


@tool
def process_ezt_from_s3(s3_key: str) -> str:
    """Read an Easytrieve (.ezt) file from S3 and run the full 5-phase pipeline.

    Easytrieve source code is processed through the same BRE extraction pipeline.
    The LLM understands Easytrieve syntax and extracts business rules from it.

    Args:
        s3_key: S3 object key for the EZT file, e.g. 'input/ezt/pgm4.ezt'

    Returns:
        JSON string with pipeline results including BRE, spec, COBOL, validation, and analysis.
    """
    return _run_pipeline_from_s3(s3_key, "Easytrieve")


@tool
def process_source_from_s3(s3_key: str) -> str:
    """Read a source file (ASM or Easytrieve) from S3 and run the full 5-phase pipeline.

    Automatically detects the source language from the file extension:
    - .asm → Assembly
    - .ezt → Easytrieve

    Args:
        s3_key: S3 object key, e.g. 'input/asm/sample.asm' or 'input/ezt/pgm4.ezt'

    Returns:
        JSON string with pipeline results including BRE, spec, COBOL, validation, and analysis.
    """
    return _run_pipeline_from_s3(s3_key, None)


def _run_pipeline_from_s3(s3_key: str, expected_type: Optional[str]) -> str:
    """Shared pipeline logic for processing any source file from S3.

    Args:
        s3_key: S3 object key for the source file.
        expected_type: 'ASM' or 'Easytrieve' to require that language, or None to
            detect it from the file extension.

    Returns:
        JSON string with pipeline results.
    """
    phase = f"process_{(expected_type or 'source').lower()}_from_s3"
    try:
        program_name, source_type = _validate_source_key(s3_key, expected_type)
        output_prefix = _output_prefix(program_name, source_type, s3_key)
        storage = S3StorageHandler()

        # Read source from S3
        source_code = storage.read_file(s3_key)
        logger.info(f"Processing {source_type} file: {s3_key} (program: {program_name})")

        # Phase 1: Extract BRE
        with _observer.phase_context("extract_bre", program_name):
            bre_doc = _services["bre_extractor"].extract_bre(source_code, program_name)
        bre_dict = {
            "program_name": bre_doc.program_name,
            "business_rules": [asdict(r) for r in bre_doc.business_rules],
            "data_mappings": [asdict(m) for m in bre_doc.data_mappings],
            "summary": bre_doc.summary,
        }
        storage.write_json(f"{output_prefix}/phase1_bre.json", bre_dict)

        # Phase 2: Generate spec
        with _observer.phase_context("generate_spec", program_name):
            spec = _services["spec_generator"].generate_spec(bre_doc)
        spec_dict = asdict(spec)
        storage.write_json(f"{output_prefix}/phase2_spec.json", spec_dict)

        # Phase 3: Generate COBOL
        with _observer.phase_context("generate_cobol", program_name):
            cobol_code = _services["cobol_generator"].generate_cobol(source_code, bre_doc, spec)
        storage.write_file(f"{output_prefix}/phase3_cobol.cbl", cobol_code)

        # Phase 4: Validate
        with _observer.phase_context("validate_translation", program_name):
            validation = _services["validator"].validate(source_code, cobol_code, bre_doc, spec)
        storage.write_json(f"{output_prefix}/phase4_validation.json", validation)

        # Phase 5: Analyze
        with _observer.phase_context("analyze_results", program_name):
            analysis = _services["analyzer"].analyze(source_code, cobol_code, validation, bre_doc)
        storage.write_json(f"{output_prefix}/phase5_analysis.json", analysis)

        return json.dumps({
            "status": "success",
            "program_name": program_name,
            "source_type": source_type,
            "artifacts": {
                "bre": f"{output_prefix}/phase1_bre.json",
                "spec": f"{output_prefix}/phase2_spec.json",
                "cobol": f"{output_prefix}/phase3_cobol.cbl",
                "validation": f"{output_prefix}/phase4_validation.json",
                "analysis": f"{output_prefix}/phase5_analysis.json",
            },
            "equivalence_score": validation.get("equivalence_score", 0.0),
            "quality_level": analysis.get("quality_assessment", {}).get("quality_level", "unknown"),
        })
    except Exception as e:
        return _error_response(phase, e)
