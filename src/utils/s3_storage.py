"""
S3 Storage Handler

Provides S3-backed file I/O with the same interface as FileHandler.
Used as the sole storage backend for the AgentCore pipeline.
"""

import json
import logging
import os
import time
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


class SourceTooLargeError(ValueError):
    """Raised when an S3 object exceeds the configured size limit (safe to return to callers)."""


class S3StorageHandler:
    """S3-backed storage with the same interface as FileHandler."""

    def __init__(self, bucket: str | None = None, max_retries: int = 2, retry_delay: float = 1.0):
        """
        Initialize S3 storage handler.

        Args:
            bucket: S3 bucket name. Falls back to the PIPELINE_S3_BUCKET env var (required if not given).
            max_retries: Max retries for transient S3 errors (5xx).
            retry_delay: Delay in seconds between retries.
        """
        self.bucket = bucket or os.environ.get("PIPELINE_S3_BUCKET")
        if not self.bucket:
            raise ValueError(
                "S3 bucket not configured. Set the PIPELINE_S3_BUCKET environment "
                "variable to the name of your bucket."
            )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        self.s3_client = boto3.client("s3", region_name=region)
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _max_source_bytes() -> int:
        """Maximum object size read from S3 (env PIPELINE_MAX_SOURCE_BYTES, default 1 MB)."""
        try:
            return int(os.environ.get("PIPELINE_MAX_SOURCE_BYTES", "1000000"))
        except ValueError:
            return 1000000

    def _is_transient_error(self, error: ClientError) -> bool:
        """Check if an S3 error is transient (5xx) and worth retrying."""
        http_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        error_code = error.response.get("Error", {}).get("Code", "")
        return http_code >= 500 or error_code in ("InternalError", "ServiceUnavailable", "SlowDown")

    def read_file(self, key: str) -> str:
        """
        Read a file from S3.

        Args:
            key: S3 object key (e.g. 'input/asm/sample.asm')

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If the key does not exist.
            SourceTooLargeError: If the object exceeds PIPELINE_MAX_SOURCE_BYTES.
            IOError: If the read fails after retries.
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
                max_bytes = self._max_source_bytes()
                if response.get("ContentLength", 0) > max_bytes:
                    response["Body"].close()
                    raise SourceTooLargeError(
                        f"S3 object {key} exceeds the {max_bytes}-byte limit."
                    )
                content = response["Body"].read().decode("utf-8")
                self.logger.debug(f"Read s3://{self.bucket}/{key}")
                return content
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "")
                if error_code in ("NoSuchKey", "404") or e.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                    raise FileNotFoundError(f"S3 key not found: {key}") from e
                if self._is_transient_error(e) and attempt < self.max_retries:
                    self.logger.warning(f"Transient S3 error reading {key} (attempt {attempt + 1}), retrying...")
                    time.sleep(self.retry_delay)
                else:
                    raise IOError(f"Failed to read S3 key {key}: {str(e)}") from e

    def write_file(self, key: str, content: str) -> None:
        """
        Write a file to S3.

        Args:
            key: S3 object key.
            content: String content to write.

        Raises:
            IOError: If the write fails after retries.
        """
        for attempt in range(self.max_retries + 1):
            try:
                self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=content.encode("utf-8"))
                self.logger.debug(f"Wrote s3://{self.bucket}/{key}")
                return
            except ClientError as e:
                if self._is_transient_error(e) and attempt < self.max_retries:
                    self.logger.warning(f"Transient S3 error writing {key} (attempt {attempt + 1}), retrying...")
                    time.sleep(self.retry_delay)
                else:
                    raise IOError(f"Failed to write S3 key {key}: {str(e)}") from e

    def read_json(self, key: str) -> Dict[str, Any]:
        """
        Read and parse a JSON file from S3.

        Args:
            key: S3 object key.

        Returns:
            Parsed JSON as dictionary.

        Raises:
            FileNotFoundError: If the key does not exist.
            ValueError: If JSON parsing fails.
        """
        content = self.read_file(key)
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from S3 key {key}: {str(e)}") from e

    def write_json(self, key: str, data: Dict[str, Any], indent: int = 2) -> None:
        """
        Serialize data to JSON and write to S3.

        Args:
            key: S3 object key.
            data: Data to serialize.
            indent: JSON indentation level.

        Raises:
            IOError: If the write fails.
            ValueError: If data cannot be serialized.
        """
        try:
            json_content = json.dumps(data, indent=indent, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Failed to serialize data to JSON for S3 key {key}: {str(e)}") from e
        self.write_file(key, json_content)
