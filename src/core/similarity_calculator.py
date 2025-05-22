import os
import logging
import json
import sys
import dotenv
from typing import Dict, Any, List, Optional, Tuple
import anthropic

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.core.linkedin_scraper import LinkedInScraper

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

class SimilarityCalculator:
    """
    Class to calculate similarity between LinkedIn profiles using Anthropic's Claude.
    """
    def __init__(self):
        self.linkedin_scraper = LinkedInScraper()
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY environment variable not set. Similarity calculation will not work.")
        else:
            self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def get_profiles(self, base_user_name: str, compare_user_name: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Get LinkedIn profiles for two users by their names.
        
        Args:
            base_user_name: The name of the base user
            compare_user_name: The name of the user to compare against
            
        Returns:
            A tuple of (base_user_profile, compare_user_profile)
        """
        base_profile = self.linkedin_scraper.find_linkedin_profile_by_name(base_user_name)
        compare_profile = self.linkedin_scraper.find_linkedin_profile_by_name(compare_user_name)
        
        if not base_profile or not base_profile.get("success", False):
            logger.error(f"Could not find LinkedIn profile for base user: {base_user_name}")
            return None, None
            
        if not compare_profile or not compare_profile.get("success", False):
            logger.error(f"Could not find LinkedIn profile for compare user: {compare_user_name}")
            return base_profile, None
            
        return base_profile, compare_profile
    
    def prepare_profile_summary(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract a summarized version of the profile for comparison.
        
        Args:
            profile: The full LinkedIn profile data
            
        Returns:
            A dictionary with summarized profile data
        """
        if not profile or not profile.get("success", False):
            return {}
            
        # Use the extract_linkedin_summary method from LinkedInScraper
        return self.linkedin_scraper.extract_linkedin_summary(profile)
    
    def calculate_similarity(self, base_user_name: str, compare_user_name: str) -> Dict[str, Any]:
        """
        Calculate similarity between two LinkedIn profiles.
        
        Args:
            base_user_name: The name of the base user
            compare_user_name: The name of the user to compare against
            
        Returns:
            A dictionary with similarity score and explanation
        """
        if not self.api_key:
            return {
                "error": "Anthropic API key not set",
                "similarity_score": 0,
                "explanation": "Cannot calculate similarity without Anthropic API key."
            }
            
        # Get profiles
        base_profile, compare_profile = self.get_profiles(base_user_name, compare_user_name)
        
        if not base_profile:
            return {
                "error": f"Could not find LinkedIn profile for base user: {base_user_name}",
                "similarity_score": 0,
                "explanation": "Base user profile not found."
            }
            
        if not compare_profile:
            return {
                "error": f"Could not find LinkedIn profile for compare user: {compare_user_name}",
                "similarity_score": 0,
                "explanation": "Compare user profile not found."
            }
            
        # Prepare summaries
        base_summary = self.prepare_profile_summary(base_profile)
        compare_summary = self.prepare_profile_summary(compare_profile)
        
        # Create prompt for Claude
        prompt = self._create_similarity_prompt(base_summary, compare_summary)
        
        try:
            # Call Anthropic API
            response = self.client.messages.create(
                model="claude-3-7-sonnet-20250219",
                max_tokens=1024,
                system="You are a professional career analyst comparing LinkedIn profiles. You will assess the similarity between two profiles on a scale from 0-100%. Be precise and analytical in your assessment.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse response
            content = response.content[0].text
            
            # Extract similarity score and explanation
            similarity_data = self._parse_similarity_response(content)
            
            return {
                "similarity_score": similarity_data["similarity_score"],
                "explanation": similarity_data["explanation"],
                "base_user": base_summary,
                "compare_user": compare_summary,
                "raw_response": content
            }
            
        except Exception as e:
            logger.error(f"Error calling Anthropic API: {e}")
            return {
                "error": f"Error calling Anthropic API: {str(e)}",
                "similarity_score": 0,
                "explanation": "An error occurred while calculating similarity."
            }
    
    def _create_similarity_prompt(self, base_summary: Dict[str, Any], compare_summary: Dict[str, Any]) -> str:
        """
        Create a prompt for Claude to calculate similarity.
        
        Args:
            base_summary: The summary of the base user's LinkedIn profile
            compare_summary: The summary of the comparison user's LinkedIn profile
            
        Returns:
            A string prompt for Claude
        """
        prompt = """I want you to analyze the similarity between two LinkedIn profiles.
Rate their similarity on a scale from 0% (completely different) to 100% (identical).

Base on factors like:
- Skills and expertise
- Industry and job roles
- Education background
- Career trajectory
- Experience level

PROFILE 1:
"""
        
        # Add base user profile details
        prompt += f"Name: {base_summary.get('name', 'Unknown')}\n"
        prompt += f"Headline: {base_summary.get('headline', 'N/A')}\n"
        prompt += f"Summary: {base_summary.get('summary', 'N/A')}\n"
        prompt += f"Skills: {', '.join(base_summary.get('skills', []))}\n"
        
        # Add positions
        prompt += "Experience:\n"
        for position in base_summary.get('positions', []):
            prompt += f"- {position.get('title', '')} at {position.get('company', '')}"
            if position.get('start_date'):
                prompt += f" ({position.get('start_date', '')} to {position.get('end_date', 'Present')})"
            prompt += f": {position.get('description', '')}\n"
        
        prompt += "\nPROFILE 2:\n"
        
        # Add compare user profile details
        prompt += f"Name: {compare_summary.get('name', 'Unknown')}\n"
        prompt += f"Headline: {compare_summary.get('headline', 'N/A')}\n"
        prompt += f"Summary: {compare_summary.get('summary', 'N/A')}\n"
        prompt += f"Skills: {', '.join(compare_summary.get('skills', []))}\n"
        
        # Add positions
        prompt += "Experience:\n"
        for position in compare_summary.get('positions', []):
            prompt += f"- {position.get('title', '')} at {position.get('company', '')}"
            if position.get('start_date'):
                prompt += f" ({position.get('start_date', '')} to {position.get('end_date', 'Present')})"
            prompt += f": {position.get('description', '')}\n"
        
        prompt += """
Provide your analysis in the following format:
1. Similarity Score: [0-100]%
2. Explanation: A detailed explanation of your similarity assessment.

Remember to focus on professional similarities and provide a clear justification for your similarity score.
"""
        
        return prompt
    
    def _parse_similarity_response(self, response: str) -> Dict[str, Any]:
        """
        Parse the similarity score and explanation from the Claude response.
        
        Args:
            response: The raw response from Claude
            
        Returns:
            A dictionary with similarity score and explanation
        """
        try:
            # Default values
            similarity_score = 0
            explanation = "Could not parse response."
            
            # Try to extract similarity score using regex
            import re
            
            # Look for patterns like "Similarity Score: 75%" or "similarity score: 75%"
            score_match = re.search(r'similarity score:?\s*(\d+)%', response, re.IGNORECASE)
            if score_match:
                similarity_score = int(score_match.group(1))
            
            # Extract explanation - everything after "Explanation:" or "explanation:"
            explanation_match = re.search(r'explanation:?\s*(.*)', response, re.IGNORECASE | re.DOTALL)
            if explanation_match:
                explanation = explanation_match.group(1).strip()
            
            return {
                "similarity_score": similarity_score,
                "explanation": explanation
            }
            
        except Exception as e:
            logger.error(f"Error parsing similarity response: {e}")
            return {
                "similarity_score": 0,
                "explanation": "Could not parse response due to an error."
            }

if __name__ == "__main__":
    # Set up environment variables
    dotenv.load_dotenv()
    
    # Initialize the calculator
    calculator = SimilarityCalculator()
    
    # Get the base user and compare user names from arguments
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python similarity_calculator.py <base_user_name> <compare_user_name>")
        sys.exit(1)
    
    base_user_name = sys.argv[1]
    compare_user_name = sys.argv[2]
    
    print(f"Calculating similarity between {base_user_name} and {compare_user_name}...")
    
    # Calculate similarity
    result = calculator.calculate_similarity(base_user_name, compare_user_name)
    
    # Print result
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        print(f"Similarity Score: {result['similarity_score']}%")
        print(f"Explanation: {result['explanation']}")
    
    # Print raw response if available
    if "raw_response" in result:
        print("\nRaw Response:")
        print(result['raw_response'])
