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

class ActionGetTravelBudget(Action):
    def name(self) -> Text:
        return "action_get_travel_budget"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get YNAB credentials from environment variables
        ACCESS_TOKEN = os.environ.get("YNAB_ACCESS_TOKEN")
        BUDGET_ID = os.environ.get("YNAB_BUDGET_ID")
        CATEGORY_NAME = os.environ.get("YNAB_TRAVEL_CATEGORY")
        
        if not ACCESS_TOKEN or not BUDGET_ID:
            dispatcher.utter_message(text="Sorry, I couldn't access your budget information. Please check your configuration.")
            return []
        
        try:
            # YNAB API endpoint for categories
            url = f"https://api.youneedabudget.com/v1/budgets/{BUDGET_ID}/categories/{CATEGORY_NAME}"
            headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
            
            # Make the API request
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            
            # Parse the response
            data = response.json()
            
            # Find the Travel category
            travel_category = data['data']['category']
            print(travel_category)
            # Extract budget information
            budgeted = travel_category['budgeted'] / 1000  # YNAB amounts are in milliunits
            balance = travel_category['balance'] / 1000
            activity = travel_category['activity'] / 1000
            
            # Set slots with the budget information
            return [
                SlotSet("travel_budget", budgeted),
                #SlotSet("travel_budget_spent", abs(activity)),
            #    SlotSet("travel_budget_remaining", balance)
            ]
            
        except requests.exceptions.RequestException as e:
            dispatcher.utter_message(text=f"Sorry, I encountered an error while retrieving your budget: {str(e)}")
            return []
        except (KeyError, ValueError) as e:
            dispatcher.utter_message(text=f"Sorry, I had trouble processing your budget information: {str(e)}")
            return []
