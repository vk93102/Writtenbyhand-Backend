"""
Text Processing Service - Handles text cleaning, language detection, and translation
"""

from langdetect import detect, DetectorFactory
from deep_translator import GoogleTranslator
import re
import logging

logger = logging.getLogger(__name__)

# Set seed for consistent language detection
DetectorFactory.seed = 0


class TextProcessingService:
    def __init__(self):
        self.translator = GoogleTranslator(source='auto', target='en')
    
    def clean_text(self, text):
        """
        Clean and normalize extracted text
        - Remove extra whitespace
        - Fix common OCR errors
        - Normalize punctuation
        """
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep mathematical symbols
        # Keep: +, -, *, /, =, (), [], {}, numbers, letters
        text = re.sub(r'[^\w\s\+\-\*/=\(\)\[\]\{\}\?\.,:;°√∫∑∏αβγδεπθλμσφψω]', '', text)
        
        # Fix common OCR errors
        replacements = {
            '0': 'O',  # Only in certain contexts
            'l': '1',  # Only in numeric contexts
        }
        
        # Normalize whitespace around operators
        text = re.sub(r'\s*([+\-*/=])\s*', r' \1 ', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def detect_language(self, text):
        """
        Detect language of the text
        Returns language code (en, hi, etc.)
        """
        try:
            if not text or len(text.strip()) < 3:
                return 'unknown'
            
            lang = detect(text)
            return lang
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return 'unknown'
    
    def translate_to_english(self, text, source_lang='auto'):
        """
        Translate text to English if needed
        
        Args:
            text: Text to translate
            source_lang: Source language code (auto-detect if 'auto')
            
        Returns:
            dict: {
                'original': original text,
                'translated': translated text,
                'source_lang': detected/specified source language,
                'success': boolean
            }
        """
        try:
            if not text:
                return {
                    'success': False,
                    'error': 'Empty text',
                    'original': '',
                    'translated': ''
                }
            
            # Detect if already in English
            detected_lang = self.detect_language(text)
            
            if detected_lang == 'en':
                return {
                    'success': True,
                    'original': text,
                    'translated': text,
                    'source_lang': 'en',
                    'translation_needed': False
                }
            
            # Translate to English
            translator = GoogleTranslator(source='auto', target='en')
            translated = translator.translate(text)
            
            return {
                'success': True,
                'original': text,
                'translated': translated,
                'source_lang': detected_lang,
                'translation_needed': True
            }
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'original': text,
                'translated': text,  # Return original if translation fails
                'source_lang': source_lang
            }
    
    def generate_search_queries(self, text, max_queries=3):
        """
        Generate multiple search queries from extracted text
        
        Returns list of search queries optimized for finding solutions
        """
        queries = []
        
        # Query 1: Original cleaned text
        queries.append(text)
        
        # Query 2: Add "solution" keyword
        queries.append(f"{text} solution")
        
        # Query 3: Add context for educational search
        if 'jee' in text.lower() or 'neet' in text.lower():
            queries.append(f"{text} JEE solution step by step")
        else:
            queries.append(f"{text} solved example explanation")
        
        return queries[:max_queries]
    
    def extract_keywords(self, text):
        """
        Extract important keywords from text
        Focus on mathematical, scientific terms
        """
        # Remove common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                     'of', 'with', 'is', 'are', 'was', 'were', 'find', 'calculate', 'solve'}
        
        words = text.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords[:10]  # Return top 10 keywords
    
    def normalize_question(self, text):
        """
        Normalize question text for better matching
        - Standardize mathematical notation
        - Fix spacing
        - Remove noise
        """
        text = self.clean_text(text)
        
        # Standardize mathematical operators
        text = text.replace('×', '*')
        text = text.replace('÷', '/')
        text = text.replace('–', '-')
        
        # Ensure proper spacing around numbers and operators
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
        
        return text


# Global instance
text_processor = TextProcessingService()
