import os
import logging
import json
import re
import time
import sys
from typing import Dict, Any, List, Optional, Tuple
import threading
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.errors import SlackApiError
import dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.platforms.slack import SlackConfiguration, User as SlackUser
from src.core.linkedin_scraper import LinkedInScraper
from src.core.similarity_calculator import SimilarityCalculator
from src.utils.api_tracker import ApiTracker

dotenv.load_dotenv()

# Configure main logger
logger = logging.getLogger(__name__)

# Create a dedicated API timing logger
api_timing_logger = logging.getLogger("api_timing")

# Create console handler for API timing
api_timing_handler = logging.StreamHandler()
api_timing_handler.setLevel(logging.INFO)
api_timing_formatter = logging.Formatter('⏱️ %(asctime)s - %(message)s', datefmt='%H:%M:%S')
api_timing_handler.setFormatter(api_timing_formatter)
api_timing_logger.addHandler(api_timing_handler)
api_timing_logger.setLevel(logging.INFO)
api_timing_logger.propagate = False  # Don't propagate to root logger

class SlackBotV2:
    """
    A Slack bot that responds to DMs using Socket Mode for real-time events.
    Much more efficient than polling-based approach.
    """
    def __init__(self):
        self.bot_token = os.environ.get("SLACK_BOT_TOKEN")
        self.app_token = os.environ.get("SLACK_APP_TOKEN")  # Required for Socket Mode
        
        if not self.bot_token or not self.app_token:
            logger.error("SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in environment variables")
            raise ValueError("Missing required environment variables")
            
        self.client = WebClient(token=self.bot_token)
        
        # Initialize Socket Mode client for real-time events
        self.socket_mode_client = SocketModeClient(
            app_token=self.app_token,
            web_client=self.client
        )
        
        # Initialize API call tracking
        self.api_call_stats = {
            "slack_auth_test": [],
            "slack_conversations_list": [],
            "slack_conversations_history": [],
            "slack_chat_postMessage": []
        }
        
        # Initialize API tracker
        self.api_tracker = ApiTracker(report_dir="reports/api")
        
        # Start tracking time
        self.start_time = time.time()
        
        # Print startup banner
        self._print_banner("SLACK BOT V2 STARTING (EVENT-BASED)")
        print("Real-time event handling enabled - no more polling!")
        print("API timing will be displayed for all requests\n")
        
        # Get the bot's user ID
        start_time = time.time()
        auth_response = self.client.auth_test()
        elapsed_time = time.time() - start_time
        self.api_call_stats["slack_auth_test"].append({
            "timestamp": time.time(),
            "duration_seconds": elapsed_time
        })
        self._log_api_timing("slack_auth_test", elapsed_time)
        
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
        
        # Register event handlers
        self._register_event_handlers()
        
        # Schedule regular performance reports
        self._schedule_performance_reports()
        
    def _print_banner(self, text: str):
        """Print a formatted banner to the console."""
        width = 60
        padding = (width - len(text) - 2) // 2
        print("\n" + "=" * width)
        print(" " * padding + text + " " * padding)
        print("=" * width + "\n")
    
    def _log_api_timing(self, api_name: str, duration: float, extra_info: str = ""):
        """Log API timing information in a consistent, visible format."""
        if extra_info:
            api_timing_logger.info(f"API: {api_name:<25} | Time: {duration:.3f}s | {extra_info}")
        else:
            api_timing_logger.info(f"API: {api_name:<25} | Time: {duration:.3f}s")
    
    def _register_event_handlers(self):
        """Register event handlers for Socket Mode."""
        # Handle message events
        self.socket_mode_client.socket_mode_request_listeners.append(self._handle_socket_mode_request)
        logger.info("Event handlers registered for Socket Mode")
    
    def _handle_socket_mode_request(self, client: SocketModeClient, req: SocketModeRequest):
        """Handle incoming Socket Mode requests."""
        try:
            # Acknowledge the request immediately
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)
            
            # Handle different types of events
            if req.type == "events_api":
                event = req.payload.get("event", {})
                event_type = event.get("type")
                
                if event_type == "message":
                    self._handle_message_event(event)
                    
        except Exception as e:
            logger.error(f"Error handling socket mode request: {e}")
    
    def _handle_message_event(self, event: Dict[str, Any]):
        """Handle message events from Slack."""
        try:
            # Skip messages from bots
            if event.get("bot_id") or event.get("user") == self.bot_id:
                return
            
            # Only handle direct messages
            channel_type = event.get("channel_type")
            if channel_type != "im":
                return
            
            # Skip messages we've already processed
            message_ts = event.get("ts")
            if message_ts in self.processed_messages:
                return
            
            # Add to processed messages
            self.processed_messages.add(message_ts)
            
            user_id = event.get("user")
            text = event.get("text", "")
            channel_id = event.get("channel")
            
            logger.info(f"Received DM from {user_id}: {text}")
            
            # Check if user is in a conversation
            if user_id in self.conversations:
                self._continue_conversation(channel_id, user_id, text)
            else:
                # Start new conversation
                self.start_conversation(channel_id, user_id, message_ts)
                
        except Exception as e:
            logger.error(f"Error handling message event: {e}")
    
    def _schedule_performance_reports(self):
        """Schedule regular performance reports to be generated."""
        # Generate a report every hour
        report_interval = 60 * 60  # 1 hour in seconds
        
        def generate_report_task():
            while True:
                time.sleep(report_interval)
                self._generate_performance_report()
        
        # Start the report generation thread
        report_thread = threading.Thread(target=generate_report_task, daemon=True)
        report_thread.start()
        logger.info("Scheduled hourly API performance reports")
        
    def _generate_performance_report(self):
        """Generate a performance report for API calls."""
        try:
            stats = self.get_api_call_stats()
            
            # Generate timestamp for report name
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Generate report
            report_path = self.api_tracker.generate_report(stats, f"api_performance_{timestamp}.json")
            
            # Generate analysis
            analysis = self.api_tracker.analyze_api_performance(stats)
            
            # Log summary
            uptime = time.time() - self.start_time
            hours, remainder = divmod(uptime, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            self._print_banner("API PERFORMANCE REPORT")
            print(f"Bot uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s")
            print(f"Report generated at: {report_path}")
            
            if analysis["recommendations"]:
                print("\nRecommendations:")
                for rec in analysis["recommendations"]:
                    print(f"  {rec['api']}: {rec['issue']} - {rec['recommendation']}")
            print()
                    
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
        
    def start(self):
        """Start the bot and listen for events using Socket Mode."""
        logger.info("Bot starting up...")
        logger.info(f"Bot is ready. Send a direct message to @{self.bot_name} to start.")
        logger.info("Using Socket Mode for real-time event handling...")
        
        try:
            # Start the Socket Mode client
            self.socket_mode_client.connect()
            logger.info("Socket Mode client connected successfully")
            
            # Keep the main thread alive
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            # Disconnect the Socket Mode client
            self.socket_mode_client.disconnect()
            logger.info("Socket Mode client disconnected")
    
    def start_conversation(self, channel_id: str, user_id: str, ts: str):
        """Start a conversation with a user."""
        try:
            logger.info(f"Starting conversation with user {user_id}")
            
            # Ask if the user wants to search for similar profiles
            start_time = time.time()
            response = self.client.chat_postMessage(
                channel=channel_id,
                text=f"Hello <@{user_id}>! Would you like to search for similar profiles and connect? (yes/no)"
            )
            elapsed_time = time.time() - start_time
            self.api_call_stats["slack_chat_postMessage"].append({
                "timestamp": time.time(),
                "duration_seconds": elapsed_time,
                "channel": channel_id
            })
            self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
            
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Great! Please provide your LinkedIn profile URL."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
                # Update conversation state
                self.conversations[user_id]["state"] = "awaiting_linkedin_url"
                logger.info(f"User {user_id} confirmed, awaiting LinkedIn URL")
                
            else:
                # User doesn't want to search for similar profiles
                logger.info(f"User {user_id} declined")
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="No problem! Let me know if you change your mind."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Would you like to:\n1️⃣ Compare with a specific LinkedIn profile\n2️⃣ Search for similar profiles among workspace members\n\nPlease respond with 1 or 2."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
                # Update conversation state
                self.conversations[user_id]["state"] = "awaiting_comparison_choice"
                logger.info(f"User {user_id} provided LinkedIn URL: {linkedin_url}, waiting for comparison choice")
                
            else:
                # Invalid LinkedIn URL
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="That doesn't look like a valid LinkedIn URL. Please provide a URL in the format: https://linkedin.com/in/username"
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                logger.info(f"User {user_id} provided invalid LinkedIn URL")
                
        elif state == "awaiting_comparison_choice":
            # User is choosing between direct comparison and searching for similar profiles
            choice = text.strip()
            
            if choice == "1":
                # User wants to compare with a specific profile
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Please provide the LinkedIn URL of the profile you want to compare with."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
                # Update conversation state
                self.conversations[user_id]["state"] = "awaiting_comparison_url"
                logger.info(f"User {user_id} chose to compare with a specific profile")
                
            elif choice == "2":
                # User wants to search for similar profiles
                base_linkedin_url = self.conversations[user_id].get("base_linkedin_url")
                
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Thanks! I'm searching for similar profiles among workspace members. This may take a minute..."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Please respond with 1 to compare with a specific profile or 2 to search for similar profiles."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
        elif state == "awaiting_comparison_url":
            # User is providing the URL to compare with
            comparison_url = self._clean_slack_url(text.strip())
            logger.info(f"Cleaned comparison URL: {comparison_url}")
            
            # Check if the text contains a LinkedIn URL
            if "linkedin.com/in/" in comparison_url:
                base_linkedin_url = self.conversations[user_id].get("base_linkedin_url")
                
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Thanks! I'm comparing the profiles. This may take a minute..."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="That doesn't look like a valid LinkedIn URL. Please provide a URL in the format: https://linkedin.com/in/username"
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Sorry, I couldn't retrieve that LinkedIn profile. Please check the URL and try again."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="Sorry, I couldn't find any LinkedIn profiles for the users in this workspace."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I encountered an error while calculating profile similarities: {str(e)}"
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
                return
            
            if not results:
                # No similar profiles found
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text="I couldn't find any similar profiles in this workspace."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
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
            start_time = time.time()
            self.client.chat_postMessage(
                channel=channel_id,
                text=message
            )
            elapsed_time = time.time() - start_time
            self.api_call_stats["slack_chat_postMessage"].append({
                "timestamp": time.time(),
                "duration_seconds": elapsed_time,
                "channel": channel_id
            })
            self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
            
            logger.info("Sent similarity results to channel")
            
        except Exception as e:
            logger.error(f"Error finding similar profiles: {e}")
            start_time = time.time()
            self.client.chat_postMessage(
                channel=channel_id,
                text=f"Sorry, an error occurred while finding similar profiles: {str(e)}"
            )
            elapsed_time = time.time() - start_time
            self.api_call_stats["slack_chat_postMessage"].append({
                "timestamp": time.time(),
                "duration_seconds": elapsed_time,
                "channel": channel_id
            })
            self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")

    def _compare_specific_profiles(self, channel_id: str, user_id: str, base_url: str, comparison_url: str):
        """Compare two specific LinkedIn profiles."""
        try:
            logger.info(f"Starting to compare profiles: {base_url} and {comparison_url}")
            
            # Get the base profile
            base_profile = self.linkedin_scraper.get_linkedin_profile(base_url)
            
            if not base_profile or not base_profile.get("success", False):
                # Failed to get the base profile
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I couldn't retrieve the LinkedIn profile for {base_url}. Please check the URL and try again."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
                logger.error(f"Failed to retrieve LinkedIn profile for {base_url}")
                return
            
            # Get the comparison profile
            comparison_profile = self.linkedin_scraper.get_linkedin_profile(comparison_url)
            
            if not comparison_profile or not comparison_profile.get("success", False):
                # Failed to get the comparison profile
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I couldn't retrieve the LinkedIn profile for {comparison_url}. Please check the URL and try again."
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
                logger.error(f"Failed to retrieve LinkedIn profile for {comparison_url}")
                return
            
            logger.info("Successfully retrieved both LinkedIn profiles")
            
            # Calculate similarity between the two profiles
            try:
                result = self.similarity_calculator.compare_profiles(base_profile, comparison_profile)
                
                logger.info(f"Similarity calculation result: {json.dumps(result, indent=2) if result else 'None'}")
                
                if not result:
                    start_time = time.time()
                    self.client.chat_postMessage(
                        channel=channel_id,
                        text="I couldn't calculate the similarity between these profiles."
                    )
                    elapsed_time = time.time() - start_time
                    self.api_call_stats["slack_chat_postMessage"].append({
                        "timestamp": time.time(),
                        "duration_seconds": elapsed_time,
                        "channel": channel_id
                    })
                    self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                    
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
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=message
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
                logger.info("Sent comparison results to channel")
                
            except Exception as e:
                logger.error(f"Error in similarity calculation: {e}")
                start_time = time.time()
                self.client.chat_postMessage(
                    channel=channel_id,
                    text=f"Sorry, I encountered an error while calculating profile similarities: {str(e)}"
                )
                elapsed_time = time.time() - start_time
                self.api_call_stats["slack_chat_postMessage"].append({
                    "timestamp": time.time(),
                    "duration_seconds": elapsed_time,
                    "channel": channel_id
                })
                self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
                
        except Exception as e:
            logger.error(f"Error comparing profiles: {e}")
            start_time = time.time()
            self.client.chat_postMessage(
                channel=channel_id,
                text=f"Sorry, an error occurred while comparing the profiles: {str(e)}"
            )
            elapsed_time = time.time() - start_time
            self.api_call_stats["slack_chat_postMessage"].append({
                "timestamp": time.time(),
                "duration_seconds": elapsed_time,
                "channel": channel_id
            })
            self._log_api_timing("chat_postMessage", elapsed_time, f"channel: {channel_id}")
    
    def get_api_call_stats(self) -> Dict[str, Any]:
        """
        Get statistics about API calls.
        
        Returns:
            A dictionary with API call statistics
        """
        stats = {}
        
        # Calculate statistics for each API call type
        for api_type, calls in self.api_call_stats.items():
            if calls:
                total_duration = sum(call["duration_seconds"] for call in calls)
                avg_duration = total_duration / len(calls)
                stats[api_type] = {
                    "total_calls": len(calls),
                    "avg_duration_seconds": avg_duration,
                    "total_duration_seconds": total_duration,
                    "last_10_calls": calls[-10:] if len(calls) > 10 else calls
                }
        
        # Get stats from similarity calculator
        if hasattr(self, 'similarity_calculator') and hasattr(self.similarity_calculator, 'get_api_call_stats'):
            similarity_stats = self.similarity_calculator.get_api_call_stats()
            stats["anthropic"] = similarity_stats
        
        return stats
    
    def print_api_stats(self) -> None:
        """Print a summary of API call statistics to the console."""
        stats = self.get_api_call_stats()
        self._print_banner("API CALL STATISTICS")
        self.api_tracker.print_summary(stats)

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    
    # Start the bot
    bot = SlackBotV2()
    
    try:
        logger.info("Starting V2 bot with Socket Mode...")
        bot.start()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        
        # Generate a final performance report
        bot._generate_performance_report()
        
        # Print API stats before exiting
        bot.print_api_stats()
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}") 