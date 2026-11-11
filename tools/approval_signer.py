import hmac
import hashlib
import secrets
import json
import os
from typing import Dict, Any

class ApprovalSigner:
    def __init__(self, base_dir: str):
        self.secret_path = os.path.join(base_dir, "state", "approval_secret.key")
        self.secret = self.create_secret_if_missing()

    def create_secret_if_missing(self) -> bytes:
        if not os.path.exists(os.path.dirname(self.secret_path)):
            os.makedirs(os.path.dirname(self.secret_path), exist_ok=True)
            
        if not os.path.exists(self.secret_path):
            new_secret = secrets.token_bytes(32)
            with open(self.secret_path, "wb") as f:
                f.write(new_secret)
            try:
                os.chmod(self.secret_path, 0o600)
            except OSError:
                pass
            return new_secret
            
        with open(self.secret_path, "rb") as f:
            return f.read()

    def _get_signature_payload(self, record: Dict[str, Any]) -> str:
        # Create deterministic payload ignoring existing signature
        payload_dict = {
            k: v for k, v in record.items() 
            if k != "signature"
        }
        # Sort keys to ensure deterministic ordering
        return json.dumps(payload_dict, sort_keys=True)

    def sign_approval(self, record_without_signature: Dict[str, Any]) -> str:
        payload = self._get_signature_payload(record_without_signature)
        signature = hmac.new(
            self.secret, 
            payload.encode('utf-8'), 
            hashlib.sha256
        ).hexdigest()
        return signature

    def verify_approval(self, record: Dict[str, Any]) -> bool:
        if "signature" not in record:
            return False
        
        expected_signature = self.sign_approval(record)
        return self.constant_time_compare(record["signature"], expected_signature)

    def constant_time_compare(self, val1: str, val2: str) -> bool:
        return hmac.compare_digest(val1, val2)
