#!/usr/bin/env python3
"""
Validation utilities for Amplitude Bulk Annotation Maker.

This module provides validation functions for various inputs
like chart IDs, URLs, and project IDs.
"""
import re
import logging
from typing import List, Tuple, Optional

from constants import CHART_ID_PATTERN, CHART_URL_PATTERN, CHART_ID_MIN_LENGTH

logger = logging.getLogger(__name__)


def extract_chart_ids(input_text: str) -> List[str]:
    """
    Extract chart IDs from text input containing IDs or URLs.
    
    Args:
        input_text: Text containing chart IDs or Amplitude URLs
        
    Returns:
        List of unique chart IDs
        
    Examples:
        >>> extract_chart_ids("abc123")
        ['abc123']
        >>> extract_chart_ids("https://app.amplitude.com/analytics/demo/chart/xyz789")
        ['xyz789']
        >>> extract_chart_ids("abc123, def456\\nxyz789")
        ['abc123', 'def456', 'xyz789']
    """
    if not input_text.strip():
        return []
    
    chart_ids: List[str] = []
    lines = input_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if it's a URL
        if 'amplitude.com' in line and '/chart/' in line:
            # Extract chart ID from URL
            match = re.search(CHART_URL_PATTERN, line)
            if match:
                chart_ids.append(match.group(1))
                logger.debug(f"Extracted chart ID from URL: {match.group(1)}")
        else:
            # Assume it's a direct chart ID - split by comma or whitespace
            for part in re.split(r'[,\s]+', line):
                part = part.strip()
                if part and re.match(CHART_ID_PATTERN, part):
                    chart_ids.append(part)
                    logger.debug(f"Found direct chart ID: {part}")
    
    unique_ids = list(set(chart_ids))
    logger.info(f"Extracted {len(unique_ids)} unique chart IDs from input")
    return unique_ids


def validate_chart_ids(chart_ids: List[str]) -> Tuple[List[str], List[str]]:
    """
    Validate chart IDs format.
    
    Args:
        chart_ids: List of chart IDs to validate
        
    Returns:
        Tuple of (valid_ids, invalid_ids)
    """
    valid_ids: List[str] = []
    invalid_ids: List[str] = []
    
    for chart_id in chart_ids:
        if re.match(CHART_ID_PATTERN, chart_id):
            valid_ids.append(chart_id)
        else:
            invalid_ids.append(chart_id)
            logger.warning(f"Invalid chart ID format: {chart_id}")
    
    logger.info(f"Validated chart IDs: {len(valid_ids)} valid, {len(invalid_ids)} invalid")
    return valid_ids, invalid_ids


def validate_project_id(project_id_str: str) -> Optional[int]:
    """
    Validate and convert project ID string to integer.
    
    Args:
        project_id_str: String representation of project ID
        
    Returns:
        Integer project ID if valid, None otherwise
    """
    if not project_id_str:
        return None
    
    project_id_str = project_id_str.strip()
    
    if not project_id_str.isdigit():
        logger.warning(f"Invalid project ID format: {project_id_str}")
        return None
    
    try:
        project_id = int(project_id_str)
        if project_id <= 0:
            logger.warning(f"Invalid project ID value: {project_id}")
            return None
        return project_id
    except ValueError:
        logger.warning(f"Failed to convert project ID to integer: {project_id_str}")
        return None


def validate_annotation_name(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate annotation name.
    
    Args:
        name: Annotation name to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Annotation name is required"
    
    name = name.strip()
    
    if len(name) > 255:
        return False, "Annotation name must be 255 characters or less"
    
    # Check for potentially problematic characters
    if any(char in name for char in ['<', '>', '&', '"', "'"]):
        logger.warning(f"Annotation name contains special characters: {name}")
    
    return True, None


def sanitize_text(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize text input by trimming whitespace and optionally truncating.
    
    Args:
        text: Text to sanitize
        max_length: Optional maximum length
        
    Returns:
        Sanitized text
    """
    text = text.strip()
    
    if max_length and len(text) > max_length:
        text = text[:max_length-3] + "..."
        logger.debug(f"Truncated text to {max_length} characters")
    
    return text 