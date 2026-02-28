import logging
import os
from typing import Optional

# OddsAPI Quota Logger
class OddsApiQuotaLogger:
    def __init__(self, log_path: Optional[str] = None):
        self.logger = logging.getLogger("OddsApiQuota")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            # File handler if path provided, else stream
            if log_path:
                fh = logging.FileHandler(log_path)
                fh.setLevel(logging.INFO)
                formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                fh.setFormatter(formatter)
                self.logger.addHandler(fh)
            else:
                sh = logging.StreamHandler()
                sh.setLevel(logging.INFO)
                formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
                sh.setFormatter(formatter)
                self.logger.addHandler(sh)

    def log_quota(self, quota, context: str = ""):  # quota: OddsApiQuota
        msg = f"Quota status after {context}: remaining={quota.remaining}, used={quota.used}, last_cost={quota.last_cost}"
        self.logger.info(msg)

    def log_warning(self, msg: str):
        self.logger.warning(msg)

    def log_error(self, msg: str):
        self.logger.error(msg)
