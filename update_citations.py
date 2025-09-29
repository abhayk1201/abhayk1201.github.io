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
from datetime import datetime

# Your Google Scholar user ID
SCHOLAR_ID = 'hMTQZDQAAAAJ'

# Minimum expected values - these should never decrease
# NOTE: Update these values when your citations grow significantly to maintain protection
MIN_CITATIONS = 486
MIN_HINDEX = 10  
MIN_I10INDEX = 10

def fetch_citation_data_from_url(user_id, lang='en', domain='scholar.google.com'):
    """Fetch citation data from Google Scholar profile"""
    url = f'https://{domain}/citations?user={user_id}&hl={lang}'
    
    # Create more realistic headers to avoid detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"'
    }
    
    try:
        # Add random delay to appear more human-like (2-5 seconds)
        delay = random.uniform(2.0, 5.0)
        print(f"⏳ Waiting {delay:.1f}s to avoid rate limiting...")
        time.sleep(delay)
        
        # Create SSL context that handles certificate issues
        ssl_context = ssl.create_default_context()
        # For GitHub Actions and some environments, we need to handle cert issues
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        print(f"🌐 Requesting: {url}")
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
            print(f"📡 Response status: {response.status}")
            
            # Handle gzip/compressed responses
            raw_data = response.read()
            
            # Check if the response is gzip-compressed
            if raw_data[:2] == b'\x1f\x8b':  # gzip magic number
                content = gzip.decompress(raw_data).decode('utf-8')
                print("📦 Decompressed gzip response")
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
        
        return {
            'citations': citations_match.group(1) if citations_match else '0',
            'hindex': hindex_match.group(1) if hindex_match else '0',
            'i10index': i10index_match.group(1) if i10index_match else '0',
            'chart': chart_data,
            'url': url
        }
        
    except urllib.error.HTTPError as e:
        if e.code == 403:
            print(f"❌ Error fetching data: HTTP 403 Forbidden")
            print("🚫 Google Scholar is blocking automated requests")
            print("💡 Possible solutions:")
            print("   • Try running the script manually instead of automated")
            print("   • Wait 24-48 hours before trying again")
            print("   • Consider using a VPN or different IP address")
            print("   • The profile might be private or restricted")
        else:
            print(f"❌ HTTP Error {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"❌ Error fetching data: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
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
        print("🚨 VALIDATION FAILED - Citation numbers are unexpectedly low:")
        for issue in issues:
            print(f"   ❌ {issue}")
        print("\n💡 Possible causes:")
        print("   • Google Scholar is experiencing issues")
        print("   • The HTML structure changed and extraction failed")
        print("   • Network issues during data fetching")
        print("   • Temporary access restrictions")
        print("\n🔒 Skipping update to prevent incorrect data")
        return False
    
    print("✅ Citation data validation passed")
    return True

def update_index_html(data):
    """Update index.html with new citation data"""
    index_file = 'index.html'
    
    try:
        # Read current content and store original length
        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_length = len(content)
        print(f"📏 Original file length: {original_length:,} characters")
        
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
        if updated_count > 0:
            print(f"📝 Found and updated {updated_count} citation reference(s)")
        
        # Update chart data if available - robust pattern matching
        if data['chart']:
            print("🔄 Updating citation chart with fresh data from Google Scholar...")
            
            # Use a more robust pattern - the chart div ends with </div></div></div> followed by whitespace and </td>
            chart_pattern = r'(<div class="gsc_rsb_s gsc_prf_pnl" id="gsc_rsb_cit"[^>]*>).*?(</div></div></div>)(\s*</td>)'
            
            # Check if the pattern exists in the content
            if re.search(chart_pattern, content, re.DOTALL):
                # Replace the entire chart div with fresh data
                replacement = f'\\g<1>{data["chart"]}\\g<2>\\g<3>'
                content = re.sub(chart_pattern, replacement, content, flags=re.DOTALL)
                print("✅ Citation chart successfully updated with latest data")
            else:
                # Fallback: use simpler pattern without the closing tag constraint
                fallback_pattern = r'(<div class="gsc_rsb_s gsc_prf_pnl" id="gsc_rsb_cit"[^>]*>).*?(?=\s*</td>)'
                if re.search(fallback_pattern, content, re.DOTALL):
                    replacement = f'\\g<1>{data["chart"]}'
                    content = re.sub(fallback_pattern, replacement, content, flags=re.DOTALL)  
                    print("✅ Citation chart updated using fallback pattern")
                else:
                    print("❌ Failed to locate chart div for replacement")
        else:
            print("⚠️  No chart data available to update")
        
        # Verify file length is reasonable before writing (safety check)
        new_length = len(content)
        length_diff = abs(new_length - original_length)
        length_change_percent = (length_diff / original_length) * 100 if original_length > 0 else 0
        
        print(f"📏 Updated file length: {new_length:,} characters")
        print(f"📐 Length change: {length_diff:,} characters ({length_change_percent:.1f}%)")
        
        # Safety check: Only update if change is less than 2%
        if length_change_percent >= 2.0:
            print(f"🚫 SAFETY CHECK FAILED: File size changed by {length_change_percent:.1f}% (≥2%)")
            print("❌ Changes discarded to prevent potential corruption")
            print("💡 This suggests the citation data extraction may have failed")
            return False
        
        # Write updated content (only if change is <2%)
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Successfully updated index.html")
        print(f"📊 Citations: {data['citations']}")
        print(f"📈 H-index: {data['hindex']}")
        print(f"📋 I10-index: {data['i10index']}")
        
        return True
        
    except FileNotFoundError:
        print(f"❌ Error: {index_file} not found")
        return False
    except Exception as e:
        print(f"❌ Error updating {index_file}: {e}")
        return False

def fetch_citation_data(user_id, lang='en'):
    """Fetch citation data from Google Scholar profile with retry logic"""
    domains_to_try = [
        'scholar.google.com',
        'scholar.google.co.in',
        'scholar.google.co.uk'
    ]
    
    for i, domain in enumerate(domains_to_try):
        if i > 0:
            print(f"🔄 Retrying with {domain}...")
        
        try:
            data = fetch_citation_data_from_url(user_id, lang, domain)
            if data:
                return data
        except Exception as e:
            print(f"⚠️  Failed with {domain}: {str(e)[:50]}...")
            continue
    
    return None

def main():
    """Main execution function"""
    print("🔍 Fetching latest citation data from Google Scholar...")
    
    data = fetch_citation_data(SCHOLAR_ID)
    
    if data:
        print("📥 Data fetched successfully!")
        print(f"🔗 Source: {data['url']}")
        
        # Validate the data before updating
        if validate_citation_data(data):
            if update_index_html(data):
                print("\n🎉 Citation data updated successfully!")
            else:
                print("\n❌ Failed to update index.html")
                print("🔒 File was not modified to ensure data integrity")
        else:
            print("\n❌ Citation data validation failed")
            print("🔒 Skipping update to prevent incorrect values")
    else:
        print("❌ Failed to fetch citation data from all domains")
        print("\n💡 Possible solutions:")
        print("   • Try again in a few minutes (Google Scholar may have rate limits)")
        print("   • Wait 24-48 hours before trying automated requests again")
        print("   • Check your internet connection")
        print("   • Verify your Google Scholar profile is public")
        print("   • Consider running the script manually instead of via GitHub Actions")
        print("   • The automated workflow may be temporarily blocked by Google")

if __name__ == '__main__':
    main()
