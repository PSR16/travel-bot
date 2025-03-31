from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

from .db import read_database, User


class ActionCheckUserFlights(Action):
    """Rasa action to check if a user has flights and offer to show details."""

    def name(self) -> Text:
        return "action_check_user_flights"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get user_id from the tracker
        user_id = tracker.get_slot("user_id")
        
        if not user_id:
            # User is not identified, don't do anything here
            # This would be handled by a separate login flow
            return []
        
        # Read the database
        db = read_database()
        flights = db.get("flights", [])
        
        # Filter flights for the specific user
        user_flights = [flight for flight in flights if flight.get("user_id") == user_id]
        
        # Get user information for personalized greeting
        users = db.get("users", [])
        user_data = next((user for user in users if user.get("id") == user_id), None)
        user = User(user_data) if user_data else None
        
        events = []
        
        # Set a slot to indicate if the user has flights
        events.append(SlotSet("has_flights", bool(user_flights)))
        
        # If user has flights, set the count and offer to check them
        if user_flights:
            events.append(SlotSet("flight_count", len(user_flights)))
            
            # Get the next upcoming flight
            # Assuming flights have a 'date' field that can be compared
            upcoming_flights = sorted(user_flights, key=lambda f: f.get('date', ''))
            if upcoming_flights:
                next_flight = upcoming_flights[0]
                departure = next_flight.get("departure", {})
                arrival = next_flight.get("arrival", {})
                
                # Store information about the next flight
                events.append(SlotSet("next_flight_date", next_flight.get('date')))
                events.append(SlotSet("next_flight_departure", 
                                      f"{departure.get('city', '')}, {departure.get('country', '')}"))
                events.append(SlotSet("next_flight_arrival", 
                                      f"{arrival.get('city', '')}, {arrival.get('country', '')}"))
                
                # Personalized greeting with subtle flight reminder
                greeting = f"Welcome back{' ' + user.first_name if user and user.first_name else ''}! "
                
                if len(user_flights) == 1:
                    greeting += "Would you like to check the status of your upcoming flight?"
                else:
                    greeting += f"You have {len(user_flights)} upcoming flights. Would you like to check their status?"
                
                dispatcher.utter_message(text=greeting)
        
        return events


class ActionGetUserFlights(Action):
    """Rasa action to retrieve and display existing flights for a user."""

    def name(self) -> Text:
        return "action_get_user_flights"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get user_id from the tracker
        user_id = tracker.get_slot("user_id")
        has_flights = tracker.get_slot("has_flights")
        
        if not user_id:
            dispatcher.utter_message(text="I couldn't identify your user account. Please log in first.")
            return []
        
        if has_flights is False:
            dispatcher.utter_message(text="You don't have any flights booked yet. Would you like to book a new flight?")
            return []
        
        # Read the database
        db = read_database()
        flights = db.get("flights", [])
        
        # Filter flights for the specific user
        user_flights = [flight for flight in flights if flight.get("user_id") == user_id]
        
        # Format and display the flights
        dispatcher.utter_message(text=f"Here are your upcoming flights:")
        
        for i, flight in enumerate(user_flights, 1):
            departure = flight.get("departure", {})
            arrival = flight.get("arrival", {})
            
            flight_info = (
                f"Flight {i}:\n"
                f"From: {departure.get('city', 'Unknown')}, {departure.get('country', 'Unknown')}\n"
                f"To: {arrival.get('city', 'Unknown')}, {arrival.get('country', 'Unknown')}\n"
                f"Date: {flight.get('date', 'Unknown')}\n"
                f"Flight Number: {flight.get('flightNumber', 'Unknown')}\n"
            )
            
            dispatcher.utter_message(text=flight_info)
        
        return []
