from typing import Dict, List, Optional, Any
from .amadeus_service import AmadeusService

class FlightService:
    def __init__(self):
        self.amadeus_service = AmadeusService()
    
    def get_location_iata(self, location: str) -> Optional[str]:
        """Get IATA code for a location"""
        return self.amadeus_service.get_iata_code(location)
    
    def search_flights(self, departure: str, destination: Optional[str] = None, 
                      duration: Optional[str] = None, max_price: Optional[str] = None, 
                      one_way: Optional[bool] = None) -> Dict[str, Any]:
        """
        Search for flights based on parameters
        Returns a dictionary with success status and data/error message
        """
        result = {"success": False, "data": None, "message": None}
        
        # Get access token
        access_token = self.amadeus_service.get_access_token()
        if not access_token:
            result["message"] = "Failed to connect to flight database"
            return result
        
        # Get departure IATA code
        dep_iata_code = self.get_location_iata(departure)
        if not dep_iata_code:
            result["message"] = f"Couldn't find an IATA airport code for {departure}"
            return result
        
        # Build API request parameters
        params = {"origin": dep_iata_code.upper()}
        
        # Determine which API to use based on whether destination is provided
        if destination:
            # Get destination IATA code
            arr_iata_code = self.get_location_iata(destination)
            if not arr_iata_code:
                result["message"] = f"Couldn't find an IATA airport code for {destination}"
                return result
                
            params["destination"] = arr_iata_code
            response_data = self.amadeus_service.search_cheapest_flights(params)
        else:
            response_data = self.amadeus_service.search_flight_destinations(params)
        
        # Add optional parameters
        if max_price:
            params["maxPrice"] = max_price
        if duration:
            params["duration"] = duration
        if one_way:
            params["oneWay"] = one_way
            
        if not response_data or "data" not in response_data or not response_data["data"]:
            result["message"] = "No flights found matching your criteria"
            return result
            
        result["success"] = True
        result["data"] = response_data["data"]
        return result
    
    def format_flight_suggestions(self, flights: List[Dict[str, Any]], start_idx: int = 0, count: int = 3) -> str:
        """Format flight suggestions into a readable message"""
        end_idx = min(start_idx + count, len(flights))
        flights_to_show = flights[start_idx:end_idx]
        
        if not flights_to_show:
            return "No more flight suggestions available."
            
        response_message = "These are some flight suggestions for you:\n\n"
        
        for i, flight in enumerate(flights_to_show):
            flight_text = (
                f"✈️ **Flight {start_idx + i + 1}**\n"
                f"🛫 From: {flight['origin']} "
                f"🛬 To: {flight['destination']}"
                f"📅 Depart: {flight['departureDate']}\n"
                f"📅 Return: {flight['returnDate']}\n"
                f"💰 Price: ${flight['price'].get('total', 'Unavailable')}"
            )
            response_message += flight_text + "\n\n"
            
        return response_message
