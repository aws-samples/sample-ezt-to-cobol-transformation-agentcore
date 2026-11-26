"""
File Handler Utility

Provides robust file I/O operations with error handling and retry logic.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict


logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file I/O operations with error handling and retry logic."""
    
    def __init__(self, max_retries: int = 2, retry_delay: float = 1.0):
        """
        Initialize file handler.
        
        Args:
            max_retries: Maximum number of retry attempts for transient failures
            retry_delay: Delay in seconds between retries
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logging.getLogger(__name__)
    
    def read_file(self, file_path: str) -> str:
        """
        Read text file with error handling and retry logic.
        
        Args:
            file_path: Path to file to read
            
        Returns:
            File contents as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read after retries
        """
        file_path = Path(file_path)
        
        # Validate file exists before attempting to read
        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Attempt to read with retry logic
        for attempt in range(self.max_retries + 1):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.logger.debug(f"Successfully read file: {file_path}")
                return content
            except IOError as e:
                if attempt < self.max_retries:
                    self.logger.warning(
                        f"Failed to read {file_path} (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}. "
                        f"Retrying in {self.retry_delay}s..."
                    )
                    time.sleep(self.retry_delay)
                else:
                    error_msg = f"Failed to read {file_path} after {self.max_retries + 1} attempts: {str(e)}"
                    self.logger.error(error_msg)
                    raise IOError(error_msg) from e
    
    def write_file(self, file_path: str, content: str) -> None:
        """
        Write text file with error handling and retry logic.
        
        Args:
            file_path: Path to file to write
            content: Content to write
            
        Raises:
            IOError: If file cannot be written after retries
        """
        file_path = Path(file_path)
        
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Attempt to write with retry logic
        for attempt in range(self.max_retries + 1):
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.logger.debug(f"Successfully wrote file: {file_path}")
                return
            except IOError as e:
                if attempt < self.max_retries:
                    self.logger.warning(
                        f"Failed to write {file_path} (attempt {attempt + 1}/{self.max_retries + 1}): {str(e)}. "
                        f"Retrying in {self.retry_delay}s..."
                    )
                    time.sleep(self.retry_delay)
                else:
                    error_msg = f"Failed to write {file_path} after {self.max_retries + 1} attempts: {str(e)}"
                    self.logger.error(error_msg)
                    raise IOError(error_msg) from e
    
    def read_json(self, file_path: str) -> Dict[str, Any]:
        """
        Read JSON file with robust parsing and error handling.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If JSON parsing fails
        """
        file_path = Path(file_path)
        
        # Validate file exists
        if not file_path.exists():
            error_msg = f"JSON file not found: {file_path}"
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        # Read file content
        content = self.read_file(str(file_path))
        
        # Parse JSON with error handling
        try:
            data = json.loads(content)
            self.logger.debug(f"Successfully parsed JSON from: {file_path}")
            return data
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON from {file_path}: {str(e)}"
            self.logger.error(error_msg)
            # Log warning and return empty dict as fallback
            self.logger.warning(f"Returning empty dictionary as fallback for {file_path}")
            raise ValueError(error_msg) from e
    
    def write_json(self, file_path: str, data: Dict[str, Any], indent: int = 2) -> None:
        """
        Write JSON file with error handling.
        
        Args:
            file_path: Path to JSON file
            data: Data to write as JSON
            indent: JSON indentation level
            
        Raises:
            IOError: If file cannot be written
            ValueError: If data cannot be serialized to JSON
        """
        file_path = Path(file_path)
        
        # Serialize to JSON with error handling
        try:
            json_content = json.dumps(data, indent=indent, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            error_msg = f"Failed to serialize data to JSON for {file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e
        
        # Write to file
        self.write_file(str(file_path), json_content)
