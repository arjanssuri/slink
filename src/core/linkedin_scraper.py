import os
import logging
import json
import requests
from typing import Optional, Dict, List, Any
import sys
import dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the slack functionality
from src.platforms.slack import SlackConfiguration, User as SlackUser

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

class LinkedInScraper:
    """
    Class to scrape LinkedIn profiles using the RapidAPI LinkedIn API.
    This class leverages Slack user data to find and enrich with LinkedIn profiles.
    """
    def __init__(self):
        self.slack_config = SlackConfiguration()
        self.api_key = os.environ.get("RAPIDAPI_KEY")
        self.api_host = os.environ.get("RAPIDAPI_HOST", "linkedin-api-live-data1.p.rapidapi.com")
        
        if not self.api_key:
            logger.warning("RAPIDAPI_KEY environment variable not set. LinkedIn scraping will not work.")
    
    def get_linkedin_profile(self, linkedin_url: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a LinkedIn profile using the RapidAPI.
        
        Args:
            linkedin_url: The LinkedIn profile URL to fetch
            
        Returns:
            The LinkedIn profile data or None if an error occurred
        """
        if not self.api_key:
            logger.error("Cannot fetch LinkedIn profile without API key")
            return None
            
        url = "https://linkedin-api-live-data1.p.rapidapi.com/enrichment/profile"
        
        querystring = {"linkedInUrl": linkedin_url}
        
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.api_host
        }
        
        try:
            response = requests.get(url, headers=headers, params=querystring)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching LinkedIn profile for {linkedin_url}: {e}")
            return None
    
    def find_linkedin_profile_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Try to find a LinkedIn profile by name.
        
        Args:
            name: The name to search for
            
        Returns:
            The LinkedIn profile data or None if not found
        """
        # Construct LinkedIn URL from name (lowercase, remove spaces)
        name_formatted = name.lower().replace(" ", "")
        linkedin_url = f"https://linkedin.com/in/{name_formatted}"
        
        return self.get_linkedin_profile(linkedin_url)
    
    def get_slack_users_with_linkedin(self) -> List[Dict[str, Any]]:
        """
        Get all Slack users and enrich them with LinkedIn profile data if possible.
        
        Returns:
            A list of dictionaries containing Slack user data and LinkedIn profile data
        """
        users_with_linkedin = []
        slack_users = self.slack_config.clean_users()
        
        for slack_user in slack_users:
            # Skip bots
            if slack_user.is_bot:
                continue
                
            user_data = {
                "slack_user": slack_user,
                "linkedin_profile": None
            }
            
            # Try to find LinkedIn profile by name
            linkedin_profile = self.find_linkedin_profile_by_name(slack_user.real_name)
            if linkedin_profile and linkedin_profile.get("success", False):
                user_data["linkedin_profile"] = linkedin_profile
                
            users_with_linkedin.append(user_data)
            
        return users_with_linkedin
    
    def extract_linkedin_summary(self, linkedin_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract key information from a LinkedIn profile.
        
        Args:
            linkedin_profile: The full LinkedIn profile data
            
        Returns:
            A dictionary with key information from the profile
        """
        if not linkedin_profile or not linkedin_profile.get("success", False):
            return {}
            
        person = linkedin_profile.get("person", {})
        
        summary = {
            "name": f"{person.get('firstName', '')} {person.get('lastName', '')}",
            "headline": person.get("headline", ""),
            "summary": person.get("summary", ""),
            "location": person.get("location", ""),
            "photo_url": person.get("photoUrl", ""),
            "linkedin_url": person.get("linkedInUrl", ""),
            "skills": person.get("skills", []),
            "positions": []
        }
        
        # Extract current position
        positions = person.get("positions", {}).get("positionHistory", [])
        for position in positions:
            pos_data = {
                "title": position.get("title", ""),
                "company": position.get("companyName", ""),
                "description": position.get("description", ""),
                "start_date": self._format_date(position.get("startEndDate", {}).get("start", {})),
                "end_date": self._format_date(position.get("startEndDate", {}).get("end", {}))
            }
            summary["positions"].append(pos_data)
            
        return summary
    
    def _format_date(self, date_dict: Dict[str, int]) -> str:
        """Format a date dictionary into a string."""
        if not date_dict:
            return ""
            
        year = date_dict.get("year", "")
        month = date_dict.get("month", "")
        
        if year and month:
            return f"{month}/{year}"
        elif year:
            return str(year)
        else:
            return ""

if __name__ == "__main__":
    # Set up environment variables
    dotenv.load_dotenv()
    
    # Initialize the scraper
    scraper = LinkedInScraper()
    
    # Test with a specific profile
    test_profile = scraper.get_linkedin_profile("https://linkedin.com/in/arjansuri")
    if test_profile and test_profile.get("success", False):
        print("Successfully fetched LinkedIn profile for arjansuri")
        summary = scraper.extract_linkedin_summary(test_profile)
        print(json.dumps(summary, indent=2))
    else:
        print("Failed to fetch LinkedIn profile for arjansuri")
    
    # Get all Slack users with LinkedIn profiles
    print("\nFetching LinkedIn profiles for all Slack users...")
    users_with_linkedin = scraper.get_slack_users_with_linkedin()
    print(f"Found {len(users_with_linkedin)} Slack users")
    
    # Print users with LinkedIn profiles
    for user_data in users_with_linkedin:
        slack_user = user_data["slack_user"]
        linkedin_profile = user_data["linkedin_profile"]
        
        print(f"\nSlack User: {slack_user.real_name} ({slack_user.email})")
        if linkedin_profile:
            summary = scraper.extract_linkedin_summary(linkedin_profile)
            print(f"LinkedIn: {summary.get('linkedin_url', 'Not found')}")
            print(f"Headline: {summary.get('headline', 'N/A')}")
            if summary.get("positions"):
                print("Current position:", summary["positions"][0]["title"], "at", summary["positions"][0]["company"])
        else:
            print("LinkedIn: Not found")
