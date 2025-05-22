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
    
    def calculate_similarity_by_names(self, base_user_name: str, compare_user_name: str) -> Dict[str, Any]:
        """
        Calculate similarity between two LinkedIn profiles using their names.
        
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
        
        return self.calculate_similarity(base_profile, compare_profile)
    
    def calculate_similarity(self, base_profile: Dict[str, Any], compare_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate similarity between two LinkedIn profiles.
        
        Args:
            base_profile: The LinkedIn profile data of the base user
            compare_profile: The LinkedIn profile data of the user to compare against
            
        Returns:
            A dictionary with similarity score and explanation
        """
        if not self.api_key:
            return {
                "error": "Anthropic API key not set",
                "similarity_score": 0,
                "explanation": "Cannot calculate similarity without Anthropic API key."
            }
            
        if not base_profile or not base_profile.get("success", False):
            return {
                "error": "Invalid base profile data",
                "similarity_score": 0,
                "explanation": "Base user profile data is invalid."
            }
            
        if not compare_profile or not compare_profile.get("success", False):
            return {
                "error": "Invalid compare profile data",
                "similarity_score": 0,
                "explanation": "Compare user profile data is invalid."
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
    
    def find_similar_profiles(self, base_profile: Dict[str, Any], comparison_profiles: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar profiles to the base profile from a list of comparison profiles.
        
        Args:
            base_profile: The base LinkedIn profile to compare against.
            comparison_profiles: A list of LinkedIn profiles to compare with the base profile.
            limit: The maximum number of similar profiles to return.
            
        Returns:
            A list of dictionaries containing similarity scores and explanations.
        """
        results = []
        
        if not base_profile or not comparison_profiles:
            logger.warning("No profiles to compare")
            return []
        
        # Process the base profile
        base_user = self._extract_user_data(base_profile)
        if not base_user:
            logger.error("Failed to extract base user data")
            return []
            
        # Compare with each profile
        for comparison_profile in comparison_profiles:
            compare_user = self._extract_user_data(comparison_profile)
            if not compare_user:
                logger.warning("Failed to extract comparison user data")
                continue
                
            # Skip if comparing the same profile
            if base_user.get("linkedin_url") == compare_user.get("linkedin_url"):
                logger.info("Skipping comparison with the same profile")
                continue
                
            # Calculate similarity
            result = self._calculate_similarity(base_user, compare_user)
            if result:
                result["compare_user"] = compare_user
                results.append(result)
                
        # Sort by similarity score (highest first)
        results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        
        # Limit the number of results
        return results[:limit]
        
    def compare_profiles(self, base_profile: Dict[str, Any], comparison_profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Compare two specific LinkedIn profiles.
        
        Args:
            base_profile: The base LinkedIn profile.
            comparison_profile: The profile to compare with the base profile.
            
        Returns:
            A dictionary with the similarity score and explanation.
        """
        if not base_profile or not comparison_profile:
            logger.warning("Missing profiles for comparison")
            return None
            
        # Process the profiles
        base_user = self._extract_user_data(base_profile)
        compare_user = self._extract_user_data(comparison_profile)
        
        if not base_user or not compare_user:
            logger.error("Failed to extract user data")
            return None
            
        # Calculate similarity
        result = self._calculate_similarity(base_user, compare_user)
        if result:
            result["base_user"] = base_user
            result["compare_user"] = compare_user
            
        return result
        
    def _extract_user_data(self, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract relevant user data from a LinkedIn profile.
        
        Args:
            profile: The LinkedIn profile data.
            
        Returns:
            A dictionary containing the extracted user data.
        """
        try:
            if not profile or not profile.get("success", False):
                return None
                
            person = profile.get("person", {})
            
            # Extract basic info
            user_data = {
                "linkedin_url": person.get("linkedInUrl", ""),
                "name": f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(),
                "headline": person.get("headline", ""),
                "location": person.get("location", ""),
                "photo_url": person.get("photoUrl", ""),
                "summary": person.get("summary", ""),
                "skills": person.get("skills", []),
                "languages": person.get("languages", []),
            }
            
            # Extract positions
            positions = []
            position_history = person.get("positions", {}).get("positionHistory", [])
            for position in position_history:
                positions.append({
                    "title": position.get("title", ""),
                    "company_name": position.get("companyName", ""),
                    "description": position.get("description", ""),
                })
            user_data["positions"] = positions
            
            # Extract education
            education = []
            education_history = person.get("schools", {}).get("educationHistory", [])
            for school in education_history:
                education.append({
                    "school_name": school.get("schoolName", ""),
                    "degree_name": school.get("degreeName", ""),
                    "field_of_study": school.get("fieldOfStudy", ""),
                })
            user_data["education"] = education
            
            # Extract certifications
            certifications = []
            certification_history = person.get("certifications", {}).get("certificationHistory", [])
            for cert in certification_history:
                certifications.append({
                    "name": cert.get("name", ""),
                    "organization_name": cert.get("organizationName", ""),
                })
            user_data["certifications"] = certifications
            
            return user_data
            
        except Exception as e:
            logger.error(f"Error extracting user data: {e}")
            return None
            
    def _calculate_similarity(self, user1: Dict[str, Any], user2: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Calculate the similarity between two users using the Anthropic API.
        
        Args:
            user1: The first user data.
            user2: The second user data.
            
        Returns:
            A dictionary containing the similarity score and explanation.
        """
        try:
            # Create a prompt for the AI to calculate similarity
            system_message = """
            You are a professional similarity analyzer for LinkedIn profiles. Your task is to compare two LinkedIn profiles and determine their similarity on a scale of 0-100%.
            
            Consider the following factors:
            1. Education background (schools, degrees, fields of study)
            2. Work experience (companies, roles, industries)
            3. Skills and expertise
            4. Certifications and achievements
            5. Overall career trajectory and level
            
            Provide:
            1. A similarity score (0-100%)
            2. A detailed explanation of why they are similar or different
            
            Format your answer as VALID JSON with the following structure:
            {
                "similarity_score": 75,
                "explanation": "These profiles are similar because..."
            }
            
            Make sure your response contains only the JSON object, with no additional text before or after. 
            Ensure the JSON is properly formatted and all special characters in the explanation are properly escaped.
            """
            
            # Clean and simplify the user data to avoid JSON parsing issues
            cleaned_user1 = self._clean_user_data_for_prompt(user1)
            cleaned_user2 = self._clean_user_data_for_prompt(user2)
            
            user_message = f"""
            Please compare these two LinkedIn profiles and calculate their similarity:
            
            PROFILE 1:
            {json.dumps(cleaned_user1, indent=2)}
            
            PROFILE 2:
            {json.dumps(cleaned_user2, indent=2)}
            
            Return only a valid JSON object with similarity_score and explanation.
            """
            
            # Call the Anthropic API
            response = self.client.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=1000,
                temperature=0,
                system=system_message,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            # Parse the response
            response_content = response.content[0].text.strip()
            logger.info(f"Raw response from Anthropic: {response_content[:100]}...")
            
            try:
                # First, try to parse the entire response as JSON
                result = json.loads(response_content)
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"Initial JSON parsing failed: {e}")
                
                # Find JSON in the response using regex
                import re
                json_pattern = r'({[\s\S]*})'
                match = re.search(json_pattern, response_content)
                
                if match:
                    json_str = match.group(1)
                    try:
                        result = json.loads(json_str)
                        return result
                    except json.JSONDecodeError as e2:
                        logger.error(f"Failed to parse extracted JSON: {e2}")
                
                # If all else fails, create a simple result
                return {
                    "similarity_score": 50,
                    "explanation": "Unable to calculate precise similarity. The profiles appear to have some commonalities in their professional backgrounds."
                }
                
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            # Return a default result instead of None
            return {
                "similarity_score": 50,
                "explanation": "Could not calculate similarity due to a technical error. Please try again later."
            }
            
    def _clean_user_data_for_prompt(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean user data to avoid JSON parsing issues.
        
        Args:
            user_data: The user data to clean.
            
        Returns:
            A cleaned version of the user data.
        """
        # Create a simplified version with just the most important fields
        cleaned_data = {
            "name": user_data.get("name", ""),
            "headline": user_data.get("headline", ""),
            "skills": user_data.get("skills", []),
        }
        
        # Add education (but simplified)
        cleaned_data["education"] = []
        for edu in user_data.get("education", []):
            cleaned_data["education"].append({
                "school": edu.get("school_name", ""),
                "degree": edu.get("degree_name", ""),
                "field": edu.get("field_of_study", "")
            })
            
        # Add positions (but simplified)
        cleaned_data["positions"] = []
        for position in user_data.get("positions", []):
            cleaned_data["positions"].append({
                "title": position.get("title", ""),
                "company": position.get("company_name", "")
            })
            
        # Add certifications (but simplified)
        cleaned_data["certifications"] = []
        for cert in user_data.get("certifications", []):
            cleaned_data["certifications"].append(cert.get("name", ""))
            
        return cleaned_data
    
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
    result = calculator.calculate_similarity_by_names(base_user_name, compare_user_name)
    
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
