#!/usr/bin/env python3
"""
Analyze Gatling stress test results and generate comparison reports.

Usage:
    python scripts/analyze_stress_test.py [result_dir]
    python scripts/analyze_stress_test.py --compare dir1 dir2
    python scripts/analyze_stress_test.py --latest
"""

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime


def parse_simulation_log(log_path: Path) -> dict:
    """Parse Gatling simulation.log file."""
    
    stats = {
        'total_requests': 0,
        'ok_requests': 0,
        'ko_requests': 0,
        'response_times': [],
        'errors': {},
        'scenarios': {},
        'start_time': None,
        'end_time': None,
    }
    
    with open(log_path, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            
            if not parts or len(parts) < 4:
                continue
            
            record_type = parts[0]
            
            if record_type == 'REQUEST':
                # REQUEST  scenario  request  start_time  end_time  status  message
                scenario = parts[1]
                request_name = parts[2]
                start_time = int(parts[3])
                end_time = int(parts[4])
                status = parts[5] if len(parts) > 5 else 'UNKNOWN'
                message = parts[6] if len(parts) > 6 else ''
                
                response_time = end_time - start_time
                
                stats['total_requests'] += 1
                stats['response_times'].append(response_time)
                
                if status == 'OK':
                    stats['ok_requests'] += 1
                else:
                    stats['ko_requests'] += 1
                    # Parse error message
                    if message:
                        error_key = message[:100]  # Truncate long messages
                        stats['errors'][error_key] = stats['errors'].get(error_key, 0) + 1
                
                # Track per-scenario stats
                if scenario not in stats['scenarios']:
                    stats['scenarios'][scenario] = {
                        'total': 0,
                        'ok': 0,
                        'ko': 0,
                        'response_times': []
                    }
                
                stats['scenarios'][scenario]['total'] += 1
                stats['scenarios'][scenario]['response_times'].append(response_time)
                if status == 'OK':
                    stats['scenarios'][scenario]['ok'] += 1
                else:
                    stats['scenarios'][scenario]['ko'] += 1
                
                # Track time range
                if stats['start_time'] is None or start_time < stats['start_time']:
                    stats['start_time'] = start_time
                if stats['end_time'] is None or end_time > stats['end_time']:
                    stats['end_time'] = end_time
    
    return stats


def calculate_percentiles(values: list, percentiles: list = [50, 75, 95, 99]) -> dict:
    """Calculate percentiles from a list of values."""
    if not values:
        return {p: 0 for p in percentiles}
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    result = {}
    for p in percentiles:
        idx = int(n * p / 100)
        if idx >= n:
            idx = n - 1
        result[p] = sorted_values[idx]
    
    return result


def format_duration(ms: int) -> str:
    """Format milliseconds as human-readable duration."""
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms/1000:.1f}s"
    else:
        return f"{ms/60000:.1f}m"


def print_report(stats: dict, title: str = "Stress Test Results"):
    """Print formatted stress test report."""
    
    print("=" * 80)
    print(f" {title}")
    print("=" * 80)
    print()
    
    # Summary
    success_rate = (stats['ok_requests'] / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
    error_rate = (stats['ko_requests'] / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
    
    duration_ms = stats['end_time'] - stats['start_time'] if stats['start_time'] and stats['end_time'] else 0
    duration_s = duration_ms / 1000
    rps = stats['total_requests'] / duration_s if duration_s > 0 else 0
    
    print("SUMMARY")
    print("-" * 80)
    print(f"  Total Requests:     {stats['total_requests']:,}")
    print(f"  Successful (OK):    {stats['ok_requests']:,} ({success_rate:.1f}%)")
    print(f"  Failed (KO):        {stats['ko_requests']:,} ({error_rate:.1f}%)")
    print(f"  Duration:           {format_duration(duration_ms)}")
    print(f"  Throughput:         {rps:.1f} req/s")
    print()
    
    # Response Times
    if stats['response_times']:
        percentiles = calculate_percentiles(stats['response_times'])
        
        print("RESPONSE TIMES")
        print("-" * 80)
        print(f"  Min:                {format_duration(min(stats['response_times']))}")
        print(f"  P50 (median):       {format_duration(percentiles[50])}")
        print(f"  P75:                {format_duration(percentiles[75])}")
        print(f"  P95:                {format_duration(percentiles[95])}")
        print(f"  P99:                {format_duration(percentiles[99])}")
        print(f"  Max:                {format_duration(max(stats['response_times']))}")
        print(f"  Mean:               {format_duration(int(sum(stats['response_times']) / len(stats['response_times'])))}")
        print()
    
    # Per-Scenario Stats
    if stats['scenarios']:
        print("PER-SCENARIO BREAKDOWN")
        print("-" * 80)
        for scenario, scenario_stats in stats['scenarios'].items():
            scenario_success = (scenario_stats['ok'] / scenario_stats['total'] * 100) if scenario_stats['total'] > 0 else 0
            scenario_p95 = calculate_percentiles(scenario_stats['response_times'], [95])[95] if scenario_stats['response_times'] else 0
            
            print(f"  {scenario}")
            print(f"    Total:    {scenario_stats['total']:,} ({scenario_success:.1f}% success)")
            print(f"    P95:      {format_duration(scenario_p95)}")
        print()
    
    # Top Errors
    if stats['errors']:
        print("TOP ERRORS")
        print("-" * 80)
        sorted_errors = sorted(stats['errors'].items(), key=lambda x: x[1], reverse=True)
        for i, (error, count) in enumerate(sorted_errors[:5], 1):
            percentage = (count / stats['total_requests'] * 100) if stats['total_requests'] > 0 else 0
            print(f"  {i}. [{count:,} times, {percentage:.1f}%]")
            print(f"     {error}")
        print()
    
    # Pass/Fail Assessment
    print("ASSESSMENT")
    print("-" * 80)
    
    if success_rate >= 95:
        status = "✅ EXCELLENT"
        print(f"  Status: {status}")
        print(f"  Success rate is {success_rate:.1f}% - production ready!")
    elif success_rate >= 80:
        status = "⚠️  GOOD"
        print(f"  Status: {status}")
        print(f"  Success rate is {success_rate:.1f}% - acceptable but could be better")
    elif success_rate >= 50:
        status = "⚠️  POOR"
        print(f"  Status: {status}")
        print(f"  Success rate is {success_rate:.1f}% - needs improvement")
    else:
        status = "❌ FAILING"
        print(f"  Status: {status}")
        print(f"  Success rate is only {success_rate:.1f}% - system is overloaded")
    
    if percentiles := calculate_percentiles(stats['response_times'], [95]):
        p95_ms = percentiles[95]
        if p95_ms < 1000:
            print(f"  P95 latency: ✅ {format_duration(p95_ms)} (excellent)")
        elif p95_ms < 3000:
            print(f"  P95 latency: ⚠️  {format_duration(p95_ms)} (acceptable)")
        else:
            print(f"  P95 latency: ❌ {format_duration(p95_ms)} (too slow)")
    
    print("=" * 80)
    print()


def compare_reports(stats1: dict, stats2: dict, label1: str, label2: str):
    """Compare two stress test runs."""
    
    print("=" * 80)
    print(f" COMPARISON: {label1} vs {label2}")
    print("=" * 80)
    print()
    
    # Calculate metrics
    sr1 = (stats1['ok_requests'] / stats1['total_requests'] * 100) if stats1['total_requests'] > 0 else 0
    sr2 = (stats2['ok_requests'] / stats2['total_requests'] * 100) if stats2['total_requests'] > 0 else 0
    
    p95_1 = calculate_percentiles(stats1['response_times'], [95])[95] if stats1['response_times'] else 0
    p95_2 = calculate_percentiles(stats2['response_times'], [95])[95] if stats2['response_times'] else 0
    
    rps1 = stats1['total_requests'] / ((stats1['end_time'] - stats1['start_time']) / 1000) if stats1['start_time'] and stats1['end_time'] else 0
    rps2 = stats2['total_requests'] / ((stats2['end_time'] - stats2['start_time']) / 1000) if stats2['start_time'] and stats2['end_time'] else 0
    
    # Print comparison
    print(f"{'Metric':<25} {label1:<20} {label2:<20} {'Change':<15}")
    print("-" * 80)
    
    # Success Rate
    sr_diff = sr2 - sr1
    sr_symbol = "📈" if sr_diff > 0 else "📉" if sr_diff < 0 else "➡️"
    print(f"{'Success Rate':<25} {sr1:>6.1f}% {sr2:>20.1f}% {sr_symbol} {sr_diff:>+6.1f}%")
    
    # P95 Latency
    p95_diff = p95_2 - p95_1
    p95_pct_diff = (p95_diff / p95_1 * 100) if p95_1 > 0 else 0
    p95_symbol = "📉" if p95_diff < 0 else "📈" if p95_diff > 0 else "➡️"  # Lower is better
    print(f"{'P95 Latency':<25} {format_duration(p95_1):>8} {format_duration(p95_2):>20} {p95_symbol} {p95_pct_diff:>+6.1f}%")
    
    # Throughput
    rps_diff = rps2 - rps1
    rps_pct_diff = (rps_diff / rps1 * 100) if rps1 > 0 else 0
    rps_symbol = "📈" if rps_diff > 0 else "📉" if rps_diff < 0 else "➡️"
    print(f"{'Throughput (req/s)':<25} {rps1:>8.1f} {rps2:>20.1f} {rps_symbol} {rps_pct_diff:>+6.1f}%")
    
    # Total Requests
    req_diff = stats2['total_requests'] - stats1['total_requests']
    req_pct_diff = (req_diff / stats1['total_requests'] * 100) if stats1['total_requests'] > 0 else 0
    print(f"{'Total Requests':<25} {stats1['total_requests']:>8,} {stats2['total_requests']:>20,} {req_pct_diff:>+6.1f}%")
    
    print()
    print("SUMMARY")
    print("-" * 80)
    
    improvements = []
    regressions = []
    
    if sr_diff > 5:
        improvements.append(f"✅ Success rate improved by {sr_diff:.1f}%")
    elif sr_diff < -5:
        regressions.append(f"❌ Success rate decreased by {abs(sr_diff):.1f}%")
    
    if p95_pct_diff < -10:  # Lower is better
        improvements.append(f"✅ P95 latency improved by {abs(p95_pct_diff):.1f}%")
    elif p95_pct_diff > 10:
        regressions.append(f"❌ P95 latency increased by {p95_pct_diff:.1f}%")
    
    if rps_pct_diff > 10:
        improvements.append(f"✅ Throughput increased by {rps_pct_diff:.1f}%")
    elif rps_pct_diff < -10:
        regressions.append(f"❌ Throughput decreased by {abs(rps_pct_diff):.1f}%")
    
    if improvements:
        print("Improvements:")
        for imp in improvements:
            print(f"  {imp}")
    
    if regressions:
        print("Regressions:")
        for reg in regressions:
            print(f"  {reg}")
    
    if not improvements and not regressions:
        print("  ➡️  Performance is similar")
    
    print("=" * 80)
    print()


def find_latest_result() -> Path:
    """Find the most recent stress test result."""
    results_dir = Path("api_under_stress/stress-test/user-files/results")
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")
    
    result_dirs = [d for d in results_dir.iterdir() if d.is_dir() and (d / "simulation.log").exists()]
    if not result_dirs:
        raise FileNotFoundError("No test results found")
    
    # Sort by timestamp in directory name
    result_dirs.sort(key=lambda d: d.name, reverse=True)
    return result_dirs[0]


def main():
    parser = argparse.ArgumentParser(description="Analyze Gatling stress test results")
    parser.add_argument("result_dir", nargs="?", help="Path to result directory")
    parser.add_argument("--latest", action="store_true", help="Analyze latest test result")
    parser.add_argument("--compare", nargs=2, metavar=("DIR1", "DIR2"), help="Compare two test runs")
    
    args = parser.parse_args()
    
    try:
        if args.compare:
            # Compare mode
            dir1 = Path(args.compare[0])
            dir2 = Path(args.compare[1])
            
            log1 = dir1 / "simulation.log"
            log2 = dir2 / "simulation.log"
            
            if not log1.exists():
                print(f"Error: {log1} not found")
                sys.exit(1)
            if not log2.exists():
                print(f"Error: {log2} not found")
                sys.exit(1)
            
            print(f"Analyzing {log1}...")
            stats1 = parse_simulation_log(log1)
            
            print(f"Analyzing {log2}...")
            stats2 = parse_simulation_log(log2)
            
            compare_reports(stats1, stats2, dir1.name, dir2.name)
            
        else:
            # Single report mode
            if args.latest:
                result_dir = find_latest_result()
                print(f"Analyzing latest result: {result_dir.name}\n")
            elif args.result_dir:
                result_dir = Path(args.result_dir)
            else:
                result_dir = find_latest_result()
                print(f"No result directory specified, using latest: {result_dir.name}\n")
            
            log_path = result_dir / "simulation.log"
            if not log_path.exists():
                print(f"Error: {log_path} not found")
                sys.exit(1)
            
            stats = parse_simulation_log(log_path)
            print_report(stats, f"Results: {result_dir.name}")
            
            # Check if HTML report exists
            html_report = result_dir / "index.html"
            if html_report.exists():
                print(f"📊 Full HTML report: {html_report}")
                print()
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

