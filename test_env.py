#!/usr/bin/env python3
import os
import dotenv

# Load environment variables
dotenv.load_dotenv()

print("Environment Variables Check:")
print(f"SLACK_BOT_TOKEN: {'✅ SET' if os.environ.get('SLACK_BOT_TOKEN') else '❌ MISSING'}")
print(f"SLACK_APP_TOKEN: {'✅ SET' if os.environ.get('SLACK_APP_TOKEN') else '❌ MISSING'}")
print(f"ANTHROPIC_API_KEY: {'✅ SET' if os.environ.get('ANTHROPIC_API_KEY') else '❌ MISSING'}")

# Show partial values (masked)
bot_token = os.environ.get('SLACK_BOT_TOKEN')
if bot_token:
    print(f"SLACK_BOT_TOKEN preview: {bot_token[:10]}...")

app_token = os.environ.get('SLACK_APP_TOKEN')
if app_token:
    print(f"SLACK_APP_TOKEN preview: {app_token[:10]}...")
else:
    print("\n🔧 To enable Socket Mode (real-time events):")
    print("1. Go to https://api.slack.com/apps")
    print("2. Select your app")
    print("3. Go to 'Socket Mode' and enable it")
    print("4. Generate an App-Level Token with 'connections:write' scope")
    print("5. Add SLACK_APP_TOKEN=xapp-your-token to your .env file") 