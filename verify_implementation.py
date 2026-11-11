#!/usr/bin/env python3
"""
Verification Script - Browser LLM Bridge Implementation
Run this to verify the implementation is complete and working.
"""

import subprocess
import json
import sys
import os

def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Command: {cmd}")
    print('='*60)

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print(f"✓ PASSED")
            if result.stdout:
                # Show first 500 chars of output
                output = result.stdout[:500]
                print(f"Output (truncated): {output}")
        else:
            print(f"✗ FAILED")
            print(f"Error: {result.stderr}")
            return False

        return True
    except subprocess.TimeoutExpired:
        print(f"✗ TIMEOUT")
        return False
    except Exception as e:
        print(f"✗ ERROR: {e}")
        return False

def main():
    """Run verification checks."""
    print("\n" + "="*60)
    print("BROWSER LLM BRIDGE - VERIFICATION SUITE")
    print("="*60)

    tests = [
        ("python -m pytest tests/ -q", "Run all tests (should pass 63)"),
        ("python runtime.py --doctor", "Doctor health check"),
        ("python runtime.py --browser-provider-status", "Browser provider status"),
        ("python runtime.py --generate-browser-model-prompt", "Generate browser model prompt"),
    ]

    results = []
    for cmd, description in tests:
        passed = run_command(cmd, description)
        results.append((description, passed))

    # Summary
    print(f"\n{'='*60}")
    print("VERIFICATION SUMMARY")
    print('='*60)

    for description, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {description}")

    total = len(results)
    passed_count = sum(1 for _, p in results if p)

    print(f"\nTotal: {passed_count}/{total} checks passed")

    if passed_count == total:
        print("\n✓ ALL VERIFICATION CHECKS PASSED")
        print("\nNext steps:")
        print("1. python runtime.py --open-browser-provider")
        print("2. Log into BoodleBox at https://box.boodle.ai/launch/chat")
        print("3. Copy prompt from state/model_prompt.md")
        print("4. Paste into BoodleBox chat")
        print("5. Copy response and save to inbox/provider_responses/response.txt")
        print("6. python runtime.py --ingest-browser-model-response")
        print("7. python runtime.py --run-next")
        return 0
    else:
        print("\n✗ SOME CHECKS FAILED - SEE ABOVE")
        return 1

if __name__ == "__main__":
    sys.exit(main())
