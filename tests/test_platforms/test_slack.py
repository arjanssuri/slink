import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.platforms.slack import SlackConfiguration, User

class TestUser(unittest.TestCase):
    def test_user_initialization(self):
        """Test that a User can be properly initialized."""
        user = User(
            user_id="U12345",
            real_name="Test User",
            email="test@example.com",
            profile={"status_text": "Working remotely"},
            display_name="testuser",
            image="http://example.com/image.jpg",
            is_bot=False,
            is_admin=True,
            team_id="T12345"
        )
        
        self.assertEqual(user.user_id, "U12345")
        self.assertEqual(user.real_name, "Test User")
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.profile, {"status_text": "Working remotely"})
        self.assertEqual(user.display_name, "testuser")
        self.assertEqual(user.image, "http://example.com/image.jpg")
        self.assertEqual(user.is_bot, False)
        self.assertEqual(user.is_admin, True)
        self.assertEqual(user.team_id, "T12345")
    
    def test_user_repr(self):
        """Test the string representation of a User."""
        user = User(
            user_id="U12345",
            real_name="Test User",
            email="test@example.com",
            profile={}
        )
        
        expected_repr = "User(id=U12345, name=Test User, email=test@example.com, bot=False)"
        self.assertEqual(repr(user), expected_repr)

class TestSlackConfiguration(unittest.TestCase):
    @patch('src.platforms.slack.WebClient')
    def setUp(self, mock_web_client):
        """Set up a SlackConfiguration with a mocked WebClient."""
        self.mock_client = MagicMock()
        mock_web_client.return_value = self.mock_client
        self.slack_config = SlackConfiguration()
    
    def test_get_users(self):
        """Test that get_users returns the members from the API response."""
        # Mock the response from users_list
        mock_response = {"members": [{"id": "U12345", "name": "test_user"}]}
        self.mock_client.users_list.return_value = mock_response
        
        users = self.slack_config.get_users()
        
        self.mock_client.users_list.assert_called_once()
        self.assertEqual(users, mock_response["members"])
    
    def test_get_user_profile(self):
        """Test that get_user_profile returns the profile from the API response."""
        # Mock the response from users_profile_get
        mock_response = {"profile": {"real_name": "Test User", "email": "test@example.com"}}
        self.mock_client.users_profile_get.return_value = mock_response
        
        profile = self.slack_config.get_user_profile("U12345")
        
        self.mock_client.users_profile_get.assert_called_once_with(user="U12345")
        self.assertEqual(profile, mock_response["profile"])
    
    def test_clean_users(self):
        """Test that clean_users creates User objects from raw user data."""
        # Mock the response from get_users
        mock_raw_users = [
            {
                "id": "U12345",
                "real_name": "Test User",
                "deleted": False,
                "profile": {
                    "email": "test@example.com",
                    "display_name": "testuser",
                    "image_192": "http://example.com/image.jpg"
                },
                "is_bot": False,
                "is_admin": True,
                "team_id": "T12345"
            },
            {
                "id": "U67890",
                "real_name": "Test Bot",
                "deleted": False,
                "profile": {
                    "display_name": "testbot",
                    "image_192": "http://example.com/bot.jpg"
                },
                "is_bot": True,
                "is_admin": False,
                "team_id": "T12345"
            },
            {
                "id": "U13579",
                "real_name": "Deleted User",
                "deleted": True,
                "profile": {}
            }
        ]
        
        # Patch the get_users method to return our mock data
        with patch.object(self.slack_config, 'get_users', return_value=mock_raw_users):
            clean_users = self.slack_config.clean_users()
            
            # Should have 2 users (one deleted user should be filtered out)
            self.assertEqual(len(clean_users), 2)
            
            # Check the first user
            user1 = clean_users[0]
            self.assertEqual(user1.user_id, "U12345")
            self.assertEqual(user1.real_name, "Test User")
            self.assertEqual(user1.email, "test@example.com")
            self.assertEqual(user1.display_name, "testuser")
            self.assertEqual(user1.image, "http://example.com/image.jpg")
            self.assertEqual(user1.is_bot, False)
            self.assertEqual(user1.is_admin, True)
            self.assertEqual(user1.team_id, "T12345")
            
            # Check the second user (bot)
            user2 = clean_users[1]
            self.assertEqual(user2.user_id, "U67890")
            self.assertEqual(user2.real_name, "Test Bot")
            self.assertEqual(user2.email, "")  # Empty email for bot
            self.assertEqual(user2.display_name, "testbot")
            self.assertEqual(user2.image, "http://example.com/bot.jpg")
            self.assertEqual(user2.is_bot, True)
            self.assertEqual(user2.is_admin, False)
            self.assertEqual(user2.team_id, "T12345")

if __name__ == "__main__":
    unittest.main()
