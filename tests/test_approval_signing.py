import pytest
import os
import shutil
from tools.approval_signer import ApprovalSigner

@pytest.fixture
def temp_env(tmp_path):
    base_dir = str(tmp_path)
    os.makedirs(os.path.join(base_dir, "state"))
    return base_dir

def test_signer_creates_secret(temp_env):
    signer = ApprovalSigner(temp_env)
    assert os.path.exists(os.path.join(temp_env, "state", "approval_secret.key"))

def test_signing_and_verification(temp_env):
    signer = ApprovalSigner(temp_env)
    record = {"plan_id": "p1", "action_id": "a1", "decision": "approved"}
    
    # Sign it
    sig = signer.sign_approval(record)
    record["signature"] = sig
    
    # Verify it
    assert signer.verify_approval(record) == True
    
    # Tamper it
    record["action_id"] = "a2"
    assert signer.verify_approval(record) == False
