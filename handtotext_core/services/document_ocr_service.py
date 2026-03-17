"""
OCR Service - Handles text extraction from images with multi-language support
Supports Hindi, English, and other languages using Google Cloud Vision API
"""

import easyocr
import pytesseract
from PIL import Image
import numpy as np
import logging
import os
import json
from django.conf import settings

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self):
        """Initialize OCR service with optimized settings for speed"""
        self.google_vision_available = False
        self.easyocr_available = False
        self.vision_client = None
        self.reader = None
        self._initialized = False

    def _initialize_services(self):
        """Lazy initialization of OCR services - prioritize speed"""
        if self._initialized:
            return

        # For low-latency mode we disable EasyOCR on CPU environments
        # and rely on Tesseract for OCR. EasyOCR on CPU is very slow
        # (was causing 12-16s per image). If you have a GPU, re-enable
        # by setting `self.easyocr_available = True` and initializing
        # the reader with `easyocr.Reader(['en'], gpu=True)`.
        self.easyocr_available = False
        self.reader = None
        logger.info("EasyOCR disabled (using Tesseract for OCR to reduce latency)")
        
        # Initialize Google Cloud Vision as backup (slower but more accurate)
        try:
            if settings.GOOGLE_VISION_API_KEY:
                import google.auth
                from google.oauth2 import service_account
                from google.cloud import vision
                
                # Parse the service account JSON
                service_account_info = json.loads(settings.GOOGLE_VISION_API_KEY)
                credentials = service_account.Credentials.from_service_account_info(service_account_info)
                
                self.vision_client = vision.ImageAnnotatorClient(credentials=credentials)
                self.google_vision_available = True
                logger.info("Google Cloud Vision API initialized as backup")
        except Exception as e:
            logger.warning(f"Failed to initialize Google Cloud Vision API: {e}")
        
    @property
    def ocr_available(self):
        """Check if OCR services are available"""
        self._initialize_services()
        return self.google_vision_available or self.easyocr_available
    
    def extract_text_from_image(self, image_path):
        """
        Extract text from image using optimized pipeline with caching
        
        Args:
            image_path: Path to the image file
            
        Returns:
            dict: {
                'text': extracted text,
                'confidence': average confidence score,
                'language': detected language,
                'success': boolean
            }
        """
        import time
        start_time = time.time()
        
        # Try cache first (using file size + modification time as key)
        import os
        try:
            from .cache_service import ocr_cache
            stat = os.stat(image_path)
            cache_key = f"{stat.st_size}_{stat.st_mtime}"
            cached_result = ocr_cache.get(cache_key)
            if cached_result:
                logger.info(f"OCR cache hit! Saved {time.time() - start_time:.2f}s")
                cached_result['processing_time'] = time.time() - start_time
                return cached_result
        except Exception as e:
            logger.debug(f"Cache check failed: {e}")
        
        self._initialize_services()
        try:
            # Preprocess image for faster processing
            processed_image_path = self._preprocess_image_for_speed(image_path)
            
            # Use EasyOCR only for maximum speed (no Google Vision fallback)
            if self.easyocr_available:
                result = self._extract_with_easyocr(processed_image_path)
                processing_time = time.time() - start_time
                logger.info(f"OCR completed in {processing_time:.2f}s using EasyOCR")
                result['processing_time'] = processing_time
                # Cache the result
                try:
                    from .cache_service import ocr_cache
                    ocr_cache.set(cache_key, result)
                except:
                    pass
                return result
            
            # Fallback to Tesseract only if EasyOCR unavailable
            result = self._fallback_tesseract(processed_image_path)
            processing_time = time.time() - start_time
            logger.info(f"OCR completed in {processing_time:.2f}s using Tesseract")
            result['processing_time'] = processing_time
            return result
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0,
                'processing_time': time.time() - start_time
            }
    
    def _preprocess_image_for_speed(self, image_path):
        """
        Minimal preprocessing for maximum speed - just return original
        """
        # Skip preprocessing to avoid PIL compatibility issues
        # EasyOCR can handle images directly
        return image_path
    
    def _extract_with_google_vision(self, image_path):
        """Extract text using Google Cloud Vision API"""
        try:
            from google.cloud import vision
            
            # Read image file
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Perform text detection
            response = self.vision_client.text_detection(image=image)
            texts = response.text_annotations
            
            if not texts:
                logger.warning("No text detected by Google Cloud Vision")
                return self._extract_with_easyocr(image_path)
            
            # Extract the full text
            full_text = texts[0].description
            
            # Calculate confidence (Google Vision provides confidence per word)
            confidences = []
            for text in texts[1:]:  # Skip first annotation (full text)
                if hasattr(text, 'bounding_poly') and text.bounding_poly:
                    confidences.append(text.confidence or 0.8)  # Default confidence if not provided
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.8
            
            # Detect language
            language = self._detect_language_simple(full_text)
            
            return {
                'success': True,
                'text': full_text,
                'confidence': round(avg_confidence * 100, 2),
                'language': language,
                'method': 'google_vision'
            }
            
        except Exception as e:
            logger.error(f"Google Cloud Vision extraction failed: {e}")
            # Fallback to EasyOCR
            return self._extract_with_easyocr(image_path)
    
    def _extract_with_easyocr(self, image_path):
        """Extract text using EasyOCR with speed optimizations"""
        try:
            if not self.easyocr_available:
                return self._fallback_tesseract(image_path)
            
            # Read image using EasyOCR with maximum speed optimizations
            # Wrap in try-catch for PIL compatibility issues
            try:
                results = self.reader.readtext(
                    image_path,
                    detail=1,  # Return bounding box, text, and confidence
                    paragraph=False,  # Don't group into paragraphs for speed
                    min_size=5,  # Very low minimum text size
                    text_threshold=0.3,  # Very low confidence threshold for speed
                    low_text=0.1,  # Very low low text threshold
                    link_threshold=0.05,  # Very low link threshold
                    canvas_size=1280,  # Smaller canvas for faster processing
                    mag_ratio=1.0,  # No magnification for speed
                    slope_ths=0.3,  # Wider slope tolerance
                    ycenter_ths=0.9,  # Wider Y-center tolerance
                    height_ths=0.9,  # Wider height tolerance
                    width_ths=0.9,  # Wider width tolerance
                    add_margin=0.0  # No margin for speed
                )
            except AttributeError as ae:
                # Handle PIL compatibility issues
                logger.warning(f"EasyOCR PIL compatibility issue: {ae}, falling back to Tesseract")
                return self._fallback_tesseract(image_path)
            
            if not results:
                # Fallback to Tesseract if EasyOCR fails
                return self._fallback_tesseract(image_path)
            
            # Extract text and confidence scores
            extracted_text = []
            confidences = []
            
            for (bbox, text, confidence) in results:
                # Clean the text
                text = text.strip()
                if text and len(text) > 1:  # Filter out single characters
                    extracted_text.append(text)
                    confidences.append(confidence)
            
            # Combine all text
            full_text = ' '.join(extracted_text)
            
            # Calculate average confidence
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Detect language (simple heuristic)
            language = self._detect_language_simple(full_text)
            
            return {
                'success': True,
                'text': full_text,
                'confidence': round(avg_confidence * 100, 2),
                'language': language,
                'method': 'easyocr'
            }
            
        except Exception as e:
            logger.error(f"EasyOCR extraction failed: {e}")
            # Fallback to Tesseract on any EasyOCR error
            return self._fallback_tesseract(image_path)
    
    def _fallback_tesseract(self, image_path):
        """Fallback to Tesseract OCR"""
        try:
            image = Image.open(image_path)
            text = pytesseract.image_to_string(image, lang='eng+hin')
            
            return {
                'success': True,
                'text': text,
                'confidence': 70,  # Estimated confidence
                'language': 'mixed',
                'method': 'tesseract'
            }
        except Exception as e:
            logger.error(f"Tesseract fallback failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': '',
                'confidence': 0
            }
    
    def _detect_language_simple(self, text):
        """Simple language detection based on Unicode ranges"""
        if not text:
            return 'unknown'
        
        # Check for Devanagari script (Hindi)
        hindi_chars = sum(1 for char in text if '\u0900' <= char <= '\u097F')
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        
        total_chars = hindi_chars + english_chars
        if total_chars == 0:
            return 'unknown'
        
        hindi_ratio = hindi_chars / total_chars
        
        if hindi_ratio > 0.5:
            return 'hindi'
        elif hindi_ratio > 0.1:
            return 'mixed'
        else:
            return 'english'
    
    def preprocess_image(self, image_path, output_path=None):
        """
        Preprocess image for better OCR accuracy
        - Convert to grayscale
        - Increase contrast
        - Denoise
        """
        try:
            image = Image.open(image_path)
            
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Enhance contrast
            img_array = np.array(image)
            # Simple contrast enhancement
            img_array = np.clip((img_array - img_array.min()) * 255.0 / 
                               (img_array.max() - img_array.min()), 0, 255).astype(np.uint8)
            
            enhanced_image = Image.fromarray(img_array)
            
            if output_path:
                enhanced_image.save(output_path)
                return output_path
            
            return enhanced_image
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image_path


# Global instance
ocr_service = OCRService()
