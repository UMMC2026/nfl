"""
Delayed Verification System for Prop Betting
Implements: Stats are better late than wrong
"""

import json
import time
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import threading
from pathlib import Path
import logging
import schedule
import pandas as pd

# Import your existing modules
try:
    from injury_gate import get_injury_feed_health
except ImportError:
    def get_injury_feed_health():
        return "UNKNOWN"


class VerificationStatus(Enum):
    PENDING = "pending"           # Waiting for verification
    IN_PROGRESS = "in_progress"   # Currently verifying
    VERIFIED = "verified"         # Successfully verified
    FAILED = "failed"             # Verification failed
    TIMEOUT = "timeout"           # Verification timed out


class ConfidenceLevel(Enum):
    ESTIMATE = "estimate"         # Unverified, from fast sources
    MEDIUM = "medium"             # Partially verified
    HIGH = "high"                 # Fully verified
    CONSERVATIVE = "conservative" # Conservative estimate (degraded mode)


@dataclass
class StatsRequest:
    """A request for stats verification"""
    request_id: str
    player: str
    player_id: Optional[str]
    game_date: str  # YYYY-MM-DD
    game_id: Optional[str]
    stat_type: str  # points, rebounds, assists, etc.
    created_at: datetime
    timeout_minutes: int = 120  # Max wait for verification
    priority: int = 1  # 1=high (star players), 5=low

    # Sources attempted
    sources_attempted: List[str] = None
    sources_succeeded: List[str] = None

    # Results
    estimated_value: Optional[float] = None
    verified_value: Optional[float] = None
    verification_time: Optional[datetime] = None
    confidence: ConfidenceLevel = ConfidenceLevel.ESTIMATE
    status: VerificationStatus = VerificationStatus.PENDING

    # Metadata
    sport: str = "NBA"
    team: Optional[str] = None
    opponent: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.verification_time:
            data['verification_time'] = self.verification_time.isoformat()
        data['confidence'] = self.confidence.value
        data['status'] = self.status.value
        return data

    @property
    def is_expired(self) -> bool:
        """Check if verification has timed out"""
        expiry = self.created_at + timedelta(minutes=self.timeout_minutes)
        return datetime.now() > expiry

    @property
    def age_minutes(self) -> float:
        """How many minutes since request was created"""
        return (datetime.now() - self.created_at).total_seconds() / 60


class DelayedVerificationSystem:
    """
    Main system for delayed stats verification
    Core principle: Better to wait for accurate stats than use wrong ones
    """

    def __init__(self, config_path: Optional[Path] = None):
        # Configuration
        if config_path is None:
            config_path = Path("config/stats_sources/verification_config.json")
        self.config = self._load_config(config_path)

        # Storage paths
        self.queue_dir = Path("data/verification_queue")
        self.verified_dir = Path("data/verified_stats")
        self.log_dir = Path("logs/stats_verification")

        # Ensure directories exist
        for directory in [self.queue_dir, self.verified_dir, self.log_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        # In-memory tracking
        self.active_requests: Dict[str, StatsRequest] = {}
        self.pending_verifications: List[str] = []  # Request IDs
        self.verified_stats: Dict[str, Dict] = {}   # player_game_date -> verified stats

        # Threading
        self.lock = threading.Lock()
        self.running = False
        self.verification_thread = None

        # Setup logging
        self.logger = self._setup_logging()

        # Load existing verified stats
        self._load_verified_stats()

        self.logger.info("Delayed Verification System initialized")

    # ==================== PUBLIC API ====================

    def get_player_stats(self, player: str, game_date: str,
                         stat_type: str, immediate_only: bool = False) -> Dict[str, Any]:
        """Get player stats with delayed verification
        Returns immediately with best available data"""
        # Generate unique key
        stats_key = f"{player}_{game_date}_{stat_type}"

        # Check if already verified
        with self.lock:
            if stats_key in self.verified_stats:
                verified = self.verified_stats[stats_key]
                self.logger.debug(f"Returning verified stats for {stats_key}: {verified['value']}")
                return verified

        # Check for pending verification
        pending_request = self._find_pending_request(player, game_date, stat_type)

        if pending_request and not immediate_only:
            # Return current best estimate from pending request
            return {
                'value': pending_request.estimated_value,
                'confidence': pending_request.confidence.value,
                'verified': False,
                'request_id': pending_request.request_id,
                'status': 'pending_verification',
                'estimated_verification_time': (
                    pending_request.created_at +
                    timedelta(minutes=self.config['verification_timeout'])
                ).isoformat()
            }

        # Create new verification request
        request = self._create_verification_request(
            player=player,
            game_date=game_date,
            stat_type=stat_type,
            immediate_only=immediate_only
        )

        # Start background verification if needed
        if not immediate_only:
            self._queue_for_verification(request)

        # Return immediate estimate
        return {
            'value': request.estimated_value,
            'confidence': request.confidence.value,
            'verified': False,
            'request_id': request.request_id,
            'status': 'estimated' if immediate_only else 'queued_for_verification',
            'note': 'Using fast estimate, verification in progress' if not immediate_only else 'Immediate estimate only'
        }

    def get_conservative_estimate(self, player: str, game_date: str,
                                  stat_type: str) -> Dict[str, Any]:
        """Get conservative estimate for degraded mode
        Uses historical averages with safety margin"""
        # Load player historical data
        historical = self._get_player_historical(player, stat_type)

        if historical:
            # Use 10th percentile for unders, 90th for overs (conservative)
            if 'under' in stat_type.lower():
                estimate = historical.get('percentile_10', historical.get('mean', 0))
                confidence = 0.60  # Low confidence for conservative
            else:
                estimate = historical.get('percentile_90', historical.get('mean', 0))
                confidence = 0.60
        else:
            # No historical data
            estimate = 0
            confidence = 0.50

        return {
            'value': estimate,
            'confidence': 'conservative',
            'verified': False,
            'source': 'historical_estimate',
            'note': 'Conservative estimate using historical data'
        }

    def force_verify_request(self, request_id: str) -> bool:
        """Force verification of a specific request"""
        with self.lock:
            if request_id not in self.active_requests:
                self.logger.warning(f"Request {request_id} not found")
                return False

            request = self.active_requests[request_id]
            if request.status == VerificationStatus.VERIFIED:
                self.logger.info(f"Request {request_id} already verified")
                return True

            # Move to front of queue
            self.pending_verifications.insert(0, request_id)
            return True

    def get_system_status(self) -> Dict[str, Any]:
        """Get system status for monitoring"""
        with self.lock:
            total_requests = len(self.active_requests)
            pending = len([r for r in self.active_requests.values()
                           if r.status == VerificationStatus.PENDING])
            verified = len([r for r in self.active_requests.values()
                            if r.status == VerificationStatus.VERIFIED])
            in_progress = len([r for r in self.active_requests.values()
                               if r.status == VerificationStatus.IN_PROGRESS])

            avg_age = sum(r.age_minutes for r in self.active_requests.values()) / total_requests if total_requests > 0 else 0

            return {
                'total_requests': total_requests,
                'pending': pending,
                'verified': verified,
                'in_progress': in_progress,
                'failed': total_requests - pending - verified - in_progress,
                'average_age_minutes': avg_age,
                'verified_stats_count': len(self.verified_stats),
                'queue_size': len(self.pending_verifications)
            }

    def start_background_verification(self):
        """Start background verification thread"""
        if self.running:
            self.logger.warning("Background verification already running")
            return

        self.running = True
        self.verification_thread = threading.Thread(
            target=self._verification_worker,
            daemon=True,
            name="StatsVerificationWorker"
        )
        self.verification_thread.start()
        self.logger.info("Background verification started")

    def stop_background_verification(self):
        """Stop background verification"""
        self.running = False
        if self.verification_thread:
            self.verification_thread.join(timeout=5)
        self.logger.info("Background verification stopped")

    # ==================== PRIVATE METHODS ====================

    def _load_config(self, config_path: Path) -> Dict:
        """Load verification configuration"""
        default_config = {
            'verification_timeout': 120,  # minutes
            'max_concurrent_verifications': 5,
            'retry_attempts': 3,
            'retry_delay_minutes': 5,
            'sources': {
                'fast': {
                    'nba_api': {'timeout': 5, 'priority': 1},
                    'espn_scrape': {'timeout': 10, 'priority': 2}
                },
                'slow_reliable': {
                    'basketball_reference': {'delay_minutes': 30, 'priority': 1},
                    'nba_official_boxscore': {'delay_minutes': 45, 'priority': 1},
                    'espn_official': {'delay_minutes': 60, 'priority': 2}
                }
            },
            'conservative_estimates': {
                'historical_games': 10,
                'safety_margin': 0.15,  # 15% safety margin
                'min_confidence': 0.60
            }
        }

        if config_path.exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                # Deep merge
                import copy
                config = copy.deepcopy(default_config)
                self._deep_merge(config, user_config)
                return config

        # Create default config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=2)

        return default_config

    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge two dictionaries"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value

    def _setup_logging(self) -> logging.Logger:
        """Setup logging for verification system"""
        logger = logging.getLogger("stats_verification")
        logger.setLevel(logging.INFO)

        # File handler
        log_file = self.log_dir / f"verification_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        return logger

    def _load_verified_stats(self):
        """Load previously verified stats from disk"""
        verified_files = list(self.verified_dir.glob("*.json"))

        for file_path in verified_files:
            try:
                with open(file_path, 'r') as f:
                    stats = json.load(f)

                # Create key: player_game_date_stat
                key = f"{stats['player']}_{stats['game_date']}_{stats['stat_type']}"
                self.verified_stats[key] = stats

            except Exception as e:
                self.logger.error(f"Error loading verified stats from {file_path}: {e}")

        self.logger.info(f"Loaded {len(self.verified_stats)} verified stats")

    def _create_verification_request(self, player: str, game_date: str,
                                     stat_type: str, immediate_only: bool = False) -> StatsRequest:
        """Create a new verification request"""
        # Generate request ID
        request_id = hashlib.md5(
            f"{player}_{game_date}_{stat_type}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]

        # Try fast sources first
        fast_value = self._try_fast_sources(player, game_date, stat_type)

        if fast_value is not None:
            estimated_value = fast_value
            confidence = ConfidenceLevel.ESTIMATE
            sources_succeeded = ['fast_source']
        else:
            # Use conservative estimate
            conservative = self.get_conservative_estimate(player, game_date, stat_type)
            estimated_value = conservative['value']
            confidence = ConfidenceLevel.CONSERVATIVE
            sources_succeeded = ['conservative_estimate']

        # Create request
        request = StatsRequest(
            request_id=request_id,
            player=player,
            game_date=game_date,
            stat_type=stat_type,
            created_at=datetime.now(),
            timeout_minutes=self.config['verification_timeout'],
            estimated_value=estimated_value,
            confidence=confidence,
            status=VerificationStatus.PENDING if not immediate_only else VerificationStatus.FAILED,
            sources_succeeded=sources_succeeded
        )

        # Save to disk
        self._save_request(request)

        # Store in memory
        with self.lock:
            self.active_requests[request_id] = request

        self.logger.info(f"Created verification request {request_id} for {player} ({stat_type})")

        return request

    def _try_fast_sources(self, player: str, game_date: str, stat_type: str) -> Optional[float]:
        """Try fast sources for immediate estimate"""
        fast_sources = self.config['sources']['fast']

        for source_name, source_config in fast_sources.items():
            try:
                self.logger.debug(f"Trying fast source: {source_name}")

                if source_name == 'nba_api':
                    value = self._call_nba_api(player, game_date, stat_type)
                elif source_name == 'espn_scrape':
                    value = self._scrape_espn(player, game_date, stat_type)
                else:
                    continue

                if value is not None:
                    self.logger.debug(f"Fast source {source_name} returned: {value}")
                    return value

            except Exception as e:
                self.logger.debug(f"Fast source {source_name} failed: {e}")
                continue

        return None

    def _call_nba_api(self, player: str, game_date: str, stat_type: str) -> Optional[float]:
        """Call NBA API (your existing implementation)"""
        # This would integrate with your existing NBA API calls
        # For now, return None to simulate frequent failures
        return None

    def _scrape_espn(self, player: str, game_date: str, stat_type: str) -> Optional[float]:
        """Scrape ESPN for stats"""
        # This would be your ESPN scraping logic
        # For now, return None
        return None

    def _find_pending_request(self, player: str, game_date: str,
                               stat_type: str) -> Optional[StatsRequest]:
        """Find existing pending request for same player/date/stat"""
        with self.lock:
            for request in self.active_requests.values():
                if (request.player == player and
                        request.game_date == game_date and
                        request.stat_type == stat_type and
                        request.status in [VerificationStatus.PENDING, VerificationStatus.IN_PROGRESS]):
                    return request
        return None

    def _queue_for_verification(self, request: StatsRequest):
        """Add request to verification queue"""
        with self.lock:
            if request.request_id not in self.pending_verifications:
                self.pending_verifications.append(request.request_id)
                request.status = VerificationStatus.PENDING

        self._save_request(request)
        self.logger.debug(f"Queued request {request.request_id} for verification")

    def _verification_worker(self):
        """Background worker for verification"""
        self.logger.info("Verification worker started")

        while self.running:
            try:
                # Process pending verifications
                self._process_pending_verifications()

                # Clean up expired requests
                self._cleanup_expired_requests()

                # Sleep before next iteration
                time.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Error in verification worker: {e}")
                time.sleep(60)  # Sleep longer on error

    def _process_pending_verifications(self):
        """Process pending verification requests"""
        max_concurrent = self.config['max_concurrent_verifications']

        # Count currently in progress
        with self.lock:
            in_progress = sum(
                1 for r in self.active_requests.values()
                if r.status == VerificationStatus.IN_PROGRESS
            )

        # Process available slots
        available_slots = max_concurrent - in_progress

        for _ in range(min(available_slots, len(self.pending_verifications))):
            with self.lock:
                if not self.pending_verifications:
                    break

                request_id = self.pending_verifications.pop(0)
                if request_id not in self.active_requests:
                    continue

                request = self.active_requests[request_id]
                request.status = VerificationStatus.IN_PROGRESS

            # Process in separate thread to avoid blocking
            threading.Thread(
                target=self._verify_request,
                args=(request,),
                daemon=True,
                name=f"Verify_{request_id}"
            ).start()

    def _verify_request(self, request: StatsRequest):
        """Verify a single request using reliable sources"""
        self.logger.info(f"Starting verification for {request.request_id}")

        retry_attempts = self.config['retry_attempts']

        for attempt in range(retry_attempts):
            try:
                # Wait if needed (for delayed sources)
                if attempt > 0:
                    wait_minutes = self.config['retry_delay_minutes'] * attempt
                    self.logger.debug(f"Retry attempt {attempt + 1}, waiting {wait_minutes} minutes")
                    time.sleep(wait_minutes * 60)

                # Try reliable sources
                reliable_value = self._try_reliable_sources(
                    request.player, request.game_date, request.stat_type
                )

                if reliable_value is not None:
                    # Verification successful
                    request.verified_value = reliable_value
                    request.verification_time = datetime.now()
                    request.confidence = ConfidenceLevel.HIGH
                    request.status = VerificationStatus.VERIFIED

                    # Save verified stats
                    self._save_verified_stats(request)

                    # Notify system of verified stats
                    self._notify_verified_stats(request)

                    self.logger.info(f"Verified {request.request_id}: {reliable_value}")
                    return

            except Exception as e:
                self.logger.error(f"Error verifying {request.request_id} (attempt {attempt + 1}): {e}")

        # All attempts failed
        request.status = VerificationStatus.FAILED
        self.logger.warning(f"Failed to verify {request.request_id} after {retry_attempts} attempts")

        # Save updated request
        self._save_request(request)

    def _try_reliable_sources(self, player: str, game_date: str,
                               stat_type: str) -> Optional[float]:
        """Try reliable (but slower) sources"""
        reliable_sources = self.config['sources']['slow_reliable']

        values = []

        for source_name, source_config in reliable_sources.items():
            try:
                self.logger.debug(f"Trying reliable source: {source_name}")

                # Check if enough time has passed for this source
                game_datetime = datetime.strptime(game_date, "%Y-%m-%d")
                time_since_game = datetime.now() - game_datetime
                required_delay = timedelta(minutes=source_config.get('delay_minutes', 0))

                if time_since_game < required_delay:
                    self.logger.debug(f"Skipping {source_name}, not enough time passed")
                    continue

                if source_name == 'basketball_reference':
                    value = self._scrape_basketball_reference(player, game_date, stat_type)
                elif source_name == 'nba_official_boxscore':
                    value = self._get_nba_official_boxscore(player, game_date, stat_type)
                elif source_name == 'espn_official':
                    value = self._get_espn_official(player, game_date, stat_type)
                else:
                    continue

                if value is not None:
                    values.append((value, source_name))
                    self.logger.debug(f"Reliable source {source_name} returned: {value}")

            except Exception as e:
                self.logger.debug(f"Reliable source {source_name} failed: {e}")
                continue

        if values:
            # Take the most common value if multiple sources agree
            from collections import Counter
            value_counter = Counter([v[0] for v in values])
            most_common = value_counter.most_common(1)[0]

            if most_common[1] > 1:  # Multiple sources agree
                self.logger.info(f"Multiple reliable sources agree on value: {most_common[0]}")
                return most_common[0]
            else:
                # Single source, use it with caution
                self.logger.info(f"Single reliable source: {values[0][1]} = {values[0][0]}")
                return values[0][0]

        return None

    def _scrape_basketball_reference(self, player: str, game_date: str,
                                      stat_type: str) -> Optional[float]:
        """Scrape Basketball Reference"""
        # Implementation would go here
        # For now, simulate 95% success rate
        import random
        if random.random() < 0.95:
            return random.uniform(5, 30)  # Simulated stat
        return None

    def _get_nba_official_boxscore(self, player: str, game_date: str,
                                    stat_type: str) -> Optional[float]:
        """Get NBA official boxscore"""
        # Implementation would go here
        # For now, simulate 90% success rate
        import random
        if random.random() < 0.90:
            return random.uniform(5, 30)
        return None

    def _get_espn_official(self, player: str, game_date: str,
                            stat_type: str) -> Optional[float]:
        """Get ESPN official stats"""
        # Implementation would go here
        # For now, simulate 85% success rate
        import random
        if random.random() < 0.85:
            return random.uniform(5, 30)
        return None

    def _get_player_historical(self, player: str, stat_type: str) -> Dict[str, float]:
        """Get player historical stats"""
        # This would load from your historical database
        # For now, return dummy data
        return {
            'mean': 15.5,
            'std': 5.2,
            'percentile_10': 8.3,
            'percentile_90': 22.7,
            'games': 42
        }

    def _save_request(self, request: StatsRequest):
        """Save request to disk"""
        file_path = self.queue_dir / f"{request.request_id}.json"
        with open(file_path, 'w') as f:
            json.dump(request.to_dict(), f, indent=2)

    def _save_verified_stats(self, request: StatsRequest):
        """Save verified stats to disk"""
        if not request.verified_value:
            return

        stats_data = {
            'player': request.player,
            'game_date': request.game_date,
            'stat_type': request.stat_type,
            'value': request.verified_value,
            'verified_at': request.verification_time.isoformat(),
            'request_id': request.request_id,
            'sources': request.sources_succeeded,
            'confidence': request.confidence.value
        }

        # Create key for storage
        stats_key = f"{request.player}_{request.game_date}_{request.stat_type}"

        # Save to file
        file_path = self.verified_dir / f"{stats_key}.json"
        with open(file_path, 'w') as f:
            json.dump(stats_data, f, indent=2)

        # Store in memory
        with self.lock:
            self.verified_stats[stats_key] = stats_data

    def _notify_verified_stats(self, request: StatsRequest):
        """Notify the system that stats have been verified"""
        # This would trigger updates to:
        # 1. Learning system (calibration)
        # 2. Any pending picks using these stats
        # 3. Performance tracking

        self.logger.info(f"Stats verified: {request.player} {request.game_date} {request.stat_type} = {request.verified_value}")

        # In a full implementation, this would:
        # - Update calibration_history.csv
        # - Recalculate any affected picks
        # - Send notifications if bets were made with estimates

    def _cleanup_expired_requests(self):
        """Clean up expired verification requests"""
        with self.lock:
            expired_requests = []

            for request_id, request in list(self.active_requests.items()):
                if request.is_expired and request.status == VerificationStatus.PENDING:
                    request.status = VerificationStatus.TIMEOUT
                    expired_requests.append(request_id)

                    # Remove from pending queue
                    if request_id in self.pending_verifications:
                        self.pending_verifications.remove(request_id)

                    # Save updated request
                    self._save_request(request)

            # Log cleanup
            if expired_requests:
                self.logger.warning(f"Cleaned up {len(expired_requests)} expired requests")
