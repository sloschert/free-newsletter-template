import yaml
import os
import re
from pathlib import Path

def get_latest_report(reports_dir):
    """Get the most recent report file"""
    report_files = sorted(
        [f for f in os.listdir(reports_dir) if f.endswith('.report')],
        key=lambda f: os.path.getmtime(os.path.join(reports_dir, f)),
        reverse=True
    )
    return os.path.join(reports_dir, report_files[0]) if report_files else None

def parse_report(report_path):
    """Parse the YAML report file"""
    with open(report_path, 'r') as f:
        return yaml.safe_load(f)

def generate_results_table(clients, report):
    """Generate markdown table with test results"""
    table = "\n## Test Results\n\nLatest test results from " + os.path.basename(report.get('commit', 'latest')) + ":\n\n"
    table += "| Client | Test Result |\n"
    table += "|--------|-------------|\n"
    
    for client in clients:
        # Check if all test cases passed for this client
        client_results = report['clients'].get(client, {})
        all_passed = all(
            testcase['passed'] for testcase in client_results.values()
        ) if client_results else False
        
        result = "✓" if all_passed else "✗"
        table += f"| {client} | {result} |\n"
    
    return table

def update_readme(readme_path, clients_path, reports_dir):
    """Update the README.md file with latest test results"""
    # Load clients
    with open(clients_path, 'r') as f:
        clients_data = yaml.safe_load(f)
        clients = clients_data['clients']
    
    # Get latest report
    latest_report = get_latest_report(reports_dir)
    if not latest_report:
        print("No test reports found")
        return
    
    report_data = parse_report(latest_report)
    
    # Generate new table
    new_table = generate_results_table(clients, report_data)
    
    # Update README
    with open(readme_path, 'r') as f:
        content = f.read()
    
    # Remove existing test results section if it exists
    pattern = r'\n## Test Results\n.*?(?=\n## |$)'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    # Append the new table at the end
    content += new_table
    
    with open(readme_path, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    base_dir = Path(__file__).parent.parent
    update_readme(
        readme_path=base_dir / "README.md",
        clients_path=base_dir / "tests" / "clients.yaml",
        reports_dir=base_dir / "tests" / "reports"
    ) 