
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# Search for AI regulation papers from June 2022
query = "AI regulation"
date_range = "[2022-06-01 TO 2022-06-30]"

# Build the API URL
base_url = "https://export.arxiv.org/api/query"
search_query = f"submittedDate:{date_range} AND all:{query.replace(' ', '+')}"
params = {
    "search_query": search_query,
    "start": 0,
    "max_results": 50
}

url = f"{base_url}?{urllib.parse.urlencode(params)}"
print(f"Searching: {url}")

try:
    with urllib.request.urlopen(url) as response:
        data = response.read().decode('utf-8')
        
    # Parse the XML
    root = ET.fromstring(data)
    
    # Define namespaces
    ns = {
        'atom': 'http://www.w3.org/2005/Atom',
        'arxiv': 'http://arxiv.org/schemas/atom'
    }
    
    # Find all entries
    entries = root.findall('.//atom:entry', ns)
    print(f"\nFound {len(entries)} papers\n")
    
    for entry in entries:
        title = entry.find('atom:title', ns)
        published = entry.find('atom:published', ns)
        id_elem = entry.find('atom:id', ns)
        summary = entry.find('atom:summary', ns)
        
        if title is not None:
            print(f"Title: {title.text}")
        if published is not None:
            print(f"Published: {published.text}")
        if id_elem is not None:
            print(f"ID: {id_elem.text}")
        if summary is not None:
            print(f"Summary: {summary.text[:200]}...")
        print("-" * 80)
        
except Exception as e:
    print(f"Error: {e}")
