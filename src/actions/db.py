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
