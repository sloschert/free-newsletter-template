import yaml
import os
import subprocess
import time
from pathlib import Path
from update_readme import update_readme

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def get_commit_hash():
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()
    except Exception as e:
        print(f"{RED}Error: Could not get commit hash. Make sure you're in a git repository.{RESET}")
        exit(1)

def check_uncommitted_changes():
    try:
        status = subprocess.check_output(['git', 'status', '--porcelain']).decode('utf-8').strip()
        if status:
            print(f"{YELLOW}Warning: There are uncommitted changes in the git repository.{RESET}")
            print(f"{YELLOW}Please commit or stash your changes before running tests.{RESET}")
            return True
        return False
    except Exception as e:
        print(f"{RED}Error: Could not check git status. Make sure you're in a git repository.{RESET}")
        exit(1)

def load_yaml(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def print_section_header(title):
    """Print a formatted section header"""
    terminal_width = os.get_terminal_size().columns
    print(f"\n{BLUE}{BOLD}{'=' * terminal_width}{RESET}")
    print(f"{BLUE}{BOLD}{title.center(terminal_width)}{RESET}")
    print(f"{BLUE}{BOLD}{'=' * terminal_width}{RESET}\n")

def print_progress_bar(current, total, description="Progress"):
    """Print a progress bar"""
    terminal_width = os.get_terminal_size().columns
    bar_length = min(terminal_width - len(description) - 10, 50)
    progress = current / total
    block = int(round(bar_length * progress))
    bar = "█" * block + "░" * (bar_length - block)
    percentage = round(progress * 100, 1)
    print(f"\r{description}: |{bar}| {percentage}% ({current}/{total})", end="")
    if current == total:
        print()

def prompt_testcase(testcase, questions):
    print(f"\n{BOLD}Testing: {testcase}{RESET}")
    results = {'passed': True, 'failed_questions': []}
    
    for i, question in enumerate(questions):
        print_progress_bar(i+1, len(questions), f"  Questions for {testcase}")
        while True:
            response = input(f"  {i+1}. {question} ({GREEN}Y{RESET}/{RED}n{RESET}): ").lower()
            if response in ['y', 'n', '']:
                if response == 'n':
                    results['passed'] = False
                    results['failed_questions'].append(question)
                    print(f"    {RED}✗ Failed{RESET}")
                else:
                    print(f"    {GREEN}✓ Passed{RESET}")
                break
            print(f"{YELLOW}Invalid input. Please enter 'y' or 'n' (or press Enter for yes).{RESET}")
    
    status = f"{GREEN}PASS{RESET}" if results['passed'] else f"{RED}FAIL{RESET}"
    print(f"\n  {BOLD}Testcase Result:{RESET} {status}")
    
    return results

def main():
    start_time = time.time()
    
    print_section_header("HTML Newsletter Testing")
    
    # Check for uncommitted changes
    if check_uncommitted_changes():
        proceed = input(f"{YELLOW}Do you want to proceed anyway? (y/N): {RESET}").lower()
        if proceed != 'y':
            print(f"{BLUE}Testing aborted.{RESET}")
            exit(0)
    
    # Get current commit hash
    commit_hash = get_commit_hash()
    print(f"{BOLD}Testing commit:{RESET} {commit_hash}")
    
    # Load test data
    clients = load_yaml('tests/clients.yaml')['clients']
    testcases = load_yaml('tests/testcases.yaml')
    
    print(f"\n{BOLD}Test Plan:{RESET}")
    print(f"  • {len(clients)} clients to test")
    print(f"  • {len(testcases)} test cases per client")
    print(f"  • {len(clients) * len(testcases)} total test cases")
    
    # Prepare results structure
    results = {
        'commit': commit_hash,
        'clients': {}
    }
    
    # Test statistics
    passing_clients = 0
    total_tests = 0
    passed_tests = 0
    
    # Test each client
    print_section_header("Starting Tests")
    for i, client in enumerate(clients):
        client_passed = True
        print(f"\n{BOLD}{BLUE}Testing Client {i+1}/{len(clients)}: {client}{RESET}")
        print(f"{BLUE}{'-' * (len(client) + 30)}{RESET}")
        
        client_results = {}
        for j, (testcase, questions) in enumerate(testcases.items()):
            result = prompt_testcase(testcase, questions)
            client_results[testcase] = result
            
            total_tests += 1
            if result['passed']:
                passed_tests += 1
            else:
                client_passed = False
        
        results['clients'][client] = client_results
        if client_passed:
            passing_clients += 1
            print(f"\n{GREEN}All tests PASSED for {client}{RESET}")
        else:
            print(f"\n{RED}Some tests FAILED for {client}{RESET}")
        
        # Show progress
        print_progress_bar(i+1, len(clients), "Overall progress")
    
    # Save report
    print_section_header("Test Results")
    
    # Calculate success percentage
    success_percent = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    client_success_percent = (passing_clients / len(clients)) * 100 if len(clients) > 0 else 0
    
    print(f"\n{BOLD}Test Summary:{RESET}")
    print(f"  • Passing clients: {GREEN}{passing_clients}/{len(clients)}{RESET} ({client_success_percent:.1f}%)")
    print(f"  • Passing tests: {GREEN}{passed_tests}/{total_tests}{RESET} ({success_percent:.1f}%)")
    print(f"  • Elapsed time: {time.time() - start_time:.1f} seconds")
    
    report_path = Path(f"tests/reports/{commit_hash}.report")
    if report_path.exists():
        overwrite = input(f"\n{YELLOW}Report for {commit_hash} already exists. Overwrite? (y/N): {RESET}").lower()
        if overwrite != 'y':
            print(f"{BLUE}Aborting. Report not saved.{RESET}")
            return
    
    os.makedirs(report_path.parent, exist_ok=True)
    with open(report_path, 'w') as file:
        yaml.dump(results, file)
    
    print(f"\n{GREEN}Test report saved to {report_path}{RESET}")
    
    # Update README
    print(f"\n{BLUE}Updating README with test results...{RESET}")
    update_readme(
        readme_path=Path(__file__).parent.parent / "README.md",
        clients_path=Path(__file__).parent / "clients.yaml",
        reports_dir=Path(__file__).parent / "reports"
    )
    print(f"{GREEN}README updated successfully.{RESET}")
    
    print_section_header("Testing Complete")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Testing interrupted by user.{RESET}")
        exit(0)
