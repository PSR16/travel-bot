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


class ActionGetTravelBudgetHistory(Action):
    def name(self) -> Text:
        return "action_get_travel_budget_history"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get YNAB credentials from environment variables
        ACCESS_TOKEN = os.environ.get("YNAB_ACCESS_TOKEN")
        BUDGET_ID = os.environ.get("YNAB_BUDGET_ID")
        CATEGORY_NAME = "Travel"
        
        if not ACCESS_TOKEN or not BUDGET_ID:
            dispatcher.utter_message(text="Sorry, I couldn't access your budget information. Please check your configuration.")
            return []
        
        try:
            # Get the current date and date from 3 months ago
            today = datetime.now()
            three_months_ago = today - timedelta(days=90)
            since_date = three_months_ago.strftime("%Y-%m-%d")
            
            # YNAB API endpoint for transactions
            url = f"https://api.youneedabudget.com/v1/budgets/{BUDGET_ID}/transactions?since_date={since_date}"
            headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
            
            # Make the API request
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            # Get category ID for Travel
            category_url = f"https://api.youneedabudget.com/v1/budgets/{BUDGET_ID}/categories"
            category_response = requests.get(category_url, headers=headers)
            category_response.raise_for_status()
            category_data = category_response.json()
            
            travel_category_id = None
            for category_group in category_data['data']['category_groups']:
                for category in category_group['categories']:
                    if category['name'] == CATEGORY_NAME:
                        travel_category_id = category['id']
                        break
                if travel_category_id:
                    break
            
            if not travel_category_id:
                dispatcher.utter_message(text=f"I couldn't find a '{CATEGORY_NAME}' category in your budget.")
                return []
            
            # Filter transactions for the Travel category
            travel_transactions = [
                t for t in data['data']['transactions'] 
                if t.get('category_id') == travel_category_id
            ]
            
            if not travel_transactions:
                dispatcher.utter_message(text=f"You haven't had any travel expenses in the last 3 months.")
                return []
            
            # Sort transactions by date (newest first)
            travel_transactions.sort(key=lambda x: x['date'], reverse=True)
            
            # Format the response
            message = f"Here are your recent travel expenses (last 3 months):\n"
            
            # Show up to 5 most recent transactions
            for i, transaction in enumerate(travel_transactions[:5]):
                amount = abs(transaction['amount'] / 1000)  # Convert from milliunits and make positive
                date = datetime.strptime(transaction['date'], "%Y-%m-%d").strftime("%b %d")
                payee = transaction.get('payee_name', 'Unknown')
                
                message += f"- {date}: ${amount:.2f} to {payee}\n"
            
            # Add total spent
            total_spent = sum(abs(t['amount'] / 1000) for t in travel_transactions)
            message += f"\nTotal travel spending (last 3 months): ${total_spent:.2f}"
            
            dispatcher.utter_message(text=message)
            return []
            
        except requests.exceptions.RequestException as e:
            dispatcher.utter_message(text=f"Sorry, I encountered an error while retrieving your transactions: {str(e)}")
            return []
        except (KeyError, ValueError) as e:
            dispatcher.utter_message(text=f"Sorry, I had trouble processing your transaction information: {str(e)}")
            return []
