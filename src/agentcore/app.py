"""
AgentCore Entrypoint

Sole entry point for the ASM-to-COBOL pipeline running on Bedrock AgentCore.
Replaces main_bre.py.
"""

import logging
import os
import sys

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

from src.agentcore.tools import (
    _init_services,
    extract_bre,
    generate_spec,
    generate_cobol,
    validate_translation,
    analyze_results,
    process_asm_from_s3,
    process_ezt_from_s3,
    process_source_from_s3,
)


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# SDK/HTTP wire logging can include session tokens, access key IDs, and full
# request bodies (the user's source code). Never let it reach the logs, even if
# the root level is later lowered to DEBUG for troubleshooting.
for _noisy in ("botocore", "boto3", "urllib3", "s3transfer"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

# The agent that routes prompts to tools uses an explicitly pinned model and Region,
# so the permissions it needs are known and requests stay in the intended Region.
agent_model = BedrockModel(
    model_id=os.environ.get("AGENT_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
    region_name=os.environ.get("AWS_REGION", "us-east-1"),
)

# Create app and agent at module level (lightweight, no Bedrock calls yet)
app = BedrockAgentCoreApp()
agent = Agent(
    model=agent_model,
    tools=[
        extract_bre,
        generate_spec,
        generate_cobol,
        validate_translation,
        analyze_results,
        process_asm_from_s3,
        process_ezt_from_s3,
        process_source_from_s3,
    ]
)

# Track whether services have been lazily initialized
_services_initialized = False


@app.entrypoint
def invoke(payload):
    global _services_initialized
    if not _services_initialized:
        config_path = os.environ.get("LLM_CONFIG_PATH", "config/llm_config.yaml")
        try:
            _init_services(config_path)
            _services_initialized = True
        except Exception:
            logger.error("Service initialization failed", exc_info=True)
            return {"error": "Service initialization failed. See the server logs."}

    user_message = payload.get("prompt", "Hello! Provide an ASM file to process.")
    result = agent(user_message)
    return {"result": result.message}


if __name__ == "__main__":
    app.run()
