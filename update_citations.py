#!/usr/bin/env python3
"""
Google Scholar Citation Data Updater
Updates citation metrics in index.html from Google Scholar profile
"""

import re
import urllib.request
import urllib.error
import ssl
import shutil
from datetime import datetime

# Your Google Scholar user ID
SCHOLAR_ID = 'hMTQZDQAAAAJ'

def fetch_citation_data(user_id, lang='en'):
    """Fetch citation data from Google Scholar profile"""
    url = f'https://scholar.google.co.in/citations?user={user_id}&hl={lang}'
    
    # Create request with user agent to avoid blocking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Create SSL context that doesn't verify certificates (for compatibility)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=30, context=ssl_context) as response:
            content = response.read().decode('utf-8')
            
        # Extract metrics using regex
        citations_match = re.search(r'Citations</a></td><td class="gsc_rsb_std">(\d+)</td>', content, re.IGNORECASE)
        hindex_match = re.search(r'h-index</a></td><td class="gsc_rsb_std">(\d+)</td>', content, re.IGNORECASE)
        i10index_match = re.search(r'i10-index</a></td><td class="gsc_rsb_std">(\d+)</td>', content, re.IGNORECASE)
        
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
        
    except urllib.error.URLError as e:
        print(f"❌ Error fetching data: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def update_index_html(data):
    """Update index.html with new citation data"""
    index_file = 'index.html'
    
    try:
        # Read current content
        with open(index_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Create backup
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        backup_name = f'{index_file}.backup.{timestamp}'
        shutil.copy2(index_file, backup_name)
        print(f"📁 Backup created: {backup_name}")
        
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
        
        # Write updated content
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

def main():
    """Main execution function"""
    print("🔍 Fetching latest citation data from Google Scholar...")
    
    data = fetch_citation_data(SCHOLAR_ID)
    
    if data:
        print("📥 Data fetched successfully!")
        print(f"🔗 Source: {data['url']}")
        
        if update_index_html(data):
            print("\n🎉 Citation data updated successfully!")
        else:
            print("\n❌ Failed to update index.html")
    else:
        print("❌ Failed to fetch citation data")
        print("\n💡 Possible solutions:")
        print("   • Try again in a few minutes (Google Scholar may have rate limits)")
        print("   • Check your internet connection")
        print("   • Verify your Google Scholar profile is public")

if __name__ == '__main__':
    main()
