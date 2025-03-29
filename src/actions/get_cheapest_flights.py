from typing import Any, Dict, List, Text
import requests
import json
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

# Load environment variables
load_dotenv()

# Amadeus API credentials and endpoints
CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")
AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
FLIGHT_DESTINATIONS_URL = "https://test.api.amadeus.com/v1/shopping/flight-destinations"
CHEAPEST_FLIGHT_URL = "https://test.api.amadeus.com/v1/shopping/flight-dates" ## given both from and to, search for cheapest dates
AIRPORT_SEARCH_URL = os.getenv("AMADEUS_AIRPORT_SEARCH_URL", "https://test.api.amadeus.com/v1/reference-data/locations")

class ActionGetCheapestFlights(Action):
    def name(self) -> Text:
        return "action_get_cheapest_flights"

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
        departure = tracker.get_slot("departure")
        destination = tracker.get_slot("destination")
        duration = tracker.get_slot("duration")
        maxPrice = tracker.get_slot("maxPrice")
        oneWay = tracker.get_slot("oneWay")

        travel_budget = tracker.get_slot("travel_budget")
        # Get the Bearer token
        access_token = self.get_access_token()
        if not access_token:
            dispatcher.utter_message(text="I'm having trouble connecting to the flight database. Please try again later.")
            return []
    
        dep_iata_code = self.get_iata_code(access_token, departure, dispatcher)
        print("IATACODE" + dep_iata_code)

        # Build API request parameters
        params = {"origin": dep_iata_code.upper()}
        if destination:
            url = CHEAPEST_FLIGHT_URL
            arr_iata_code = self.get_iata_code(access_token, destination, dispatcher)
            print("IATACODE" + arr_iata_code)

            params["destination"] = arr_iata_code
        else: 
            url = FLIGHT_DESTINATIONS_URL

        if maxPrice:
            params["maxPrice"] = maxPrice
        elif travel_budget:
            params["maxPrice"] = travel_budget
            
        if duration:
            params["duration"] = duration
        if oneWay:
            params["oneWay"] = oneWay

        headers = {"Authorization": f"Bearer {access_token}"}

        print(params)

        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "data" not in data or not data["data"]:
                dispatcher.utter_message(text="I couldn't find any destinations matching your criteria. Would you like to adjust your preferences?")
                return []

            # Extract top 3 destinations
            destinations = data["data"]
            show_destinations = destinations[:3]
            print(destinations)
            # Generate response message
            response_message = "These are some flight suggestions for you:\n\n"

            for i, flight in enumerate(show_destinations):
                flight_text = (
                    f"✈️ **Flight {i+1}**\n"
                    f"🛫 From: {flight['origin']} "
                    f"🛬 To: {flight['destination']}"
                    f"📅 Depart: {flight['departureDate']}\n"
                    f"📅 Return: {flight['returnDate']}\n"
                    f"💰 Price: ${flight['price'].get('total', 'Unavailable')}"
                )
                response_message += flight_text + "\n"

            dispatcher.utter_message(text=response_message)

            return [SlotSet("flight_suggestions", destinations), SlotSet("success", "success")]

        except requests.exceptions.RequestException as e:
            dispatcher.utter_message(text="Sorry, I ran into an issue while searching for flights. Please try again later.")
            print(f"Error fetching flight data: {e}")
            return [SlotSet("success", "failure")]

class ActionGetMoreCheapestFlights(Action):
    def name(self) -> Text:
        return "action_get_more_cheapest_flights"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        print("HERE")
        destinations = tracker.get_slot("flight_suggestions")
       # index = tracker.get_slot("index")
        print(destinations)

        if len(destinations) > 3:
            show_destinations = destinations[3:6]
            dispatcher.utter_message(text="Here are the next 3 flight suggestions:")
        else:
            show_destinations = destinations
            dispatcher.utter_message(text="Here are all the flight suggestions:")

        response_message = "These are some flight suggestions for you:\n\n"

        for i, flight in enumerate(show_destinations):
            flight_text = (
                f"✈️ **Flight {i+1}**\n"
                f"🛫 From: {flight['origin']} "
                f"🛬 To: {flight['destination']}"
                f"📅 Depart: {flight['departureDate']}\n"
                f"📅 Return: {flight['returnDate']}\n"
                f"💰 Price: ${flight['price'].get('total', 'Unavailable')}"
            )
            response_message += flight_text + "\n"

        dispatcher.utter_message(text=response_message)

        return []
