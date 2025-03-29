from typing import Any, Dict, List, Text
from datetime import datetime, timedelta

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from services.flight_service import FlightService

class ActionGetCheapestFlights(Action):
    def __init__(self):
        self.flight_service = FlightService()
        
    def name(self) -> Text:
        return "action_get_cheapest_flights"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Get user-provided slots
        departure = tracker.get_slot("departure_city")
        destination = tracker.get_slot("destination")
        duration = tracker.get_slot("duration")
        max_price = tracker.get_slot("maxPrice") or tracker.get_slot("travel_budget")
        one_way = tracker.get_slot("oneWay")
        departure_date = tracker.get_slot("departureDate")

        # Search for flights
        result = self.flight_service.search_flights(
            departure=departure,
            destination=destination,
            duration=duration,
            max_price=max_price,
            one_way=one_way,
            departure_date=departure_date
        )
        
        print("RESULTS ", result)
        if not result["success"]:
            dispatcher.utter_message(text=result["message"] or "I couldn't find any flights matching your criteria. Would you like to adjust your preferences?")
            return [SlotSet("success", "failure")]
            
        # Format and display flight suggestions
        response_message = self.flight_service.format_flight_suggestions(result["data"])
        dispatcher.utter_message(text=response_message)
        
        return [
            SlotSet("flight_suggestions", result["data"]), 
            SlotSet("success", "success")
        ]

class ActionGetMoreCheapestFlights(Action):
    def __init__(self):
        self.flight_service = FlightService()
        
    def name(self) -> Text:
        return "action_get_more_cheapest_flights"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        destinations = tracker.get_slot("flight_suggestions")
        
        if not destinations:
            dispatcher.utter_message(text="I don't have any flight suggestions to show you. Let's search for flights first.")
            return []
            
        # Show the next batch of flights (3-5)
        response_message = self.flight_service.format_flight_suggestions(destinations, start_idx=3, count=3)
        dispatcher.utter_message(text=response_message)

        return []
