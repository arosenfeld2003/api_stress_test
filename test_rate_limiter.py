#!/usr/bin/env python3
"""
Comprehensive rate limiter test script
Tests the Flask rate limiter with various scenarios
"""

import requests
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import sys

ENDPOINT = "http://localhost:5001/health"
DEFAULT_LIMIT = 100  # requests per minute


def test_single_request():
    """Test a single request"""
    try:
        response = requests.get(ENDPOINT, timeout=5)
        return response.status_code, response.elapsed.total_seconds()
    except Exception as e:
        return None, 0


def test_rapid_requests(num_requests=110):
    """Test rapid sequential requests to see when rate limiting kicks in"""
    print(f"\n{'='*60}")
    print(f"Test 1: Rapid Sequential Requests ({num_requests} requests)")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    
    for i in range(1, num_requests + 1):
        status_code, elapsed = test_single_request()
        timestamp = time.time() - start_time
        
        if status_code:
            symbol = "✓" if status_code == 200 else "🚫" if status_code == 429 else "✗"
            print(f"[{timestamp:6.3f}s] Request {i:3d}: {symbol} {status_code}")
            results.append((i, status_code, elapsed, timestamp))
        else:
            print(f"[{timestamp:6.3f}s] Request {i:3d}: ✗ ERROR")
            results.append((i, None, 0, timestamp))
        
        # Very small delay to avoid overwhelming the system
        time.sleep(0.01)
    
    total_time = time.time() - start_time
    analyze_results(results, total_time, num_requests)


def test_concurrent_requests(num_requests=50, num_threads=10):
    """Test concurrent requests from multiple threads"""
    print(f"\n{'='*60}")
    print(f"Test 2: Concurrent Requests ({num_requests} requests, {num_threads} threads)")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {executor.submit(test_single_request): i for i in range(1, num_requests + 1)}
        
        for future in as_completed(futures):
            request_num = futures[future]
            try:
                status_code, elapsed = future.result()
                timestamp = time.time() - start_time
                
                if status_code:
                    symbol = "✓" if status_code == 200 else "🚫" if status_code == 429 else "✗"
                    print(f"[{timestamp:6.3f}s] Request {request_num:3d}: {symbol} {status_code} ({elapsed*1000:.1f}ms)")
                    results.append((request_num, status_code, elapsed, timestamp))
                else:
                    print(f"[{timestamp:6.3f}s] Request {request_num:3d}: ✗ ERROR")
                    results.append((request_num, None, 0, timestamp))
            except Exception as e:
                print(f"Request {request_num} failed with exception: {e}")
    
    total_time = time.time() - start_time
    analyze_results(results, total_time, num_requests)


def test_sustained_rate(target_rps=2, duration=30):
    """Test sustained request rate over time"""
    print(f"\n{'='*60}")
    print(f"Test 3: Sustained Rate ({target_rps} req/s for {duration}s)")
    print(f"{'='*60}\n")
    
    results = []
    start_time = time.time()
    interval = 1.0 / target_rps
    request_num = 0
    
    while time.time() - start_time < duration:
        request_num += 1
        status_code, elapsed = test_single_request()
        timestamp = time.time() - start_time
        
        if status_code:
            symbol = "✓" if status_code == 200 else "🚫" if status_code == 429 else "✗"
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
    print(f"Successful (200):   {status_counts.get(200, 0)}")
    print(f"Rate limited (429): {status_counts.get(429, 0)}")
    print(f"Other errors:       {sum(v for k, v in status_counts.items() if k not in [200, 429])}")
    print(f"Total time:         {total_time:.2f}s")
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
    elif status_counts.get(200, 0) == total_requests:
        print(f"\n✓ All requests succeeded (within rate limit)")
    
    print()


def check_endpoint():
    """Check if the endpoint is reachable"""
    try:
        response = requests.get(ENDPOINT, timeout=5)
        return True
    except Exception as e:
        print(f"❌ Cannot reach endpoint: {ENDPOINT}")
        print(f"   Error: {e}")
        print(f"\n   Make sure the Flask app is running:")
        print(f"   python limiter.py")
        return False


def main():
    print("="*60)
    print("Rate Limiter Test Suite")
    print("="*60)
    
    if not check_endpoint():
        sys.exit(1)
    
    print(f"✓ Endpoint is reachable: {ENDPOINT}")
    print(f"  Flask limit: {DEFAULT_LIMIT} requests per minute")
    
    try:
        # Test 1: Rapid sequential requests
        test_rapid_requests(110)  # Should hit limit around 100
        
        time.sleep(2)  # Brief pause between tests
        
        # Test 2: Concurrent requests
        test_concurrent_requests(50, 10)
        
        time.sleep(2)
        
        # Test 3: Sustained rate
        test_sustained_rate(target_rps=2, duration=10)  # Should be well within limit
        
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

