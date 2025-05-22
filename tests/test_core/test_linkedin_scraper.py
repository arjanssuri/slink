import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.linkedin_scraper import LinkedInScraper
from src.platforms.slack import User as SlackUser

class TestLinkedInScraper(unittest.TestCase):
    def setUp(self):
        """Set up a LinkedInScraper with mocked dependencies."""
        # Create a patcher for the SlackConfiguration class
        self.slack_config_patcher = patch('src.core.linkedin_scraper.SlackConfiguration')
        self.mock_slack_config_class = self.slack_config_patcher.start()
        self.mock_slack_config = self.mock_slack_config_class.return_value
        
        # Create the scraper with the API key set to a test value
        with patch.dict('os.environ', {'RAPIDAPI_KEY': 'test_api_key'}):
            self.scraper = LinkedInScraper()
            
        # Override the scraper's slack_config with our mock
        self.scraper.slack_config = self.mock_slack_config
    
    def tearDown(self):
        """Clean up after tests."""
        self.slack_config_patcher.stop()
    
    @patch('src.core.linkedin_scraper.requests.get')
    def test_get_linkedin_profile(self, mock_get):
        """Test that get_linkedin_profile sends the correct request and processes the response."""
        # Set up the mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "person": {"firstName": "Test"}}
        mock_get.return_value = mock_response
        
        # Call the method
        result = self.scraper.get_linkedin_profile("https://linkedin.com/in/testuser")
        
        # Check that the request was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["x-rapidapi-key"], "test_api_key")
        self.assertEqual(kwargs["params"]["linkedInUrl"], "https://linkedin.com/in/testuser")
        
        # Check that the response was processed correctly
        self.assertEqual(result, {"success": True, "person": {"firstName": "Test"}})
    
    def test_find_linkedin_profile_by_name(self):
        """Test that find_linkedin_profile_by_name formats the name correctly."""
        # Mock the get_linkedin_profile method
        self.scraper.get_linkedin_profile = MagicMock(return_value={"success": True})
        
        # Call the method with a name that needs formatting
        result = self.scraper.find_linkedin_profile_by_name("Test User")
        
        # Check that the name was formatted correctly
        self.scraper.get_linkedin_profile.assert_called_once_with("https://linkedin.com/in/testuser")
        self.assertEqual(result, {"success": True})
    
    def test_get_slack_users_with_linkedin(self):
        """Test that get_slack_users_with_linkedin integrates Slack and LinkedIn data."""
        # Set up mock Slack users
        mock_user1 = SlackUser("U12345", "Test User", "test@example.com", {})
        mock_user1.is_bot = False
        
        mock_user2 = SlackUser("U67890", "Bot User", "", {})
        mock_user2.is_bot = True
        
        self.mock_slack_config.clean_users.return_value = [mock_user1, mock_user2]
        
        # Mock the find_linkedin_profile_by_name method
        self.scraper.find_linkedin_profile_by_name = MagicMock(return_value={"success": True, "person": {}})
        
        # Call the method
        result = self.scraper.get_slack_users_with_linkedin()
        
        # Check that bots were filtered out
        self.assertEqual(len(result), 1)
        
        # Check that the LinkedIn profile was fetched for the non-bot user
        self.scraper.find_linkedin_profile_by_name.assert_called_once_with("Test User")
        
        # Check the structure of the result
        self.assertEqual(result[0]["slack_user"], mock_user1)
        self.assertEqual(result[0]["linkedin_profile"], {"success": True, "person": {}})
    
    def test_extract_linkedin_summary(self):
        """Test that extract_linkedin_summary extracts the correct information."""
        # Load sample profile data
        linkedin_profile = {
            "success": True,
            "person": {
                "firstName": "Test",
                "lastName": "User",
                "headline": "Software Engineer",
                "summary": "Experienced developer",
                "location": "San Francisco, CA",
                "photoUrl": "http://example.com/photo.jpg",
                "linkedInUrl": "https://linkedin.com/in/testuser",
                "skills": ["Python", "JavaScript"],
                "positions": {
                    "positionHistory": [
                        {
                            "title": "Senior Developer",
                            "companyName": "Tech Corp",
                            "description": "Leading development",
                            "startEndDate": {
                                "start": {"year": 2020, "month": 1},
                                "end": None
                            }
                        },
                        {
                            "title": "Junior Developer",
                            "companyName": "Startup Inc",
                            "description": "Full-stack development",
                            "startEndDate": {
                                "start": {"year": 2018, "month": 6},
                                "end": {"year": 2019, "month": 12}
                            }
                        }
                    ]
                }
            }
        }
        
        # Call the method
        result = self.scraper.extract_linkedin_summary(linkedin_profile)
        
        # Check the result
        self.assertEqual(result["name"], "Test User")
        self.assertEqual(result["headline"], "Software Engineer")
        self.assertEqual(result["linkedin_url"], "https://linkedin.com/in/testuser")
        self.assertEqual(result["skills"], ["Python", "JavaScript"])
        
        # Check positions
        self.assertEqual(len(result["positions"]), 2)
        self.assertEqual(result["positions"][0]["title"], "Senior Developer")
        self.assertEqual(result["positions"][0]["company"], "Tech Corp")
        self.assertEqual(result["positions"][0]["start_date"], "1/2020")
        self.assertEqual(result["positions"][0]["end_date"], "")
        
        self.assertEqual(result["positions"][1]["title"], "Junior Developer")
        self.assertEqual(result["positions"][1]["company"], "Startup Inc")
        self.assertEqual(result["positions"][1]["start_date"], "6/2018")
        self.assertEqual(result["positions"][1]["end_date"], "12/2019")
    
    def test_format_date(self):
        """Test the _format_date helper method."""
        # Test with year and month
        result = self.scraper._format_date({"year": 2023, "month": 5})
        self.assertEqual(result, "5/2023")
        
        # Test with only year
        result = self.scraper._format_date({"year": 2023})
        self.assertEqual(result, "2023")
        
        # Test with empty dictionary
        result = self.scraper._format_date({})
        self.assertEqual(result, "")
        
        # Test with None
        result = self.scraper._format_date(None)
        self.assertEqual(result, "")

if __name__ == "__main__":
    unittest.main() 