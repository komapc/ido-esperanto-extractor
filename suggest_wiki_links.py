import requests
import json
import time

def get_popular_ido_pages():
    """Fetches popular pages from Ido Wikipedia using the Wikimedia API."""
    # Top pages in the last month (example)
    url = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/io.wikipedia/all-access/2026/02/all-days"
    headers = {"User-Agent": "IdoEpoLinkSuggester/1.0 (komapc@example.com)"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data['items'][0]['articles']
        else:
            print(f"Failed to fetch popular pages: {response.status_code}")
            return []
    except Exception as e:
        print(f"Error: {e}")
        return []

def check_external_links(title):
    """Checks if a page already has links to major Ido dictionaries or Apertium."""
    url = f"https://io.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extlinks",
        "titles": title,
        "format": "json"
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        pages = data.get('query', {}).get('pages', {})
        for page_id in pages:
            extlinks = pages[page_id].get('extlinks', [])
            links_str = "".join([l.get('*', '') for l in extlinks])
            
            # Keywords indicating an existing dictionary link
            keywords = ['apertium', 'vortaro', 'dict', 'traduk', 'esperanto']
            has_link = any(kw in links_str.lower() for kw in keywords)
            return has_link
    except:
        return False

def main():
    print("Fetching popular Ido Wikipedia pages...")
    popular_pages = get_popular_ido_pages()
    
    suggestions = []
    # Filter out special pages and media
    filtered_pages = [p for p in popular_pages if ":" not in p['article'] and p['article'] != "Chefpagino"]
    
    print(f"Analyzing {len(filtered_pages[:20])} pages for missing links...")
    
    for page in filtered_pages[:20]:
        title = page['article']
        if not check_external_links(title):
            suggestions.append({
                "title": title,
                "views": page['views'],
                "url": f"https://io.wikipedia.org/wiki/{title}"
            })
        time.sleep(0.1) # Be nice to the API
        
    print("\n--- RECOMMENDED WIKIPEDIA TARGETS ---")
    print("These high-traffic Ido pages currently LACK Ido-Esperanto dictionary/translator links:")
    for s in suggestions:
        print(f"- {s['title']} ({s['views']} views): {s['url']}")
        
    with open("wiki_link_suggestions.json", "w") as f:
        json.dump(suggestions, f, indent=2)
    print("\nResults saved to wiki_link_suggestions.json")

if __name__ == "__main__":
    main()
