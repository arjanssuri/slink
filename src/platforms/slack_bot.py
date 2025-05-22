import os
import logging
import json
import re
import time
from typing import Dict, Any, List, Optional, Tuple
import threading
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import dotenv
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.platforms.slack import SlackConfiguration, User as SlackUser
from src.core.linkedin_scraper import LinkedInScraper
from src.core.similarity_calculator import SimilarityCalculator

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

class SlackBot:
    """
    A Slack bot that responds to DMs and can find similar profiles based on LinkedIn data.
    """
    def __init__(self):
        self.bot_token = os.environ.get("SLACK_BOT_TOKEN")
        
        if not self.bot_token:
            logger.error("SLACK_BOT_TOKEN must be set in environment variables")
            raise ValueError("Missing required environment variables")
            
        self.client = WebClient(token=self.bot_token)
        
        # Get the bot's user ID
        auth_response = self.client.auth_test()
        self.bot_id = auth_response["user_id"]
        self.bot_name = auth_response["user"]
        logger.info(f"Bot initialized with ID: {self.bot_id}, name: {self.bot_name}")
        
        self.slack_config = SlackConfiguration()
        self.linkedin_scraper = LinkedInScraper()
        self.similarity_calculator = SimilarityCalculator()
        
        # Store conversation state for each user
        self.conversations = {}
        
        # Processed message IDs to avoid duplicates
        self.processed_messages = set()
        
    def start(self):
        """Start the bot and listen for events."""
        logger.info("Bot starting up...")
        logger.info(f"Bot is ready. Send a direct message to @{self.bot_name} to start.")
        
        # Check for new DMs periodically
        try:
            while True:
                self.check_direct_messages()
                time.sleep(1)  # Check every 1 second
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
    
    def check_direct_messages(self):
        """Check for direct messages to the bot."""
        try:
            # Get list of DMs
            dm_response = self.client.conversations_list(types="im")
            
            for dm in dm_response["channels"]:
                channel_id = dm["id"]
                
                try:
                    # Get recent messages
                    history_response = self.client.conversations_history(
                        channel=channel_id,
                        limit=5
                    )
                    
                    for message in history_response["messages"]:
                        # Skip messages we've already processed
                        if message.get("ts") in self.processed_messages:
                            continue
                        
                        # Add to processed messages
                        self.processed_messages.add(message.get("ts"))
                        
                        # Skip bot's own messages
                        if message.get("user") == self.bot_id:
                            continue
                        
                        user_id = message.get("user")
                        text = message.get("text", "")
                        ts = message.get("ts")
                        
                        logger.info(f"Received DM from {user_id}: {text}")
                        
                        # Check if user is in a conversation
                        if user_id in self.conversations:
                            self._continue_conversation(channel_id, user_id, text)
                        else:
                            # Start new conversation
                            self.start_conversation(channel_id, user_id, ts)
                            
                except SlackApiError as e:
                    logger.error(f"Error checking DM history for {channel_id}: {e}")
        
        except SlackApiError as e:
            logger.error(f"Error checking DMs: {e}")
    
    def start_conversation(self, channel_id: str, user_id: str, ts: str):
        """Start a conversation with a user."""
        try:
            logger.info(f"Starting conversation with user {user_id}")
            
            # Ask if the user wants to search for similar profiles
            response = self.client.chat_postMessage(
                channel=channel_id,
                text=f"Hello <@{user_id}>! Would you like to search for similar profiles and connect? (yes/no)"
            )
            
            # Store the conversation state
            self.conversations[user_id] = {
                "channel_id": channel_id,
                "thread_ts": response["ts"],  # Use the bot's message timestamp
                "state": "awaiting_confirmation",
            }
            
            logger.info(f"Started conversation with user {user_id}, awaiting confirmation")
            
        except SlackApiError as e:
            logger.error(f"Error posting message: {e}")
    
    def _continue_conversation(self, channel_id: str, user_id: str, text: str):
        """Continue an ongoing conversation with a user."""
        # Get the current state of the conversation
        conversation = self.conversations.get(user_id, {})
        state = conversation.get("state")
        thread_ts = conversation.get("thread_ts")
        
        logger.info(f"Continuing conversation with user {user_id}, state: {state}, message: '{text}'")
        
        if state == "awaiting_confirmation":
            # User is responding to whether they want to search for similar profiles
            text_lower = text.lower().strip()
            
            # Simple check for confirmation
            if any(word in text_lower for word in ["y", "yes", "sure", "ok", "okay"]):
                # User wants to search for similar profiles
                logger.info(f"User {user_id} confirmed YES")
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Great! Please provide your LinkedIn profile URL."
                )
                
                # Update conversation state
                self.conversations[user_id]["state"] = "awaiting_linkedin_url"
                logger.info(f"User {user_id} confirmed, awaiting LinkedIn URL")
                
            else:
                # User doesn't want to search for similar profiles
                logger.info(f"User {user_id} declined")
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="No problem! Let me know if you change your mind."
                )
                
                # End the conversation
                del self.conversations[user_id]
                logger.info(f"User {user_id} declined, ending conversation")
                
        elif state == "awaiting_linkedin_url":
            # User is providing their LinkedIn URL
            linkedin_url = self._clean_slack_url(text.strip())
            logger.info(f"Cleaned LinkedIn URL: {linkedin_url}")
            
            # Check if the text contains a LinkedIn URL
            if "linkedin.com/in/" in linkedin_url:
                # Store the user's LinkedIn URL in the conversation state
                self.conversations[user_id]["base_linkedin_url"] = linkedin_url
                
                # Ask if they want to compare with a specific profile or search for similar profiles
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Would you like to:\n1️⃣ Compare with a specific LinkedIn profile\n2️⃣ Search for similar profiles among workspace members\n\nPlease respond with 1 or 2."
                )
                
                # Update conversation state
                self.conversations[user_id]["state"] = "awaiting_comparison_choice"
                logger.info(f"User {user_id} provided LinkedIn URL: {linkedin_url}, waiting for comparison choice")
                
            else:
                # Invalid LinkedIn URL
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="That doesn't look like a valid LinkedIn URL. Please provide a URL in the format: https://linkedin.com/in/username"
                )
                logger.info(f"User {user_id} provided invalid LinkedIn URL")
                
        elif state == "awaiting_comparison_choice":
            # User is choosing between direct comparison and searching for similar profiles
            choice = text.strip()
            
            if choice == "1":
                # User wants to compare with a specific profile
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Please provide the LinkedIn URL of the profile you want to compare with."
                )
                
                # Update conversation state
                self.conversations[user_id]["state"] = "awaiting_comparison_url"
                logger.info(f"User {user_id} chose to compare with a specific profile")
                
            elif choice == "2":
                # User wants to search for similar profiles
                base_linkedin_url = self.conversations[user_id].get("base_linkedin_url")
                
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Thanks! I'm searching for similar profiles among workspace members. This may take a minute..."
                )
                
                logger.info(f"User {user_id} chose to search for similar profiles")
                
                # Find similar profiles
                thread = threading.Thread(
                    target=self._find_similar_profiles,
                    args=(channel_id, user_id, base_linkedin_url)
                )
                thread.start()
                
                # End the conversation (it will be continued by the _find_similar_profiles method)
                del self.conversations[user_id]
                
            else:
                # Invalid choice
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Please respond with 1 to compare with a specific profile or 2 to search for similar profiles."
                )
                
        elif state == "awaiting_comparison_url":
            # User is providing the URL to compare with
            comparison_url = self._clean_slack_url(text.strip())
            logger.info(f"Cleaned comparison URL: {comparison_url}")
            
            # Check if the text contains a LinkedIn URL
            if "linkedin.com/in/" in comparison_url:
                base_linkedin_url = self.conversations[user_id].get("base_linkedin_url")
                
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Thanks! I'm comparing the profiles. This may take a minute..."
                )
                
                logger.info(f"User {user_id} provided comparison URL: {comparison_url}, starting comparison")
                
                # Compare the profiles
                thread = threading.Thread(
                    target=self._compare_specific_profiles,
                    args=(channel_id, user_id, base_linkedin_url, comparison_url)
                )
                thread.start()
                
                # End the conversation (it will be continued by the _compare_specific_profiles method)
                del self.conversations[user_id]
                
            else:
                # Invalid LinkedIn URL
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="That doesn't look like a valid LinkedIn URL. Please provide a URL in the format: https://linkedin.com/in/username"
                )
                logger.info(f"User {user_id} provided invalid comparison URL")
                
    def _clean_slack_url(self, text: str) -> str:
        """
        Extract a clean URL from Slack's formatted URL text.
        
        Slack formats URLs in different ways:
        1. <https://example.com> - Simple URL
        2. <https://example.com|example.com> - URL with display text
        
        This function extracts the actual URL from these formats.
        """
        # Check if this is a Slack formatted URL
        if text.startswith('<') and text.endswith('>'):
            # Remove the angle brackets
            text = text[1:-1]
            
            # If there's a pipe character, take the part before it (the actual URL)
            if '|' in text:
                text = text.split('|')[0]
                
            logger.info(f"Extracted URL from Slack format: {text}")
        
        return text
    
    def _find_similar_profiles(self, channel_id: str, user_id: str, linkedin_url: str):
        """Find similar profiles to the provided LinkedIn URL."""
        try:
            logger.info(f"Starting to find similar profiles for {linkedin_url}")
            
            # Get the base profile
            base_profile = self.linkedin_scraper.get_linkedin_profile(linkedin_url)
            
            # Debug: Log the full response
            logger.info(f"LinkedIn API Response: {json.dumps(base_profile, indent=2) if base_profile else 'None'}")
            
            if not base_profile or not base_profile.get("success", False):
                # Failed to get the profile
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Sorry, I couldn't retrieve that LinkedIn profile. Please check the URL and try again."
                )
                logger.error(f"Failed to retrieve LinkedIn profile for {linkedin_url}")
                return
            
            logger.info(f"Successfully retrieved LinkedIn profile for {linkedin_url}")
            
            # Get Slack users
            slack_users = self.slack_config.clean_users()
            
            # Debug: Log all users
            logger.info(f"Found {len(slack_users)} total Slack users")
            for user in slack_users:
                logger.info(f"Slack User: {user.real_name}, Is bot: {user.is_bot}")
            
            # Filter out bots, empty names, and limit to 10 users
            slack_users = [user for user in slack_users if not user.is_bot and user.real_name][:10]
            
            logger.info(f"Found {len(slack_users)} non-bot Slack users with names to compare against")
            
            # Get LinkedIn profiles for the Slack users
            linkedin_profiles = []
            for slack_user in slack_users:
                logger.info(f"Searching for LinkedIn profile for {slack_user.real_name}")
                try:
                    profile = self.linkedin_scraper.find_linkedin_profile_by_name(slack_user.real_name)
                    
                    # Debug: Log success or failure
                    if profile and profile.get("success", False):
                        logger.info(f"✅ Found LinkedIn profile for {slack_user.real_name}")
                        linkedin_profiles.append({
                            "slack_user": slack_user,
                            "linkedin_profile": profile
                        })
                    else:
                        logger.info(f"❌ No LinkedIn profile found for {slack_user.real_name}")
                except Exception as e:
                    logger.error(f"Error finding LinkedIn profile for {slack_user.real_name}: {e}")
            
            logger.info(f"Found {len(linkedin_profiles)} LinkedIn profiles for Slack users")
            
            if not linkedin_profiles:
                # No LinkedIn profiles found
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Sorry, I couldn't find any LinkedIn profiles for the users in this workspace."
                )
                return
            
            # Find similar profiles
            logger.info(f"Calculating similarity with {len(linkedin_profiles)} profiles")
            try:
                results = self.similarity_calculator.find_similar_profiles(
                    base_profile,
                    [p["linkedin_profile"] for p in linkedin_profiles],
                    limit=5
                )
                
                # Debug: Log similarity results
                logger.info(f"Similarity calculation results: {json.dumps(results, indent=2) if results else 'None'}")
                
            except Exception as e:
                logger.error(f"Error in similarity calculation: {e}")
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I encountered an error while calculating profile similarities: {str(e)}"
                )
                return
            
            if not results:
                # No similar profiles found
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="I couldn't find any similar profiles in this workspace."
                )
                logger.info("No similar profiles found")
                return
            
            logger.info(f"Found {len(results)} similar profiles")
            
            # Create a message with the results
            message = "Here are the most similar profiles:\n\n"
            
            for i, result in enumerate(results, 1):
                # Find the corresponding Slack user
                slack_user = None
                for profile_data in linkedin_profiles:
                    if profile_data["linkedin_profile"].get("person", {}).get("linkedInUrl") == result["compare_user"].get("linkedin_url"):
                        slack_user = profile_data["slack_user"]
                        break
                
                if not slack_user:
                    logger.warning(f"Could not find Slack user for LinkedIn profile: {result['compare_user'].get('linkedin_url')}")
                    continue
                
                message += f"*{i}. <@{slack_user.user_id}> ({slack_user.real_name})*\n"
                message += f"Similarity Score: {result['similarity_score']}%\n"
                message += f"LinkedIn: {result['compare_user'].get('linkedin_url', 'N/A')}\n"
                message += f"Headline: {result['compare_user'].get('headline', 'N/A')}\n"
                
                # Add a condensed explanation (first 100 characters)
                explanation = result.get("explanation", "")
                if len(explanation) > 100:
                    explanation = explanation[:100] + "..."
                message += f"Why similar: {explanation}\n\n"
            
            # Send the message
            self.client.chat_postMessage(
                channel=channel_id,
                text=message
            )
            
            logger.info("Sent similarity results to channel")
            
        except Exception as e:
            logger.error(f"Error finding similar profiles: {e}")
            self.client.chat_postMessage(
                channel=channel_id,
                text=f"Sorry, an error occurred while finding similar profiles: {str(e)}"
            )

    def _compare_specific_profiles(self, channel_id: str, user_id: str, base_url: str, comparison_url: str):
        """Compare two specific LinkedIn profiles."""
        try:
            logger.info(f"Starting to compare profiles: {base_url} and {comparison_url}")
            
            # Get the base profile
            base_profile = self.linkedin_scraper.get_linkedin_profile(base_url)
            
            if not base_profile or not base_profile.get("success", False):
                # Failed to get the base profile
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I couldn't retrieve the LinkedIn profile for {base_url}. Please check the URL and try again."
                )
                logger.error(f"Failed to retrieve LinkedIn profile for {base_url}")
                return
            
            # Get the comparison profile
            comparison_profile = self.linkedin_scraper.get_linkedin_profile(comparison_url)
            
            if not comparison_profile or not comparison_profile.get("success", False):
                # Failed to get the comparison profile
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I couldn't retrieve the LinkedIn profile for {comparison_url}. Please check the URL and try again."
                )
                logger.error(f"Failed to retrieve LinkedIn profile for {comparison_url}")
                return
            
            logger.info("Successfully retrieved both LinkedIn profiles")
            
            # Calculate similarity between the two profiles
            try:
                result = self.similarity_calculator.compare_profiles(base_profile, comparison_profile)
                
                logger.info(f"Similarity calculation result: {json.dumps(result, indent=2) if result else 'None'}")
                
                if not result:
                    self.client.chat_postMessage(
                        channel=channel_id,
                        text="I couldn't calculate the similarity between these profiles."
                    )
                    return
                
                # Create a message with the result
                message = "*Profile Comparison Results*\n\n"
                message += f"Base Profile: {base_url}\n"
                message += f"Comparison Profile: {comparison_url}\n\n"
                message += f"*Similarity Score*: {result.get('similarity_score', 'N/A')}%\n\n"
                
                # Add the explanation
                explanation = result.get("explanation", "")
                message += f"*Why similar*: {explanation}\n\n"
                
                # Send the message
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=message
                )
                
                logger.info("Sent comparison results to channel")
                
            except Exception as e:
                logger.error(f"Error in similarity calculation: {e}")
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I encountered an error while calculating profile similarities: {str(e)}"
                )
                
        except Exception as e:
            logger.error(f"Error comparing profiles: {e}")
            self.client.chat_postMessage(
                channel=channel_id,
                text=f"Sorry, an error occurred while comparing the profiles: {str(e)}"
            )

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start the bot
    bot = SlackBot()
    
    try:
        logger.info("Starting bot...")
        bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")