"""
CloudWatch Observability for Pipeline Phases

Provides structured logging and custom metrics for monitoring
the ASM-to-COBOL pipeline running on AgentCore.
"""

import json
import logging
import os
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import boto3


logger = logging.getLogger(__name__)


@dataclass
class PhaseLogEntry:
    """Structured log entry for pipeline phase events."""
    phase: str
    program_name: str
    timestamp: str  # ISO 8601
    event: str  # "start", "end", "error"
    duration_ms: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None


class PipelineObserver:
    """Structured logging and CloudWatch metrics for pipeline phases."""

    LOG_GROUP = "/bedrock-agentcore/asm-to-cobol"
    LOG_STREAM_PREFIX = "pipeline"
    METRIC_NAMESPACE = "ASMtoCOBOL/Pipeline"

    def __init__(self):
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        self.cw_client = boto3.client("cloudwatch", region_name=region)
        self.logs_client = boto3.client("logs", region_name=region)
        self.logger = logging.getLogger(__name__)
        self._log_stream = f"{self.LOG_STREAM_PREFIX}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        self._ensure_log_group()

    def _ensure_log_group(self):
        """Create log group and stream if they don't exist."""
        try:
            self.logs_client.create_log_group(logGroupName=self.LOG_GROUP)
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as e:
            self.logger.warning(f"Could not create log group (permissions?): {e}")
        try:
            self.logs_client.create_log_stream(
                logGroupName=self.LOG_GROUP, logStreamName=self._log_stream
            )
        except self.logs_client.exceptions.ResourceAlreadyExistsException:
            pass
        except Exception as e:
            self.logger.warning(f"Could not create log stream (permissions?): {e}")

    def _put_log_event(self, entry: PhaseLogEntry):
        """Send a structured log entry to CloudWatch Logs."""
        try:
            self.logs_client.put_log_events(
                logGroupName=self.LOG_GROUP,
                logStreamName=self._log_stream,
                logEvents=[
                    {
                        "timestamp": int(time.time() * 1000),
                        "message": json.dumps(asdict(entry), default=str),
                    }
                ],
            )
        except Exception as e:
            self.logger.warning(f"Failed to send log to CloudWatch: {e}")

    def log_phase_start(self, phase: str, program_name: str) -> None:
        entry = PhaseLogEntry(
            phase=phase,
            program_name=program_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event="start",
        )
        self._put_log_event(entry)
        self.logger.info(f"Phase {phase} started for {program_name}")

    def log_phase_end(self, phase: str, program_name: str, duration_ms: float) -> None:
        entry = PhaseLogEntry(
            phase=phase,
            program_name=program_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event="end",
            duration_ms=duration_ms,
        )
        self._put_log_event(entry)
        self.logger.info(f"Phase {phase} completed for {program_name} in {duration_ms:.1f}ms")

    def log_phase_error(self, phase: str, program_name: str, error: Exception) -> None:
        entry = PhaseLogEntry(
            phase=phase,
            program_name=program_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event="error",
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
        )
        self._put_log_event(entry)
        self.logger.error(f"Phase {phase} failed for {program_name}: {error}")

    def record_latency(self, phase: str, program_name: str, duration_ms: float) -> None:
        try:
            self.cw_client.put_metric_data(
                Namespace=self.METRIC_NAMESPACE,
                MetricData=[
                    {
                        "MetricName": "PipelinePhaseLatency",
                        "Dimensions": [
                            {"Name": "Phase", "Value": phase},
                            {"Name": "ProgramName", "Value": program_name},
                        ],
                        "Value": duration_ms,
                        "Unit": "Milliseconds",
                    }
                ],
            )
        except Exception as e:
            self.logger.warning(f"Failed to record latency metric: {e}")

    def record_error(self, phase: str, error_type: str) -> None:
        try:
            self.cw_client.put_metric_data(
                Namespace=self.METRIC_NAMESPACE,
                MetricData=[
                    {
                        "MetricName": "PipelinePhaseError",
                        "Dimensions": [
                            {"Name": "Phase", "Value": phase},
                            {"Name": "ErrorType", "Value": error_type},
                        ],
                        "Value": 1,
                        "Unit": "Count",
                    }
                ],
            )
        except Exception as e:
            self.logger.warning(f"Failed to record error metric: {e}")

    @contextmanager
    def phase_context(self, phase: str, program_name: str):
        """Context manager that logs start/end/error and records metrics."""
        self.log_phase_start(phase, program_name)
        start = time.time()
        try:
            yield
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            self.log_phase_error(phase, program_name, e)
            self.record_error(phase, type(e).__name__)
            raise
        else:
            duration_ms = (time.time() - start) * 1000
            self.log_phase_end(phase, program_name, duration_ms)
            self.record_latency(phase, program_name, duration_ms)
