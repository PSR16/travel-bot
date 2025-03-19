from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

class ActionProvideLostBaggageInfo(Action):
    def name(self) -> Text:
        return "action_provide_lost_baggage_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get slot values
        airport = tracker.get_slot("airport")
        airline = tracker.get_slot("airline")
        
        # Prepare the prompt for ChatGPT
        prompt = f"""
        A passenger has lost their baggage at {airport} airport while flying with {airline}.
        Look for accurate steps and information on how to report and track their lost baggage.
        This information is often provided on the airline's website or through the airline's customer service.

        Provide helpful information about:
        The typical lost baggage procedure for {airline}
        Format the response in a clear, concise, and helpful manner.

        Focus on the immediate steps they can take. 

        If there are any links for a form to fill out, provide a link.
        """
        
        """
        2. Contact information for {airline}'s lost baggage department at {airport}
        3. Steps the passenger should take to report and track their lost baggage
        4. Estimated timeline for baggage recovery
        5. Compensation policies if applicable
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
            baggage_info = response_data["choices"][0]["message"]["content"]
            
            # Send the response to the user
            dispatcher.utter_message(text=baggage_info)
            
        except Exception as e:
            # Fallback response in case of API failure
            dispatcher.utter_message(text=f"I recommend contacting {airline}'s lost baggage counter at {airport} airport as soon as possible. You should have your boarding pass and baggage claim ticket ready. Most airlines also have an online baggage tracking system on their website or mobile app.")
            dispatcher.utter_message(text=f"Error details: {str(e)}")
        
        return []
