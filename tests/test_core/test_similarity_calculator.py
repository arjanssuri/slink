import unittest
from unittest.mock import patch, MagicMock
import json
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.similarity_calculator import SimilarityCalculator

class TestSimilarityCalculator(unittest.TestCase):
    def setUp(self):
        """Set up a SimilarityCalculator with mocked dependencies."""
        # Create a patcher for the LinkedInScraper class
        self.linkedin_scraper_patcher = patch('src.core.similarity_calculator.LinkedInScraper')
        self.mock_linkedin_scraper_class = self.linkedin_scraper_patcher.start()
        self.mock_linkedin_scraper = self.mock_linkedin_scraper_class.return_value
        
        # Create the calculator with the API key set to a test value
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test_api_key'}):
            self.calculator = SimilarityCalculator()
            
        # Override the calculator's linkedin_scraper with our mock
        self.calculator.linkedin_scraper = self.mock_linkedin_scraper
    
    def tearDown(self):
        """Clean up after tests."""
        self.linkedin_scraper_patcher.stop()
    
    def test_get_profiles_success(self):
        """Test that get_profiles returns profiles when both are found."""
        # Set up mock profiles
        base_profile = {"success": True, "person": {"firstName": "Base"}}
        compare_profile = {"success": True, "person": {"firstName": "Compare"}}
        
        # Set up mock find_linkedin_profile_by_name method
        self.mock_linkedin_scraper.find_linkedin_profile_by_name.side_effect = [base_profile, compare_profile]
        
        # Call the method
        result_base, result_compare = self.calculator.get_profiles("Base User", "Compare User")
        
        # Check that profiles were returned
        self.assertEqual(result_base, base_profile)
        self.assertEqual(result_compare, compare_profile)
        
        # Check that find_linkedin_profile_by_name was called with correct arguments
        self.mock_linkedin_scraper.find_linkedin_profile_by_name.assert_any_call("Base User")
        self.mock_linkedin_scraper.find_linkedin_profile_by_name.assert_any_call("Compare User")
    
    def test_get_profiles_base_not_found(self):
        """Test that get_profiles returns None, None when base profile is not found."""
        # Set up mock find_linkedin_profile_by_name method to return None for base profile
        self.mock_linkedin_scraper.find_linkedin_profile_by_name.return_value = None
        
        # Call the method
        result_base, result_compare = self.calculator.get_profiles("Base User", "Compare User")
        
        # Check that None was returned for both profiles
        self.assertIsNone(result_base)
        self.assertIsNone(result_compare)
    
    def test_get_profiles_compare_not_found(self):
        """Test that get_profiles returns base profile, None when compare profile is not found."""
        # Set up mock profiles
        base_profile = {"success": True, "person": {"firstName": "Base"}}
        
        # Set up mock find_linkedin_profile_by_name method
        self.mock_linkedin_scraper.find_linkedin_profile_by_name.side_effect = [base_profile, None]
        
        # Call the method
        result_base, result_compare = self.calculator.get_profiles("Base User", "Compare User")
        
        # Check that base profile was returned but compare profile is None
        self.assertEqual(result_base, base_profile)
        self.assertIsNone(result_compare)
    
    def test_prepare_profile_summary(self):
        """Test that prepare_profile_summary calls extract_linkedin_summary."""
        # Set up mock profile
        profile = {"success": True, "person": {"firstName": "Test"}}
        
        # Set up mock extract_linkedin_summary method
        expected_summary = {"name": "Test User", "skills": ["Python"]}
        self.mock_linkedin_scraper.extract_linkedin_summary.return_value = expected_summary
        
        # Call the method
        result = self.calculator.prepare_profile_summary(profile)
        
        # Check that extract_linkedin_summary was called with the profile
        self.mock_linkedin_scraper.extract_linkedin_summary.assert_called_once_with(profile)
        
        # Check that the summary was returned
        self.assertEqual(result, expected_summary)
    
    def test_create_similarity_prompt(self):
        """Test that _create_similarity_prompt formats the prompt correctly."""
        # Set up mock summaries
        base_summary = {
            "name": "Base User",
            "headline": "Software Engineer",
            "summary": "Experienced developer",
            "skills": ["Python", "JavaScript"],
            "positions": [
                {
                    "title": "Senior Developer",
                    "company": "Tech Corp",
                    "description": "Leading development",
                    "start_date": "1/2020",
                    "end_date": ""
                }
            ]
        }
        
        compare_summary = {
            "name": "Compare User",
            "headline": "Data Scientist",
            "summary": "AI specialist",
            "skills": ["Python", "Machine Learning"],
            "positions": [
                {
                    "title": "ML Engineer",
                    "company": "AI Corp",
                    "description": "Building ML models",
                    "start_date": "6/2019",
                    "end_date": "5/2021"
                }
            ]
        }
        
        # Call the method
        prompt = self.calculator._create_similarity_prompt(base_summary, compare_summary)
        
        # Check that the prompt contains expected information
        self.assertIn("Base User", prompt)
        self.assertIn("Software Engineer", prompt)
        self.assertIn("Compare User", prompt)
        self.assertIn("Data Scientist", prompt)
        self.assertIn("Python, JavaScript", prompt)
        self.assertIn("Python, Machine Learning", prompt)
        self.assertIn("Senior Developer at Tech Corp", prompt)
        self.assertIn("ML Engineer at AI Corp", prompt)
    
    def test_parse_similarity_response(self):
        """Test that _parse_similarity_response extracts the score and explanation."""
        # Sample response
        response = """
        Based on my analysis of the two LinkedIn profiles, I can provide the following assessment:

        Similarity Score: 65%

        Explanation: Both profiles show professionals with Python skills working in technology, but they differ in their specific roles. While the base user is a Software Engineer focused on development, the compare user is a Data Scientist specializing in AI and machine learning. They share some technical skills like Python, but their overall career paths and specializations are different.
        """
        
        # Call the method
        result = self.calculator._parse_similarity_response(response)
        
        # Check that the score and explanation were extracted correctly
        self.assertEqual(result["similarity_score"], 65)
        self.assertIn("Both profiles show professionals with Python skills", result["explanation"])
    
    @patch('anthropic.Anthropic')
    def test_calculate_similarity(self, mock_anthropic_class):
        """Test that calculate_similarity integrates all components correctly."""
        # Set up mock profiles
        base_profile = {"success": True, "person": {"firstName": "Base"}}
        compare_profile = {"success": True, "person": {"firstName": "Compare"}}
        
        # Set up mock summaries
        base_summary = {"name": "Base User", "skills": ["Python"]}
        compare_summary = {"name": "Compare User", "skills": ["Python", "ML"]}
        
        # Set up mock Anthropic client and response
        mock_anthropic_instance = mock_anthropic_class.return_value
        mock_messages = MagicMock()
        mock_anthropic_instance.messages = mock_messages
        mock_create = MagicMock()
        mock_messages.create = mock_create
        
        mock_content = MagicMock()
        mock_content.text = "Similarity Score: 70%\nExplanation: These profiles are somewhat similar."
        mock_response = MagicMock()
        mock_response.content = [mock_content]
        mock_create.return_value = mock_response
        
        # Set up mock method returns for the calculator's methods
        self.calculator.get_profiles = MagicMock(return_value=(base_profile, compare_profile))
        self.calculator.prepare_profile_summary = MagicMock(side_effect=[base_summary, compare_summary])
        
        # Ensure the client attribute is properly set on the calculator
        self.calculator.client = mock_anthropic_instance
        
        # Call the method
        result = self.calculator.calculate_similarity("Base User", "Compare User")
        
        # Check that the methods were called
        self.calculator.get_profiles.assert_called_once_with("Base User", "Compare User")
        self.calculator.prepare_profile_summary.assert_any_call(base_profile)
        self.calculator.prepare_profile_summary.assert_any_call(compare_profile)
        
        # Check that Anthropic API was called
        mock_create.assert_called_once()
        
        # Check the result
        self.assertEqual(result["similarity_score"], 70)
        self.assertEqual(result["explanation"], "These profiles are somewhat similar.")
        self.assertEqual(result["base_user"], base_summary)
        self.assertEqual(result["compare_user"], compare_summary)

if __name__ == "__main__":
    unittest.main() 