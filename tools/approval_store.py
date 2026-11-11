import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from tools.approval_signer import ApprovalSigner

class ApprovalStore:
    def __init__(self, base_dir: str):
        self.approvals_path = os.path.join(base_dir, "state", "approvals.json")
        self.signer = ApprovalSigner(base_dir)
        # Ensure state dir exists
        os.makedirs(os.path.dirname(self.approvals_path), exist_ok=True)
        # Initialize if missing
        if not os.path.exists(self.approvals_path):
            self.save_approvals([])

    def load_approvals(self) -> List[Dict[str, Any]]:
        try:
            with open(self.approvals_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def save_approvals(self, approvals: List[Dict[str, Any]]) -> None:
        with open(self.approvals_path, "w", encoding="utf-8") as f:
            json.dump(approvals, f, indent=2)

    def list_approvals(self) -> List[Dict[str, Any]]:
        return self.load_approvals()

    def create_approval(
        self, plan_id: str, action_id: str, decision: str, 
        reason: str, risk_level: str, expires_minutes: int = 60
    ) -> Dict[str, Any]:
        approvals = self.load_approvals()
        
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=expires_minutes)
        
        record = {
            "approval_id": f"approval_{int(now.timestamp())}_{os.urandom(4).hex()}",
            "plan_id": plan_id,
            "action_id": action_id,
            "decision": decision,
            "approved_by": "local_user",
            "reason": reason,
            "scope": "single_action",
            "risk_level": risk_level,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "used": False,
            "used_at": None
        }
        
        record["signature"] = self.signer.sign_approval(record)
        approvals.append(record)
        self.save_approvals(approvals)
        return record

    def reject_approval(self, plan_id: str, action_id: str, reason: str) -> Dict[str, Any]:
        return self.create_approval(
            plan_id=plan_id,
            action_id=action_id,
            decision="rejected",
            reason=reason,
            risk_level="unknown",
            expires_minutes=60
        )

    def find_valid_approval(self, plan_id: str, action_id: str) -> Optional[Dict[str, Any]]:
        approvals = self.load_approvals()
        now = datetime.now(timezone.utc)
        
        for approval in approvals:
            if approval.get("plan_id") == plan_id and approval.get("action_id") == action_id:
                # Check signature
                if not self.signer.verify_approval(approval):
                    continue
                # Check unused
                if approval.get("used", False):
                    continue
                # Check decision
                if approval.get("decision") != "approved":
                    continue
                # Check expiry
                try:
                    expires_at = datetime.fromisoformat(approval.get("expires_at", ""))
                    if now > expires_at:
                        continue
                except ValueError:
                    continue
                    
                return approval
                
        return None

    def mark_used(self, approval_id: str) -> bool:
        approvals = self.load_approvals()
        for i, approval in enumerate(approvals):
            if approval.get("approval_id") == approval_id:
                if approval.get("used"):
                    return False
                approvals[i]["used"] = True
                approvals[i]["used_at"] = datetime.now(timezone.utc).isoformat()
                # Re-sign the record since we modified it
                approvals[i]["signature"] = self.signer.sign_approval(approvals[i])
                self.save_approvals(approvals)
                return True
        return False

    def list_pending_approval_actions(self) -> List[Dict[str, Any]]:
        # This requires reading from something that holds pending actions.
        # Since this wasn't fully specified, we will implement this by checking 
        # inbox or the current blocked state, or it can be passed in.
        # For MVP, returning an empty list. Real implementations will pull from a state file.
        return []
