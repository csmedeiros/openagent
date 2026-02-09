
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

# Search for AI regulation papers from June 2022
# Try a simpler query
query = "regulation"

# Build the API URL
base_url = "https://export.arxiv.org/api/query"
params = {
    "search_query": query,
    "start": 0,
    "max_results": 100,
    "sortBy": "submittedDate",
    "sortOrder": "descending"
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
        
        # Check if published date is in June 2022
        if published is not None:
            pub_date = published.text
            if '2022-06' in pub_date:
                print(f"Title: {title.text if title is not None else 'N/A'}")
                print(f"Published: {pub_date}")
                print(f"ID: {id_elem.text if id_elem is not None else 'N/A'}")
                if summary is not None:
                    print(f"Summary: {summary.text[:300]}...")
                print("-" * 80)
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
