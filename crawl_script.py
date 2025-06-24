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
CRAWL4AI_BASE_URL = "https://main-crwal4ai.vmm7pe.easypanel.host" #                |
API_TOKEN = "2W&B4Q&ePBKz3V**" # omit this if your installation is unsecured.      |
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

def clean_and_validate_url(url):
    """Clean URL and validate it's a proper URL"""
    if not url:
        return None
    
    # Remove RTF formatting codes and other artifacts
    url = re.sub(r'\{[^}]*\}', '', url)  # Remove RTF codes like {\*\expandedcolortbl;;...}
    url = re.sub(r'\\[a-zA-Z]+\d*', '', url)  # Remove RTF commands like \cssrgb
    url = re.sub(r'[^\x20-\x7E]', '', url)  # Remove non-printable characters
    url = url.strip()
    
    # Skip if it's empty after cleaning
    if not url:
        return None
    
    # Skip comments
    if url.startswith('#'):
        return None
    
    # Add https:// if missing protocol
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Basic URL validation
    parsed = urlparse(url)
    if not parsed.netloc or not parsed.scheme:
        return None
    
    return url

def read_urls_from_file(file_path):
    """Read URLs from a text file, one per line"""
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                cleaned_url = clean_and_validate_url(line.strip())
                if cleaned_url:
                    urls.append(cleaned_url)
                elif line.strip() and not line.strip().startswith('#'):
                    print(f"⚠️  Skipping invalid URL on line {line_num}: {line.strip()[:50]}...")
        return urls
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return []
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return []

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

def process_single_url(url):
    """Process a single URL"""
    # Clean and validate URL first
    cleaned_url = clean_and_validate_url(url)
    if not cleaned_url:
        print(f"❌ Invalid URL: {url}")
        return False
    
    print(f"🌐 Crawling: {cleaned_url}")
    
    # Prepare crawl request
    headers = get_auth_headers()
    crawl_data = {
        "urls": [cleaned_url],
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
                
                if wait_for_completion(task_id, headers, cleaned_url):
                    return True
                else:
                    print("❌ Failed to extract content")
                    return False
            else:
                # Direct response
                content = extract_clean_content(result)
                if content:
                    save_markdown(content, cleaned_url)
                    return True
                else:
                    print("❌ No content found")
                    return False
        else:
            print(f"❌ Error: {response.status_code}")
            if response.status_code == 422:
                print("❌ Invalid URL format")
            else:
                print(response.text)
            return False
            
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def main():
    """Main function"""
    import os
    
    while True:
        os.system('clear' if os.name == 'posix' else 'cls')
        print("🚀 Crawl4AI Markdown Extractor")
        print("=" * 40)
        print("Choose an option:")
        print("1. Process a single URL")
        print("2. Batch process URLs from text file")
        print("3. Exit")
        print()
        
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == '1':
            # Single URL processing
            url = input("Enter the full URL to scrape: ").strip()
            if not url:
                print("❌ No URL provided")
                input("Press Enter to continue...")
                continue
            
            success = process_single_url(url)
            if success:
                print("✅ Success!")
            
        elif choice == '2':
            # Batch processing
            file_path = input("Enter the filename (or full path) to your text file with URLs: ").strip()
            if not file_path:
                print("❌ No file path provided")
                input("Press Enter to continue...")
                continue
            
            # Check if file exists in current directory if no path separators
            import os
            if not os.path.sep in file_path and not os.path.exists(file_path):
                # Try common extensions
                for ext in ['', '.txt', '.list']:
                    test_path = file_path + ext
                    if os.path.exists(test_path):
                        file_path = test_path
                        break
            
            urls = read_urls_from_file(file_path)
            if not urls:
                print("❌ No valid URLs found in file or file not found")
                print(f"   Tried to read: {file_path}")
                print(f"   Current directory: {os.getcwd()}")
                input("Press Enter to continue...")
                continue
            
            print(f"📋 Found {len(urls)} URLs to process")
            print("Starting batch processing...")
            print()
            
            successful = 0
            failed = 0
            
            for i, url in enumerate(urls, 1):
                print(f"[{i}/{len(urls)}] Processing: {url}")
                if process_single_url(url):
                    successful += 1
                    print("✅ Success!")
                else:
                    failed += 1
                    print("❌ Failed!")
                print("-" * 50)
                time.sleep(1)  # Brief pause between requests
            
            print(f"📊 Batch processing complete!")
            print(f"✅ Successful: {successful}")
            print(f"❌ Failed: {failed}")
            
        elif choice == '3':
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")
            input("Press Enter to continue...")
            continue
        
        # Ask if user wants to continue
        print()
        input("Press Enter to continue...")

if __name__ == "__main__":
    main()
