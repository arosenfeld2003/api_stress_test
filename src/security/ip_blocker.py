"""
IP Blocker and Abuse Detection System

Tracks IP addresses and automatically blocks those that demonstrate
illegitimate request patterns (high failure rates, excessive requests, etc.)
"""

import time
from collections import defaultdict
from typing import Dict, Set, Optional, Tuple
from threading import Lock
import logging

logger = logging.getLogger(__name__)


class IPTracker:
    """Tracks request metrics per IP address."""
    
    def __init__(self, window_seconds: int = 60):
        """
        Args:
            window_seconds: Time window for tracking metrics (default: 60 seconds)
        """
        self.window_seconds = window_seconds
        self.request_history: Dict[str, list] = defaultdict(list)  # IP -> list of (timestamp, status_code)
        self.lock = Lock()
    
    def record_request(self, ip: str, status_code: int):
        """Record a request from an IP address."""
        current_time = time.time()
        
        with self.lock:
            # Add this request
            self.request_history[ip].append((current_time, status_code))
            
            # Clean up old requests outside the window
            cutoff_time = current_time - self.window_seconds
            self.request_history[ip] = [
                (ts, code) for ts, code in self.request_history[ip]
                if ts > cutoff_time
            ]
    
    def get_metrics(self, ip: str) -> Dict:
        """
        Get metrics for an IP address.
        
        Returns:
            Dictionary with:
            - total_requests: Total requests in the window
            - failed_requests: Count of failed requests (4xx, 5xx, excluding 429)
            - rate_limited: Count of 429 responses
            - failure_rate: Percentage of failed requests (0-100)
            - rate_limit_rate: Percentage of rate-limited requests (0-100)
            - requests_per_second: Average requests per second
        """
        with self.lock:
            requests = self.request_history.get(ip, [])
            current_time = time.time()
            cutoff_time = current_time - self.window_seconds
            
            # Filter to window
            recent_requests = [
                (ts, code) for ts, code in requests
                if ts > cutoff_time
            ]
            
            if not recent_requests:
                return {
                    'total_requests': 0,
                    'failed_requests': 0,
                    'rate_limited': 0,
                    'failure_rate': 0.0,
                    'rate_limit_rate': 0.0,
                    'requests_per_second': 0.0,
                }
            
            total = len(recent_requests)
            failed = sum(1 for _, code in recent_requests if 400 <= code < 600 and code != 429)
            rate_limited = sum(1 for _, code in recent_requests if code == 429)
            
            # Calculate requests per second
            if recent_requests:
                time_span = max(ts for ts, _ in recent_requests) - min(ts for ts, _ in recent_requests)
                time_span = max(time_span, 1.0)  # Avoid division by zero
                rps = total / time_span
            else:
                rps = 0.0
            
            return {
                'total_requests': total,
                'failed_requests': failed,
                'rate_limited': rate_limited,
                'failure_rate': (failed / total * 100) if total > 0 else 0.0,
                'rate_limit_rate': (rate_limited / total * 100) if total > 0 else 0.0,
                'requests_per_second': rps,
            }


class IPBlocker:
    """
    Detects and blocks IP addresses that demonstrate abusive behavior.
    
    An IP is considered abusive if it shows:
    - High failure rate (many 4xx/5xx responses, excluding intentional 429s)
    - Extremely high request rate (likely automated attacks)
    - Pattern of repeated failures (probing, scanning)
    """
    
    def __init__(
        self,
        window_seconds: int = 60,
        max_requests_per_minute: int = 200,  # Higher than normal rate limit
        max_failure_rate: float = 50.0,  # 50% failure rate threshold
        max_rate_limit_rate: float = 90.0,  # 90% rate-limited = abusive
        block_duration_seconds: int = 300,  # 5 minutes
        min_requests_for_abuse: int = 20,  # Need at least 20 requests to judge
    ):
        """
        Args:
            window_seconds: Time window for tracking (default: 60 seconds)
            max_requests_per_minute: Max requests/min before blocking (default: 200)
            max_failure_rate: Max failure rate % before blocking (default: 50%)
            max_rate_limit_rate: Max rate-limit rate % before blocking (default: 90%)
            block_duration_seconds: How long to block an IP (default: 300 = 5 min)
            min_requests_for_abuse: Minimum requests needed to judge abuse (default: 20)
        """
        self.tracker = IPTracker(window_seconds)
        self.max_requests_per_minute = max_requests_per_minute
        self.max_failure_rate = max_failure_rate
        self.max_rate_limit_rate = max_rate_limit_rate
        self.block_duration_seconds = block_duration_seconds
        self.min_requests_for_abuse = min_requests_for_abuse
        
        # Blocked IPs: IP -> unblock timestamp
        self.blocked_ips: Dict[str, float] = {}
        self.whitelist: Set[str] = set()
        self.lock = Lock()
    
    def whitelist_ip(self, ip: str):
        """Add an IP to the whitelist (never blocked)."""
        with self.lock:
            self.whitelist.add(ip)
            # Remove from blocked if present
            self.blocked_ips.pop(ip, None)
    
    def remove_from_whitelist(self, ip: str):
        """Remove an IP from the whitelist."""
        with self.lock:
            self.whitelist.discard(ip)
    
    def is_whitelisted(self, ip: str) -> bool:
        """Check if an IP is whitelisted."""
        with self.lock:
            return ip in self.whitelist
    
    def record_request(self, ip: str, status_code: int):
        """Record a request and check if IP should be blocked."""
        # Don't track whitelisted IPs
        if self.is_whitelisted(ip):
            return
        
        self.tracker.record_request(ip, status_code)
        self._check_and_block(ip)
    
    def _check_and_block(self, ip: str):
        """Check if an IP should be blocked based on metrics."""
        metrics = self.tracker.get_metrics(ip)
        
        # Need enough requests to make a judgment
        if metrics['total_requests'] < self.min_requests_for_abuse:
            return
        
        # Check various abuse patterns
        should_block = False
        reason = None
        
        # Pattern 1: Extremely high request rate (likely automated attack)
        requests_per_minute = metrics['requests_per_second'] * 60
        if requests_per_minute > self.max_requests_per_minute:
            should_block = True
            reason = f"excessive request rate ({requests_per_minute:.1f} req/min)"
        
        # Pattern 2: High failure rate (probing, scanning, invalid requests)
        elif metrics['failure_rate'] > self.max_failure_rate:
            should_block = True
            reason = f"high failure rate ({metrics['failure_rate']:.1f}%)"
        
        # Pattern 3: Extremely high rate-limit rate (persistent abuse despite rate limits)
        elif metrics['rate_limit_rate'] > self.max_rate_limit_rate:
            should_block = True
            reason = f"persistent rate limit violations ({metrics['rate_limit_rate']:.1f}%)"
        
        if should_block:
            with self.lock:
                unblock_time = time.time() + self.block_duration_seconds
                self.blocked_ips[ip] = unblock_time
                logger.warning(
                    f"Blocked IP {ip} for {reason}. "
                    f"Metrics: {metrics['total_requests']} req, "
                    f"{metrics['failure_rate']:.1f}% failures, "
                    f"{metrics['rate_limit_rate']:.1f}% rate-limited, "
                    f"{metrics['requests_per_second']:.1f} req/s"
                )
    
    def is_blocked(self, ip: str) -> bool:
        """
        Check if an IP is currently blocked.
        
        Returns:
            True if IP is blocked, False otherwise
        """
        # Whitelisted IPs are never blocked
        if self.is_whitelisted(ip):
            return False
        
        with self.lock:
            # Clean up expired blocks
            current_time = time.time()
            expired_ips = [
                blocked_ip for blocked_ip, unblock_time in self.blocked_ips.items()
                if unblock_time <= current_time
            ]
            for expired_ip in expired_ips:
                del self.blocked_ips[expired_ip]
                logger.info(f"Unblocked IP {expired_ip} (block expired)")
            
            return ip in self.blocked_ips
    
    def get_block_info(self, ip: str) -> Optional[Dict]:
        """
        Get information about a blocked IP.
        
        Returns:
            Dictionary with block info or None if not blocked
        """
        with self.lock:
            if ip not in self.blocked_ips:
                return None
            
            unblock_time = self.blocked_ips[ip]
            remaining = max(0, unblock_time - time.time())
            metrics = self.tracker.get_metrics(ip)
            
            return {
                'blocked': True,
                'unblock_time': unblock_time,
                'remaining_seconds': remaining,
                'metrics': metrics,
            }
    
    def get_metrics(self, ip: str) -> Dict:
        """Get current metrics for an IP."""
        return self.tracker.get_metrics(ip)
    
    def manually_block(self, ip: str, duration_seconds: Optional[int] = None):
        """Manually block an IP address."""
        duration = duration_seconds or self.block_duration_seconds
        with self.lock:
            self.blocked_ips[ip] = time.time() + duration
            logger.info(f"Manually blocked IP {ip} for {duration} seconds")
    
    def manually_unblock(self, ip: str):
        """Manually unblock an IP address."""
        with self.lock:
            if ip in self.blocked_ips:
                del self.blocked_ips[ip]
                logger.info(f"Manually unblocked IP {ip}")

