#!/usr/bin/env python
"""
Chat Functionality Test Runner

This script runs all chat-related tests and generates a report 
of the test results for easy analysis.
"""

import os
import sys
import time
import json
import subprocess
from datetime import datetime
import argparse

# Set up paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Default report location
DEFAULT_REPORT_DIR = os.path.join(PROJECT_ROOT, "test_reports")

# Test files
TEST_FILES = [
    os.path.join(SCRIPT_DIR, "test_chat_functionality.py"),
    os.path.join(SCRIPT_DIR, "test_chat_e2e.py"),
]

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run chat functionality tests and generate reports")
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR, 
                        help="Directory to save test reports")
    parser.add_argument("--verbose", "-v", action="store_true", 
                        help="Enable verbose output")
    parser.add_argument("--junit", action="store_true", 
                        help="Generate JUnit XML reports")
    parser.add_argument("--html", action="store_true", 
                        help="Generate HTML report")
    parser.add_argument("--filter", default=None, 
                        help="Filter tests by name pattern")
    return parser.parse_args()

def run_tests(args):
    """Run all the chat-related tests."""
    # Ensure report directory exists
    os.makedirs(args.report_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_prefix = f"chat_tests_{timestamp}"
    
    # Dictionary to store test results
    results = {
        "timestamp": timestamp,
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "duration": 0,
        "test_files": []
    }
    
    # Measure total duration
    start_time = time.time()
    
    # Run each test file
    for test_file in TEST_FILES:
        if not os.path.exists(test_file):
            print(f"Warning: Test file {test_file} does not exist. Skipping.")
            continue
        
        file_name = os.path.basename(test_file)
        file_result = {
            "file": file_name,
            "duration": 0,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "cases": []
        }
        
        # Prepare pytest arguments
        pytest_args = ["-v"]
        
        # Add filter if provided
        if args.filter:
            pytest_args.append(f"-k={args.filter}")
        
        # Add JUnit XML output if requested
        if args.junit:
            junit_file = os.path.join(args.report_dir, f"{report_prefix}_{file_name}.xml")
            pytest_args.extend(["--junitxml", junit_file])
        
        # Add HTML report if requested
        if args.html:
            html_file = os.path.join(args.report_dir, f"{report_prefix}_{file_name}.html")
            pytest_args.extend(["--html", html_file, "--self-contained-html"])
        
        # Run the test
        file_start_time = time.time()
        print(f"\n{'-'*60}")
        print(f"Running tests from {file_name}...")
        print(f"{'-'*60}")
        
        command = [sys.executable, "-m", "pytest", test_file] + pytest_args
        
        try:
            # Run pytest as a subprocess
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Process the output
            for line in process.stdout:
                if args.verbose:
                    print(line, end='')
                
                # Parse test results (simplified)
                if line.strip().startswith("test_"):
                    file_result["total"] += 1
                    if "PASSED" in line:
                        file_result["passed"] += 1
                        result = "PASSED" 
                    elif "FAILED" in line:
                        file_result["failed"] += 1
                        result = "FAILED"
                    elif "ERROR" in line:
                        file_result["errors"] += 1
                        result = "ERROR"
                    elif "SKIPPED" in line:
                        file_result["skipped"] += 1
                        result = "SKIPPED"
                    else:
                        continue
                    
                    # Extract test case name
                    test_name = line.strip().split(" ")[0]
                    file_result["cases"].append({
                        "name": test_name,
                        "result": result
                    })
            
            process.wait()
            
        except Exception as e:
            print(f"Error running tests: {e}")
            file_result["errors"] += 1
        
        # Calculate duration
        file_end_time = time.time()
        file_duration = file_end_time - file_start_time
        file_result["duration"] = round(file_duration, 2)
        
        # Update total results
        results["total_tests"] += file_result["total"]
        results["passed"] += file_result["passed"]
        results["failed"] += file_result["failed"]
        results["errors"] += file_result["errors"]
        results["skipped"] += file_result["skipped"]
        results["test_files"].append(file_result)
    
    # Calculate total duration
    end_time = time.time()
    results["duration"] = round(end_time - start_time, 2)
    
    # Save the results as JSON
    results_file = os.path.join(args.report_dir, f"{report_prefix}_results.json")
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Generate a summary report
    return generate_summary(results, args.report_dir, report_prefix)

def generate_summary(results, report_dir, report_prefix):
    """Generate a summary report from the test results."""
    summary_file = os.path.join(report_dir, f"{report_prefix}_summary.txt")
    
    with open(summary_file, 'w') as f:
        f.write(f"Chat Functionality Test Summary\n")
        f.write(f"=============================\n\n")
        f.write(f"Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {results['duration']} seconds\n\n")
        
        f.write(f"Total Tests: {results['total_tests']}\n")
        f.write(f"Passed: {results['passed']}\n")
        f.write(f"Failed: {results['failed']}\n")
        f.write(f"Errors: {results['errors']}\n")
        f.write(f"Skipped: {results['skipped']}\n\n")
        
        f.write(f"Test Files:\n")
        f.write(f"-----------\n")
        
        for file_result in results["test_files"]:
            f.write(f"\n{file_result['file']}:\n")
            f.write(f"  Duration: {file_result['duration']} seconds\n")
            f.write(f"  Total: {file_result['total']}\n")
            f.write(f"  Passed: {file_result['passed']}\n")
            f.write(f"  Failed: {file_result['failed']}\n")
            f.write(f"  Errors: {file_result['errors']}\n")
            f.write(f"  Skipped: {file_result['skipped']}\n")
            
            if file_result['failed'] > 0 or file_result['errors'] > 0:
                f.write(f"\n  Failed Tests:\n")
                for case in file_result['cases']:
                    if case['result'] in ['FAILED', 'ERROR']:
                        f.write(f"    - {case['name']}: {case['result']}\n")
    
    # Print the summary to stdout
    with open(summary_file, 'r') as f:
        print(f.read())
    
    print(f"\nSummary report saved to: {summary_file}")
    
    # Return success or failure
    return results['failed'] == 0 and results['errors'] == 0

if __name__ == "__main__":
    args = parse_args()
    success = run_tests(args)
    sys.exit(0 if success else 1) 