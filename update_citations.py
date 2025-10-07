#!/usr/bin/env python3
"""
Google Scholar Citation Data Updater
Updates citation metrics in index.html from Google Scholar profile
"""

import re
import urllib.request
import urllib.error
import ssl
import time
import random
import gzip
import io
import json
from datetime import datetime
from urllib.parse import urlencode

# Try to import scholarly, install if not available
try:
    from scholarly import scholarly
    SCHOLARLY_AVAILABLE = True
    print("✅ Scholarly library available - using hybrid approach")
except ImportError:
    print("📦 Scholarly library not found, installing...")
    try:
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "scholarly"])
        from scholarly import scholarly
        SCHOLARLY_AVAILABLE = True
        print("✅ Scholarly library installed and imported successfully!")
    except Exception as e:
        SCHOLARLY_AVAILABLE = False
        print(f"⚠️  Failed to install scholarly: {e}")
        print("💡 Will use manual scraping only")

# Your Google Scholar user ID
SCHOLAR_ID = 'hMTQZDQAAAAJ'

# Minimum expected values - these should never decrease
# NOTE: Update these values when your citations grow significantly to maintain protection
MIN_CITATIONS = 486
MIN_HINDEX = 10  
MIN_I10INDEX = 10

# User agents pool for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
]

# Proxy list (you can add your own proxies here)
PROXY_LIST = [
    # Add your proxy servers here if you have them
    # Format: {'http': 'http://proxy:port', 'https': 'https://proxy:port'}
]

def try_scholarly_method(user_id):
    """Try to fetch citation data using the Scholarly library (primary method)"""
    if not SCHOLARLY_AVAILABLE:
        return None
    
    try:
        # Search for author by ID
        author = scholarly.search_author_id(user_id)
        
        if not author:
            return None
        
        # Extract citation metrics
        citations = author.get('citedby', 0)
        hindex = author.get('hindex', 0)
        i10index = author.get('i10index', 0)
        
        # Try to get more detailed author info if h-index/i10-index are missing
        if citations > 0 and (hindex == 0 or i10index == 0):
            try:
                # Try to get more detailed author information
                author_filled = scholarly.fill(author)
                hindex = author_filled.get('hindex', hindex)
                i10index = author_filled.get('i10index', i10index)
            except Exception:
                pass
        
        # Check if we have complete data
        has_citations = citations > 0
        has_hindex = hindex > 0
        has_i10index = i10index > 0
        
        
        # If we have citations but missing h-index or i10-index, that's okay
        # We'll use what we have and let manual scraping fill in the gaps
        if has_citations:
            # Check if citations meet minimum threshold
            if citations < MIN_CITATIONS:
                print(f"⚠️  Scholarly citations ({citations}) below minimum ({MIN_CITATIONS})")
                return None
            
            # Return partial data - manual scraping will fill in missing values
            return {
                'citations': str(citations),
                'hindex': str(hindex) if has_hindex else '0',
                'i10index': str(i10index) if has_i10index else '0',
                'chart': '',  # Scholarly doesn't provide chart data
                'url': f'https://scholar.google.com/citations?user={user_id}',
                'method': 'scholarly',
                'incomplete': not (has_hindex and has_i10index)  # Flag for incomplete data
            }
        else:
            return None
        
    except Exception:
        return None

def fetch_citation_data_from_url(user_id, lang='en', domain='scholar.google.com', use_proxy=False):
    """Fetch citation data from Google Scholar profile with enhanced anti-detection"""
    url = f'https://{domain}/citations?user={user_id}&hl={lang}'
    
    # Rotate user agents for better stealth
    user_agent = random.choice(USER_AGENTS)
    
    # Create more realistic headers to avoid detection
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'DNT': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-ch-ua-platform-version': '"13.0.0"',
        'sec-ch-ua-arch': '"x86"',
        'sec-ch-ua-bitness': '"64"',
        'sec-ch-ua-full-version': '"120.0.6099.109"',
        'sec-ch-ua-full-version-list': '"Not_A Brand";v="8.0.0.0", "Chromium";v="120.0.6099.109", "Google Chrome";v="120.0.6099.109"',
        'sec-ch-ua-wow64': '?0'
    }
    
    try:
        # Add random delay to appear more human-like (3-8 seconds for better stealth)
        delay = random.uniform(3.0, 8.0)
        time.sleep(delay)
        
        # Create SSL context that handles certificate issues
        ssl_context = ssl.create_default_context()
        # For GitHub Actions and some environments, we need to handle cert issues
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        # Additional SSL settings for better compatibility
        ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')
        
        # Add proxy support if available
        opener = urllib.request.build_opener()
        if use_proxy and PROXY_LIST:
            proxy = random.choice(PROXY_LIST)
            proxy_handler = urllib.request.ProxyHandler(proxy)
            opener.add_handler(proxy_handler)
        
        # Add cookie jar for session management
        cookie_jar = urllib.request.HTTPCookieProcessor()
        opener.add_handler(cookie_jar)
        
        
        request = urllib.request.Request(url, headers=headers)
        
        # Use opener for better session management with SSL context
        opener.add_handler(urllib.request.HTTPSHandler(context=ssl_context))
        with opener.open(request, timeout=30) as response:
            # Handle gzip/compressed responses
            raw_data = response.read()
            
            # Check if the response is gzip-compressed
            if raw_data[:2] == b'\x1f\x8b':  # gzip magic number
                content = gzip.decompress(raw_data).decode('utf-8')
            else:
                content = raw_data.decode('utf-8')
            
        # Extract metrics using more flexible regex patterns
        citations_match = re.search(r'Citations</a></td><td[^>]*>(\d+)', content, re.IGNORECASE)
        hindex_match = re.search(r'h-index</a></td><td[^>]*>(\d+)', content, re.IGNORECASE)
        i10index_match = re.search(r'i10-index</a></td><td[^>]*>(\d+)', content, re.IGNORECASE)
        
        # Extract chart data
        chart_match = re.search(
            r'<div class="gsc_rsb_s gsc_prf_pnl" id="gsc_rsb_cit"[^>]*>(.*?)</div><div class="gsc_rsb_s gsc_prf_pnl"',
            content, re.DOTALL | re.IGNORECASE
        )
        
        # Clean the chart data to maintain user preferences  
        chart_data = ''
        if chart_match:
            raw_chart = chart_match.group(1)
            
            # Remove the detailed table completely
            raw_chart = re.sub(r'<h3[^>]*>.*?</h3>', '', raw_chart, flags=re.DOTALL)
            raw_chart = re.sub(r'<table[^>]*>.*?</table>', '', raw_chart, flags=re.DOTALL)
            
            # Remove the "A0" text from the chart (handle all formats)
            raw_chart = re.sub(r'content:\s*"\s*A0\s*";?', 'content:"";', raw_chart)
            raw_chart = re.sub(r'content:" A0";?', 'content:"";', raw_chart)  
            raw_chart = re.sub(r'content:\s*" A0";?', 'content:"";', raw_chart)
            raw_chart = re.sub(r'content:"A0";?', 'content:"";', raw_chart)
            # Handle Unicode, null bytes, and special characters  
            raw_chart = re.sub(r'content:\s*\"[^\x20-\x7E]*A0[^\x20-\x7E]*\";?', 'content:"";', raw_chart)
            raw_chart = re.sub(r'content:\s*\"\x00A0\";?', 'content:"";', raw_chart)
            # Handle literal \00A0 pattern
            raw_chart = re.sub(r'\\00A0', '', raw_chart)
            
            chart_data = raw_chart
        
        # Extract and validate the data
        citations = int(citations_match.group(1)) if citations_match else 0
        hindex = int(hindex_match.group(1)) if hindex_match else 0
        i10index = int(i10index_match.group(1)) if i10index_match else 0
        
        # Check if citations meet minimum threshold
        if citations < MIN_CITATIONS:
            print(f"⚠️  Manual scraping citations ({citations}) below minimum ({MIN_CITATIONS})")
            return None
        
        return {
            'citations': str(citations),
            'hindex': str(hindex),
            'i10index': str(i10index),
            'chart': chart_data,
            'url': url
        }
        
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print("❌ Google Scholar is blocking automated requests")
        return None
    except Exception:
        return None

def validate_citation_data(data):
    """Validate that citation numbers are not lower than expected minimums"""
    citations = int(data['citations'])
    hindex = int(data['hindex'])
    i10index = int(data['i10index'])
    
    issues = []
    
    if citations < MIN_CITATIONS:
        issues.append(f"Citations: {citations} < {MIN_CITATIONS} (minimum)")
    if hindex < MIN_HINDEX:
        issues.append(f"H-index: {hindex} < {MIN_HINDEX} (minimum)")
    if i10index < MIN_I10INDEX:
        issues.append(f"I10-index: {i10index} < {MIN_I10INDEX} (minimum)")
    
    if issues:
        print("🚨 VALIDATION FAILED - Citation numbers are unexpectedly low")
        for issue in issues:
            print(f"   ❌ {issue}")
        print("🔒 Skipping update to prevent incorrect data")
        return False
    
    print(f"✅ Validation passed: {citations} citations, h-index: {hindex}, i10-index: {i10index}")
    return True

def update_index_html(data):
    """Update index.html with new citation data"""
    index_file = 'index.html'
    
    try:
        # Read current content and store original length
        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_length = len(content)
        
        # Update citation summary text - flexible pattern that preserves publication count
        summary_pattern = r'\((\d+\+) publications, \d+\+ citations, h-index: \d+, i-10 index: \d+\)'
        
        def replace_summary(match):
            publications_count = match.group(1)  # Preserve existing publication count
            return f"({publications_count} publications, {data['citations']}+ citations, h-index: {data['hindex']}, i-10 index: {data['i10index']})"
        
        # Update ALL instances of citation summary (not just the first one)
        content = re.sub(summary_pattern, replace_summary, content)
        
        # Count how many updates were made  
        updated_pattern = r'\(\d+\+ publications, ' + str(data['citations']) + r'\+ citations'
        updated_count = len(re.findall(updated_pattern, content))
        
        # Update chart data if available - robust pattern matching
        if data['chart']:
            # Use a more robust pattern - the chart div ends with </div></div></div> followed by whitespace and </td>
            chart_pattern = r'(<div class="gsc_rsb_s gsc_prf_pnl" id="gsc_rsb_cit"[^>]*>).*?(</div></div></div>)(\s*</td>)'
            
            # Check if the pattern exists in the content
            if re.search(chart_pattern, content, re.DOTALL):
                # Replace the entire chart div with fresh data
                replacement = f'\\g<1>{data["chart"]}\\g<2>\\g<3>'
                content = re.sub(chart_pattern, replacement, content, flags=re.DOTALL)
            else:
                # Fallback: use simpler pattern without the closing tag constraint
                fallback_pattern = r'(<div class="gsc_rsb_s gsc_prf_pnl" id="gsc_rsb_cit"[^>]*>).*?(?=\s*</td>)'
                if re.search(fallback_pattern, content, re.DOTALL):
                    replacement = f'\\g<1>{data["chart"]}'
                    content = re.sub(fallback_pattern, replacement, content, flags=re.DOTALL)
        
        # Verify file length is reasonable before writing (safety check)
        new_length = len(content)
        length_diff = abs(new_length - original_length)
        length_change_percent = (length_diff / original_length) * 100 if original_length > 0 else 0
        
        # Safety check: Only update if change is less than 2%
        if length_change_percent >= 2.0:
            print(f"🚫 SAFETY CHECK FAILED: File size changed by {length_change_percent:.1f}% (≥2%)")
            return False
        
        # Write updated content (only if change is <2%)
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Successfully updated index.html")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Error: {index_file} not found")
        return False
    except Exception:
        return False

def try_alternative_sources(user_id):
    """Try alternative methods to get citation data"""
    # Method 1: Try with different language settings
    for lang in ['en', 'es', 'fr']:
        try:
            data = fetch_citation_data_from_url(user_id, lang, 'scholar.google.com', use_proxy=False)
            if data and int(data['citations']) > 0:
                return data
        except Exception:
            continue
    
    # Method 2: Try with proxy if available
    if PROXY_LIST:
        for proxy in PROXY_LIST:
            try:
                data = fetch_citation_data_from_url(user_id, 'en', 'scholar.google.com', use_proxy=True)
                if data and int(data['citations']) > 0:
                    return data
            except Exception:
                continue
    
    return None

def fetch_citation_data(user_id, lang='en'):
    """Fetch citation data using hybrid approach: Scholarly first, then manual scraping"""
    
    # PHASE 1: Try Scholarly library (primary method)
    scholarly_data = try_scholarly_method(user_id)
    if scholarly_data:
        # Check if Scholarly data is complete
        if not scholarly_data.get('incomplete', False):
            return scholarly_data
        else:
            # Try to get missing data from manual scraping
            manual_data = try_manual_scraping_for_missing_data(user_id, scholarly_data)
            if manual_data:
                return manual_data
            else:
                return scholarly_data
    
    # PHASE 2: Fall back to manual scraping (existing method)
    domains_to_try = [
        'scholar.google.com',
        'scholar.google.co.in', 
        'scholar.google.co.uk',
        'scholar.google.ca',
        'scholar.google.com.au'
    ]
    
    # Try manual scraping with different domains
    for domain in domains_to_try:
        try:
            data = fetch_citation_data_from_url(user_id, lang, domain)
            if data and int(data['citations']) > 0:
                data['method'] = 'manual_scraping'
                return data
        except Exception:
            continue
    
    # PHASE 3: Try alternative manual methods
    alternative_data = try_alternative_sources(user_id)
    if alternative_data:
        alternative_data['method'] = 'manual_alternative'
        return alternative_data
    
    return None

def try_manual_scraping_for_missing_data(user_id, scholarly_data):
    """Try to get missing h-index and i10-index from manual scraping"""
    try:
        # Try one quick manual scrape to get missing data
        manual_data = fetch_citation_data_from_url(user_id, 'en', 'scholar.google.com')
        
        if manual_data and int(manual_data['citations']) > 0:
            # Combine data: use Scholarly citations, manual h-index/i10-index
            combined_data = {
                'citations': scholarly_data['citations'],  # Use Scholarly citations
                'hindex': manual_data['hindex'] if int(manual_data['hindex']) > 0 else scholarly_data['hindex'],
                'i10index': manual_data['i10index'] if int(manual_data['i10index']) > 0 else scholarly_data['i10index'],
                'chart': manual_data.get('chart', ''),
                'url': scholarly_data['url'],
                'method': 'scholarly+manual',
                'incomplete': False
            }
            
            # Validate combined data meets minimum thresholds
            citations = int(combined_data['citations'])
            hindex = int(combined_data['hindex'])
            i10index = int(combined_data['i10index'])
            
            if citations >= MIN_CITATIONS and hindex >= MIN_HINDEX and i10index >= MIN_I10INDEX:
                return combined_data
            else:
                print(f"⚠️  Combined data below minimums: citations={citations}, h-index={hindex}, i10-index={i10index}")
                return None
        
    except Exception:
        pass
    
    return None

def load_cached_data():
    """Load cached citation data from a backup file"""
    try:
        with open('citations_backup.json', 'r') as f:
            cached_data = json.load(f)
            return cached_data
    except FileNotFoundError:
        return None
    except Exception:
        return None

def save_cached_data(data):
    """Save current citation data as backup"""
    try:
        with open('citations_backup.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def main():
    """Main execution function with enhanced error handling"""
    print("🔍 Fetching latest citation data from Google Scholar...")
    
    data = fetch_citation_data(SCHOLAR_ID)
    
    if data:
        print("📥 Data fetched successfully!")
        print(f"🛠️  Method: {data.get('method', 'unknown')}")
        
        # Save successful data as backup
        save_cached_data(data)
        
        # Validate the data before updating
        if validate_citation_data(data):
            if update_index_html(data):
                print("🎉 Citation data updated successfully!")
            else:
                print("❌ Failed to update index.html")
        else:
            print("❌ Citation data validation failed")
    else:
        print("❌ Failed to fetch citation data from all domains")
        
        # Try to use cached data as fallback
        cached_data = load_cached_data()
        
        if cached_data:
            print("📂 Using cached citation data")
            
            # Use cached data but mark it as such
            if update_index_html(cached_data):
                print("🎉 Website updated with cached citation data!")
            else:
                print("❌ Failed to update with cached data")
        else:
            print("💡 Try again later or check your Google Scholar profile")

if __name__ == '__main__':
    main()
