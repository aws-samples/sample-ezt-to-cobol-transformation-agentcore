"""
Configuration Manager

Centralized configuration loading with environment variable overrides.
Handles LLM settings. AWS credentials are never read or stored here; they
resolve through the standard boto3 credential chain (SSO, profiles, roles,
environment variables).
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yaml


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class ConfigManager:
    """Manages application configuration with environment variable overrides."""
    
    # Variables that must never be loaded from a plaintext settings file
    _CREDENTIAL_KEYS = frozenset({
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_SESSION_TOKEN',
    })
    
    def __init__(self, config_path: str = 'config/llm_config.yaml',
                 env_file_path: str = 'config/settings.env'):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to LLM configuration YAML file
            env_file_path: Path to a non-secret settings file (region, model overrides).
                Credentials in this file are ignored.
        """
        self.config_path = config_path
        self.env_file_path = env_file_path
        self._config = None
        self._load_configuration()
    
    def _load_env_file(self) -> None:
        """Load environment variables from .env file if it exists."""
        env_file = Path(self.env_file_path)
        
        if not env_file.exists():
            logger.debug(f"Environment file not found: {self.env_file_path}")
            return
        
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=VALUE format
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # Never load credential material from a plaintext file
                        if key.upper() in self._CREDENTIAL_KEYS:
                            logger.warning(
                                f"Ignoring {key} in {self.env_file_path}: do not store "
                                "credentials in project files. Use `aws configure sso`, "
                                "AWS_PROFILE, or an IAM role."
                            )
                            continue
                        
                        # Only set if not already in environment
                        if key and not os.getenv(key):
                            os.environ[key] = value
                            logger.debug(f"Loaded env variable from file: {key}")
        
        except Exception as e:
            logger.warning(f"Failed to load environment file: {str(e)}")
    
    def _load_llm_config(self) -> Dict[str, Any]:
        """
        Load LLM configuration from YAML file.
        
        Returns:
            Dictionary with LLM configuration
            
        Raises:
            ConfigurationError: If config file is invalid
        """
        config_file = Path(self.config_path)
        
        if not config_file.exists():
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            return self._get_default_llm_config()
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                
                if not config or 'llm' not in config:
                    logger.warning("Invalid config format, using defaults")
                    return self._get_default_llm_config()
                
                llm_config = config['llm']
                logger.info(f"Loaded LLM configuration from {self.config_path}")
                return llm_config
        
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in config file: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load config file: {str(e)}")
    
    def _get_default_llm_config(self) -> Dict[str, Any]:
        """Get default LLM configuration."""
        return {
            'provider': 'aws_bedrock',
            'model': 'us.anthropic.claude-sonnet-4-5-20250929-v1:0',
            'max_tokens': 4096,
            'temperature': 0.0,
            'region': 'us-east-1'
        }
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply environment variable overrides to configuration.
        
        Environment variables take precedence over config file values.
        
        Supported overrides:
        - AWS_REGION: Override AWS region
        - LLM_MODEL: Override LLM model name
        - LLM_MAX_TOKENS: Override max tokens
        - LLM_TEMPERATURE: Override temperature
        
        Args:
            config: Base configuration dictionary
            
        Returns:
            Configuration with environment overrides applied
        """
        # AWS Region override
        if os.getenv('AWS_REGION'):
            config['region'] = os.getenv('AWS_REGION')
            logger.info(f"AWS region overridden by environment: {config['region']}")
        
        # LLM Model override
        if os.getenv('LLM_MODEL'):
            config['model'] = os.getenv('LLM_MODEL')
            logger.info(f"LLM model overridden by environment: {config['model']}")
        
        # Max Tokens override
        if os.getenv('LLM_MAX_TOKENS'):
            try:
                config['max_tokens'] = int(os.getenv('LLM_MAX_TOKENS'))
                logger.info(f"Max tokens overridden by environment: {config['max_tokens']}")
            except ValueError:
                logger.warning(f"Invalid LLM_MAX_TOKENS value, using config default")
        
        # Temperature override
        if os.getenv('LLM_TEMPERATURE'):
            try:
                config['temperature'] = float(os.getenv('LLM_TEMPERATURE'))
                logger.info(f"Temperature overridden by environment: {config['temperature']}")
            except ValueError:
                logger.warning(f"Invalid LLM_TEMPERATURE value, using config default")
        
        return config
    
    def _load_configuration(self) -> None:
        """Load complete configuration with environment overrides."""
        # Load environment variables from file first
        self._load_env_file()
        
        # Load LLM configuration
        llm_config = self._load_llm_config()
        
        # Apply environment variable overrides
        llm_config = self._apply_env_overrides(llm_config)
        
        # Store final configuration
        self._config = {
            'llm': llm_config,
            'aws': {
                'region': llm_config.get('region', 'us-east-1')
            }
        }
    
    def get_llm_config(self) -> Dict[str, Any]:
        """
        Get LLM configuration.
        
        Returns:
            Dictionary with LLM settings (model, max_tokens, temperature, region)
        """
        return self._config['llm'].copy()
    
    def get_aws_config(self) -> Dict[str, Any]:
        """
        Get AWS configuration.
        
        Returns:
            Dictionary with AWS settings (region)
        """
        return self._config['aws'].copy()
    
    def get_aws_region(self) -> str:
        """Get AWS region."""
        return self._config['aws']['region']
    
    def get_model_name(self) -> str:
        """Get LLM model name."""
        return self._config['llm']['model']
    
    def get_max_tokens(self) -> int:
        """Get max tokens for LLM generation."""
        return self._config['llm']['max_tokens']
    
    def get_temperature(self) -> float:
        """Get temperature for LLM generation."""
        return self._config['llm']['temperature']
    
    def has_aws_credentials(self) -> bool:
        """
        Check if AWS credentials resolve through the default boto3 chain.
        
        Supports SSO, named profiles, IAM roles, and environment variables.
        No key material is read or stored by this class.
        
        Returns:
            True if credentials can be resolved, False otherwise
        """
        try:
            import boto3
            return boto3.Session().get_credentials() is not None
        except Exception:
            return False
    
    def validate(self) -> None:
        """
        Validate configuration at startup.
        
        Checks:
        - Required configuration fields are present
        - AWS credentials are available
        - LLM model name is valid
        
        Raises:
            ConfigurationError: If configuration is invalid
        """
        errors = []
        
        # Validate LLM configuration
        llm_config = self._config.get('llm', {})
        
        if not llm_config.get('model'):
            errors.append("LLM model name is missing")
        else:
            # Validate model name format
            model = llm_config['model']
            if not self._is_valid_model_name(model):
                errors.append(f"Invalid LLM model name: {model}. Expected format: 'anthropic.claude-*' or 'amazon.titan-*'")
        
        if not llm_config.get('max_tokens'):
            errors.append("LLM max_tokens is missing")
        elif not isinstance(llm_config['max_tokens'], int) or llm_config['max_tokens'] <= 0:
            errors.append(f"Invalid max_tokens value: {llm_config['max_tokens']}. Must be a positive integer")
        
        if 'temperature' not in llm_config:
            errors.append("LLM temperature is missing")
        elif not isinstance(llm_config['temperature'], (int, float)) or not (0.0 <= llm_config['temperature'] <= 1.0):
            errors.append(f"Invalid temperature value: {llm_config['temperature']}. Must be between 0.0 and 1.0")
        
        if not llm_config.get('region'):
            errors.append("AWS region is missing")
        
        # Validate AWS credentials
        if not self.has_aws_credentials():
            errors.append(
                "No AWS credentials found. Configure them with `aws configure sso`, "
                "set AWS_PROFILE, or use an IAM role. Do not store access keys in project files."
            )
        
        # Log and raise errors if any
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
            logger.error(error_msg)
            raise ConfigurationError(error_msg)
        
        logger.info("Configuration validation passed")
    
    def _is_valid_model_name(self, model: str) -> bool:
        """
        Validate LLM model name format.
        
        Args:
            model: Model name to validate
            
        Returns:
            True if model name is valid, False otherwise
        """
        # Valid Amazon Bedrock model prefixes
        valid_prefixes = [
            'anthropic.claude-',
            'amazon.titan-',
            'ai21.j2-',
            'cohere.command-',
            'meta.llama-',
            'mistral.',
            'us.anthropic.claude-',
            'eu.anthropic.claude-',
            'ap.anthropic.claude-',
            'us.amazon.titan-',
            'us.meta.llama-',
            'anthropic.claude-sonnet-',
        ]
        
        return any(model.startswith(prefix) for prefix in valid_prefixes)
    
    def reload(self) -> None:
        """Reload configuration from files."""
        logger.info("Reloading configuration...")
        self._load_configuration()
        logger.info("Configuration reloaded successfully")
