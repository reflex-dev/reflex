
# def find_and_check_urls(repo_dir):
#     url_pattern = re.compile(r'http[s]?://reflex\.dev[^\s"]*')  
#     #url_pattern = re.compile(r'http[s]?://reflex\.dev[^ ]*')
#     for root, dirs, files in os.walk(repo_dir):
#         # Skip any __pycache__ directories
#         if '__pycache__' in root:
#             continue
        
#         for file_name in files:
#             if not file_name.endswith('.py'):  # Only process .py files to further narrow down the search
#                 continue
                
#             file_path = os.path.join(root, file_name)
#             try:
#                 with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
#                     for line in file:
#                         urls = url_pattern.findall(line)
#                         for url in set(urls):  # Use set to remove duplicates
#                             if url.startswith('http://'):
#                                 raise ValueError(f"Found insecure HTTP URL: {url}")
                    
#                             url = url.strip('"\n')  # Sanitize URL
                            
#                             try:
#                                 response = requests.head(url, allow_redirects=True, timeout=5)
#                                 response.raise_for_status()  # Checks for HTTP errors
#                                 print(f"URL is accessible: {url}")
#                             except requests.RequestException as e:
#                                 print(f"Error accessing URL: {url} | Error: {e}, Check your path ends with a /")
#                                 print(f"file path: {file_path}")
#             except Exception as e:
#                 print(f"Error reading file: {file_path} | Error: {e}")


# # Get the directory one level above the current script's directory
# reflex_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'reflex')

# # Start checking URLs
# find_and_check_urls(reflex_dir)

import os
import re
import pytest
import requests

def check_urls(repo_dir):
    url_pattern = re.compile(r'http[s]?://reflex\.dev[^\s"]*')
    errors = []

    for root, dirs, files in os.walk(repo_dir):
        if '__pycache__' in root:
            continue

        for file_name in files:
            if not file_name.endswith('.py'):
                continue

            file_path = os.path.join(root, file_name)
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    for line in file:
                        urls = url_pattern.findall(line)
                        for url in set(urls):
                            if url.startswith('http://'):
                                errors.append(f"Found insecure HTTP URL: {url} in {file_path}")
                            url = url.strip('"\n')
                            try:
                                response = requests.head(url, allow_redirects=True, timeout=5)
                                response.raise_for_status()
                            except requests.RequestException as e:
                                errors.append(f"Error accessing URL: {url} in {file_path} | Error: {e}, , Check your path ends with a /")
            except Exception as e:
                errors.append(f"Error reading file: {file_path} | Error: {e}")
    
    return errors

@pytest.mark.parametrize("repo_dir", [
    os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'reflex')
])
def test_find_and_check_urls(repo_dir):
    errors = check_urls(repo_dir)
    assert not errors, "\n".join(errors)
