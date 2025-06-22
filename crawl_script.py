#!/usr/bin/env python3
"""
Title: Simple Crawl4AI Script
Author: David Soden
Contact: https://davidsoden.com
Date: 06/22/25
"""

import requests
import json
import time
import re
from urllib.parse import urljoin, urlparse
from html import unescape

#-----------------------------------------------------------------------------------
# Your Crawl4AI server configuration                                               |
CRAWL4AI_BASE_URL = "https://yoursite.com" #                                       |
API_TOKEN = "123456" # omit this if your installation is unsecured.                |
# Documentation https://docs.crawl4ai.com                                          |
# Note: This script requires the Crawl4AI server to be running and accessible.     |
#-----------------------------------------------------------------------------------

def get_auth_headers():
    """Get authentication headers for API requests"""
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
        "X-API-Key": API_TOKEN,
        "X-Auth-Token": API_TOKEN
    }

def get_filename_from_url(url):
    """Generate a smart filename based on the URL"""
    parsed = urlparse(url)
    hostname = parsed.hostname.replace('www.', '') if parsed.hostname else 'unknown'
    
    # Clean up hostname for filename
    hostname = re.sub(r'[^\w\-]', '', hostname)
    
    # Check if it's the home page
    path = parsed.path.strip('/')
    if not path or path == 'index.html' or path == 'index.php':
        return f"{hostname}.md"
    
    # Extract page name from path
    path_parts = path.split('/')
    page_name = path_parts[-1] if path_parts else ''
    
    # Remove file extension if present
    if '.' in page_name:
        page_name = page_name.split('.')[0]
    
    # Clean page name
    page_name = re.sub(r'[^\w\-]', '', page_name)
    
    if page_name:
        return f"{hostname}-{page_name}.md"
    else:
        return f"{hostname}.md"

def clean_markdown_content(content):
    """Clean markdown content gently"""
    if not content:
        return ""
    
    text = str(content)
    
    # Remove citation markers like ⟨1⟩, ⟨2⟩ etc.
    text = re.sub(r'⟨\d+⟩', '', text)
    
    # Replace "URL" placeholders with nothing
    text = re.sub(r'\bURL\b', '', text)
    
    # Clean up broken image links
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)
    
    # Remove excessive newlines but keep paragraph structure
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Clean up spaces around punctuation
    text = re.sub(r'\s+([,.!?])', r'\1', text)
    
    # Clean up extra spaces
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove empty markdown links
    text = re.sub(r'\[\]\([^)]*\)', '', text)
    
    # Clean up any remaining artifacts
    text = re.sub(r'\.{2,}', '.', text)
    
    return text.strip()

def extract_clean_content(result):
    """Extract clean markdown content from crawl results"""
    # Handle nested results structure
    if isinstance(result, dict) and 'results' in result and result['results']:
        actual_result = result['results'][0]
    else:
        actual_result = result
    
    # Try to get clean markdown content
    if 'markdown' in actual_result and actual_result['markdown']:
        content = actual_result['markdown']
        return clean_markdown_content(content)
    
    # Try markdown_v2
    if 'markdown_v2' in actual_result and actual_result['markdown_v2']:
        markdown_v2 = actual_result['markdown_v2']
        if isinstance(markdown_v2, dict) and 'raw_markdown' in markdown_v2:
            content = markdown_v2['raw_markdown']
            return clean_markdown_content(content)
    
    return None

def wait_for_completion(task_id, headers, target_url):
    """Wait for async task to complete"""
    endpoints = [f"/task/{task_id}", f"/tasks/{task_id}", f"/result/{task_id}"]
    
    for attempt in range(24):  # Wait up to 2 minutes
        for endpoint in endpoints:
            try:
                url = urljoin(CRAWL4AI_BASE_URL, endpoint)
                response = requests.get(url, headers=headers, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    status = str(result.get('status', '')).lower()
                    
                    if status in ['completed', 'success', 'finished']:
                        print("✅ Crawling completed!")
                        final_result = result.get('result', result)
                        
                        # Extract and save content
                        content = extract_clean_content(final_result)
                        if content:
                            save_markdown(content, target_url)
                            return True
                        else:
                            print("❌ No content found in completed result")
                            return False
                            
                    elif status in ['failed', 'error']:
                        print(f"❌ Task failed: {status}")
                        return False
                    elif status in ['pending', 'running']:
                        print(f"⏳ Status: {status}")
                        break
                        
            except:
                continue
        
        time.sleep(5)
    
    print("⏰ Timeout waiting for results")
    return False

def save_markdown(content, url):
    """Save content as markdown file with smart filename"""
    filename = get_filename_from_url(url)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    markdown = f"""# Content from {url}

**Extracted:** {timestamp}  
**Length:** {len(content):,} characters  

---

{content}

---

*Content automatically extracted and cleaned for readability*
"""
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print(f"💾 Saved: {filename}")
    print(f"📏 Content length: {len(content):,} characters")

def main():
    """Main function"""
    print("🚀 Crawl4AI Markdown Extractor")
    print("=" * 40)
    
    # Get URL from user
    url = input("Enter the full URL to scrape: ").strip()
    
    if not url:
        print("❌ No URL provided")
        return
    
    # Add https:// if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    print(f"🌐 Crawling: {url}")
    
    # Prepare crawl request
    headers = get_auth_headers()
    crawl_data = {
        "urls": [url],
        "cache_key": f"fresh_{int(time.time())}"
    }
    
    try:
        response = requests.post(
            urljoin(CRAWL4AI_BASE_URL, "/crawl"),
            json=crawl_data,
            headers=headers,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Check for async task
            if 'task_id' in result or 'id' in result:
                task_id = result.get('task_id') or result.get('id')
                print(f"📋 Task ID: {task_id}")
                
                if wait_for_completion(task_id, headers, url):
                    print("✅ Success!")
                else:
                    print("❌ Failed to extract content")
            else:
                # Direct response
                content = extract_clean_content(result)
                if content:
                    save_markdown(content, url)
                    print("✅ Success!")
                else:
                    print("❌ No content found")
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    main()
