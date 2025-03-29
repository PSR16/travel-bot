from typing import Any, Dict, List, Text
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
import requests
import os
import json
from actions.db import get_user_by_id, get_preferred_departure_city
from dotenv import load_dotenv
from datetime import datetime, timedelta
import calendar
import re
# Amadeus API Credentials
load_dotenv()

# Amadeus API Credentials from environment variables
CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")
AUTH_URL = os.getenv("AMADEUS_AUTH_URL", "https://test.api.amadeus.com/v1/security/oauth2/token")
FLIGHT_SEARCH_URL = os.getenv("AMADEUS_FLIGHT_SEARCH_URL", "https://test.api.amadeus.com/v1/shopping/flight-destinations")
AIRPORT_SEARCH_URL = os.getenv("AMADEUS_AIRPORT_SEARCH_URL", "https://test.api.amadeus.com/v1/reference-data/locations")

class ActionProcessTravelDates(Action):
    def name(self) -> Text:
        return "action_process_travel_dates"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        travel_timeframe = tracker.get_slot("travel_timeframe")
        if not travel_timeframe:
            return []
        
        # Convert to lowercase for easier matching
        timeframe = travel_timeframe.lower()
        
        # Get current date for reference
        current_date = datetime.now()
        departure_date = None
        return_date = None
        
        # Check for month names
        months = {month.lower(): i for i, month in enumerate(calendar.month_name) if month}
        for month_name, month_num in months.items():
            if month_name in timeframe:
                # If month is in the past for this year, assume next year
                year = current_date.year
                if month_num < current_date.month:
                    year += 1
                
                # Set to the 1st of the month
                departure_date = f"{year}-{month_num:02d}-01"
                # Set return date to last day of month
                last_day = calendar.monthrange(year, month_num)[1]
                return_date = f"{year}-{month_num:02d}-{last_day:02d}"
                break
        
        # Check for "next month"
        if "next month" in timeframe:
            next_month = current_date.month + 1
            year = current_date.year
            if next_month > 12:
                next_month = 1
                year += 1
            
            departure_date = f"{year}-{next_month:02d}-01"
            last_day = calendar.monthrange(year, next_month)[1]
            return_date = f"{year}-{next_month:02d}-{last_day:02d}"
        
        # Check for seasons
        seasons = {
            "spring": ("03-21", "06-20"),
            "summer": ("06-21", "09-22"),
            "fall": ("09-23", "12-20"),
            "autumn": ("09-23", "12-20"),
            "winter": ("12-21", "03-20")
        }
        
        for season, (start, end) in seasons.items():
            if season in timeframe:
                year = current_date.year
                start_month, start_day = map(int, start.split("-"))
                end_month, end_day = map(int, end.split("-"))
                
                # If we're past this season, use next year
                if (current_date.month > end_month or 
                    (current_date.month == end_month and current_date.day > end_day)):
                    year += 1
                
                # Handle winter spanning year boundary
                if season == "winter" and start_month > end_month:
                    departure_date = f"{year}-{start_month:02d}-{start_day:02d}"
                    return_date = f"{year+1}-{end_month:02d}-{end_day:02d}"
                else:
                    departure_date = f"{year}-{start_month:02d}-{start_day:02d}"
                    return_date = f"{year}-{end_month:02d}-{end_day:02d}"
                break
        
        # Check for specific date patterns (YYYY-MM-DD or MM/DD/YYYY)
        date_patterns = [
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})/(\d{1,2})/(\d{4})'   # MM/DD/YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, timeframe)
            if match:
                if pattern == r'(\d{4})-(\d{1,2})-(\d{1,2})':
                    year, month, day = match.groups()
                else:  # MM/DD/YYYY
                    month, day, year = match.groups()
                
                departure_date = f"{year}-{int(month):02d}-{int(day):02d}"
                # Set return date to 7 days later by default
                return_date_obj = datetime(int(year), int(month), int(day)) + timedelta(days=7)
                return_date = return_date_obj.strftime("%Y-%m-%d")
                break
        
        # If we couldn't determine dates, use defaults (next month)
        if not departure_date:
            next_month = current_date.month + 1
            year = current_date.year
            if next_month > 12:
                next_month = 1
                year += 1
            
            departure_date = f"{year}-{next_month:02d}-15"
            return_date_obj = datetime(year, next_month, 15) + timedelta(days=7)
            return_date = return_date_obj.strftime("%Y-%m-%d")
            
            dispatcher.utter_message(text=f"I'll look for flights around {departure_date}.")
        
        return [
            SlotSet("departureDate", departure_date),
            SlotSet("returnDate", return_date)
        ]
    
class ActionGetDepartureLocation(Action):
    def name(self) -> Text:
        return "action_get_departure_location"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the user ID from the tracker
        user_id = tracker.get_slot("user_id")
        print("userID" , user_id)
        if not user_id:
            dispatcher.utter_message(text="I don't know who you are. Please provide your departure city.")
            return []
        
        # Get the preferred departure city from the database
        departure_city = get_preferred_departure_city(user_id)
        
        if departure_city:
            #dispatcher.utter_message(text=f"I'll use your preferred departure city: {departure_city}")
            return [SlotSet("departure_city", departure_city)]
        else:
            #dispatcher.utter_message(text="I don't have your preferred departure city saved. Please provide it.")
            return []
        
class ActionSuggestTrip(Action):
    def name(self) -> Text:
        return "action_suggest_a_trip"

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
        departure = tracker.get_slot("departure_city")
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
            destinations = data["data"][:3]
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

class ActionSuggestSurpriseTrip(Action):
    def name(self) -> Text:
        return "action_surprise_trip"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Prepare the prompt for ChatGPT

        departure_city = tracker.get_slot("departure_city")
        trip_budget = tracker.get_slot("trip_budget")
        dom_or_int = tracker.get_slot("dom_or_int")
        duration = tracker.get_slot("duration")

        # Base prompt
        prompt = """
        Generate a surprise travel destination suggestion for an adventurous traveler.
        """

        # Add dynamic constraints based on available slots
        if departure_city:
            prompt += f"\nThe traveler will be departing from {departure_city}."
        
        if trip_budget:
            prompt += f"\nThe traveler has a budget of approximately {trip_budget}. It is important you consider this information."
        
        if dom_or_int:
            if dom_or_int.lower() == "domestic":
                prompt += "\nPlease suggest a domestic destination within the traveler's country."
            elif dom_or_int.lower() == "international":
                prompt += "\nPlease suggest an international destination outside the traveler's country."
        
        if duration:
            prompt += f"\nThe trip will last for {duration}. This is an important factor to take into consideration. Make sure the trip recommendation is reasonable to do in this time frame especially if a budget is provided." ### consider days/weeks
        

        # Add the rest of the prompt
        prompt += """
        Make sure the budget is realistic for the destination and includes accommodation, food, local transportation, and key activities.
        Keep the entire response concise and engaging, focusing only on these four elements.

        Your response must follow this information:

        📍 Destination: [City, Country] or [City, State]
        📆 Best Time: [Season or months to visit]
        🎭 Must-Do: [2-3 key activities or experiences]
        💰 Budget Estimate: ~$[Amount] for [X] days

        Do not include any additional information or formatting beyond what is specified above.

        Return the data in a JSON Format as follow:

            {
                "destination": "Tulum, Mexico",
                "duration": "4 days",
                "budget": "$X",
                "stay": "Hotel ",
                "activities": ["Snorkeling", "Mayan ruins", "Cenotes"]
            }
        Only return the fields: destination, duration, budget, stay, activities. 
        """

        try:
            # Call ChatGPT API
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found in environment variables")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "gpt-4",  # or whichever model you prefer
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 200
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            response_data = response.json()
            print(response_data)
            surprise_trip = json.loads(response_data["choices"][0]["message"]["content"])
            print(surprise_trip)
            # Parse the JSON response
            destination = surprise_trip.get("destination", "Unknown location")
            duration = surprise_trip.get("duration", "")
            budget = surprise_trip.get("budget", "")
            stay = surprise_trip.get("stay", "")
            activities = surprise_trip.get("activities", [])
            
            # Build the message
            message = f"🌍 *{destination}* ({duration})\n"
            
            if budget:
                message += f"💰 *Budget:* {budget}\n"
            
            if stay:
                message += f"🏠 *Accommodation:* {stay}\n"
            
            if activities:
                message += f"🎯 *Top Activities:*\n"
                for idx, activity in enumerate(activities, 1):
                    message += f" {idx}. {activity}\n"            

            print(message)
            # Send the response to the user
            dispatcher.utter_message("Here's a surprise trip suggestion for you!")
            dispatcher.utter_message(text=message)
            
        except Exception as e:
            # Fallback response in case of API failure
            dispatcher.utter_message(text="I'm sorry, I couldn't generate a surprise trip suggestion at the moment. Please try again later.")
            print(f"Error details: {str(e)}")
        
        return [SlotSet("destination", destination), SlotSet("suggested_trip_text", message)]

class ActionSuggestSimpleTrip(Action):
    def name(self) -> Text:
        return "action_suggest_a_simple_trip"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Get user-provided slots
        trip_setting = tracker.get_slot("trip_setting")
        dom_or_int = tracker.get_slot("dom_or_int")
        trip_budget = tracker.get_slot("trip_budget")
        duration = tracker.get_slot("duration")

         # Prepare the prompt for ChatGPT
        prompt = f"""
        Generate personalized travel destination suggestions based on the following preferences:
        
        Setting preference: {trip_setting if trip_setting else "Any"}
        Travel scope: {dom_or_int if dom_or_int else "Any (domestic or international)"}
        Budget level: {trip_budget if trip_budget else "Not specified"} Focus on the budget for the entire trip. 
        Trip duration: {duration if duration else "Not specified"} days. Be realistic on the destinations that can be enjoyed within the specified duration. 
        For example, a national park visit requires more than 2 or 3 days often. 
        
        Suggest ONLY ONE destinations that would be a good fit for these preferences. 
        Format the response in a clear, concise, and engaging manner suitable for a travel chatbot response.

        Return ONLY the destination with some detail feasible for a chat or a text message.
        It is preferred to add some information surrounding cost even if it is a range. 

        Return the destination in JSON FORMAT similar to this: 

        {
            "destination": "Tulum, Mexico",
            "duration": "4 days",
            "budget": "Mid-range",
            "stay": "Beachfront Airbnb",
            "activities": ["Snorkeling", "Mayan ruins", "Cenotes"]
        }

        Ensure you are only returning a JSON format
        """

        try:
            # Call ChatGPT API
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found in environment variables")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "gpt-4",  # or whichever model you prefer
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 300
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            response_data = response.json()
            print(response_data)
            suggested_trips = response_data["choices"][0]["message"]["content"]
            print(suggested_trips)

            # Send the response to the user
            #dispatcher.utter_message(text=suggested_trips)
            
        except Exception as e:
            # Fallback response in case of API failure
            dispatcher.utter_message(text=f"Here are some travel suggestions")
            dispatcher.utter_message(text=f"Error details: {str(e)}")
        
        return [SlotSet("suggested_trip_text", suggested_trips)]
        
class ActionSuggestDetailedTripInfo(Action):
    def name(self) -> Text:
        return "action_suggest_detailed_trip_info"
    
    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        # Get user-provided slots
        departure_city = tracker.get_slot("departure_city")
        preferred_transportation = tracker.get_slot("preferred_transportation")
        special_requirements = tracker.get_slot("special_requirements")
        accomodation_preferences = tracker.get_slot("accomodation_preferences")
        trip_season = tracker.get_slot("trip_season")
        activity_preferences = tracker.get_slot("activity_preferences")

        suggested_trip = tracker.get_slot("suggested_trip_text")
        destination = tracker.get_slot("destination")
        # Prepare the prompt for ChatGPT
        prompt = f"""
        Expand on the following trip suggestion with more details:
        {suggested_trip}. 
        
        It is absolutely critical that you do not deviate from this suggestion, but elevate it.

        Additional information to include in the itinerary generation is:

        Departure City: {departure_city or 'Not specified'}
        Preferred Transportation: {preferred_transportation or 'Not specified'}
        Special Requirements: {special_requirements or 'None'}
        Accommodation Preferences: {accomodation_preferences or 'Not specified'}
        Travel Season: {trip_season or 'Not specified'}
        Activity Preferences: {activity_preferences or 'Not specified'}
    
        Please elaborate on the trip suggestion by:
        1. Recommending more specific transport. 
        For example, if the user prefers airports, try to combine the budget and known flights from their departure city to destination. 
        Use this to make the budget more accurate.
        2. Suggesting an itinerary with day-by-day activities. Be very cognizant of the budget. If you have to go over, be conservative.
        3. Providing transportation options from {departure_city or 'their location'}
        4. Recommending suitable accommodations based on their preferences. If you can find historical information on price, integrate it into the total budget.
        Do make a separate line item. Again, be aware of the prices and make a good judgement. 
        5. Highlighting seasonal attractions or considerations for {trip_season or 'their travel time'}
        6. Including activities that align with their stated preferences. Keep this concise and relevant to the trip. No need to detail a day by day itinerary.
        7. Addressing any special requirements in your recommendations
    
         Return ONLY valid JSON format without any additional text or explanation. Example format:
        """
        prompt += """
        {
            "destination": "Tulum, Mexico",
            "duration": "4 days",
            "summary": "A summary of the trip in a few concise lines", 
            "budget": {
                "total": "$1,200-1,500 USD (mid-range)",
                "flight": "$350-450 USD round-trip",
                "accommodation": "$480-720 total",
                "food": "$120-200 total",
                "activities": "$150-200 USD total",
                "transportation": "$50-100 USD total"
            },
            "travel": {
                "departure_airport": "Miami International Airport (MIA)",
                "arrival_airport": "Cancún International Airport (CUN)",
                "airline_options": ["American Airlines", "JetBlue", "United"],
                "flight_duration": "Approximately 2 hours",
                "ground_transfer": "1.5-hour drive from Cancún to Tulum (taxi ~$80 USD or shared shuttle ~$45 USD)"
            },
            "accommodation": {
                "type": "Beachfront Airbnb",
                "location": "Tulum Beach Zone",
                "amenities": ["Private beach access", "Wi-Fi", "kitchen", "air conditioning"],
                "rating": "4.8/5 stars",
                "check_in": "3:00 PM",
                "check_out": "11:00 AM"
            },
            "activities": [
                {"name": "Snorkeling at Tulum Reef", "cost": "$40-60 USD for guided tour"},
                {"name": "Exploring Tulum Archaeological Zone", "cost": "$4 USD entrance fee"},
                {"name": "Swimming in Gran Cenote", "cost": "$25 USD entrance fee"},
                {"name": "Visit to Cenote Dos Ojos", "cost": "$15 USD entrance fee"},
                {"name": "Bike rental for local exploration", "cost": "$10 USD per day"},
                {"name": "Yoga class on the beach", "cost": "$15-20 USD"}
            ],
            "special_notes": "The beach zone has limited accessibility options, but several resorts offer accessible rooms and beach access."
        }

        Again, ensure ONLY JSON format. Double Check this. 
        """


        print(prompt)
        try:
            # Call ChatGPT API
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API key not found in environment variables")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "gpt-4",  # or whichever model you prefer
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 400
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            response_data = response.json()
            print(response_data)
            # Validate response structure
            if not response_data.get("choices") or not response_data["choices"]:
                raise ValueError("Invalid response format: 'choices' field missing or empty")
            
            try:
                content = response_data["choices"][0]["message"]["content"]
                itinerary = json.loads(content)
            except (KeyError, json.JSONDecodeError) as e:
                raise ValueError(f"Failed to parse response content: {str(e)}")
            
            # Extract data with proper default values and correct spelling
            summary = itinerary.get("summary", "None")
            detailed_budget = itinerary.get("budget", {})
            detailed_accommodation = itinerary.get("accommodation", {})  # Corrected spelling
            detailed_activities = itinerary.get("activities", [])
            detailed_travel = itinerary.get("travel", {})
            print(itinerary)
            # Send the response to the user
            dispatcher.utter_message(text=summary)
            return [SlotSet("detailed_budget", detailed_budget), SlotSet("detailed_accomodation", detailed_accommodation), SlotSet("detailed_activities", detailed_activities), SlotSet("detailed_travel", detailed_travel)]

        except Exception as e:
            # Fallback response in case of API failure
            dispatcher.utter_message(text=f"Error details: {str(e)}")
        
    
