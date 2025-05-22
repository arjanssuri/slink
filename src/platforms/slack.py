import logging
import os
# Import WebClient from Python SDK (github.com/slackapi/python-slack-sdk)
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import dotenv
import os

dotenv.load_dotenv()

class SlackConfiguration:
    def __init__(self):
        # WebClient instantiates a client that can call API methods
        # When using Bolt, you can use either `app.client` or the `client` passed to listeners.
        self.client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

    def get_users(self) -> list:
        try:
            response = self.client.users_list()
            return response["members"]
        except SlackApiError as e:
            logger.error(f"Error getting users: {e}")
            return []
        
    def get_user_profile(self, user_id: str) -> dict:
        try:
            response = self.client.users_profile_get(user=user_id)
            return response["profile"]
        except SlackApiError as e:
            logger.error(f"Error getting user profile: {e}")
            return None
            
    def clean_users(self) -> list:
        """Extract important data from raw user data and return a list of User objects."""
        users = []
        raw_users = self.get_users()
        
        for raw_user in raw_users:
            # Skip deleted users
            if raw_user.get("deleted", False):
                continue
                
            user_id = raw_user.get("id", "")
            real_name = raw_user.get("real_name", "")
            
            profile = raw_user.get("profile", {})
            email = profile.get("email", "")
            display_name = profile.get("display_name", "")
            image = profile.get("image_192", "")  # Medium size image
            
            is_bot = raw_user.get("is_bot", False)
            is_admin = raw_user.get("is_admin", False)
            team_id = raw_user.get("team_id", "")
            
            user = User(
                user_id=user_id,
                real_name=real_name,
                email=email,
                profile=profile,
                display_name=display_name,
                image=image,
                is_bot=is_bot,
                is_admin=is_admin,
                team_id=team_id
            )
            users.append(user)
            
        return users

logger = logging.getLogger(__name__)

class User:
    def __init__(self, user_id: str, real_name: str, email: str, profile: dict, 
                 display_name: str = "", image: str = "", is_bot: bool = False, 
                 is_admin: bool = False, team_id: str = ""):
        self.user_id = user_id
        self.real_name = real_name
        self.email = email
        self.profile = profile
        self.display_name = display_name
        self.image = image
        self.is_bot = is_bot
        self.is_admin = is_admin
        self.team_id = team_id
        
    def __repr__(self):
        return f"User(id={self.user_id}, name={self.real_name}, email={self.email}, bot={self.is_bot})"

if __name__ == "__main__":
    slack_config = SlackConfiguration()
    # Print raw users
    # print(slack_config.get_users())
    
    # Print clean users
    clean_users = slack_config.clean_users()
    for user in clean_users:
        print(user)