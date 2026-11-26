"""Tests for S3 input and output boundaries in AgentCore tools."""

import hashlib

import boto3
import pytest
from moto import mock_aws

from src.agentcore.tools import (
    InputValidationError,
    _output_prefix,
    _validate_source_key,
)
from src.utils.s3_storage import S3StorageHandler, SourceTooLargeError


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("input/ezt/Payroll.ezt", ("Payroll", "Easytrieve")),
        ("input/asm/PGM-1.asm", ("PGM-1", "ASM")),
        ("input/ezt/REPORT.EZT", ("REPORT", "Easytrieve")),
    ],
)
def test_validate_source_key_accepts_supported_input_keys(key, expected):
    assert _validate_source_key(key) == expected


@pytest.mark.parametrize(
    "key",
    [
        "outputs/Payroll/phase3_cobol.cbl",
        "input/ezt/Payroll.txt",
        "input//ezt/Payroll.ezt",
        "input/ezt/../Payroll.ezt",
        "input/ezt/pay roll.ezt",
    ],
)
def test_validate_source_key_rejects_unsafe_or_unsupported_keys(key):
    with pytest.raises(InputValidationError):
        _validate_source_key(key)


def test_validate_source_key_rejects_an_unexpected_source_type():
    with pytest.raises(InputValidationError, match="Expected a ASM file"):
        _validate_source_key("input/ezt/Payroll.ezt", expected_type="ASM")


def test_output_prefix_uses_the_source_key_hash_for_duplicate_program_names():
    first_key = "input/team-a/Payroll.ezt"
    second_key = "input/team-b/Payroll.ezt"
    first_prefix = _output_prefix("Payroll", "Easytrieve", first_key)
    second_prefix = _output_prefix("Payroll", "Easytrieve", second_key)

    assert first_prefix == (
        f"outputs/Payroll-easytrieve-{hashlib.sha256(first_key.encode()).hexdigest()[:12]}"
    )
    assert second_prefix == (
        f"outputs/Payroll-easytrieve-{hashlib.sha256(second_key.encode()).hexdigest()[:12]}"
    )
    assert first_prefix != second_prefix


@pytest.fixture
def s3_bucket(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")

    with mock_aws():
        bucket = "pipeline-boundary-tests"
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=bucket)
        yield bucket, client


def test_read_file_allows_content_at_the_configured_limit(s3_bucket, monkeypatch):
    bucket, client = s3_bucket
    monkeypatch.setenv("PIPELINE_MAX_SOURCE_BYTES", "4")
    client.put_object(Bucket=bucket, Key="input/ezt/Payroll.ezt", Body=b"ABCD")

    assert S3StorageHandler(bucket=bucket).read_file("input/ezt/Payroll.ezt") == "ABCD"


def test_read_file_rejects_content_above_the_configured_limit(s3_bucket, monkeypatch):
    bucket, client = s3_bucket
    monkeypatch.setenv("PIPELINE_MAX_SOURCE_BYTES", "4")
    client.put_object(Bucket=bucket, Key="input/ezt/Payroll.ezt", Body=b"ABCDE")

    with pytest.raises(SourceTooLargeError, match="exceeds the 4-byte limit"):
        S3StorageHandler(bucket=bucket).read_file("input/ezt/Payroll.ezt")
