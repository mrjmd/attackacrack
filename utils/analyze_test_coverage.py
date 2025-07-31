#!/usr/bin/env python3
"""
Analyze test coverage and identify quick wins
"""
import subprocess
import json

def run_test_analysis():
    """Run pytest and analyze results"""
    print("Analyzing test suite...")
    
    # Run pytest with json output
    cmd = ["docker", "exec", "crm_web_app", "python", "-m", "pytest", 
           "--tb=no", "-v", "--json-report", "--json-report-file=/tmp/report.json"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Get the JSON report
    json_cmd = ["docker", "exec", "crm_web_app", "cat", "/tmp/report.json"]
    json_result = subprocess.run(json_cmd, capture_output=True, text=True)
    
    if json_result.returncode == 0:
        try:
            data = json.loads(json_result.stdout)
            
            print(f"\nTest Summary:")
            print(f"Total tests: {data['summary']['total']}")
            print(f"Passed: {data['summary']['passed']}")
            print(f"Failed: {data['summary']['failed']}")
            print(f"Errors: {data['summary']['error']}")
            
            # Analyze failures by file
            failures_by_file = {}
            for test in data['tests']:
                if test['outcome'] in ['failed', 'error']:
                    file_name = test['nodeid'].split('::')[0]
                    if file_name not in failures_by_file:
                        failures_by_file[file_name] = []
                    failures_by_file[file_name].append(test['nodeid'])
            
            print(f"\nFiles with most failures:")
            sorted_files = sorted(failures_by_file.items(), key=lambda x: len(x[1]), reverse=True)
            for file_name, tests in sorted_files[:10]:
                print(f"  {file_name}: {len(tests)} failures")
                
        except json.JSONDecodeError:
            print("Could not parse JSON report")
    
    # Now run coverage with only passing tests
    print("\n\nRunning coverage analysis with passing tests...")
    coverage_cmd = ["docker", "exec", "crm_web_app", "python", "-m", "pytest",
                    "-x", "--cov=services", "--cov=routes", "--cov-report=term"]
    
    coverage_result = subprocess.run(coverage_cmd, capture_output=True, text=True)
    
    # Extract coverage percentage
    for line in coverage_result.stdout.split('\n'):
        if 'TOTAL' in line:
            print(f"\nCurrent coverage: {line}")
            break

if __name__ == "__main__":
    run_test_analysis()