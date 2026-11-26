"""
Amazon Bedrock LLM Client

Provides a client for invoking Claude Sonnet via Amazon Bedrock
with retry logic and error handling.
"""

import json
import logging
import re
import time
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from src.utils.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class SonnetClient:
    """Amazon Bedrock client for Claude Sonnet with retry logic."""

    # Retryable error codes from Bedrock
    RETRYABLE_ERRORS = {
        "ThrottlingException",
        "ServiceUnavailableException",
        "InternalServerException",
        "ModelTimeoutException",
    }

    def __init__(
        self,
        config_path: str = "config/llm_config.yaml",
        max_retries: int = 3,
        retry_wait: float = 30.0,
    ):
        """
        Initialize the Bedrock LLM client.

        Args:
            config_path: Path to LLM configuration YAML file.
            max_retries: Number of retry attempts for transient errors.
            retry_wait: Seconds to wait between retries.
        """
        self.config_manager = ConfigManager(config_path)
        llm_config = self.config_manager.get_llm_config()

        self.model_id: str = llm_config.get(
            "model", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        )
        self.max_tokens: int = int(llm_config.get("max_tokens", 4096))
        self.temperature: float = float(llm_config.get("temperature", 0.0))
        self.region: str = llm_config.get("region", "us-east-1")

        self.max_retries = max_retries
        self.retry_wait = retry_wait

        self.client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            config=boto3.session.Config(
                read_timeout=600,
                connect_timeout=10,
                retries={"max_attempts": 0},
            ),
        )

        logger.info(
            f"SonnetClient initialized: model={self.model_id}, "
            f"region={self.region}, max_tokens={self.max_tokens}, "
            f"temperature={self.temperature}"
        )

    def generate(self, prompt: str) -> str:
        """
        Send a prompt to Claude via Bedrock and return the response text.

        Retries on transient errors (throttling, service unavailable,
        internal server errors) up to ``max_retries`` times with
        ``retry_wait`` seconds between attempts.  Validation errors
        (e.g. input too long) are raised immediately.

        Args:
            prompt: The prompt text to send to the model.

        Returns:
            The model's response text.

        Raises:
            ClientError: If the request fails after all retries or
                         encounters a non-retryable error.
            RuntimeError: If the response cannot be parsed.
        """
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
        )

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    contentType="application/json",
                    accept="application/json",
                    body=body,
                )

                response_body = json.loads(response["body"].read())
                text = response_body.get("content", [{}])[0].get("text", "")

                if not text:
                    raise RuntimeError(
                        "Empty response from Bedrock model"
                    )

                # Surface truncated output: a response cut off at max_tokens
                # produces incomplete JSON that downstream parsing rejects.
                stop_reason = response_body.get("stop_reason")
                if stop_reason == "max_tokens":
                    logger.warning(
                        f"LLM response truncated at max_tokens={self.max_tokens} "
                        f"({len(text)} chars). Output is likely incomplete; "
                        f"consider raising max_tokens in llm_config.yaml."
                    )

                logger.debug(
                    f"LLM response received ({len(text)} chars) "
                    f"on attempt {attempt}"
                )
                return text

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                last_error = e

                if error_code in self.RETRYABLE_ERRORS:
                    if attempt < self.max_retries:
                        logger.warning(
                            f"Retryable error '{error_code}' on attempt "
                            f"{attempt}/{self.max_retries}. "
                            f"Waiting {self.retry_wait}s before retry..."
                        )
                        time.sleep(self.retry_wait)
                        continue
                    else:
                        logger.error(
                            f"LLM API call failed after {self.max_retries} "
                            f"retries: {error_code}"
                        )
                        raise
                else:
                    # Non-retryable (e.g. ValidationException) — fail fast
                    logger.error(
                        f"Non-retryable LLM error: {error_code} — "
                        f"{e.response['Error']['Message']}"
                    )
                    raise

            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(
                        f"Unexpected error on attempt "
                        f"{attempt}/{self.max_retries}: {e}. "
                        f"Waiting {self.retry_wait}s before retry..."
                    )
                    time.sleep(self.retry_wait)
                else:
                    logger.error(
                        f"LLM call failed after {self.max_retries} "
                        f"attempts: {e}"
                    )
                    raise

        # Should not reach here, but just in case
        raise RuntimeError(
            f"LLM call failed after {self.max_retries} attempts: "
            f"{last_error}"
        )

    @staticmethod
    def extract_json_from_response(response: str) -> str:
        """
        Extract a JSON string from an LLM response that may contain
        markdown code fences or surrounding prose.

        Handles patterns like:
            ```json
            { ... }
            ```
        or bare JSON objects/arrays.

        Args:
            response: Raw LLM response text.

        Returns:
            The extracted JSON string.

        Raises:
            ValueError: If no JSON can be found in the response.
        """
        # Try direct parse first (response is already valid JSON)
        stripped = response.strip()
        if stripped.startswith(("{", "[")):
            try:
                json.loads(stripped)
                return stripped
            except json.JSONDecodeError:
                pass

        # Try markdown code block
        match = re.search(
            r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", response
        )
        if match:
            return match.group(1).strip()

        # Try to find a bare JSON object or array
        for pattern in [
            r"(\{[\s\S]*\})",   # JSON object
            r"(\[[\s\S]*\])",   # JSON array
        ]:
            match = re.search(pattern, response)
            if match:
                candidate = match.group(1).strip()
                # Quick validation — try to parse it
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue

        raise ValueError(
            "Could not extract JSON from LLM response. "
            f"Response starts with: {response[:200]}"
        )
