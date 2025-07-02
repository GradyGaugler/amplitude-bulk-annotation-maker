"""
Amplitude API Client for bulk annotation operations
"""
import base64
import requests
from typing import List, Dict, Optional, Tuple
from datetime import date
import json
import re


class AmplitudeAPIClient:
    """Client for interacting with Amplitude API"""
    
    def __init__(self, api_key: str, secret_key: str, region: str = "US"):
        self.api_key = api_key
        self.secret_key = secret_key
        
        # Set base URL based on region
        if region == "EU":
            self.base_url = "https://analytics.eu.amplitude.com"
        else:
            self.base_url = "https://amplitude.com"
        
        # Create auth header
        credentials = f"{api_key}:{secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test API connection by making a simple request"""
        try:
            # Try to get existing annotations to test the connection
            response = requests.get(
                f"{self.base_url}/api/2/annotations",
                headers=self.headers,
                timeout=10
            )
            if response.status_code == 200:
                return True, "Connection successful"
            elif response.status_code == 401:
                return False, "Authentication failed - check your API keys"
            else:
                return False, f"API error: {response.status_code}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    @staticmethod
    def extract_chart_ids(input_text: str) -> List[str]:
        """Extract chart IDs from text input containing IDs or URLs"""
        if not input_text.strip():
            return []
        
        chart_ids = []
        lines = input_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check if it's a URL
            if 'amplitude.com' in line and '/chart/' in line:
                # Extract chart ID from URL like: https://app.amplitude.com/analytics/gitkraken/chart/ez25o7zy
                match = re.search(r'/chart/([a-zA-Z0-9_-]+)', line)
                if match:
                    chart_ids.append(match.group(1))
            else:
                # Assume it's a direct chart ID - split by comma or whitespace
                for part in re.split(r'[,\s]+', line):
                    part = part.strip()
                    if part and re.match(r'^[a-zA-Z0-9_-]+$', part):
                        chart_ids.append(part)
        
        return list(set(chart_ids))  # Remove duplicates
    
    @staticmethod
    def validate_chart_ids(chart_ids: List[str]) -> Tuple[List[str], List[str]]:
        """Validate chart IDs format"""
        valid_ids = []
        invalid_ids = []
        
        for chart_id in chart_ids:
            # Chart IDs should be alphanumeric with possible dashes/underscores
            if re.match(r'^[a-zA-Z0-9_-]{3,}$', chart_id):
                valid_ids.append(chart_id)
            else:
                invalid_ids.append(chart_id)
        
        return valid_ids, invalid_ids
    
    def create_annotation(self, 
                         project_id: int,
                         annotation_date: date,
                         label: str,
                         details: str = "",
                         chart_id: Optional[str] = None) -> Tuple[bool, str]:
        """Create an annotation for a chart or globally"""
        
        params = {
            "app_id": project_id,
            "date": annotation_date.strftime("%Y-%m-%d"),
            "label": label
        }
        
        if chart_id:
            params["chart_id"] = chart_id
            
        if details:
            params["details"] = details
        
        try:
            response = requests.post(
                f"{self.base_url}/api/2/annotations",
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    return True, f"Annotation created: {result.get('annotation', {}).get('id', 'Unknown')}"
                else:
                    return False, "API returned success=false"
            else:
                return False, f"HTTP {response.status_code}: {response.text}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def bulk_annotate(self,
                     project_id: int,
                     chart_ids: List[str],
                     annotation_date: date,
                     label: str,
                     details: str = "",
                     progress_callback=None) -> List[Tuple[str, bool, str]]:
        """Apply the same annotation to multiple charts"""
        results = []
        total = len(chart_ids)
        
        for i, chart_id in enumerate(chart_ids):
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
        
        return results 