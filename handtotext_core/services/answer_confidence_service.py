"""
Confidence Scoring Service - Calculates confidence scores for solutions
Based on OCR quality, search match quality, and domain trust
"""

import logging
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

logger = logging.getLogger(__name__)


class ConfidenceScoreService:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=100)
    
    def calculate_overall_confidence(self, ocr_confidence, search_results, original_query):
        """
        Calculate overall confidence score (0-100)
        
        Components:
        1. OCR Confidence (30% weight)
        2. Search Match Quality (40% weight)
        3. Domain Trust Score (30% weight)
        
        Args:
            ocr_confidence: OCR confidence score (0-100)
            search_results: List of search results with trust scores
            original_query: Original query text
            
        Returns:
            dict: Detailed confidence breakdown
        """
        try:
            # Component 1: OCR Confidence (0-30 points)
            ocr_score = (ocr_confidence / 100) * 30
            
            # Component 2: Search Match Quality (0-40 points)
            match_score = self._calculate_match_quality(search_results, original_query) * 40
            
            # Component 3: Domain Trust (0-30 points)
            trust_score = self._calculate_domain_trust(search_results) * 30
            
            # Overall confidence
            overall = ocr_score + match_score + trust_score
            
            return {
                'overall_confidence': round(overall, 2),
                'components': {
                    'ocr_confidence': round(ocr_score, 2),
                    'match_quality': round(match_score, 2),
                    'domain_trust': round(trust_score, 2)
                },
                'grade': self._get_confidence_grade(overall),
                'reliability': self._get_reliability_level(overall)
            }
            
        except Exception as e:
            logger.error(f"Confidence calculation failed: {e}")
            return {
                'overall_confidence': 50,
                'components': {
                    'ocr_confidence': 0,
                    'match_quality': 0,
                    'domain_trust': 0
                },
                'grade': 'C',
                'reliability': 'medium'
            }
    
    def _calculate_match_quality(self, search_results, query):
        """
        Calculate how well search results match the query
        Uses text similarity (cosine similarity)
        """
        if not search_results or not query:
            return 0.5
        
        try:
            # Combine all result snippets
            result_texts = [
                f"{r.get('title', '')} {r.get('snippet', '')}"
                for r in search_results if r.get('snippet')
            ]
            
            if not result_texts:
                return 0.5
            
            # Add query to the list for vectorization
            all_texts = [query] + result_texts
            
            # Calculate TF-IDF vectors
            tfidf_matrix = self.vectorizer.fit_transform(all_texts)
            
            # Calculate cosine similarity between query and each result
            query_vector = tfidf_matrix[0:1]
            result_vectors = tfidf_matrix[1:]
            
            similarities = cosine_similarity(query_vector, result_vectors)[0]
            
            # Average similarity as match quality
            avg_similarity = np.mean(similarities)
            
            return float(avg_similarity)
            
        except Exception as e:
            logger.error(f"Match quality calculation failed: {e}")
            return 0.5
    
    def _calculate_domain_trust(self, search_results):
        """
        Calculate average trust score from search results
        """
        if not search_results:
            return 0.5
        
        trust_scores = [r.get('trust_score', 50) for r in search_results if 'trust_score' in r]
        
        if not trust_scores:
            return 0.5
        
        # Normalize to 0-1 range
        avg_trust = sum(trust_scores) / len(trust_scores)
        return avg_trust / 100
    
    def _get_confidence_grade(self, score):
        """
        Convert confidence score to letter grade
        """
        if score >= 90:
            return 'A+'
        elif score >= 80:
            return 'A'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        elif score >= 50:
            return 'D'
        else:
            return 'F'
    
    def _get_reliability_level(self, score):
        """
        Get reliability level description
        """
        if score >= 80:
            return 'very_high'
        elif score >= 70:
            return 'high'
        elif score >= 60:
            return 'medium'
        elif score >= 40:
            return 'low'
        else:
            return 'very_low'
    
    def score_individual_result(self, result, query, rank_position):
        """
        Score an individual search result
        
        Args:
            result: Search result dict
            query: Original query
            rank_position: Position in search results (1-based)
            
        Returns:
            float: Score for this result (0-100)
        """
        score = 0
        
        # Domain trust (40 points)
        trust = result.get('trust_score', 50)
        score += (trust / 100) * 40
        
        # Position in results (20 points - higher rank = higher score)
        position_score = max(0, (10 - rank_position) / 10) * 20
        score += position_score
        
        # Title/snippet relevance (40 points)
        relevance = self._calculate_text_relevance(
            query,
            f"{result.get('title', '')} {result.get('snippet', '')}"
        )
        score += relevance * 40
        
        return round(score, 2)
    
    def _calculate_text_relevance(self, query, text):
        """
        Calculate relevance between query and text
        Simple keyword-based approach
        """
        if not query or not text:
            return 0.5
        
        query_words = set(query.lower().split())
        text_words = set(text.lower().split())
        
        # Jaccard similarity
        intersection = query_words & text_words
        union = query_words | text_words
        
        if not union:
            return 0
        
        return len(intersection) / len(union)


# Global instance
confidence_scorer = ConfidenceScoreService()
