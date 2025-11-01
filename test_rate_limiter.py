#!/usr/bin/env python3
"""
Comprehensive rate limiter test script
Tests the Flask rate limiter with various warrior API endpoints
"""

import requests
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import sys
import random
import uuid

BASE_URL = "http://localhost:5001"
DEFAULT_LIMIT = 100  # requests per minute

# Warrior endpoints to test
ENDPOINTS = {
    'count': f"{BASE_URL}/counting-warriors",
    'search': f"{BASE_URL}/warrior",
    'create': f"{BASE_URL}/warrior",
}

# Sample warrior data for testing
SAMPLE_WARRIORS = [
    {"name": "Master Yoda", "dob": "1970-01-01", "fight_skills": ["BJJ", "KungFu", "Judo"]},
    {"name": "Obi-Wan Kenobi", "dob": "1950-05-10", "fight_skills": ["Lightsaber", "Force", "Meditation"]},
    {"name": "Luke Skywalker", "dob": "1980-12-20", "fight_skills": ["X-Wing", "Force", "Leadership"]},
    {"name": "Princess Leia", "dob": "1980-12-20", "fight_skills": ["Diplomacy", "Blaster", "Leadership"]},
    {"name": "Darth Vader", "dob": "1945-03-15", "fight_skills": ["Lightsaber", "Force", "Intimidation"]},
]


def test_count_warriors():
    """Test GET /counting-warriors endpoint"""
    try:
        response = requests.get(ENDPOINTS['count'], timeout=5)
        return response.status_code, response.elapsed.total_seconds()
    except Exception as e:
        return None, 0


def test_search_warriors(term=None):
    """Test GET /warrior?t={term} endpoint"""
    try:
        if term is None:
            term = random.choice(["Yoda", "Luke", "Force", "Leadership", "Judo"])
        response = requests.get(ENDPOINTS['search'], params={'t': term}, timeout=5)
        return response.status_code, response.elapsed.total_seconds()
    except Exception as e:
        return None, 0


def test_create_warrior(warrior_data=None):
    """Test POST /warrior endpoint"""
    try:
        if warrior_data is None:
            warrior_data = random.choice(SAMPLE_WARRIORS).copy()
            warrior_data['name'] = f"{warrior_data['name']} {uuid.uuid4().hex[:8]}"
        response = requests.post(
            ENDPOINTS['create'],
            json=warrior_data,
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        return response.status_code, response.elapsed.total_seconds()
    except Exception as e:
        return None, 0


def test_single_request(endpoint_type=None):
    """Test a single request to a warrior endpoint"""
    if endpoint_type is None:
        endpoint_type = random.choice(['count', 'search', 'create'])
    
    if endpoint_type == 'count':
        return test_count_warriors()
    elif endpoint_type == 'search':
        return test_search_warriors()
    elif endpoint_type == 'create':
        return test_create_warrior()
    else:
        return None, 0


def test_rapid_requests(num_requests=110, endpoint_mix=True):
    """Test rapid sequential requests to see when rate limiting kicks in"""
    print(f"\n{'='*60}")
    print(f"Test 1: Rapid Sequential Requests ({num_requests} requests)")
    if endpoint_mix:
        print("  Testing mix of: GET /counting-warriors, GET /warrior?t=..., POST /warrior")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    
    # Use count endpoint for consistent testing (it's read-only and fast)
    endpoint_type = 'count' if not endpoint_mix else None
    
    for i in range(1, num_requests + 1):
        status_code, elapsed = test_single_request(endpoint_type)
        timestamp = time.time() - start_time
        
        if status_code:
            # Accept both 200 (success) and 201 (created) as success
            symbol = "✓" if status_code in [200, 201] else "🚫" if status_code == 429 else "✗"
            print(f"[{timestamp:6.3f}s] Request {i:3d}: {symbol} {status_code}")
            results.append((i, status_code, elapsed, timestamp))
        else:
            print(f"[{timestamp:6.3f}s] Request {i:3d}: ✗ ERROR")
            results.append((i, None, 0, timestamp))
        
        # Very small delay to avoid overwhelming the system
        time.sleep(0.01)
    
    total_time = time.time() - start_time
    analyze_results(results, total_time, num_requests)


def test_concurrent_requests(num_requests=50, num_threads=10, endpoint_mix=False):
    """Test concurrent requests from multiple threads"""
    print(f"\n{'='*60}")
    print(f"Test 2: Concurrent Requests ({num_requests} requests, {num_threads} threads)")
    if endpoint_mix:
        print("  Testing mix of warrior endpoints")
    else:
        print("  Testing GET /counting-warriors endpoint")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    
    # Use count endpoint for concurrent testing (read-only, no conflicts)
    endpoint_type = 'count' if not endpoint_mix else None
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(test_single_request, endpoint_type): i for i in range(1, num_requests + 1)}
        
        for future in as_completed(futures):
            request_num = futures[future]
            try:
                status_code, elapsed = future.result()
                timestamp = time.time() - start_time
                
                if status_code:
                    # Accept both 200 (success) and 201 (created) as success
                    symbol = "✓" if status_code in [200, 201] else "🚫" if status_code == 429 else "✗"
                    print(f"[{timestamp:6.3f}s] Request {request_num:3d}: {symbol} {status_code} ({elapsed*1000:.1f}ms)")
                    results.append((request_num, status_code, elapsed, timestamp))
                else:
                    print(f"[{timestamp:6.3f}s] Request {request_num:3d}: ✗ ERROR")
                    results.append((request_num, None, 0, timestamp))
            except Exception as e:
                print(f"Request {request_num} failed with exception: {e}")
    
    total_time = time.time() - start_time
    analyze_results(results, total_time, num_requests)


def test_sustained_rate(target_rps=2, duration=30, endpoint_mix=True):
    """Test sustained request rate over time"""
    print(f"\n{'='*60}")
    print(f"Test 3: Sustained Rate ({target_rps} req/s for {duration}s)")
    if endpoint_mix:
        print("  Testing mix of warrior endpoints")
    else:
        print("  Testing GET /counting-warriors endpoint")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    interval = 1.0 / target_rps
    request_num = 0
    
    endpoint_type = None if endpoint_mix else 'count'
    
    while time.time() - start_time < duration:
        request_num += 1
        status_code, elapsed = test_single_request(endpoint_type)
        timestamp = time.time() - start_time
        
        if status_code:
            # Accept both 200 (success) and 201 (created) as success
            symbol = "✓" if status_code in [200, 201] else "🚫" if status_code == 429 else "✗"
            print(f"[{timestamp:6.1f}s] Request {request_num:3d}: {symbol} {status_code}")
            results.append((request_num, status_code, elapsed, timestamp))
        
        time.sleep(interval)
    
    total_time = time.time() - start_time
    analyze_results(results, total_time, request_num)


def analyze_results(results, total_time, total_requests):
    """Analyze and display test results"""
    print(f"\n{'-'*60}")
    print("Results Summary")
    print(f"{'-'*60}")
    
    status_counts = defaultdict(int)
    response_times = []
    
    for _, status_code, elapsed, _ in results:
        if status_code:
            status_counts[status_code] += 1
            if elapsed > 0:
                response_times.append(elapsed * 1000)  # Convert to ms
    
    print(f"Total requests:     {total_requests}")
    successful = status_counts.get(200, 0) + status_counts.get(201, 0)
    print(f"Successful (200/201): {successful}")
    print(f"Rate limited (429): {status_counts.get(429, 0)}")
    print(f"Other errors:       {sum(v for k, v in status_counts.items() if k not in [200, 201, 429])}")
    print(f"Total time:         {total_time:.2f}s")
    if total_time > 0:
        print(f"Average rate:       {total_requests/total_time:.2f} req/s")
    
    if response_times:
        print(f"\nResponse Times:")
        print(f"  Average: {statistics.mean(response_times):.2f}ms")
        print(f"  Median:  {statistics.median(response_times):.2f}ms")
        if len(response_times) > 1:
            print(f"  Min:     {min(response_times):.2f}ms")
            print(f"  Max:     {max(response_times):.2f}ms")
            print(f"  Std Dev: {statistics.stdev(response_times):.2f}ms")
    
    if status_counts.get(429, 0) > 0:
        print(f"\n⚠️  Rate limiting detected! {status_counts[429]} requests were throttled.")
    elif successful == total_requests:
        print(f"\n✓ All requests succeeded (within rate limit)")
    
    print()


def check_endpoint():
    """Check if the API endpoints are reachable"""
    try:
        # Check health endpoint first (it's exempt from rate limiting)
        health_response = requests.get(f"{BASE_URL}/health", timeout=5)
        if health_response.status_code != 200:
            print(f"❌ Health check failed with status {health_response.status_code}")
            return False
        
        # Check a warrior endpoint
        count_response = requests.get(ENDPOINTS['count'], timeout=5)
        if count_response.status_code not in [200, 429]:  # 429 is OK if rate limited
            print(f"❌ Warrior endpoint test failed with status {count_response.status_code}")
            return False
        
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Cannot connect to API at {BASE_URL}")
        print(f"   Error: {e}")
        print(f"\n   Make sure the Flask app is running:")
        print(f"   python limiter.py")
        return False
    except Exception as e:
        print(f"❌ Error checking endpoints: {e}")
        return False


def main():
    print("="*60)
    print("Warrior API Rate Limiter Test Suite")
    print("="*60)
    
    if not check_endpoint():
        sys.exit(1)
    
    print(f"✓ API is reachable at {BASE_URL}")
    print(f"  Flask limit: {DEFAULT_LIMIT} requests per minute")
    print(f"  Testing endpoints:")
    print(f"    - GET /counting-warriors")
    print(f"    - GET /warrior?t={{term}}")
    print(f"    - POST /warrior")
    
    try:
        # Test 1: Rapid sequential requests
        test_rapid_requests(110, endpoint_mix=False)  # Use count endpoint for consistency
        
        time.sleep(2)  # Brief pause between tests
        
        # Test 2: Concurrent requests
        test_concurrent_requests(50, 10, endpoint_mix=False)  # Use count endpoint
        
        time.sleep(2)
        
        # Test 3: Sustained rate
        test_sustained_rate(target_rps=2, duration=10, endpoint_mix=True)  # Mix endpoints
        
        print("="*60)
        print("All tests completed!")
        print("="*60)
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

