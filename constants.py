#!/usr/bin/env python3
"""
Constants for Amplitude Bulk Annotation Maker.

This module contains all constants used throughout the application,
following the principle of DRY (Don't Repeat Yourself).
"""
from typing import Final

# Application metadata
APP_NAME: Final[str] = "Amplitude Bulk Annotation Maker"
APP_VERSION: Final[str] = "1.0.0"

# Environment variable names
ENV_API_KEY: Final[str] = "AMPLITUDE_API_KEY"
ENV_SECRET_KEY: Final[str] = "AMPLITUDE_SECRET_KEY"
ENV_PROJECT_ID: Final[str] = "AMPLITUDE_PROJECT_ID"
ENV_REGION: Final[str] = "AMPLITUDE_REGION"

# API Configuration
API_TIMEOUT: Final[int] = 10  # seconds
API_BASE_URL_US: Final[str] = "https://amplitude.com"
API_BASE_URL_EU: Final[str] = "https://analytics.eu.amplitude.com"
API_ANNOTATIONS_ENDPOINT: Final[str] = "/api/2/annotations"
VALID_REGIONS: Final[list[str]] = ["US", "EU"]
DEFAULT_REGION: Final[str] = "US"

# UI Configuration
WINDOW_WIDTH: Final[int] = 900
WINDOW_HEIGHT: Final[int] = 700
STATUS_TEXT_MAX_HEIGHT: Final[int] = 100
DESCRIPTION_MAX_HEIGHT: Final[int] = 100
CHART_INPUT_MIN_HEIGHT: Final[int] = 150
RESULTS_TEXT_MAX_HEIGHT: Final[int] = 150

# File names
DISTRIBUTION_DIR: Final[str] = "dist"
DISTRIBUTION_INSTRUCTIONS_FILE: Final[str] = "DISTRIBUTION_INSTRUCTIONS.txt"

# UI Text constants
MASKED_CREDENTIAL_DISPLAY: Final[str] = "••••••••••••••••"
DATE_FORMAT: Final[str] = "yyyy-MM-dd"

# Validation patterns
CHART_ID_PATTERN: Final[str] = r'^[a-zA-Z0-9_-]{3,}$'
CHART_URL_PATTERN: Final[str] = r'/chart/([a-zA-Z0-9_-]+)'
CHART_ID_MIN_LENGTH: Final[int] = 3

# Timer delays (milliseconds)
AUTO_TEST_DELAY: Final[int] = 500
AUTO_TEST_DELAY_FAST: Final[int] = 200
AUTO_PROGRESS_DELAY: Final[int] = 100
STATUS_DISPLAY_DURATION: Final[int] = 2000

# Tab indices
TAB_CONFIG: Final[int] = 0
TAB_SELECTION: Final[int] = 1
TAB_ANNOTATION: Final[int] = 2

# Files to include in distribution
DISTRIBUTION_FILES: Final[list[str]] = [
    'amplitude_bulk_annotator.py',
    'amplitude_api.py',
    'config_manager.py',
    'constants.py',
    'requirements.txt',
    'README.md',
    'SETUP_ENVIRONMENT.md',
    'run.bat',
    'run.sh',
    'package_for_distribution.py',
    'utils/__init__.py',
    'utils/validators.py',
    '.gitignore'
] 