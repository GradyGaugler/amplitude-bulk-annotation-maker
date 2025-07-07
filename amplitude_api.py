#!/usr/bin/env python3
"""
Amplitude API Client for bulk annotation operations.

This module provides a robust client for interacting with the Amplitude API,
with features including retry logic, session reuse, and comprehensive error handling.
"""
import base64
import logging
from typing import List, Dict, Optional, Tuple, Callable, Any
from datetime import date
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from constants import (
    API_TIMEOUT,
    API_BASE_URL_US,
    API_BASE_URL_EU,
    API_ANNOTATIONS_ENDPOINT,
    VALID_REGIONS
)

# Configure logging
logger = logging.getLogger(__name__)


class AmplitudeAPIError(Exception):
    """Base exception for Amplitude API errors."""
    pass


class AmplitudeAuthenticationError(AmplitudeAPIError):
    """Raised when authentication fails."""
    pass


class AmplitudeConnectionError(AmplitudeAPIError):
    """Raised when connection to API fails."""
    pass


class AmplitudeAPIClient:
    """
    Client for interacting with Amplitude API.
    
    This client provides methods for creating annotations on Amplitude charts
    with support for bulk operations, retry logic, and session reuse.
    
    Attributes:
        api_key: The Amplitude API key
        secret_key: The Amplitude secret key
        region: The Amplitude region (US or EU)
        base_url: The base URL for API requests
        session: Persistent requests session for connection reuse
    """
    
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        region: str = "US",
        timeout: int = API_TIMEOUT,
        max_retries: int = 3
    ) -> None:
        """
        Initialize the Amplitude API client.
        
        Args:
            api_key: Amplitude API key
            secret_key: Amplitude secret key
            region: Amplitude region (US or EU)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            
        Raises:
            ValueError: If region is not valid
        """
        if region not in VALID_REGIONS:
            raise ValueError(f"Invalid region: {region}. Must be one of {VALID_REGIONS}")
            
        self.api_key = api_key
        self.secret_key = secret_key
        self.region = region
        self.timeout = timeout
        
        # Set base URL based on region
        self.base_url = API_BASE_URL_EU if region == "EU" else API_BASE_URL_US
        
        # Create persistent session for connection reuse
        self.session = self._create_session(max_retries)
        
        # Set authentication headers
        self._set_auth_headers()
    
    def _create_session(self, max_retries: int) -> requests.Session:
        """
        Create a requests session with retry logic.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Configured requests session
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _set_auth_headers(self) -> None:
        """Set authentication headers for the session."""
        credentials = f"{self.api_key}:{self.secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        self.session.headers.update({
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        })
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test API connection by making a simple request.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            response = self.session.get(
                urljoin(self.base_url, API_ANNOTATIONS_ENDPOINT),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info("API connection successful")
                return True, "Connection successful"
            elif response.status_code == 401:
                logger.error("Authentication failed")
                return False, "Authentication failed - check your API keys"
            else:
                logger.error(f"API error: {response.status_code}")
                return False, f"API error: {response.status_code}"
                
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return False, "Connection timeout - please try again"
        except requests.exceptions.ConnectionError:
            logger.error("Connection error")
            return False, "Connection error - check your internet connection"
        except Exception as e:
            logger.exception("Unexpected error during connection test")
            return False, f"Unexpected error: {str(e)}"
    

    
    def create_annotation(
        self,
        project_id: int,
        annotation_date: date,
        label: str,
        details: str = "",
        chart_id: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Create an annotation for a chart or globally.
        
        Args:
            project_id: Amplitude project ID
            annotation_date: Date for the annotation
            label: Annotation label/title
            details: Optional annotation details/description
            chart_id: Optional specific chart ID (if None, creates global annotation)
            
        Returns:
            Tuple of (success: bool, message: str)
            
        Raises:
            AmplitudeAPIError: If API request fails
        """
        params: Dict[str, Any] = {
            "app_id": project_id,
            "date": annotation_date.strftime("%Y-%m-%d"),
            "label": label
        }
        
        if chart_id:
            params["chart_id"] = chart_id
            
        if details:
            params["details"] = details
        
        try:
            response = self.session.post(
                urljoin(self.base_url, API_ANNOTATIONS_ENDPOINT),
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    annotation_id = result.get('annotation', {}).get('id', 'Unknown')
                    logger.info(f"Annotation created successfully: {annotation_id}")
                    return True, f"Annotation created: {annotation_id}"
                else:
                    logger.error("API returned success=false")
                    return False, "API returned success=false"
            elif response.status_code == 401:
                raise AmplitudeAuthenticationError("Authentication failed")
            else:
                logger.error(f"HTTP {response.status_code}: {response.text}")
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            return False, "Request timeout"
        except requests.exceptions.ConnectionError:
            logger.error("Connection error")
            return False, "Connection error"
        except AmplitudeAPIError:
            raise
        except Exception as e:
            logger.exception("Unexpected error creating annotation")
            return False, f"Error: {str(e)}"
    
    def bulk_annotate(
        self,
        project_id: int,
        chart_ids: List[str],
        annotation_date: date,
        label: str,
        details: str = "",
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Tuple[str, bool, str]]:
        """
        Apply the same annotation to multiple charts.
        
        Args:
            project_id: Amplitude project ID
            chart_ids: List of chart IDs to annotate
            annotation_date: Date for the annotation
            label: Annotation label/title
            details: Optional annotation details/description
            progress_callback: Optional callback for progress updates (current, total)
            
        Returns:
            List of tuples (chart_id, success, message) for each chart
        """
        results: List[Tuple[str, bool, str]] = []
        total = len(chart_ids)
        
        logger.info(f"Starting bulk annotation for {total} charts")
        
        for i, chart_id in enumerate(chart_ids):
            try:
                success, message = self.create_annotation(
                    project_id=project_id,
                    annotation_date=annotation_date,
                    label=label,
                    details=details,
                    chart_id=chart_id
                )
                
                results.append((chart_id, success, message))
                
                if progress_callback:
                    progress_callback(i + 1, total)
                    
            except AmplitudeAuthenticationError:
                # Stop on authentication error
                logger.error("Authentication error - stopping bulk operation")
                results.append((chart_id, False, "Authentication failed"))
                break
            except Exception as e:
                logger.exception(f"Error annotating chart {chart_id}")
                results.append((chart_id, False, str(e)))
        
        success_count = sum(1 for _, success, _ in results if success)
        logger.info(f"Bulk annotation completed: {success_count}/{total} successful")
        
        return results
    
    def __enter__(self) -> 'AmplitudeAPIClient':
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[Any]) -> None:
        """Context manager exit - close session."""
        self.close()
    
    def close(self) -> None:
        """Close the requests session."""
        if hasattr(self, 'session'):
            self.session.close()
            logger.debug("API client session closed") 