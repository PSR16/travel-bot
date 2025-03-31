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
        

