import os
import json
from typing import Any, Dict, List, Optional

from rasa.shared.utils.io import read_json_file
from rasa.nlu.utils import write_json_to_file

# Define the database path
DATABASE_PATH = "db/database.json"

class User:
    """Class representing a user in the database."""
    def __init__(self, user_data: Dict[str, Any]):
        self.id = user_data.get("id")
        name_data = user_data.get("name", {})
        self.first_name = name_data.get("firstName")
        self.last_name = name_data.get("lastName")
        self.preferred_departure_city = user_data.get("preferredDepartureCity")
        self.preferred_departure_country = user_data.get("preferredDepartureCountry")
        self._raw_data = user_data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user object back to dictionary."""
        return self._raw_data

def read_database() -> Dict[str, Any]:
    """Read the database file."""
    try:
        return read_json_file(DATABASE_PATH)
    except Exception as e:
        print(f"Error reading database: {e}")
        return {"users": []}

def write_database(data: Dict[str, Any]) -> None:
    """Write data to the database file."""
    try:
        write_json_to_file(DATABASE_PATH, data)
    except Exception as e:
        print(f"Error writing to database: {e}")

def get_users() -> List[User]:
    """Get all users from the database."""
    db = read_database()
    return [User(user_data) for user_data in db.get("users", [])]

def get_user_by_id(user_id: int) -> Optional[User]:
    """Get a user by their ID."""
    users = get_users()
    for user in users:
        if user.id == user_id:
            return user
    return None

def get_user_by_name(first_name: str, last_name: str = None) -> Optional[User]:
    """Get a user by their name."""
    users = get_users()
    for user in users:
        if user.first_name == first_name:
            if last_name is None or user.last_name == last_name:
                return user
    return None

def get_preferred_departure_city(user_id: int) -> Optional[str]:
    """Get the preferred departure city for a user."""
    user = get_user_by_id(user_id)
    return user.preferred_departure_city if user else None

def get_preferred_departure_country(user_id: int) -> Optional[str]:
    """Get the preferred departure country for a user."""
    user = get_user_by_id(user_id)
    return user.preferred_departure_country if user else None

def add_user(user_data: Dict[str, Any]) -> bool:
    """Add a new user to the database."""
    db = read_database()
    users = db.get("users", [])
    
    # Generate a new ID if not provided
    if "id" not in user_data:
        max_id = 0
        for user in users:
            if user.get("id", 0) > max_id:
                max_id = user.get("id")
        user_data["id"] = max_id + 1
    
    users.append(user_data)
    db["users"] = users
    write_database(db)
    return True

def update_user(user_id: int, updated_data: Dict[str, Any]) -> bool:
    """Update an existing user in the database."""
    db = read_database()
    users = db.get("users", [])
    
    for i, user in enumerate(users):
        if user.get("id") == user_id:
            # Update only the fields provided in updated_data
            for key, value in updated_data.items():
                if key == "name" and isinstance(value, dict):
                    # Handle nested name object
                    if "name" not in user:
                        user["name"] = {}
                    for name_key, name_value in value.items():
                        user["name"][name_key] = name_value
                else:
                    user[key] = value
            
            db["users"] = users
            write_database(db)
            return True
    
    return False

def add_flight_to_user(user_id: int, flight_data: Dict[str, Any]) -> bool:
    """Add a flight booking to a user's record.
    
    Args:
        user_id: The ID of the user
        flight_data: Dictionary containing flight booking details
        
    Returns:
        bool: True if successful, False otherwise
    """
    user = get_user_by_id(user_id)
    if not user:
        return False
    
     user_dict = user.to_dict()
    
    # Initialize flights array if it doesn't exist
    if "flights" not in user_dict:
        user_dict["flights"] = []
    
    # Extract and simplify the important flight information
    simplified_flight = {
        "id": flight_data.get("id"),
        "bookingDate": flight_data.get("bookingDate"),
        "status": flight_data.get("status", "confirmed"),
        "totalPrice": {
            "amount": flight_data.get("flightDetails", {}).get("price", {}).get("total"),
            "currency": flight_data.get("flightDetails", {}).get("price", {}).get("currency", "USD")
        },
        "outboundFlight": _extract_flight_segment(flight_data, 0, 0),  # First segment of outbound journey
        "returnFlight": None,  # Will be populated if it's a round trip
        "airline": flight_data.get("flightDetails", {}).get("validatingAirlineCodes", [""])[0],
        "tripType": "ONE_WAY"
    }
    
    # Check if it's a round trip (has more than one itinerary)
    itineraries = flight_data.get("flightDetails", {}).get("itineraries", [])
    if len(itineraries) > 1:
        simplified_flight["returnFlight"] = _extract_flight_segment(flight_data, 1, 0)  # First segment of return journey
        simplified_flight["tripType"] = "ROUND_TRIP"
    
    # Generate flight ID if not provided
    if simplified_flight["id"] is None:
        max_id = 0
        for flight in user_dict["flights"]:
            if flight.get("id", 0) > max_id:
                max_id = flight.get("id")
        simplified_flight["id"] = max_id + 1
    
    # Add the simplified flight to the user's flights
    user_dict["flights"].append(simplified_flight)
    
    # Update the user in the database
    return update_user(user_id, user_dict)

def _extract_flight_segment(flight_data: Dict[str, Any], itinerary_index: int, segment_index: int) -> Dict[str, Any]:
    """Extract the important information from a flight segment.
    
    Args:
        flight_data: The complete flight data
        itinerary_index: Index of the itinerary (0 for outbound, 1 for return)
        segment_index: Index of the segment within the itinerary
        
    Returns:
        Dict containing simplified flight segment information
    """
    try:
        itineraries = flight_data.get("flightDetails", {}).get("itineraries", [])
        if itinerary_index >= len(itineraries):
            return None
            
        segments = itineraries[itinerary_index].get("segments", [])
        if segment_index >= len(segments):
            return None
            
        segment = segments[segment_index]
        
        return {
            "departureAirport": segment.get("departure", {}).get("iataCode"),
            "departureTerminal": segment.get("departure", {}).get("terminal"),
            "departureTime": segment.get("departure", {}).get("at"),
            "arrivalAirport": segment.get("arrival", {}).get("iataCode"),
            "arrivalTerminal": segment.get("arrival", {}).get("terminal"),
            "arrivalTime": segment.get("arrival", {}).get("at"),
            "flightNumber": f"{segment.get('carrierCode')}{segment.get('number')}",
            "duration": segment.get("duration"),
            "stops": segment.get("numberOfStops", 0)
        }
    except Exception as e:
        print(f"Error extracting flight segment: {e}")
        return {}