# Slack App Setup for Socket Mode

This guide will help you configure your Slack app to work with Socket Mode for real-time event handling.

## Prerequisites

- A Slack workspace where you have admin permissions
- Access to https://api.slack.com/apps

## Step 1: Create or Update Your Slack App

1. Go to https://api.slack.com/apps
2. Either create a new app or select your existing app
3. Choose "From scratch" if creating new
4. Name your app (e.g., "Slonnect")
5. Select your workspace

## Step 2: Enable Socket Mode

1. In your app settings, go to **Socket Mode** in the left sidebar
2. Toggle **Enable Socket Mode** to ON
3. You'll see a notice about needing an App-Level Token

## Step 3: Create App-Level Token

1. Click **Generate Token and Scopes**
2. Give it a name like "socket-mode-token"
3. Add the scope: `connections:write`
4. Click **Generate**
5. **IMPORTANT**: Copy the token (starts with `xapp-`) and save it securely
6. Add this to your `.env` file as `SLACK_APP_TOKEN=xapp-your-token-here`

## Step 4: Configure OAuth & Permissions

1. Go to **OAuth & Permissions** in the left sidebar
2. In the **Bot Token Scopes** section, add these scopes:
   - `chat:write` - Send messages
   - `channels:read` - View basic channel information
   - `im:read` - View direct messages
   - `im:write` - Send direct messages
   - `users:read` - View people in the workspace

## Step 5: Subscribe to Events

1. Go to **Event Subscriptions** in the left sidebar
2. Toggle **Enable Events** to ON
3. In the **Subscribe to bot events** section, add:
   - `message.im` - Listen to messages in direct messages

## Step 6: Install the App

1. Go to **Install App** in the left sidebar
2. Click **Install to Workspace**
3. Review the permissions and click **Allow**
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
5. Add this to your `.env` file as `SLACK_BOT_TOKEN=xoxb-your-token-here`

## Step 7: Test the Setup

Your `.env` file should now contain:
```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-token
ANTHROPIC_API_KEY=your-anthropic-key
```

Run the bot:
```bash
python src/platforms/slack_bot.py
```

You should see:
```
============================================================
             SLACK BOT STARTING (EVENT-BASED)             
============================================================

Real-time event handling enabled - no more polling!
```

## Troubleshooting

### Bot Not Receiving Events

If you see "No events received via Socket Mode", check:

1. **Event Subscriptions**: Ensure `message.im` is added to bot events
2. **Socket Mode**: Ensure it's enabled with a valid app-level token
3. **Permissions**: Ensure the bot has `im:read` and `im:write` scopes
4. **Installation**: Reinstall the app after making permission changes

### Permission Errors

If you get permission errors:
1. Go to **OAuth & Permissions**
2. Add any missing scopes
3. Click **Reinstall App** at the top of the page

### Token Issues

- Bot tokens start with `xoxb-`
- App-level tokens start with `xapp-`
- Make sure you're using the correct token in the right environment variable

## Fallback Mode

If Socket Mode doesn't work, the bot will automatically fall back to polling mode, which checks for messages every 5 seconds. This is less efficient but still functional. 