import os
import json
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ApiTracker:
    """
    Utility class for tracking API call performance and generating reports.
    """
    
    def __init__(self, report_dir: str = "reports"):
        """
        Initialize the API tracker.
        
        Args:
            report_dir: Directory to save reports in
        """
        self.report_dir = report_dir
        
        # Create reports directory if it doesn't exist
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
    def generate_report(self, api_stats: Dict[str, Any], report_name: Optional[str] = None) -> str:
        """
        Generate a performance report from API stats.
        
        Args:
            api_stats: Dictionary containing API call statistics
            report_name: Optional name for the report file
            
        Returns:
            Path to the generated report file
        """
        if not report_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_name = f"api_performance_{timestamp}.json"
            
        report_path = os.path.join(self.report_dir, report_name)
        
        # Add timestamp to the report
        report_data = {
            "timestamp": time.time(),
            "generated_at": datetime.now().isoformat(),
            "api_stats": api_stats
        }
        
        # Calculate summary metrics
        summary = self._calculate_summary(api_stats)
        report_data["summary"] = summary
        
        # Write report to file
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
            
        logger.info(f"Generated API performance report at {report_path}")
        
        return report_path
        
    def _calculate_summary(self, api_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate summary metrics from API stats.
        
        Args:
            api_stats: Dictionary containing API call statistics
            
        Returns:
            Dictionary containing summary metrics
        """
        summary = {
            "total_api_calls": 0,
            "total_duration_seconds": 0,
            "slowest_api": "",
            "fastest_api": "",
            "slowest_avg_duration": 0,
            "fastest_avg_duration": float('inf'),
            "apis_by_volume": [],
            "apis_by_avg_duration": []
        }
        
        # Process each API
        for api_name, stats in api_stats.items():
            # Skip nested API data
            if isinstance(stats, dict) and "total_calls" in stats:
                call_count = stats.get("total_calls", 0)
                total_duration = stats.get("total_duration_seconds", 0)
                avg_duration = stats.get("avg_duration_seconds", 0)
                
                summary["total_api_calls"] += call_count
                summary["total_duration_seconds"] += total_duration
                
                # Track slowest/fastest APIs
                if avg_duration > summary["slowest_avg_duration"]:
                    summary["slowest_avg_duration"] = avg_duration
                    summary["slowest_api"] = api_name
                    
                if avg_duration < summary["fastest_avg_duration"] and call_count > 0:
                    summary["fastest_avg_duration"] = avg_duration
                    summary["fastest_api"] = api_name
                    
                # Add to API lists
                summary["apis_by_volume"].append({
                    "api": api_name,
                    "calls": call_count
                })
                
                summary["apis_by_avg_duration"].append({
                    "api": api_name,
                    "avg_duration_seconds": avg_duration
                })
        
        # Sort the API lists
        summary["apis_by_volume"].sort(key=lambda x: x["calls"], reverse=True)
        summary["apis_by_avg_duration"].sort(key=lambda x: x["avg_duration_seconds"], reverse=True)
        
        # Fix infinite value in case no APIs were found
        if summary["fastest_avg_duration"] == float('inf'):
            summary["fastest_avg_duration"] = 0
            summary["fastest_api"] = "None"
            
        return summary
        
    def print_summary(self, api_stats: Dict[str, Any]) -> None:
        """
        Print a summary of API performance to the console.
        
        Args:
            api_stats: Dictionary containing API call statistics
        """
        summary = self._calculate_summary(api_stats)
        
        print("\n=== API PERFORMANCE SUMMARY ===")
        print(f"Total API calls: {summary['total_api_calls']}")
        print(f"Total duration: {summary['total_duration_seconds']:.2f} seconds")
        print(f"Slowest API: {summary['slowest_api']} ({summary['slowest_avg_duration']:.2f} seconds avg)")
        print(f"Fastest API: {summary['fastest_api']} ({summary['fastest_avg_duration']:.2f} seconds avg)")
        
        print("\nAPIs by call volume:")
        for api in summary["apis_by_volume"][:5]:  # Top 5
            print(f"  {api['api']}: {api['calls']} calls")
            
        print("\nAPIs by average duration:")
        for api in summary["apis_by_avg_duration"][:5]:  # Top 5
            print(f"  {api['api']}: {api['avg_duration_seconds']:.2f} seconds avg")
            
    def analyze_api_performance(self, api_stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze API performance and provide recommendations.
        
        Args:
            api_stats: Dictionary containing API call statistics
            
        Returns:
            Dictionary containing analysis and recommendations
        """
        summary = self._calculate_summary(api_stats)
        analysis = {
            "slow_apis": [],
            "high_volume_apis": [],
            "recommendations": []
        }
        
        # Identify slow APIs (over 1 second avg)
        for api in summary["apis_by_avg_duration"]:
            if api["avg_duration_seconds"] > 1.0:
                analysis["slow_apis"].append(api)
                
        # Identify high volume APIs (over 10 calls)
        for api in summary["apis_by_volume"]:
            if api["calls"] > 10:
                analysis["high_volume_apis"].append(api)
                
        # Generate recommendations
        if analysis["slow_apis"]:
            for api in analysis["slow_apis"]:
                analysis["recommendations"].append({
                    "api": api["api"],
                    "issue": "Slow response time",
                    "recommendation": "Consider implementing caching or optimizing API usage"
                })
                
        if analysis["high_volume_apis"]:
            for api in analysis["high_volume_apis"]:
                analysis["recommendations"].append({
                    "api": api["api"],
                    "issue": "High call volume",
                    "recommendation": "Consider batching requests or implementing rate limiting"
                })
                
        return analysis
    
    def analyze_response_time_distribution(self, api_stats: Dict[str, Any], api_name: str = None, 
                                          output_dir: str = None) -> Dict[str, Any]:
        """
        Analyze the distribution of API response times.
        
        Args:
            api_stats: Dictionary containing API call statistics
            api_name: Optional name of specific API to analyze
            output_dir: Optional directory to save visualization
            
        Returns:
            Dictionary containing distribution analysis
        """
        try:
            import numpy as np
            import matplotlib.pyplot as plt
            from scipy import stats
        except ImportError:
            logger.warning("Could not import numpy, matplotlib, or scipy. Cannot analyze response time distribution.")
            return {"error": "Required libraries not available"}
            
        # Create output directory if needed
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        result = {
            "apis_analyzed": [],
            "percentiles": {},
            "outliers": {}
        }
        
        # Determine which APIs to analyze
        apis_to_analyze = []
        if api_name:
            if api_name in api_stats and isinstance(api_stats[api_name], dict) and "calls" in api_stats[api_name]:
                apis_to_analyze = [api_name]
            else:
                logger.warning(f"API {api_name} not found in stats")
                return {"error": f"API {api_name} not found"}
        else:
            # Analyze all APIs
            for name, stats in api_stats.items():
                if isinstance(stats, dict) and "total_calls" in stats and stats["total_calls"] > 0:
                    apis_to_analyze.append(name)
                    
        logger.info(f"Analyzing response time distribution for {len(apis_to_analyze)} APIs")
        
        # Analyze each API
        for api in apis_to_analyze:
            api_data = api_stats[api]
            
            # Get all call durations
            durations = []
            
            # Check for direct calls list
            if "calls" in api_data:
                durations = [call.get("duration_seconds", 0) for call in api_data["calls"]]
            # Or try last_10_calls list
            elif "last_10_calls" in api_data:
                durations = [call.get("duration_seconds", 0) for call in api_data["last_10_calls"]]
                
            if not durations:
                logger.warning(f"No duration data available for {api}")
                continue
                
            # Convert to numpy array
            durations = np.array(durations)
            
            # Calculate statistics
            percentiles = {
                "min": float(np.min(durations)),
                "p25": float(np.percentile(durations, 25)),
                "p50": float(np.percentile(durations, 50)),  # median
                "p75": float(np.percentile(durations, 75)),
                "p90": float(np.percentile(durations, 90)),
                "p95": float(np.percentile(durations, 95)),
                "p99": float(np.percentile(durations, 99)),
                "max": float(np.max(durations))
            }
            
            # Identify outliers (> 1.5 IQR)
            q1, q3 = np.percentile(durations, [25, 75])
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outliers = durations[(durations < lower_bound) | (durations > upper_bound)]
            
            outlier_info = {
                "count": len(outliers),
                "percentage": (len(outliers) / len(durations)) * 100,
                "values": outliers.tolist() if len(outliers) <= 10 else outliers[:10].tolist()  # Limit to 10 values
            }
            
            # Store results
            result["apis_analyzed"].append(api)
            result["percentiles"][api] = percentiles
            result["outliers"][api] = outlier_info
            
            # Generate visualization if requested
            if output_dir:
                plt.figure(figsize=(12, 8))
                
                # Create a 2x2 subplot grid
                plt.subplot(2, 2, 1)
                plt.hist(durations, bins=20, alpha=0.7)
                plt.title(f'{api} Response Time Distribution')
                plt.xlabel('Duration (seconds)')
                plt.ylabel('Frequency')
                
                # Box plot
                plt.subplot(2, 2, 2)
                plt.boxplot(durations, vert=False, showfliers=True)
                plt.title('Response Time Box Plot')
                plt.xlabel('Duration (seconds)')
                plt.yticks([])
                
                # Percentile chart
                plt.subplot(2, 2, 3)
                percentile_labels = ['min', 'p25', 'p50', 'p75', 'p90', 'p95', 'p99', 'max']
                percentile_values = [percentiles[p] for p in percentile_labels]
                plt.bar(percentile_labels, percentile_values)
                plt.title('Response Time Percentiles')
                plt.ylabel('Duration (seconds)')
                plt.xticks(rotation=45)
                
                # CDF plot
                plt.subplot(2, 2, 4)
                sorted_data = np.sort(durations)
                yvals = np.arange(1, len(sorted_data)+1) / len(sorted_data)
                plt.plot(sorted_data, yvals)
                plt.title('Cumulative Distribution Function')
                plt.xlabel('Duration (seconds)')
                plt.ylabel('Probability')
                plt.grid(True)
                
                plt.tight_layout()
                plt.savefig(os.path.join(output_dir, f"{api}_response_time_distribution.png"))
                plt.close()
                
                logger.info(f"Generated response time distribution chart for {api}")
                
        return result

if __name__ == "__main__":
    # Example usage
    tracker = ApiTracker()
    
    # Example API stats
    example_stats = {
        "slack_conversations_list": {
            "total_calls": 50,
            "avg_duration_seconds": 0.25,
            "total_duration_seconds": 12.5
        },
        "slack_chat_postMessage": {
            "total_calls": 120,
            "avg_duration_seconds": 0.15,
            "total_duration_seconds": 18.0
        },
        "anthropic_messages_create": {
            "total_calls": 10,
            "avg_duration_seconds": 2.5,
            "total_duration_seconds": 25.0
        }
    }
    
    # Print summary
    tracker.print_summary(example_stats)
    
    # Generate report
    report_path = tracker.generate_report(example_stats)
    print(f"\nReport generated at: {report_path}")
    
    # Analyze performance
    analysis = tracker.analyze_api_performance(example_stats)
    print("\n=== PERFORMANCE ANALYSIS ===")
    print("Recommendations:")
    for rec in analysis["recommendations"]:
        print(f"  {rec['api']}: {rec['issue']} - {rec['recommendation']}") 