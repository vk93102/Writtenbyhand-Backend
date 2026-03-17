"""
Ask a Question API - Production Ready
Integrates with web search APIs (SearchAPI.io, SERP API)
No AI dependency - Pure search results
"""

import logging
import time
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from .services import search_service, text_processor

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([AllowAny])
def ask_question_search(request):
    """
    Ask a Question - Search the web for answers
    
    POST /api/ask-question/search/
    
    Request Body:
    {
        "question": "What is photosynthesis?",
        "max_results": 5,  # optional, default 5
        "language": "en"   # optional, default en
    }
    
    Response (Success):
    {
        "success": true,
        "question": "What is photosynthesis?",
        "search_results": [
            {
                "title": "Photosynthesis - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Photosynthesis",
                "snippet": "Photosynthesis is a process used by plants...",
                "domain": "wikipedia.org",
                "is_trusted": true
            },
            ...
        ],
        "summary": "Generated summary based on search results",
        "total_results": 5,
        "processing_time": 2.34,
        "sources": ["wikipedia.org", "khan academy"]
    }
    
    Response (Error):
    {
        "success": false,
        "error": "No search API keys configured",
        "error_code": "API_KEY_ERROR"
    }
    """
    try:
        start_time = time.time()
        
        # Validate request
        question = request.data.get('question', '').strip()
        max_results = int(request.data.get('max_results', 5))
        language = request.data.get('language', 'en')
        
        if not question:
            return Response({
                'success': False,
                'error': 'Question is required',
                'error_code': 'EMPTY_QUESTION'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(question) < 3:
            return Response({
                'success': False,
                'error': 'Question must be at least 3 characters',
                'error_code': 'QUESTION_TOO_SHORT'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if max_results < 1 or max_results > 10:
            max_results = 5
        
        logger.info(f"Ask Question: {question[:100]}... (max_results={max_results})")
        
        # Step 1: Clean and process question
        logger.info("Step 1: Processing question")
        cleaned_question = text_processor.clean_text(question)
        
        # Step 2: Translate if needed
        if language != 'en':
            logger.info(f"Step 2: Translating from {language} to English")
            translation_result = text_processor.translate_to_english(cleaned_question)
            if translation_result.get('success'):
                cleaned_question = translation_result.get('translated', cleaned_question)
        
        # Step 3: Generate search queries
        logger.info("Step 3: Generating search queries")
        search_queries = text_processor.generate_search_queries(cleaned_question, max_queries=1)
        primary_query = search_queries[0] if search_queries else cleaned_question
        
        # Step 4: Web search
        logger.info("Step 4: Performing web search")
        search_start = time.time()
        search_result = search_service.search(primary_query, count=max_results)
        search_time = time.time() - search_start
        
        if not search_result.get('success'):
            logger.warning(f"Search failed: {search_result.get('error')}")
            return Response({
                'success': False,
                'error': search_result.get('error', 'Search failed'),
                'error_code': 'SEARCH_FAILED'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        results = search_result.get('results', [])
        
        # Step 6: Prepare response data
        # Filter and prioritize trusted domains; fallback to top results when none marked trusted
        filtered = search_service.filter_trusted_domains(results)
        trusted_results = [r for r in filtered.get('results', []) if r.get('is_trusted')]
        if not trusted_results:
            # No strongly trusted results; use top filtered results or raw results
            trusted_results = (filtered.get('results', []) or results)[:max_results]
        
        search_results_data = []
        sources = set()
        
        for result in trusted_results[:max_results]:
            search_results_data.append({
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'snippet': result.get('snippet', ''),
                'domain': result.get('domain', ''),
                'is_trusted': bool(result.get('is_trusted', False))
            })
            sources.add(result.get('domain', 'Unknown'))
        
        # Step 7: Create summary from top snippets (no AI)
        logger.info("Step 7: Creating summary from snippets")
        summary = ""
        if trusted_results:
            # Combine snippets as summary
            snippets = [r.get('snippet', '') for r in trusted_results[:2] if r.get('snippet')]
            summary = ' '.join(snippets) if snippets else "No summary available"
        
        processing_time = time.time() - start_time
        
        logger.info(f"Ask Question completed in {processing_time:.2f}s, found {len(search_results_data)} results")
        
        return Response({
            'success': True,
            'question': question,
            'search_query': primary_query,
            'search_results': search_results_data,
            'summary': summary,
            'total_results': len(search_results_data),
            'sources': sorted(list(sources)),
            'processing_time': round(processing_time, 2),
            'search_time': round(search_time, 2),
            'metadata': {
                'language': language,
                'filters_applied': 'trusted_domains',
                'summary_type': 'snippet_based'
            }
        })
    
    except Exception as e:
        logger.error(f"Ask Question error: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Internal server error',
            'error_code': 'INTERNAL_ERROR',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def ask_question_with_sources(request):
    """
    Ask a Question - Get comprehensive search results with trusted sources
    
    POST /api/ask-question/sources/
    
    Request Body:
    {
        "question": "What is photosynthesis?",
        "max_results": 5   # optional, number of sources to return
    }
    
    Response:
    {
        "success": true,
        "question": "What is photosynthesis?",
        "sources": [
            {
                "title": "Photosynthesis - Wikipedia",
                "url": "https://en.wikipedia.org/wiki/Photosynthesis",
                "snippet": "Photosynthesis is a process where...",
                "domain": "wikipedia.org"
            }
        ],
        "num_sources": 5,
        "processing_time": 1.23
    }
    """
    try:
        start_time = time.time()
        
        question = request.data.get('question', '').strip()
        max_results = int(request.data.get('max_results', 5))
        
        if not question:
            return Response({
                'success': False,
                'error': 'Question is required',
                'error_code': 'EMPTY_QUESTION'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(question) < 3:
            return Response({
                'success': False,
                'error': 'Question must be at least 3 characters',
                'error_code': 'QUESTION_TOO_SHORT'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if max_results < 1 or max_results > 10:
            max_results = 5
        
        logger.info(f"Ask Question (Sources): {question[:100]}...")
        
        # Step 1: Clean question
        cleaned_question = text_processor.clean_text(question)
        
        # Step 2: Generate search query
        search_queries = text_processor.generate_search_queries(cleaned_question, max_queries=1)
        primary_query = search_queries[0] if search_queries else cleaned_question
        
        # Step 3: Web search
        logger.info("Step 3: Performing web search")
        search_start = time.time()
        search_result = search_service.search(primary_query, count=max_results)
        search_time = time.time() - search_start
        
        if not search_result.get('success'):
            logger.warning(f"Search failed: {search_result.get('error')}")
            return Response({
                'success': False,
                'error': search_result.get('error', 'Search failed'),
                'error_code': 'SEARCH_FAILED'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        results = search_result.get('results', [])
        
        # Step 4: Filter by trusted domains
        logger.info("Step 4: Filtering trusted domains")
        filtered_results = search_service.filter_trusted_domains(results)
        sources = filtered_results.get('results', [])[:max_results]
        
        processing_time = time.time() - start_time
        
        logger.info(f"Sources search completed in {processing_time:.2f}s")
        
        return Response({
            'success': True,
            'question': question,
            'search_query': primary_query,
            'sources': [
                {
                    'title': s.get('title', ''),
                    'url': s.get('url', ''),
                    'snippet': s.get('snippet', ''),
                    'domain': s.get('domain', ''),
                    'is_trusted': True
                }
                for s in sources
            ],
            'num_sources': len(sources),
            'processing_time': round(processing_time, 2),
            'search_time': round(search_time, 2)
        })
    
    except Exception as e:
        logger.error(f"Ask Question (Sources) error: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Internal server error',
            'error_code': 'INTERNAL_ERROR'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([AllowAny])
def get_search_status(request):
    """
    Check if search APIs are configured and working
    
    GET /api/ask-question/status/
    
    Response:
    {
        "success": true,
        "apis": {
            "searchapi": {
                "configured": true,
                "status": "healthy"
            },
            "serp_api": {
                "configured": true,
                "status": "healthy"
            }
        },
        "trusted_domains_count": 18,
        "last_check": "2026-01-14T12:30:00Z"
    }
    """
    try:
        apis_status = {
            'searchapi': {
                'configured': bool(search_service.searchapi_key),
                'status': 'configured' if search_service.searchapi_key else 'not_configured'
            },
            'serp_api': {
                'configured': bool(search_service.serp_api_key),
                'status': 'configured' if search_service.serp_api_key else 'not_configured'
            }
        }
        
        return Response({
            'success': True,
            'apis': apis_status,
            'trusted_domains_count': len(search_service.trusted_domains),
            'trusted_domains_sample': search_service.trusted_domains[:5],
            'last_check': str(time.time())
        })
    
    except Exception as e:
        logger.error(f"Search status check error: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
