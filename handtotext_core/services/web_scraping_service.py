"""  
Web Scraping Service - Fetches and parses content from URLs
Uses BeautifulSoup for parsing
"""

import requests
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)
class WebScraperService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Use session for connection pooling and reuse
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        # Configure session for speed
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=0  # No retries for speed
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
    
    def fetch_url_content(self, url, timeout=1.2):
        """
        Fetch and parse content from a URL
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            dict: {
                'success': boolean,
                'title': page title,
                'content': extracted text content,
                'url': original URL
            }
        """
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = soup.title.string if soup.title else ''
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            # Get text
            text = soup.get_text(separator=' ', strip=True)
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Limit content length for speed - reduced to 800 chars
            max_length = 800
            if len(text) > max_length:
                text = text[:max_length] + "..."
            
            return {
                'success': True,
                'title': title,
                'content': text,
                'url': url,
                'length': len(text)
            }
            
        except requests.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': url,
                'title': '',
                'content': ''
            }
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
            return {
                'success': False,
                'error': str(e),
                'url': url,
                'title': '',
                'content': ''
            }
    
    def fetch_multiple_urls(self, urls, max_concurrent=5):
        """
        Fetch content from multiple URLs in parallel
        
        Args:
            urls: List of URLs
            max_concurrent: Maximum concurrent requests
            
        Returns:
            list: List of results for each URL
        """
        results = []
        
        # Limit URLs to process
        urls_to_fetch = urls[:max_concurrent]
        
        # Use ThreadPoolExecutor for parallel requests
        with ThreadPoolExecutor(max_workers=min(max_concurrent, 5)) as executor:
            # Submit all URL fetch tasks
            future_to_url = {executor.submit(self.fetch_url_content, url): url for url in urls_to_fetch}
            
            # Collect results as they complete (with timeout)
            for future in as_completed(future_to_url, timeout=2.5):
                try:
                    result = future.result(timeout=1.5)
                    results.append(result)
                except Exception as e:
                    url = future_to_url[future]
                    logger.error(f"Failed to fetch {url}: {e}")
                    results.append({
                        'success': False,
                        'error': str(e),
                        'url': url,
                        'title': '',
                        'content': ''
                    })
        
        return results
    
    def extract_relevant_content(self, content, keywords):
        """
        Extract relevant sections from content based on keywords
        
        Args:
            content: Full text content
            keywords: List of keywords to look for
            
        Returns:
            str: Extracted relevant content
        """
        if not keywords or not content:
            return content[:1000]  # Return first 1000 chars if no keywords
        
        # Split content into sentences
        sentences = content.split('. ')
        
        # Score each sentence based on keyword presence
        scored_sentences = []
        for sentence in sentences:
            score = sum(1 for keyword in keywords if keyword.lower() in sentence.lower())
            if score > 0:
                scored_sentences.append((score, sentence))
        
        # Sort by score and take top sentences
        scored_sentences.sort(reverse=True, key=lambda x: x[0])
        top_sentences = [sent for score, sent in scored_sentences[:10]]
        
        return '. '.join(top_sentences)
    
    def extract_solution_content(self, html_content):
        """
        Extract solution-specific content from HTML
        Looks for common solution markers
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for solution-related sections
            solution_markers = [
                'solution', 'answer', 'explanation', 'step', 'solved',
                'approach', 'method', 'procedure'
            ]
            
            solution_content = []
            
            # Find divs/sections with solution-related class names or text
            for marker in solution_markers:
                elements = soup.find_all(['div', 'section', 'article'], 
                                        class_=lambda x: x and marker in x.lower() if x else False)
                for elem in elements:
                    text = elem.get_text(separator=' ', strip=True)
                    if text:
                        solution_content.append(text)
            
            if solution_content:
                return ' '.join(solution_content)[:2000]
            
            # Fallback: return first substantial text block
            paragraphs = soup.find_all('p')
            text_blocks = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 50]
            
            return ' '.join(text_blocks[:5])
            
        except Exception as e:
            logger.error(f"Error extracting solution content: {e}")
            return ""


# Global instance
web_scraper = WebScraperService()
