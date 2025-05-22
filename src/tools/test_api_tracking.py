#!/usr/bin/env python3
import os
import sys
import time
import random
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.utils.api_tracker import ApiTracker

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test API tracking functionality')
    parser.add_argument('--calls', type=int, default=50,
                        help='Number of simulated API calls to generate')
    parser.add_argument('--output', type=str, default='reports/api',
                        help='Output directory for generated reports')
    parser.add_argument('--analyze', action='store_true',
                        help='Analyze the generated report after creation')
    
    return parser.parse_args()

def simulate_api_calls(num_calls: int = 50):
    """Simulate a series of API calls with varying response times."""
    # Initialize API stats dictionary
    api_stats = {
        "api_one": {
            "total_calls": 0,
            "avg_duration_seconds": 0,
            "total_duration_seconds": 0,
            "calls": []
        },
        "api_two": {
            "total_calls": 0,
            "avg_duration_seconds": 0,
            "total_duration_seconds": 0,
            "calls": []
        },
        "api_three": {
            "total_calls": 0,
            "avg_duration_seconds": 0,
            "total_duration_seconds": 0,
            "calls": []
        }
    }
    
    # Distribution parameters for each API (mean, std_dev)
    api_params = {
        "api_one": (0.1, 0.05),     # Fast API, low variance
        "api_two": (0.5, 0.2),      # Medium API, medium variance
        "api_three": (2.0, 1.0)     # Slow API, high variance
    }
    
    # Add occasional outliers
    outlier_chance = 0.05  # 5% chance of outlier
    outlier_factor = 5     # 5x normal response time
    
    print(f"Simulating {num_calls} API calls...")
    
    # Simulate calls
    for i in range(num_calls):
        # Randomly select which API to call
        api_name = random.choice(list(api_stats.keys()))
        
        # Get distribution parameters
        mean_duration, std_dev = api_params[api_name]
        
        # Generate response time (normal distribution)
        is_outlier = random.random() < outlier_chance
        
        if is_outlier:
            # Create an outlier
            duration = mean_duration * outlier_factor * random.uniform(0.8, 1.2)
            print(f"Call {i+1}: {api_name} - {duration:.3f}s (OUTLIER)")
        else:
            # Normal response time
            duration = max(0.001, random.normalvariate(mean_duration, std_dev))
            print(f"Call {i+1}: {api_name} - {duration:.3f}s")
        
        # Record the call
        api_stats[api_name]["calls"].append({
            "timestamp": time.time(),
            "duration_seconds": duration
        })
        
        # Small pause to spread timestamps
        time.sleep(0.01)
    
    # Calculate summary statistics
    for api_name, stats in api_stats.items():
        calls = stats["calls"]
        if calls:
            total_duration = sum(call["duration_seconds"] for call in calls)
            avg_duration = total_duration / len(calls)
            
            api_stats[api_name]["total_calls"] = len(calls)
            api_stats[api_name]["avg_duration_seconds"] = avg_duration
            api_stats[api_name]["total_duration_seconds"] = total_duration
    
    return api_stats

def main():
    """Main function for the API tracking test."""
    args = parse_arguments()
    
    # Simulate API calls
    api_stats = simulate_api_calls(args.calls)
    
    # Create an API tracker
    tracker = ApiTracker(report_dir=args.output)
    
    # Generate a report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = tracker.generate_report(api_stats, f"test_api_performance_{timestamp}.json")
    
    print(f"\nReport generated at: {report_path}")
    
    # Print a summary
    tracker.print_summary(api_stats)
    
    # Analyze performance
    analysis = tracker.analyze_api_performance(api_stats)
    
    print("\n=== PERFORMANCE ANALYSIS ===")
    print("Recommendations:")
    for rec in analysis.get("recommendations", []):
        print(f"  {rec['api']}: {rec['issue']} - {rec['recommendation']}")
    
    # Analyze response time distribution and generate charts
    if args.analyze:
        try:
            # Create charts directory
            charts_dir = os.path.join(args.output, "charts")
            if not os.path.exists(charts_dir):
                os.makedirs(charts_dir)
                
            # Analyze distribution
            print("\nAnalyzing response time distribution...")
            distribution = tracker.analyze_response_time_distribution(api_stats, output_dir=charts_dir)
            
            apis_analyzed = distribution.get("apis_analyzed", [])
            print(f"Generated distribution analysis for {len(apis_analyzed)} APIs")
            
            for api in apis_analyzed:
                percentiles = distribution.get("percentiles", {}).get(api, {})
                outliers = distribution.get("outliers", {}).get(api, {})
                
                print(f"\n=== Response Time Distribution for {api} ===")
                print(f"Median response time: {percentiles.get('p50', 0):.3f} seconds")
                print(f"95th percentile: {percentiles.get('p95', 0):.3f} seconds")
                print(f"99th percentile: {percentiles.get('p99', 0):.3f} seconds")
                
                outlier_count = outliers.get("count", 0)
                outlier_pct = outliers.get("percentage", 0)
                print(f"Outliers: {outlier_count} ({outlier_pct:.1f}% of calls)")
                
                print(f"Distribution chart saved to {charts_dir}/{api}_response_time_distribution.png")
                
        except Exception as e:
            print(f"Error generating distribution analysis: {e}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error during test: {e}")
        sys.exit(1) 