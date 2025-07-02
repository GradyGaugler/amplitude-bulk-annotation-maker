#!/usr/bin/env python3
"""
Configuration manager for Amplitude Bulk Annotation Maker.

This module handles loading and saving configuration, with special emphasis
on security best practices (environment variables for sensitive data).
"""
import os
import json
import logging
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass

from constants import (
    ENV_API_KEY, ENV_SECRET_KEY, ENV_PROJECT_ID, ENV_REGION,
    CONFIG_FILE, DEFAULT_REGION, VALID_REGIONS
)

logger = logging.getLogger(__name__)


@dataclass
class AmplitudeConfig:
    """Configuration data for Amplitude API."""
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    project_id: Optional[int] = None
    region: str = DEFAULT_REGION
    from_environment: bool = False


class ConfigurationError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigManager:
    """
    Manages application configuration.
    
    Prioritizes environment variables for security-sensitive data,
    falls back to config file for non-sensitive preferences.
    """
    
    def __init__(self) -> None:
        """Initialize the configuration manager."""
        self._config: Optional[AmplitudeConfig] = None
    
    def load_config(self) -> AmplitudeConfig:
        """
        Load configuration from environment and file.
        
        Returns:
            AmplitudeConfig object with loaded configuration
            
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Start with environment variables
        config = self._load_from_environment()
        
        # If no environment config, create empty config
        if not config:
            config = AmplitudeConfig()
        
        # Load preferences from file (non-sensitive data only)
        self._load_preferences(config)
        
        self._config = config
        return config
    
    def _load_from_environment(self) -> Optional[AmplitudeConfig]:
        """
        Load configuration from environment variables.
        
        Returns:
            AmplitudeConfig if environment variables found, None otherwise
        """
        api_key = os.getenv(ENV_API_KEY)
        secret_key = os.getenv(ENV_SECRET_KEY)
        
        if not (api_key and secret_key):
            return None
        
        project_id_str = os.getenv(ENV_PROJECT_ID)
        project_id = None
        if project_id_str and project_id_str.isdigit():
            project_id = int(project_id_str)
        
        region = os.getenv(ENV_REGION, DEFAULT_REGION)
        if region not in VALID_REGIONS:
            logger.warning(f"Invalid region in environment: {region}, using default: {DEFAULT_REGION}")
            region = DEFAULT_REGION
        
        logger.info("Loaded configuration from environment variables")
        
        return AmplitudeConfig(
            api_key=api_key,
            secret_key=secret_key,
            project_id=project_id,
            region=region,
            from_environment=True
        )
    
    def _load_preferences(self, config: AmplitudeConfig) -> None:
        """
        Load non-sensitive preferences from file.
        
        Args:
            config: AmplitudeConfig object to update with preferences
        """
        if not os.path.exists(CONFIG_FILE):
            return
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                prefs = json.load(f)
                
                # Only load region if not from environment
                if not config.from_environment:
                    region = prefs.get('region', DEFAULT_REGION)
                    if region in VALID_REGIONS:
                        config.region = region
                
                # Only load project_id if not from environment
                if not config.project_id and 'project_id' in prefs:
                    project_id_str = prefs['project_id']
                    if isinstance(project_id_str, str) and project_id_str.isdigit():
                        config.project_id = int(project_id_str)
                    elif isinstance(project_id_str, int):
                        config.project_id = project_id_str
                        
            logger.info(f"Loaded preferences from {CONFIG_FILE}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
        except IOError as e:
            logger.error(f"Error reading config file: {e}")
    
    def save_preferences(self, region: str, project_id: Optional[str] = None) -> None:
        """
        Save non-sensitive preferences to file.
        
        Args:
            region: Amplitude region
            project_id: Optional project ID (only saved if not from environment)
            
        Raises:
            ConfigurationError: If save fails
        """
        prefs: Dict[str, Any] = {
            'region': region
        }
        
        # Only save project_id if it's not from environment
        if project_id and not os.getenv(ENV_PROJECT_ID):
            prefs['project_id'] = project_id
        
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(prefs, f, indent=2)
            logger.info(f"Saved preferences to {CONFIG_FILE}")
        except IOError as e:
            raise ConfigurationError(f"Failed to save preferences: {e}")
    
    def validate_config(self, config: AmplitudeConfig) -> Tuple[bool, str]:
        """
        Validate configuration completeness.
        
        Args:
            config: AmplitudeConfig to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not config.api_key:
            return False, "API key is required"
        
        if not config.secret_key:
            return False, "Secret key is required"
        
        if config.region not in VALID_REGIONS:
            return False, f"Invalid region: {config.region}"
        
        return True, "Configuration is valid"
    
    def get_config(self) -> Optional[AmplitudeConfig]:
        """
        Get the current configuration.
        
        Returns:
            Current AmplitudeConfig or None if not loaded
        """
        return self._config 