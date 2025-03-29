import os
import requests
from typing import Dict, Optional, Any, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AmadeusService:
    # Amadeus API credentials and endpoints
    CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
    CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")
    AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
    FLIGHT_DESTINATIONS_URL = "https://test.api.amadeus.com/v1/shopping/flight-destinations"
    CHEAPEST_FLIGHT_URL = "https://test.api.amadeus.com/v1/shopping/flight-dates"
    AIRPORT_SEARCH_URL = os.getenv("AMADEUS_AIRPORT_SEARCH_URL", "https://test.api.amadeus.com/v1/reference-data/locations")

    def __init__(self):
        self.access_token = None
    
    def get_access_token(self) -> Optional[str]:
        """Fetch a Bearer token from Amadeus API"""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = requests.post(self.AUTH_URL, data=payload, headers=headers)
            response.raise_for_status()
            self.access_token = response.json().get("access_token")
            return self.access_token
        except requests.exceptions.RequestException as e:
            print(f"Error fetching access token: {e}")
            return None

    def get_iata_code(self, location: str) -> Optional[str]:
        """Get IATA code for a location (city or airport)"""
        if not self.access_token:
            self.access_token = self.get_access_token()
            if not self.access_token:
                return None
                
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"keyword": location, "subType": "AIRPORT,CITY"}

        try:
            response = requests.get(self.AIRPORT_SEARCH_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "data" in data and data["data"]:
                iata_code = data["data"][0]["iataCode"]  # Take the first match
                print(f"Found IATA code for {location}: {iata_code}")
                return iata_code
            else:
                print(f"No IATA code found for {location}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching IATA code: {e}")
            return None
    
    def search_flight_destinations(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Search for flight destinations based on parameters"""
        if not self.access_token:
            self.access_token = self.get_access_token()
            if not self.access_token:
                return None
                
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(self.FLIGHT_DESTINATIONS_URL, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching flight destinations: {e}")
            return None
    
    def search_cheapest_flights(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Search for cheapest flights based on parameters"""
        if not self.access_token:
            self.access_token = self.get_access_token()
            if not self.access_token:
                return None
                
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(self.CHEAPEST_FLIGHT_URL, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching cheapest flights: {e}")
            return None
