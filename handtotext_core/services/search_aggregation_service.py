"""
Search Service - Handles web search using SearchAPI.io
Fetches top 5 results and filters trusted domains
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self):
        self.searchapi_key = settings.SEARCHAPI_KEY
        self.serp_api_key = settings.SERP_API_KEY
        
        # Use session for connection pooling
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=5,
            pool_maxsize=10,
            max_retries=0
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # Trusted domains for educational content
        self.trusted_domains = [
            'stackoverflow.com',
            'geeksforgeeks.org',
            'tutorialspoint.com',
            'w3schools.com',
            'khanacademy.org',
            'mathway.com',
            'symbolab.com',
            'chegg.com',
            'toppr.com',
            'byjus.com',
            'vedantu.com',
            'unacademy.com',
            'physics.stackexchange.com',
            'math.stackexchange.com',
            'chemistry.stackexchange.com',
            'quora.com',
            'doubtnut.com',
            'meritnation.com',
        ]
    
    def search_searchapi(self, query, count=5):
        """
        Search using SearchAPI.io with production-level error handling
        
        Args:
            query: Search query
            count: Number of results to fetch (1-10 recommended)
            
        Returns:
            dict: {
                'success': bool,
                'results': [{'title', 'url', 'snippet', 'domain', 'trust_score'}],
                'query': str,
                'source': 'searchapi',
                'error': str (if failed)
            }
        """
        if not self.searchapi_key:
            logger.warning("[SearchAPI] Key not configured - returning mock data")
            return self._mock_search_results(query, count)
        
        try:
            # Check cache first for performance
            from .cache_service import search_cache
            cache_key = f"searchapi_{query}_{count}"
            cached_result = search_cache.get(cache_key)
            if cached_result:
                logger.info(f"[SearchAPI] Cache HIT: {query[:40]}")
                return cached_result
        except Exception as cache_error:
            logger.debug(f"[SearchAPI] Cache check failed: {cache_error}")
        
        try:
            endpoint = "https://www.searchapi.io/api/v1/search"
            params = {
                "engine": "google",
                "q": query,
                "api_key": self.searchapi_key,
                "num": min(count, 10)  # Cap at 10
            }
            
            logger.info(f"[SearchAPI] Request: '{query[:40]}...' | API: ...{self.searchapi_key[-4:]}")
            
            response = self.session.get(endpoint, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'organic_results' in data:
                for item in data['organic_results'][:count]:
                    try:
                        result = {
                            'title': item.get('title', 'Untitled'),
                            'url': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'domain': self._extract_domain(item.get('link', '')),
                        }
                        results.append(result)
                    except Exception as item_error:
                        logger.warning(f"[SearchAPI] Item parsing error: {item_error}")
                        continue
            
            logger.info(f"[SearchAPI] ✅ Success: {len(results)} results for '{query[:40]}...'")
            
            result = {
                'success': True,
                'results': results,
                'query': query,
                'source': 'searchapi'
            }
            
            # Cache for future use
            try:
                from .cache_service import search_cache
                search_cache.set(cache_key, result, timeout=3600)  # 1 hour cache
            except:
                pass
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"[SearchAPI] Timeout (5s) for query: '{query[:40]}'")
            return {
                'success': False,
                'error': 'SearchAPI request timeout',
                'results': []
            }
        except requests.exceptions.HTTPError as http_err:
            if response.status_code == 401:
                logger.error(f"[SearchAPI] 401 Unauthorized - Invalid API key")
            elif response.status_code == 403:
                logger.error(f"[SearchAPI] 403 Forbidden - Quota exceeded")
            elif response.status_code == 429:
                logger.warning(f"[SearchAPI] 429 Rate limited - try again later")
            else:
                logger.error(f"[SearchAPI] HTTP {response.status_code}: {http_err}")
            return {
                'success': False,
                'error': f'SearchAPI HTTP {response.status_code}',
                'results': []
            }
        except Exception as e:
            logger.error(f"[SearchAPI] Exception: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def search_serpapi(self, query, count=5):
        """
        Search using SerpAPI (Google Search) with production-level error handling
        
        Args:
            query: Search query
            count: Number of results to fetch
            
        Returns:
            dict: {
                'success': bool,
                'results': [{'title', 'url', 'snippet', 'domain', 'trust_score'}],
                'query': str,
                'source': 'serpapi',
                'error': str (if failed)
            }
        """
        if not self.serp_api_key:
            logger.warning("[SerpAPI] Key not configured")
            return {
                'success': False,
                'error': 'SerpAPI key not configured',
                'results': []
            }
        
        try:
            logger.info(f"[SerpAPI] Request: '{query[:40]}...'")
            
            endpoint = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": self.serp_api_key,
                "num": min(count, 10),
                "engine": "google"
            }
            
            response = requests.get(endpoint, params=params, timeout=8)
            
            # Handle different HTTP status codes
            if response.status_code == 401:
                logger.error(f"[SerpAPI] 401 Unauthorized - Invalid API key (last 4: ...{self.serp_api_key[-4:]})")
                return {
                    'success': False,
                    'error': 'SerpAPI authentication failed - Invalid or expired key',
                    'results': []
                }
            elif response.status_code == 403:
                logger.error(f"[SerpAPI] 403 Forbidden - Access denied or quota exceeded")
                return {
                    'success': False,
                    'error': 'SerpAPI quota exceeded or access denied',
                    'results': []
                }
            elif response.status_code == 429:
                logger.warning(f"[SerpAPI] 429 Rate limit - Try again in a moment")
                return {
                    'success': False,
                    'error': 'SerpAPI rate limited',
                    'results': []
                }
            
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if 'organic_results' in data:
                for item in data['organic_results'][:count]:
                    try:
                        result = {
                            'title': item.get('title', 'Untitled'),
                            'url': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'domain': self._extract_domain(item.get('link', '')),
                        }
                        results.append(result)
                    except Exception as item_error:
                        logger.warning(f"[SerpAPI] Item parsing error: {item_error}")
                        continue
            
            logger.info(f"[SerpAPI] ✅ Success: {len(results)} results for '{query[:40]}...'")
            
            return {
                'success': True,
                'results': results,
                'query': query,
                'source': 'serpapi'
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"[SerpAPI] Timeout (8s) for query: '{query[:40]}'")
            return {
                'success': False,
                'error': 'SerpAPI request timeout',
                'results': []
            }
        except requests.exceptions.ConnectionError:
            logger.error(f"[SerpAPI] Connection error - Network issue")
            return {
                'success': False,
                'error': 'SerpAPI connection error',
                'results': []
            }
        except Exception as e:
            logger.error(f"[SerpAPI] Exception: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'results': []
            }
    
    def search(self, query, count=5, prefer_source='searchapi'):
        """
        Production-level unified search with intelligent fallback chain
        
        Args:
            query: Search query string (minimum 2 characters)
            count: Number of results to return (1-10, default: 5)
            prefer_source: 'searchapi' or 'serpapi' - which API to try first
            
        Returns:
            dict: {
                'success': bool,
                'results': [{'title', 'url', 'snippet', 'domain', 'trust_score'}, ...],
                'query': str,
                'source': str (searchapi, serpapi, or mock),
                'error': str (if failed),
                'warning': str (if using fallback/mock data)
            }
        """
        logger.info(f"[SEARCH] Initiated - Query: '{query[:50]}...' | Preference: {prefer_source}")
        
        # ===== INPUT VALIDATION =====
        if not query or not isinstance(query, str):
            logger.warning(f"[SEARCH] Invalid query type: {type(query)}")
            return {
                'success': False,
                'error': 'Query must be a non-empty string',
                'results': []
            }
        
        query = query.strip()
        if len(query) < 2:
            logger.warning(f"[SEARCH] Query too short: '{query}' (minimum 2 characters)")
            return {
                'success': False,
                'error': 'Query must be at least 2 characters long',
                'results': []
            }
        
        # Normalize count
        count = max(1, min(count, 10))
        
        # ===== FALLBACK CHAIN STRATEGY =====
        # Build API chain based on preference
        apis_to_try = []
        
        if prefer_source.lower() == 'searchapi':
            if self.searchapi_key:
                apis_to_try.append(('searchapi', self.search_searchapi))
            if self.serp_api_key:
                apis_to_try.append(('serpapi', self.search_serpapi))
        else:  # prefer serpapi
            if self.serp_api_key:
                apis_to_try.append(('serpapi', self.search_serpapi))
            if self.searchapi_key:
                apis_to_try.append(('searchapi', self.search_searchapi))
        
        # ===== TRY EACH API IN CHAIN =====
        last_error = None
        
        for api_name, api_func in apis_to_try:
            try:
                logger.info(f"[SEARCH] Trying {api_name}...")
                result = api_func(query, count)
                
                # Check if API returned successful results
                if result.get('success') and result.get('results') and len(result.get('results', [])) > 0:
                    logger.info(f"[SEARCH] ✅ {api_name} SUCCESS - {len(result['results'])} results found")
                    return result
                else:
                    error_msg = result.get('error', 'No results returned')
                    logger.warning(f"[SEARCH] {api_name} failed: {error_msg}")
                    last_error = error_msg
                    
            except Exception as e:
                logger.error(f"[SEARCH] {api_name} exception: {str(e)}")
                last_error = str(e)
                continue
        
        # ===== ALL APIS FAILED - FALLBACK TO MOCK DATA =====
        logger.warning(f"[SEARCH] All APIs failed. Last error: {last_error}")
        logger.info(f"[SEARCH] ⚠️ Returning mock data as fallback")
        
        mock_result = self._mock_search_results(query, count)
        mock_result['warning'] = f'Using mock data - All search APIs failed. Last error: {last_error}'
        return mock_result
    
    def filter_trusted_domains(self, results):
        """
        Filter and prioritize results from trusted educational domains
        
        Args:
            results: List of search results
            
        Returns:
            dict: Filtered results with trust scores
        """
        filtered = []
        
        for result in results:
            domain = result.get('domain', '')
            trust_score = self._calculate_trust_score(domain)
            
            result['trust_score'] = trust_score
            result['is_trusted'] = trust_score > 50
            
            filtered.append(result)
        
        # Sort by trust score
        filtered.sort(key=lambda x: x['trust_score'], reverse=True)
        
        return {
            'results': filtered,
            'trusted_count': sum(1 for r in filtered if r['is_trusted'])
        }
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.replace('www.', '')
        except:
            return ''
    
    def _calculate_trust_score(self, domain):
        """
        Calculate trust score for a domain
        Returns score 0-100
        """
        if not domain:
            return 0
        
        # Check if domain is in trusted list
        for trusted in self.trusted_domains:
            if trusted in domain.lower():
                return 90
        
        # Educational domains (.edu)
        if '.edu' in domain:
            return 80
        
        # Government/Academic domains
        if '.gov' in domain or '.ac.' in domain:
            return 75
        
        # Reputable domains heuristic
        if any(keyword in domain.lower() for keyword in ['learn', 'study', 'education', 'tutorial']):
            return 60
        
        # Default score for other domains
        return 40
    
    def _mock_search_results(self, query, count):
        """
        Mock search results for testing when API keys are not available
        """
        return {
            'success': True,
            'results': [
                {
                    'title': f'Solution for: {query}',
                    'url': 'https://example.com/solution1',
                    'snippet': f'Complete solution and explanation for {query}...',
                    'domain': 'example.com',
                    'trust_score': 50,
                    'is_trusted': False
                },
                {
                    'title': f'Step by step guide: {query}',
                    'url': 'https://stackoverflow.com/solution2',
                    'snippet': f'Detailed step-by-step solution...',
                    'domain': 'stackoverflow.com',
                    'trust_score': 90,
                    'is_trusted': True
                }
            ],
            'query': query,
            'source': 'mock',
            'warning': 'Using mock data - API keys not configured'
        }


# Global instance
search_service = SearchService()
