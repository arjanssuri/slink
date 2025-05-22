# Slink

## Project Description

Slink is an intelligent networking assistant that automatically scans introduction channels in Discord and Slack, providing personalized recommendations for meaningful connections based on members' backgrounds, skills, and interests. By analyzing introductory messages, Slink helps users identify and reach out to potential collaborators, mentors, or professional contacts they might have otherwise missed.

## Features

- **Intelligent Channel Scanning**: Automatically reads and processes introduction channels across Discord and Slack
- **Smart Matching Algorithm**: Identifies potential connection opportunities based on:
  - Professional backgrounds
  - Skills and expertise
  - Shared interests
  - Complementary professional goals

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/slink.git

# Install dependencies
cd slink
npm install

# Set up your configuration
cp .env.example .env
# Edit .env with your Slack and Discord API tokens
```

## Configuration

Create a `.env` file with the following configurations:

```
DISCORD_BOT_TOKEN=your_discord_bot_token
SLACK_BOT_TOKEN=your_slack_bot_token
CHANNELS_TO_MONITOR=comma,separated,channel,ids
```

## Usage

```python
# Basic usage example
from slink import NetworkBot

# Initialize the bot
bot = NetworkBot(discord_token, slack_token)

# Start monitoring channels
bot.start_monitoring()

# Get connection recommendations
recommendations = bot.get_recommendations()
print(recommendations)
```

## How It Works

1. **Channel Monitoring**: The bot joins specified Discord and Slack channels
2. **Message Analysis**: Parses introduction messages using natural language processing
3. **Profile Matching**: Generates connection suggestions based on sophisticated matching algorithms
4. **Notification**: Provides personalized connection recommendations to users

## Ethical Considerations

- Respects user privacy
- Provides opt-out mechanisms
- Follows platform guidelines for bot usage

## Roadmap

- [ ] Multi-platform support
- [ ] Advanced matching algorithms
- [ ] Personalization settings
- [ ] Privacy controls

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Disclaimer

Slink is designed to facilitate networking and should be used responsibly and ethically. Always respect community guidelines and individual privacy.

slink/
│
├── src/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── bot.py              # Main bot class and core functionality
│   │   ├── matcher.py          # Connection matching algorithm
│   │   └── preprocessor.py     # Message preprocessing and analysis
│   │
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── discord_handler.py  # Discord-specific integration
│   │   └── slack_handler.py    # Slack-specific integration
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration management
│   │   ├── logger.py           # Logging utilities
│   │   └── privacy.py          # Privacy and consent management
│   │
│   └── ml/
│       ├── __init__.py
│       ├── nlp_model.py        # Natural Language Processing model
│       └── similarity.py       # Similarity scoring algorithms
│
├── tests/
│   ├── test_core/
│   │   ├── test_bot.py
│   │   ├── test_matcher.py
│   │   └── test_preprocessor.py
│   │
│   ├── test_platforms/
│   │   ├── test_discord.py
│   │   └── test_slack.py
│   │
│   └── test_ml/
│       ├── test_nlp.py
│       └── test_similarity.py
│
├── scripts/
│   ├── setup.py                # Installation and setup script
│   ├── train_model.py          # Model training script
│   └── run_bot.py              # Main script to run the bot
│
├── configs/
│   ├── default_config.yaml     # Default configuration
│   └── platforms.json          # Platform-specific settings
│
├── data/
│   ├── models/                 # Saved ML models
│   └── cache/                  # Temporary data storage
│
├── docs/
│   ├── architecture.md         # System architecture documentation
│   ├── installation.md         # Detailed installation guide
│   └── usage.md                # Usage instructions
│
├── requirements.txt            # Python dependencies
├── setup.py                    # Package setup file
├── .env.example                # Example environment configuration
├── .gitignore
├── LICENSE
├── README.md
└── CONTRIBUTING.md

Directory Structure Explanation
src/

Contains the main source code for the Slink project
Organized into modular components for easy maintenance

core/

Central bot logic and core functionality
Includes main bot class, matching algorithm, and message preprocessing

platforms/

Platform-specific integration handlers
Separate modules for Discord and Slack to manage unique API interactions

utils/

Utility modules for configuration, logging, and privacy management
Provides supporting functions for the main application

ml/

Machine learning components
Natural Language Processing and similarity scoring algorithms

tests/

Comprehensive test suite mirroring the source code structure
Ensures reliability and maintains code quality

scripts/

Utility scripts for setup, model training, and bot execution

configs/

Configuration files for different environments and platforms

data/

Storage for machine learning models and temporary data

docs/

Project documentation
Includes architectural overview, installation, and usage guides

Recommended Development Workflow

Develop core functionality in the src/ directory
Write corresponding tests in the tests/ directory
Use scripts/ for deployment and maintenance tasks
Keep configurations in the configs/ directory
Document extensively in the docs/ directory

Notes

Use virtual environments for dependency management
Follow Python best practices and PEP 8 style guidelines
Maintain clear separation of concerns between modules

# Slonnect - LinkedIn Connection Recommender for Slack

Slonnect is a Slack bot that analyzes LinkedIn profiles to find similar professionals within your workspace. It helps users connect with colleagues who have similar backgrounds, skills, or experiences.

## Features

- Direct message interface for interacting with the bot
- LinkedIn profile analysis and comparison
- Similar profile search among workspace members
- Detailed similarity scoring with explanations

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables in a `.env` file:
   ```
   SLACK_BOT_TOKEN=your_slack_bot_token
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ```
4. Run the bot: `python src/platforms/slack_bot.py`

## API Performance Tracking

Slonnect includes a comprehensive API performance tracking system that monitors and analyzes the performance of all API calls made by the application. This helps identify bottlenecks, optimize performance, and ensure reliable service.

### Features

- Real-time API call timing and logging
- Automatic performance report generation
- Response time analysis with percentiles and outlier detection
- Visualization tools for performance metrics
- Recommendations for API optimization

### Real-time API Timing Display

The bot displays real-time API timing information in the terminal, making it easy to monitor the performance of all API calls:

```
⏱️ 15:54:27 - API: slack_auth_test          | Time: 0.342s
⏱️ 15:54:28 - API: slack_conversations_list | Time: 0.215s
⏱️ 15:54:29 - API: conversations_history    | Time: 0.187s | channel: D12345678
⏱️ 15:54:30 - API: chat_postMessage         | Time: 0.265s | channel: D12345678
⏱️ 15:54:35 - API: anthropic_messages_create | Time: 3.056s | model: claude-3-opus (similarity)
```

This helps you:
- Identify slow API calls in real-time
- Track API latency patterns
- Debug performance issues during development
- Monitor production performance

To test the API timing display without running the full bot:
```bash
python src/tools/test_api_timing.py --all
```

### Usage

API tracking is enabled by default in the Slack bot. Performance reports are automatically generated hourly and saved to the `reports/api` directory.

#### Analyzing Performance Reports

Use the included analysis tool to examine API performance:

```bash
# View the latest report
python src/tools/analyze_api_performance.py --latest

# Compare the last 5 reports
python src/tools/analyze_api_performance.py --compare 5

# Focus on a specific API
python src/tools/analyze_api_performance.py --api anthropic_messages_create

# Generate visualizations
python src/tools/analyze_api_performance.py --output charts/

# Analyze response time distribution
python src/tools/analyze_api_performance.py --distribution --output charts/
```

#### Performance Optimization

The analysis tool provides recommendations for optimizing API usage based on:

- APIs with high response times
- APIs with high call volumes
- Unusual response time patterns or outliers

## Architecture

- `src/platforms/slack_bot.py`: Main bot implementation
- `src/core/similarity_calculator.py`: Calculates profile similarities using Anthropic API
- `src/core/linkedin_scraper.py`: Retrieves LinkedIn profile data
- `src/utils/api_tracker.py`: Tracks and analyzes API performance
- `src/tools/analyze_api_performance.py`: Command-line tool for API analysis
- `src/tools/test_api_timing.py`: Tool to test API timing display

## License

MIT
