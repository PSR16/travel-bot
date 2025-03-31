import os
import requests
from typing import Dict, Any, Tuple, Optional

class YNABService:
    """Service class for interacting with the YNAB API"""
    
    def __init__(self):
        self.access_token = os.environ.get("YNAB_ACCESS_TOKEN")
        self.budget_id = os.environ.get("YNAB_BUDGET_ID")
        self.travel_category = os.environ.get("YNAB_TRAVEL_CATEGORY")
        self.base_url = "https://api.youneedabudget.com/v1"
        
    def get_headers(self) -> Dict[str, str]:
        """Get the authorization headers for YNAB API requests"""
        return {"Authorization": f"Bearer {self.access_token}"}
    
    def get_travel_budget(self) -> Optional[Tuple[float, float, float]]:
        """
        Retrieve travel budget information from YNAB
        
        Returns:
            Tuple of (budgeted, activity, balance) or None if error occurs
        """
        if not self.access_token or not self.budget_id or not self.travel_category:
            return None
            
        try:
            url = f"{self.base_url}/budgets/{self.budget_id}/categories/{self.travel_category}"
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            
            data = response.json()
            travel_category = data['data']['category']
            
            # YNAB amounts are in milliunits
            budgeted = travel_category['budgeted'] / 1000
            balance = travel_category['balance'] / 1000
            activity = travel_category['activity'] / 1000
            
            return budgeted, activity, balance
            
        except (requests.exceptions.RequestException, KeyError, ValueError):
            return None
