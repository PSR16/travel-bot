import requests
import os
from dotenv import load_dotenv
from typing import Any, Dict, List, Text
from rasa_sdk import Action
from rasa_sdk.events import SlotSet

# Amadeus API Credentials
load_dotenv()

# Amadeus API Credentials from environment variables
CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")
AUTH_URL = os.getenv("AMADEUS_AUTH_URL", "https://test.api.amadeus.com/v1/security/oauth2/token")
FLIGHT_SEARCH_URL = os.getenv("AMADEUS_FLIGHT_SEARCH_URL", "https://test.api.amadeus.com/v1/shopping/flight-destinations")
AIRPORT_SEARCH_URL = os.getenv("AMADEUS_AIRPORT_SEARCH_URL", "https://test.api.amadeus.com/v1/reference-data/locations")

class ActionSuggestTrip(Action):
    def name(self) -> Text:
        return "suggest_a_trip"

    def get_access_token(self) -> str:
        """Fetch a Bearer token from Amadeus API"""
        payload = {
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = requests.post(AUTH_URL, data=payload, headers=headers)
            response.raise_for_status()
            return response.json().get("access_token")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching access token: {e}")
            return None

    def get_iata_code(self, access_token, departure, dispatcher) -> str:
        # Call Amadeus API to get the IATA code
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"keyword": departure, "subType": "AIRPORT,CITY"}

        response = requests.get(AIRPORT_SEARCH_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if "data" in data and data["data"]:
            iata_code = data["data"][0]["iataCode"]  # Take the first match
            print(iata_code)
        else:
            dispatcher.utter_message(text=f"Sorry, I couldn't find an IATA airport code for {departure}.")
            return []

        return iata_code
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Get user-provided slots
        departure = tracker.get_slot("trip_departure_city")
        budget = tracker.get_slot("budget")
        duration = tracker.get_slot("length_of_trip")

        # Get the Bearer token
        access_token = self.get_access_token()
        if not access_token:
            dispatcher.utter_message(text="I'm having trouble connecting to the flight database. Please try again later.")
            return []
    
        iata_code = self.get_iata_code(access_token, departure, dispatcher)
        print(iata_code)

        # Build API request parameters
        params = {"origin": iata_code.upper()}
        if budget:
            params["maxPrice"] = budget
        if duration:
            params["duration"] = duration

        headers = {"Authorization": f"Bearer {access_token}"}

        print(params)

        try:
            response = requests.get(FLIGHT_SEARCH_URL, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "data" not in data or not data["data"]:
                dispatcher.utter_message(text="I couldn't find any destinations matching your criteria. Would you like to adjust your preferences?")
                return []

            # Extract top 5 destinations
            destinations = data["data"][:5]
            print(destinations)
            # Generate response message
            response_message = "These are some flight suggestions for you:\n\n"

            for i, flight in enumerate(destinations):
                flight_text = (
                    f"✈️ **Flight {i+1}**\n"
                    f"🛫 From: {flight['origin']}\n"
                    f"🛬 To: {flight['destination']}\n"
                    f"📅 Departure: {flight['departureDate']}\n"
                    f"📅 Return: {flight['returnDate']}\n"
                    f"💰 Price: ${flight['price'].get('total', 'Unavailable')}\n"
                )
                if "flightOffers" in flight.get("links", {}):
                    flight_text += f"🔗 [View Flight Offers]({flight['links']['flightOffers']})\n"

                response_message += flight_text + "\n"

            dispatcher.utter_message(text=response_message)

            return [SlotSet("return_value", "success")]

        except requests.exceptions.RequestException as e:
            dispatcher.utter_message(text="Sorry, I ran into an issue while searching for flights. Please try again later.")
            print(f"Error fetching flight data: {e}")
            return []