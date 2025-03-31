from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from datetime import datetime  
from services.flight_service import FlightService

# class ValidateReturnDate(Action):
#     def name(self) -> Text:
#         return "validate_returnDate"

#     def run(
#             self,
#             dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any],
#     ) -> List[Dict[Text, Any]]:
#         return_date = tracker.get_slot("returnDate")
#         departure_date = tracker.get_slot("departureDate")
        
#         if not return_date or not departure_date:
#             return []
            
#         try:
#             # Parse dates
#             dep_date = datetime.datetime.strptime(departure_date, "%Y-%m-%d").date()
            
#             # Try to parse return date or add current year
#             try:
#                 ret_date = datetime.datetime.strptime(return_date, "%Y-%m-%d").date()
#             except ValueError:
#                 current_year = datetime.datetime.now().year
#                 try:
#                     ret_date = datetime.datetime.strptime(f"{current_year}-{return_date}", "%Y-%m-%d").date()
#                 except ValueError:
#                     dispatcher.utter_message(text="Please provide a valid return date.")
#                     return [SlotSet("returnDate", None)]
            
#             # Validate return date is after departure date
#             if ret_date <= dep_date:
#                 dispatcher.utter_message(text="Return date must be after departure date.")
#                 return [SlotSet("returnDate", None)]
                
#             return [SlotSet("returnDate", ret_date.strftime("%Y-%m-%d"))]
            
#         except Exception:
#             dispatcher.utter_message(text="Invalid date format.")
#             return [SlotSet("returnDate", None)]

class ActionSearchFlights(Action):
    def name(self) -> Text:
        return "action_search_flights"

    def get_time_emoji(self, hour):
        if 5 <= hour < 8:  # Early morning/sunrise (5am-8am)
            return "🌅"
        elif 8 <= hour < 19:  # Daytime (8am-7pm)
            return "☀️"
        else:  # Nighttime (7pm-5am)
            return "🌙"
    
    def format_flight_offer(self, offer, index):
        """
        Format a flight offer into a user-friendly message
        """
        price = offer.get("price", {}).get("total", "N/A")
        currency = offer.get("price", {}).get("currency", "USD")
        
        # Extract flight details
        itineraries = offer.get("itineraries", [])
        outbound = itineraries[0] if itineraries else {}
        inbound = itineraries[1] if len(itineraries) > 1 else None
        
        # Format outbound journey
        outbound_segments = outbound.get("segments", [])
        if not outbound_segments:
            return f"Option {index}: No flight details available"
            
        # Get departure and arrival details for outbound
        first_segment = outbound_segments[0]
        last_segment = outbound_segments[-1]
        
        departure_iata = first_segment.get("departure", {}).get("iataCode", "")
        arrival_iata = last_segment.get("arrival", {}).get("iataCode", "")
        
        # Format departure and arrival times
        departure_datetime = datetime.fromisoformat(first_segment.get("departure", {}).get("at", "").replace('Z', '+00:00'))
        arrival_datetime = datetime.fromisoformat(last_segment.get("arrival", {}).get("at", "").replace('Z', '+00:00'))
        
        dep_time = departure_datetime.strftime("%H:%M")
        arr_time = arrival_datetime.strftime("%H:%M")
        
        # Add emoji based on time
        dep_hour = departure_datetime.hour
        arr_hour = arrival_datetime.hour
                
        dep_emoji = self.get_time_emoji(dep_hour)
        arr_emoji = self.get_time_emoji(arr_hour)

        # Format date
        formatted_date = departure_datetime.strftime("%b %d, %Y")
        
        # Get stops information
        stops = len(outbound_segments) - 1
        stops_text = "Direct" if stops == 0 else f"{stops} stop{'s' if stops > 1 else ''}"
        
        # Format duration
        duration = outbound.get("duration", "").replace('PT', '').replace('H', 'h ').replace('M', 'm')
                # Add price information
        price_msg = f"\n💰 {currency} {price}"
        # Create the outbound message
        outbound_msg = (
            f"Option {index}, {price_msg}\n"
            f"✈️ {departure_iata} → {arrival_iata}, 🛑 {stops_text}\n"
            f"📅 {formatted_date}\n"
            f"⏰ {dep_emoji} {dep_time} → {arr_emoji} {arr_time} ({duration})"
        )
        
        # Add return journey if it exists
        return_msg = ""
        if inbound:
            inbound_segments = inbound.get("segments", [])
            if inbound_segments:
                # Get departure and arrival details for inbound
                first_return_segment = inbound_segments[0]
                last_return_segment = inbound_segments[-1]
                
                return_departure_iata = first_return_segment.get("departure", {}).get("iataCode", "")
                return_arrival_iata = last_return_segment.get("arrival", {}).get("iataCode", "")
                
                # Format departure and arrival times
                return_departure_datetime = datetime.fromisoformat(first_return_segment.get("departure", {}).get("at", "").replace('Z', '+00:00'))
                return_arrival_datetime = datetime.fromisoformat(last_return_segment.get("arrival", {}).get("at", "").replace('Z', '+00:00'))
                
                ret_dep_time = return_departure_datetime.strftime("%H:%M")
                ret_arr_time = return_arrival_datetime.strftime("%H:%M")
                
                # Add emoji based on time
                ret_dep_hour = return_departure_datetime.hour
                ret_arr_hour = return_arrival_datetime.hour
                
                ret_dep_emoji = self.get_time_emoji(ret_dep_hour)
                ret_arr_emoji = self.get_time_emoji(ret_arr_hour)
                
                # Format date
                ret_formatted_date = return_departure_datetime.strftime("%b %d, %Y")
                
                # Get stops information
                ret_stops = len(inbound_segments) - 1
                ret_stops_text = "Direct" if ret_stops == 0 else f"{ret_stops} stop{'s' if ret_stops > 1 else ''}"
                
                # Format duration
                ret_duration = inbound.get("duration", "").replace('PT', '').replace('H', 'h ').replace('M', 'm')
                
                return_msg = (
                    f"\n🔄 Return: \n"
                    f"✈️ {return_departure_iata} → {return_arrival_iata}, 🛑 {ret_stops_text}\n"
                    f"📅 {ret_formatted_date}\n"
                    f"⏰ {ret_dep_emoji} {ret_dep_time} → {ret_arr_emoji} {ret_arr_time} ({ret_duration})\n"
                )
        
        # Combine all parts
        full_message = f"{outbound_msg}{return_msg}"
        
        return full_message
    

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get slots
        departure_city = tracker.get_slot("departure_city")
        destination = tracker.get_slot("destination")
        departure_date = tracker.get_slot("departureDate")
        return_date = tracker.get_slot("returnDate")
        number_of_pax = tracker.get_slot("number_of_pax")
        travel_class = tracker.get_slot("travel_class")
        maxPrice = int(tracker.get_slot("maxPrice") or tracker.get_slot("travel_budget"))
        
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
                num_adults=int(pax),
                travel_class=travel_class,
                max_price=maxPrice
            )
            
            if flight_result and "data" in flight_result and flight_result["data"]:
                flight_offers = flight_result["data"]
                # Store flight offers in a slot for later use
                dispatcher.utter_message(response="utter_flights_found")
                
                # Format and display flight options using the new formatting function
                for i, offer in enumerate(flight_offers[:3]):  # Show top 3 offers
                    formatted_message = self.format_flight_offer(offer, i+1)
                    dispatcher.utter_message(text=formatted_message)
                
                return [SlotSet("flight_offers", flight_offers)]
            else:
                dispatcher.utter_message(text="I couldn't find any flights matching your criteria. Would you like to try different dates or destinations?")
                return [SlotSet("flight_offers", None)]
            
        except Exception as e:
            dispatcher.utter_message(text=f"I encountered an error while searching for flights: {str(e)}")
            return [SlotSet("flight_offer_success", False)]


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
