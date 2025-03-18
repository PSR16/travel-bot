from typing import Any, Dict, List, Text
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import requests
import json
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Amadeus API Credentials
load_dotenv()


class ActionSuggestActivities(Action):
    def name(self) -> Text:
        return "suggest_activities"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Get the city from slot
        city = tracker.get_slot("city")
        
        if not city:
            dispatcher.utter_message(text="I'm not sure which city you're asking about. Could you please specify?")
            return []
        
        # Get API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            dispatcher.utter_message(text="Sorry, I'm having trouble connecting to my suggestion service.")
            return []
        
        # Prepare the prompt for ChatGPT
        prompt = f"""
        Suggest 5 popular activities or attractions in {city}. 
        
        Return ONLY a valid JSON object with the following structure:
        {{
            "activities": [
                {{
                    "name": "Activity name",
                    "description": "Brief description",
                    "category": "Category (e.g., Outdoor, Cultural, Food, etc.)"
                }},
                ...
            ]
        }}
        
        Do not include any explanations, only provide the JSON response.
        """
        
        try:
            # Make request to OpenAI API
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "You are a helpful travel assistant that provides information about activities in cities."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract the content from the response
            content = result["choices"][0]["message"]["content"]
            
            # Parse the JSON response
            activities_data = json.loads(content)
            
            # Format the response for the user
            message = f"Here are some activities you might enjoy in {city}:\n\n"
            
            for idx, activity in enumerate(activities_data["activities"], 1):
                message += f"{idx}. **{activity['name']}** ({activity['category']})\n"
                message += f"   {activity['description']}\n\n"
            
            dispatcher.utter_message(text=message)
            
            # Store the activities in a slot for potential follow-up questions
            return [SlotSet("activities", activities_data["activities"])]
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error making request to OpenAI API: {e}")
            dispatcher.utter_message(text="Sorry, I couldn't fetch activity suggestions at the moment. Please try again later.")
            return []
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing response from OpenAI API: {e}")
            dispatcher.utter_message(text="I received information about activities, but couldn't process it correctly.")
            return []
