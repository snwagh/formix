#!/usr/bin/env python3
"""
Formix Test Runner

This script provides an easy way to run all Formix tests with different configurations.
"""

import argparse
import subprocess
import sys
from pathlib import Path

def run_test(test_file: str, verbose: bool = False) -> bool:
    """Run a single test file."""
    print(f"\n{'='*60}")
    print(f"Running {test_file}")
    print('='*60)

    cmd = [sys.executable, test_file]
    if verbose:
        cmd.append('-v')

    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {test_file}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Run Formix tests")
    parser.add_argument('--test', choices=['basic', 'crypto', 'medium', 'large', 'all'],
                       default='all', help='Which test to run')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--skip-large', action='store_true', help='Skip large-scale test')

    args = parser.parse_args()

    tests_dir = Path(__file__).parent
    results = []

    if args.test == 'all' or args.test == 'basic':
        results.append(('Basic Test', run_test(str(tests_dir / 'test_basic.py'), args.verbose)))

    if args.test == 'all' or args.test == 'crypto':
        results.append(('Crypto Test', run_test(str(tests_dir / 'test_crypto.py'), args.verbose)))

    if args.test == 'all' or args.test == 'medium':
        results.append(('Medium Scale Test', run_test(str(tests_dir / 'test_medium_scale.py'), args.verbose)))

    if args.test == 'all' or args.test == 'large':
        if not args.skip_large:
            results.append(('Large Scale Test', run_test(str(tests_dir / 'test_large_scale.py'), args.verbose)))
        else:
            print("\nSkipping large-scale test (--skip-large)")

    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)

    passed = 0
    total = len(results)

    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
        if success:
            passed += 1

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
