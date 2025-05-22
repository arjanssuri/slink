#!/usr/bin/env python3
import os
import sys
import time
import logging
import argparse
import dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.platforms.slack_bot import SlackBot
from src.core.similarity_calculator import SimilarityCalculator

dotenv.load_dotenv()

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test API timing display')
    parser.add_argument('--slack', action='store_true',
                        help='Test Slack API timing')
    parser.add_argument('--anthropic', action='store_true',
                        help='Test Anthropic API timing')
    parser.add_argument('--all', action='store_true',
                        help='Test all APIs')
    
    return parser.parse_args()

def test_slack_api():
    """Test Slack API timing display."""
    print("\nTesting Slack API timing...")
    
    # Initialize SlackBot (this will make the auth_test API call)
    slack_bot = SlackBot()
    
    # Test conversations_list API
    print("\nTesting conversations_list API...")
    slack_bot.client.conversations_list(types="im")
    
    # Test chat_postMessage API to a test channel
    # Note: This will fail if the bot doesn't have access to the channel
    try:
        test_channel = os.environ.get("TEST_CHANNEL_ID")
        if test_channel:
            print(f"\nTesting chat_postMessage API to channel {test_channel}...")
            slack_bot.client.chat_postMessage(
                channel=test_channel,
                text="This is a test message from the API timing test script."
            )
    except Exception as e:
        print(f"Error posting test message: {e}")
    
    # Generate a performance report
    print("\nGenerating performance report...")
    slack_bot._generate_performance_report()
    
    # Print API stats
    slack_bot.print_api_stats()

def test_anthropic_api():
    """Test Anthropic API timing display."""
    print("\nTesting Anthropic API timing...")
    
    # Initialize SimilarityCalculator
    calculator = SimilarityCalculator()
    
    # Check if Anthropic API key is set
    if not calculator.api_key:
        print("ANTHROPIC_API_KEY environment variable not set. Cannot test Anthropic API.")
        return
    
    # Create a simple prompt for testing
    print("\nSending test request to Anthropic API...")
    try:
        start_time = time.time()
        response = calculator.client.messages.create(
            model="claude-3-7-sonnet-20250219",
            max_tokens=100,
            system="You are a helpful assistant.",
            messages=[
                {"role": "user", "content": "Hello! What time is it?"}
            ]
        )
        elapsed_time = time.time() - start_time
        
        # Log timing manually for this test
        calculator._log_api_timing("anthropic_messages_create", elapsed_time, "model: claude-3-7-sonnet (test)")
        
        # Show the response
        print(f"\nResponse: {response.content[0].text}")
        
    except Exception as e:
        print(f"Error calling Anthropic API: {e}")

def main():
    """Main function."""
    args = parse_arguments()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    
    if args.all or (not args.slack and not args.anthropic):
        # Test all APIs by default
        test_slack_api()
        test_anthropic_api()
    else:
        # Test specific APIs based on arguments
        if args.slack:
            test_slack_api()
        if args.anthropic:
            test_anthropic_api()
    
    print("\nAPI timing test completed.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error during test: {e}")
        sys.exit(1) 