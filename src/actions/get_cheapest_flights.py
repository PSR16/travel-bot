# from typing import Any, Dict, List, Text
# from datetime import datetime, timedelta
from typing import Any, Dict, List, Text
from datetime import datetime, timedelta

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from services.flight_service import FlightService

class ActionGetDestinations(Action):
    def __init__(self):
        self.flight_service = FlightService()
        
    def name(self) -> Text:
        return "action_get_destinations"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Get user-provided slots
        departure = tracker.get_slot("departure_city")
        destination = tracker.get_slot("destination")
        duration = tracker.get_slot("duration")
        max_price = tracker.get_slot("maxPrice") or tracker.get_slot("travel_budget")
        one_way = tracker.get_slot("oneWay")
        departure_date = tracker.get_slot("travel_timeframe")

        # Search for flights
        result = self.flight_service.search_flights(
            departure=departure,
            destination=destination,
            duration=duration,
            max_price=max_price,
            one_way=one_way,
            departure_date=departure_date
        )
        
        if not result["success"]:
            dispatcher.utter_message(text=result["message"] or "I couldn't find any flights matching your criteria. Would you like to adjust your preferences?")
            return [SlotSet("success", "failure")]
        
        # Store flight suggestions but don't display them yet
        return [
            SlotSet("flight_suggestions", result["data"]), 
            SlotSet("return_value", "success")
        ]

class ActionDisplayDestinations(Action):
    def __init__(self):
        self.flight_service = FlightService()
        
    def name(self) -> Text:
        return "action_ask_destination_index"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get flight suggestions from slot
        flight_suggestions = tracker.get_slot("flight_suggestions")
        
        if not flight_suggestions:
            dispatcher.utter_message(text="I don't have any flight suggestions to show you. Let's search for flights first.")
            return [SlotSet("return_value", "failure")]
        
        # Handle different numbers of suggestions
        total_suggestions = len(flight_suggestions)
        
        if total_suggestions == 0:
            dispatcher.utter_message(text="I couldn't find any flight suggestions for your criteria.")
            return [SlotSet("return_value", "failure")]
        
        # Format and display flight suggestions (up to 3)
        display_count = min(3, total_suggestions)
        response_message = self.flight_service.format_flight_suggestions(flight_suggestions, 0, display_count)
        
        # Add selection prompt
        if total_suggestions == 1:
            response_message += "\nThis is the only option available. Would you like to select this destination?"
            buttons = [{
                "title": "Select this destination",
                "payload": f"/SetSlots(destination_index=0)"
            }]
        else:
            response_message += "\nWhich destination would you like to choose?"
            
            # Create buttons for each destination
            buttons = []
            for i in range(display_count):
                buttons.append({
                    "title": f"Select Flight {i+1}",
                    "payload": f"/SetSlots(destination_index={i})"
                })
            
            # Add "See More" button if there are more than 3 suggestions
            if total_suggestions > 3:
                buttons.append({
                    "title": "See More Options",
                    "payload": "/SetSlots(destination_index=see_more)"
                })
        
        dispatcher.utter_message(text=response_message, buttons=buttons)
        return [SlotSet("current_page", 0)]  # Track which page of results we're on

class ActionShowMoreDestinations(Action):
    def __init__(self):
        self.flight_service = FlightService()
        
    def name(self) -> Text:
        return "action_show_more_destinations"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        destinations = tracker.get_slot("flight_suggestions")
        current_page = tracker.get_slot("current_page") or 0
        
        if not destinations:
           # dispatcher.utter_message(text="I don't have any flight suggestions to show you. Let's search for flights first.")
            return []
        
        # Calculate next page
        next_page = current_page + 1
        start_idx = next_page * 3
        
        # Check if we have more results to show
        if start_idx >= len(destinations):
            dispatcher.utter_message(text="There are no more flight suggestions available.")
            return []
            
        # Show the next batch of flights (3 more)
        display_count = min(3, len(destinations) - start_idx)
        response_message = self.flight_service.format_flight_suggestions(destinations, start_idx, display_count)
        response_message += "\nWhich destination would you like to choose?"
        
        # Create buttons for each destination
        buttons = []
        for i in range(start_idx, start_idx + display_count):
            buttons.append({
                "title": f"Select Flight {i+1}",
                "payload": f"/select_destination{{'destination_index': {i}}}"
            })
        
        # Add navigation buttons
        has_more = (start_idx + display_count) < len(destinations)
        if has_more:
            buttons.append({
                "title": "See More Options",
                "payload": "/show_more_destinations"
            })
        
        if current_page > 0:
            buttons.append({
                "title": "Previous Options",
                "payload": "/show_previous_destinations"
            })
        
        dispatcher.utter_message(text=response_message, buttons=buttons)
        return [SlotSet("current_page", next_page)]

class ActionShowPreviousDestinations(Action):
    def __init__(self):
        self.flight_service = FlightService()
        
    def name(self) -> Text:
        return "action_show_previous_destinations"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        destinations = tracker.get_slot("flight_suggestions")
        current_page = tracker.get_slot("current_page") or 0
        
        if not destinations or current_page <= 0:
            dispatcher.utter_message(text="There are no previous flight suggestions to show.")
            return []
        
        # Calculate previous page
        prev_page = current_page - 1
        start_idx = prev_page * 3
        
        # Show the previous batch of flights
        display_count = min(3, len(destinations) - start_idx)
        response_message = self.flight_service.format_flight_suggestions(destinations, start_idx, display_count)
        response_message += "\nWhich destination would you like to choose?"
        
        # Create buttons for each destination
        buttons = []
        for i in range(start_idx, start_idx + display_count):
            buttons.append({
                "title": f"Select Flight {i+1}",
                "payload": f"/select_destination{{'destination_index': {i}}}"
            })
        
        # Add navigation buttons
        has_more = (start_idx + display_count) < len(destinations)
        if has_more:
            buttons.append({
                "title": "See More Options",
                "payload": "/show_more_destinations"
            })
        
        if prev_page > 0:
            buttons.append({
                "title": "Previous Options",
                "payload": "/show_previous_destinations"
            })
        
        dispatcher.utter_message(text=response_message, buttons=buttons)
        return [SlotSet("current_page", prev_page)]

class ActionSelectDestination(Action):
    def name(self) -> Text:
        return "action_ask_should_book"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get flight suggestions from slot
        flight_suggestions = tracker.get_slot("flight_suggestions")
        
        if not flight_suggestions:
            #dispatcher.utter_message(text="I don't have any flight suggestions available. Let's search for flights first.")
            return []
        
        # Get the selected destination index
        destination_index = tracker.get_slot("destination_index")
        
        # if destination_index is None:
        #     # Try to extract from entities
        #     for event in reversed(tracker.events):
        #         if event.get("event") == "user":
        #             entities = event.get("parse_data", {}).get("entities", [])
        #             for entity in entities:
        #                 if entity.get("entity") == "destination_index":
        #                     destination_index = int(entity.get("value"))
        #                     break
        #             if destination_index is not None:
        #                 break
        
        # Convert to integer if it's a string
        if isinstance(destination_index, str) and destination_index.isdigit():
            destination_index = int(destination_index)
        
        if destination_index is None or not isinstance(destination_index, int):
            dispatcher.utter_message(text="Please select a destination from the options provided.")
            return []
        
        # Validate index
        if 0 <= destination_index < len(flight_suggestions):
            selected = flight_suggestions[destination_index]

            # Extract data from the selected destination for booking flow
            destination_code = selected.get('destination')
            departure_code = selected.get('origin')
            departure_date = selected.get('departureDate')
            return_date = selected.get('returnDate')
            
            # Format a message about the selected destination
            message = (f"Great choice! You've selected a trip to {destination_code} from {departure_code}.\n"
                      f"Departing on {departure_date} and returning on {return_date}.\n"
                      f"Price estimate: ${selected.get('price', {}).get('total', 'Unknown')}\n\n"
                      f"Would you like to proceed with booking this flight?")
            
            # Create buttons for booking or going back
            buttons = [
                {"title": "Book this flight", "payload": "/SetSlot(should_book=yes)"},
                {"title": "Go back to options", "payload": "/SetSlot(should_book=no)"}
            ]
            dispatcher.utter_message(text=message, buttons=buttons)

            # Set slots needed for the booking flow
            return [
                SlotSet("selected_destination", selected),
                SlotSet("destination", destination_code),  # For booking flow
                SlotSet("departureDate", departure_date),  # For booking flow
                SlotSet("returnDate", return_date),        # For booking flow
                # Keep the original departure_city slot value
            ]
        else:
            dispatcher.utter_message(text="I couldn't find that destination in the suggestions.")
            return []


class ActionTransitionToBooking(Action):
    def name(self) -> Text:
        return "action_transition_to_booking"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the selected destination details
        selected = tracker.get_slot("selected_destination")
        
        if not selected:
            dispatcher.utter_message(text="You need to select a destination first before booking.")
            return []
        
        # Extract all necessary information for the booking flow
        destination_code = selected.get('destination')
        departure_code = selected.get('origin')
        departure_date = selected.get('departureDate')
        return_date = selected.get('returnDate')
        price = selected.get('price', {}).get('total')
        
        # Set default values for booking flow
        number_of_pax = "1"  # Default to 1 passenger
        travel_class = "economy"  # Default to economy class
        
        # Prepare a message for the transition
        message = (f"I'll help you book a flight from {departure_code} to {destination_code}.\n"
                  f"Departing on {departure_date} and returning on {return_date}.\n"
                  f"Let's continue with the booking process.")
        
        dispatcher.utter_message(text=message)
        
        # Set all slots needed for the booking flow
        return [
            # Core flight details
            SlotSet("destination", destination_code),
            SlotSet("departureDate", departure_date),
            SlotSet("returnDate", return_date),
            SlotSet("maxPrice", price),
            
            # Default booking parameters
            SlotSet("number_of_pax", number_of_pax),
            SlotSet("travel_class", travel_class),
            
            # Trip type (based on whether return date exists)
            SlotSet("trip_type", "round-trip" if return_date else "one-way"),
            
            # Clear previous search results to avoid confusion
            SlotSet("flight_suggestions", None),
            SlotSet("current_page", 0)
        ]