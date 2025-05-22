#!/usr/bin/env python3
import os
import sys
import json
import argparse
import glob
from typing import Dict, Any, List, Optional
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.utils.api_tracker import ApiTracker

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Analyze API performance reports')
    parser.add_argument('--reports-dir', type=str, default='reports/api',
                        help='Directory containing API performance reports')
    parser.add_argument('--latest', action='store_true',
                        help='Only analyze the latest report')
    parser.add_argument('--compare', type=int, default=0,
                        help='Compare the latest N reports')
    parser.add_argument('--api', type=str, default=None,
                        help='Focus analysis on a specific API')
    parser.add_argument('--output', type=str, default=None,
                        help='Output directory for generated charts')
    parser.add_argument('--distribution', action='store_true',
                        help='Analyze response time distribution')
    
    return parser.parse_args()

def get_report_files(reports_dir: str, latest: bool = False, compare: int = 0) -> List[str]:
    """Get a list of report files to analyze."""
    # Find all JSON files in the reports directory
    report_files = glob.glob(os.path.join(reports_dir, '*.json'))
    
    # Sort by modification time (newest first)
    report_files.sort(key=os.path.getmtime, reverse=True)
    
    if latest:
        # Return only the latest report
        return report_files[:1] if report_files else []
    elif compare > 0:
        # Return the latest N reports
        return report_files[:compare] if report_files else []
    else:
        # Return all reports
        return report_files

def load_report(report_file: str) -> Dict[str, Any]:
    """Load a report from a JSON file."""
    try:
        with open(report_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading report {report_file}: {e}")
        return {}

def analyze_single_report(report: Dict[str, Any], api_name: Optional[str] = None,
                         analyze_distribution: bool = False, output_dir: Optional[str] = None) -> None:
    """Analyze a single API performance report."""
    if not report:
        print("No report data to analyze")
        return
    
    # Get report timestamp
    timestamp = report.get("generated_at", "Unknown")
    
    print(f"\n=== API Performance Report: {timestamp} ===")
    
    # Get summary
    summary = report.get("summary", {})
    
    print(f"Total API calls: {summary.get('total_api_calls', 0)}")
    print(f"Total duration: {summary.get('total_duration_seconds', 0):.2f} seconds")
    print(f"Slowest API: {summary.get('slowest_api', 'Unknown')} "
          f"({summary.get('slowest_avg_duration', 0):.2f} seconds avg)")
    print(f"Fastest API: {summary.get('fastest_api', 'Unknown')} "
          f"({summary.get('fastest_avg_duration', 0):.2f} seconds avg)")
    
    # If an API name is specified, show detailed stats for that API
    if api_name:
        api_stats = report.get("api_stats", {}).get(api_name)
        
        if not api_stats:
            print(f"\nNo data found for API: {api_name}")
            return
        
        print(f"\n=== Detailed Stats for {api_name} ===")
        print(f"Total calls: {api_stats.get('total_calls', 0)}")
        print(f"Average duration: {api_stats.get('avg_duration_seconds', 0):.2f} seconds")
        print(f"Total duration: {api_stats.get('total_duration_seconds', 0):.2f} seconds")
        
        # Show the last 10 calls
        last_calls = api_stats.get("last_10_calls", [])
        if last_calls:
            print("\nRecent calls:")
            for i, call in enumerate(last_calls, 1):
                ts = datetime.fromtimestamp(call.get("timestamp", 0)).strftime("%Y-%m-%d %H:%M:%S")
                duration = call.get("duration_seconds", 0)
                print(f"  {i}. {ts}: {duration:.2f} seconds")
    
    # Analyze response time distribution if requested
    if analyze_distribution and output_dir:
        tracker = ApiTracker()
        api_stats = report.get("api_stats", {})
        
        print("\nAnalyzing response time distribution...")
        distribution_result = tracker.analyze_response_time_distribution(
            api_stats, 
            api_name=api_name, 
            output_dir=output_dir
        )
        
        if "error" in distribution_result:
            print(f"Error analyzing distribution: {distribution_result['error']}")
            return
        
        apis_analyzed = distribution_result.get("apis_analyzed", [])
        print(f"Generated distribution analysis for {len(apis_analyzed)} APIs")
        
        for api in apis_analyzed:
            percentiles = distribution_result.get("percentiles", {}).get(api, {})
            outliers = distribution_result.get("outliers", {}).get(api, {})
            
            print(f"\n=== Response Time Distribution for {api} ===")
            print(f"Median response time: {percentiles.get('p50', 0):.3f} seconds")
            print(f"95th percentile: {percentiles.get('p95', 0):.3f} seconds")
            print(f"99th percentile: {percentiles.get('p99', 0):.3f} seconds")
            
            outlier_count = outliers.get("count", 0)
            outlier_pct = outliers.get("percentage", 0)
            print(f"Outliers: {outlier_count} ({outlier_pct:.1f}% of calls)")
            
            if output_dir:
                print(f"Distribution chart saved to {output_dir}/{api}_response_time_distribution.png")

def compare_reports(reports: List[Dict[str, Any]], api_name: Optional[str] = None, 
                   output_dir: Optional[str] = None) -> None:
    """Compare multiple API performance reports."""
    if not reports:
        print("No reports to compare")
        return
    
    # Create output directory if specified
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Extract timestamps and data for comparison
    timestamps = []
    total_calls = []
    total_durations = []
    
    # API-specific data
    api_calls = []
    api_durations = []
    api_avg_durations = []
    
    for report in reports:
        # Get report timestamp
        timestamp = report.get("generated_at", "Unknown")
        if timestamp != "Unknown":
            # Convert to datetime and format
            try:
                dt = datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%m-%d %H:%M")
            except:
                pass
        
        timestamps.append(timestamp)
        
        # Get summary data
        summary = report.get("summary", {})
        total_calls.append(summary.get("total_api_calls", 0))
        total_durations.append(summary.get("total_duration_seconds", 0))
        
        # Get API-specific data if requested
        if api_name:
            api_stats = report.get("api_stats", {}).get(api_name, {})
            api_calls.append(api_stats.get("total_calls", 0))
            api_durations.append(api_stats.get("total_duration_seconds", 0))
            api_avg_durations.append(api_stats.get("avg_duration_seconds", 0))
    
    # Reverse the lists so they're in chronological order
    timestamps.reverse()
    total_calls.reverse()
    total_durations.reverse()
    
    if api_name:
        api_calls.reverse()
        api_durations.reverse()
        api_avg_durations.reverse()
    
    # Print comparison
    print("\n=== API Performance Comparison ===")
    print(f"Comparing {len(reports)} reports from {timestamps[0]} to {timestamps[-1]}")
    
    # Generate charts
    if output_dir:
        # Total API calls chart
        plt.figure(figsize=(10, 6))
        plt.plot(timestamps, total_calls, marker='o')
        plt.title('Total API Calls Over Time')
        plt.xlabel('Time')
        plt.ylabel('Number of Calls')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'total_api_calls.png'))
        
        # Total API duration chart
        plt.figure(figsize=(10, 6))
        plt.plot(timestamps, total_durations, marker='o')
        plt.title('Total API Duration Over Time')
        plt.xlabel('Time')
        plt.ylabel('Duration (seconds)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'total_api_duration.png'))
        
        # API-specific charts
        if api_name:
            # API calls chart
            plt.figure(figsize=(10, 6))
            plt.plot(timestamps, api_calls, marker='o')
            plt.title(f'{api_name} Calls Over Time')
            plt.xlabel('Time')
            plt.ylabel('Number of Calls')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f'{api_name}_calls.png'))
            
            # API average duration chart
            plt.figure(figsize=(10, 6))
            plt.plot(timestamps, api_avg_durations, marker='o')
            plt.title(f'{api_name} Average Duration Over Time')
            plt.xlabel('Time')
            plt.ylabel('Average Duration (seconds)')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f'{api_name}_avg_duration.png'))
        
        print(f"\nCharts saved to {output_dir}")
    
    # If specific API is requested, show detailed comparison
    if api_name:
        print(f"\n=== Detailed Comparison for {api_name} ===")
        
        # Print a table of data
        print("\nTimestamp         | Calls | Avg Duration | Total Duration")
        print("-" * 60)
        
        for i in range(len(timestamps)):
            print(f"{timestamps[i]:16} | {api_calls[i]:5} | {api_avg_durations[i]:12.2f} | {api_durations[i]:14.2f}")
        
        # Calculate change
        if len(api_calls) >= 2:
            calls_change = api_calls[-1] - api_calls[0]
            avg_duration_change = api_avg_durations[-1] - api_avg_durations[0]
            
            print("\nChanges from first to last report:")
            print(f"Calls: {calls_change:+d}")
            print(f"Average Duration: {avg_duration_change:+.2f} seconds")

def analyze_api_trends(reports: List[Dict[str, Any]], output_dir: Optional[str] = None) -> None:
    """Analyze trends across all APIs in the reports."""
    if not reports:
        print("No reports to analyze")
        return
    
    # Create output directory if specified
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Get the most recent report
    latest_report = reports[0]
    
    # Get the list of APIs
    api_stats = latest_report.get("api_stats", {})
    apis = []
    
    for api_name, stats in api_stats.items():
        # Skip nested API data and ensure we have call stats
        if isinstance(stats, dict) and "total_calls" in stats:
            apis.append(api_name)
    
    # Sort APIs by call volume
    apis.sort(key=lambda api: api_stats.get(api, {}).get("total_calls", 0), reverse=True)
    
    print("\n=== API Usage Trends ===")
    print(f"Analyzing {len(apis)} APIs across {len(reports)} reports")
    
    # Generate API usage chart
    if output_dir:
        # Create a bar chart of API usage
        calls = [api_stats.get(api, {}).get("total_calls", 0) for api in apis]
        durations = [api_stats.get(api, {}).get("total_duration_seconds", 0) for api in apis]
        
        plt.figure(figsize=(12, 6))
        plt.bar(apis, calls)
        plt.title('API Usage by Call Volume')
        plt.xlabel('API')
        plt.ylabel('Number of Calls')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'api_usage_volume.png'))
        
        # Create a bar chart of API duration
        plt.figure(figsize=(12, 6))
        plt.bar(apis, durations)
        plt.title('API Usage by Total Duration')
        plt.xlabel('API')
        plt.ylabel('Total Duration (seconds)')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'api_usage_duration.png'))
        
        print(f"\nAPI usage charts saved to {output_dir}")
    
    # Print API usage table
    print("\nAPI                 | Calls | Avg Duration | Total Duration")
    print("-" * 60)
    
    for api in apis:
        stats = api_stats.get(api, {})
        calls = stats.get("total_calls", 0)
        avg_duration = stats.get("avg_duration_seconds", 0)
        total_duration = stats.get("total_duration_seconds", 0)
        
        print(f"{api:20} | {calls:5} | {avg_duration:12.2f} | {total_duration:14.2f}")

def main():
    """Main function for the API performance analyzer."""
    args = parse_arguments()
    
    # Get report files
    report_files = get_report_files(args.reports_dir, args.latest, args.compare)
    
    if not report_files:
        print(f"No report files found in {args.reports_dir}")
        return
    
    # Load reports
    reports = [load_report(report_file) for report_file in report_files]
    reports = [report for report in reports if report]  # Filter out empty reports
    
    if not reports:
        print("No valid reports found")
        return
    
    # Analyze reports
    if len(reports) == 1 or args.latest:
        # Analyze single report
        analyze_single_report(
            reports[0], 
            api_name=args.api, 
            analyze_distribution=args.distribution,
            output_dir=args.output
        )
    else:
        # Compare multiple reports
        compare_reports(reports, args.api, args.output)
        
        # Analyze API trends
        analyze_api_trends(reports, args.output)
        
        # Analyze distribution for latest report if requested
        if args.distribution and args.output:
            analyze_single_report(
                reports[0],
                api_name=args.api,
                analyze_distribution=True,
                output_dir=args.output
            )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAnalysis stopped by user")
    except Exception as e:
        print(f"Error during analysis: {e}")
        sys.exit(1) 