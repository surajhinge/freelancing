"""
github_automation_sample.py
Author: Suraj Hinge
Description:
    Example Python script demonstrating GitHub API usage.
    Fetches details of a public repository and lists open issues.
"""

import requests

# Replace with your GitHub username and repo name
USERNAME = "surajhinge"
REPO = "chat_bot"

# GitHub API endpoint
API_URL = f"https://api.github.com/repos/{USERNAME}/{REPO}"

def get_repo_info():
    """Fetch and display repository details."""
    response = requests.get(API_URL)
    if response.status_code == 200:
        data = response.json()
        print(f"Repository: {data['full_name']}")
        print(f"Description: {data.get('description', 'No description')}")
        print(f"Stars: {data['stargazers_count']}, Forks: {data['forks_count']}")
    else:
        print(f"Failed to fetch repo info: {response.status_code}")

def list_open_issues():
    """Fetch and list open issues in the repository."""
    issues_url = f"{API_URL}/issues"
    response = requests.get(issues_url)
    if response.status_code == 200:
        issues = response.json()
        if not issues:
            print("No open issues found.")
        else:
            print("\nOpen Issues:")
            for issue in issues:
                print(f"- #{issue['number']}: {issue['title']}")
    else:
        print(f"Failed to fetch issues: {response.status_code}")

if __name__ == "__main__":
    print("Fetching GitHub repository information...\n")
    get_repo_info()
    print("\nChecking open issues...\n")
    list_open_issues()
