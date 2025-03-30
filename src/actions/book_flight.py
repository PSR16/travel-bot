from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import datetime
from services.flight_service import FlightService

class ValidateReturnDate(Action):
    def name(self) -> Text:
        return "validate_returnDate"

    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        return_date = tracker.get_slot("returnDate")
        departure_date = tracker.get_slot("departureDate")
        
        if not return_date or not departure_date:
            return []
            
        try:
            # Parse dates
            dep_date = datetime.datetime.strptime(departure_date, "%Y-%m-%d").date()
            
            # Try to parse return date or add current year
            try:
                ret_date = datetime.datetime.strptime(return_date, "%Y-%m-%d").date()
            except ValueError:
                current_year = datetime.datetime.now().year
                try:
                    ret_date = datetime.datetime.strptime(f"{current_year}-{return_date}", "%Y-%m-%d").date()
                except ValueError:
                    dispatcher.utter_message(text="Please provide a valid return date.")
                    return [SlotSet("returnDate", None)]
            
            # Validate return date is after departure date
            if ret_date <= dep_date:
                dispatcher.utter_message(text="Return date must be after departure date.")
                return [SlotSet("returnDate", None)]
                
            return [SlotSet("returnDate", ret_date.strftime("%Y-%m-%d"))]
            
        except Exception:
            dispatcher.utter_message(text="Invalid date format.")
            return [SlotSet("returnDate", None)]

class ActionSearchFlights(Action):
    def name(self) -> Text:
        return "action_search_flights"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get slots
        departure_city = tracker.get_slot("departure_city")
        destination = tracker.get_slot("destination")
        departure_date = tracker.get_slot("departureDate")
        return_date = tracker.get_slot("returnDate")
        number_of_pax = tracker.get_slot("number_of_pax")
        
        # Validate required slots
        if not departure_city or not destination or not departure_date:
            dispatcher.utter_message(text="I need your departure city, destination, and departure date to search for flights.")
            return []
        
        # Initialize Flight service
        flight_service = FlightService()
        
        try:
            # Format dates
            # Assuming departure_date is in a recognizable format
            formatted_departure_date = departure_date
            formatted_return_date = return_date if return_date else None
            
            # Get number of passengers
            pax = int(number_of_pax) if number_of_pax else 1
            
            # Search for flights using the flight service
            flight_result = flight_service.get_flight_offers(
                departure=departure_city,
                destination=destination,
                departure_date=formatted_departure_date,
                return_date=formatted_return_date,
                num_adults=int(pax)
            )
            
            if flight_result and "data" in flight_result and flight_result["data"]:
                flight_offers = flight_result["data"]
                # Store flight offers in a slot for later use
                dispatcher.utter_message(response="utter_flights_found")
                
                # Format and display flight options
                for i, offer in enumerate(flight_offers[:3]):  # Show top 3 offers
                    price = offer.get("price", {}).get("total", "N/A")
                    currency = offer.get("price", {}).get("currency", "USD")
                    
                    # Extract flight details
                    itineraries = offer.get("itineraries", [])
                    outbound = itineraries[0] if itineraries else {}
                    inbound = itineraries[1] if len(itineraries) > 1 else None
                    
                    # Format outbound flight
                    outbound_segments = outbound.get("segments", [])
                    outbound_info = f"Outbound: {departure_city} to {destination}"
                    if outbound_segments:
                        first_segment = outbound_segments[0]
                        last_segment = outbound_segments[-1]
                        departure_time = first_segment.get("departure", {}).get("at", "")
                        arrival_time = last_segment.get("arrival", {}).get("at", "")
                        outbound_info += f" ({departure_time} - {arrival_time})"
                    
                    # Format inbound flight if it exists
                    inbound_info = ""
                    if inbound:
                        inbound_segments = inbound.get("segments", [])
                        inbound_info = f"\nReturn: {destination} to {departure_city}"
                        if inbound_segments:
                            first_segment = inbound_segments[0]
                            last_segment = inbound_segments[-1]
                            departure_time = first_segment.get("departure", {}).get("at", "")
                            arrival_time = last_segment.get("arrival", {}).get("at", "")
                            inbound_info += f" ({departure_time} - {arrival_time})"
                    
                    # Display flight offer
                    flight_message = f"Option {i+1}: {price} {currency}\n{outbound_info}{inbound_info}"
                    dispatcher.utter_message(text=flight_message)
                
                return [SlotSet("flight_offers", flight_offers)]
            else:
                dispatcher.utter_message(text="I couldn't find any flights matching your criteria. Would you like to try different dates or destinations?")
                return [SlotSet("flight_offers", None)]
            
        except Exception as e:
            dispatcher.utter_message(text=f"I encountered an error while searching for flights: {str(e)}")
            return []


class ActionConfirmFlightDetails(Action):
    def name(self) -> Text:
        return "action_confirm_flight_details"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get slots
        departure_city = tracker.get_slot("departure_city")
        destination = tracker.get_slot("destination")
        departure_date = tracker.get_slot("departureDate")
        return_date = tracker.get_slot("returnDate")
        number_of_pax = tracker.get_slot("number_of_pax") or "1"
        
        # Confirm details with the user
        dispatcher.utter_message(
            response="utter_confirm_flight_details",
            departure_city=departure_city,
            destination=destination,
            departureDate=departure_date,
            returnDate=return_date or "N/A (one-way)",
            number_of_pax=number_of_pax
        )
        
        return []


class ActionBookFlight(Action):
    def name(self) -> Text:
        return "action_book_flight"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get flight offers from slot
        flight_offers = tracker.get_slot("flight_offers")
        
        if not flight_offers:
            dispatcher.utter_message(text="I don't have any flight offers to book. Let's search for flights first.")
            return []
        
        # In a real implementation, you would:
        # 1. Get the selected flight from the user
        # 2. Call the Amadeus flight booking API
        # 3. Process payment
        # 4. Confirm booking
        
        # For this example, we'll just simulate a successful booking
        dispatcher.utter_message(response="utter_flight_booked")
        
        # Clear flight offers slot after booking
        return [SlotSet("flight_offers", None)]


class ActionResetFlightBooking(Action):
    def name(self) -> Text:
        return "action_reset_flight_booking"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Reset all flight booking related slots
        return [
            SlotSet("departure_city", None),
            SlotSet("destination", None),
            SlotSet("departureDate", None),
            SlotSet("returnDate", None),
            SlotSet("number_of_pax", "1"),
            SlotSet("flight_offers", None)
        ]
