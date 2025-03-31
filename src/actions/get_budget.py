from typing import Any, Dict, List, Text
from dotenv import load_dotenv

from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from services.ynab_service import YNABService

# Load environment variables
load_dotenv()

class ActionGetTravelBudget(Action):
    def name(self) -> Text:
        return "action_get_travel_budget"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        ynab_service = YNABService()
        budget_info = ynab_service.get_travel_budget()
        
        if not budget_info:
            dispatcher.utter_message(text="Sorry, I couldn't access your budget information. Please check your configuration.")
            return []
        
        budgeted, activity, balance = budget_info
        
        # Set slots with the budget information
        return [
            SlotSet("travel_budget", budgeted),
            # SlotSet("travel_budget_spent", abs(activity)),
            # SlotSet("travel_budget_remaining", balance)
        ]
