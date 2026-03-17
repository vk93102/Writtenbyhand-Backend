"""
Gemini AI Service for Quiz and Flashcard Generation
Uses Google's Generative AI to create educational content
"""

import os
import logging
import json
import google.generativeai as genai
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in environment variables")


class GeminiService:
    """Service for generating educational content using Gemini AI"""
    
    def __init__(self):
        # Using gemini-pro as Gemini 1.5 Flash is not available in this environment
        try:
            self.model = genai.GenerativeModel('models/gemini-2.0-flash')
            logger.info("Successfully initialized Gemini model: models/gemini-2.0-flash")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            self.model = None
    
    def generate_quiz(self, topic: str, num_questions: int = 5, difficulty: str = 'medium') -> Dict[str, Any]:
        """
        Generate a quiz based on a topic
        
        Args:
            topic: The topic or text content to generate quiz from
            num_questions: Number of questions to generate (default: 5)
            difficulty: Difficulty level - easy, medium, hard (default: medium)
        
        Returns:
            Dictionary containing quiz data with questions, options, and answers
        """
        try:
            prompt = f"""Generate a {difficulty} difficulty quiz with {num_questions} multiple-choice questions about the following topic:

Topic: {topic}

IMPORTANT FORMATTING RULES:
- Return ONLY valid JSON, no markdown, no code blocks, no explanations
- All text inside strings MUST be single-line only (no newlines/line breaks in strings)
- If a question would span multiple lines, combine it into one line using periods or semicolons
- Escape all special characters properly (use \\n for newlines in explanations if needed)
- Ensure all strings are properly closed with quotes

Please format the response as a valid JSON object with the following structure:
{{
    "title": "Quiz Title",
    "topic": "{topic}",
    "difficulty": "{difficulty}",
    "questions": [
        {{
            "id": 1,
            "question": "Question text here (single line)?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correctAnswer": 0,
            "explanation": "Explanation of the correct answer (single line)"
        }}
    ]
}}

Rules:
- Make questions clear and educational
- Provide 4 options for each question
- correctAnswer should be the index (0-3) of the correct option
- Include a brief explanation for each answer
- Ensure JSON is properly formatted with all strings on single lines
"""
            
            logger.info(f"Generating quiz for topic: {topic}")
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Try to extract JSON from markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            # Try to parse JSON, with aggressive repair if needed
            try:
                quiz_data = json.loads(response_text)
            except json.JSONDecodeError as json_err:
                logger.warning(f"Initial JSON parse failed at {json_err.pos}: {json_err.msg}. Attempting repair...")
                
                # More aggressive repair: Replace all unescaped newlines within strings
                def repair_json_strictly(text):
                    """Repair JSON by escaping all literal newlines in strings"""
                    result = []
                    i = 0
                    while i < len(text):
                        # Look for string start
                        if text[i] == '"':
                            result.append('"')
                            i += 1
                            # Process string contents
                            while i < len(text):
                                if text[i] == '\\' and i + 1 < len(text):
                                    # Escape sequence - keep as is
                                    result.append(text[i:i+2])
                                    i += 2
                                elif text[i] == '"':
                                    # End of string
                                    result.append('"')
                                    i += 1
                                    break
                                elif text[i] in '\n\r':
                                    # Literal newline in string - escape it
                                    result.append('\\n')
                                    i += 1
                                    # Skip following whitespace
                                    while i < len(text) and text[i] in ' \t':
                                        i += 1
                                else:
                                    result.append(text[i])
                                    i += 1
                        else:
                            result.append(text[i])
                            i += 1
                    return ''.join(result)
                
                repaired = repair_json_strictly(response_text)
                logger.info(f"Attempting parse with repaired JSON (length: {len(repaired)} vs {len(response_text)})")
                try:
                    quiz_data = json.loads(repaired)
                    logger.info("✅ Successfully repaired and parsed JSON!")
                except json.JSONDecodeError as err2:
                    logger.error(f"Still unable to parse after strict repair at {err2.pos}: {err2.msg}")
                    logger.error(f"Repaired text around error (chars {max(0, err2.pos-50)}...{err2.pos+50}):")
                    logger.error(repr(repaired[max(0, err2.pos-50):err2.pos+50]))
                    raise json_err  # Raise original error
            
            logger.info(f"Successfully generated {len(quiz_data.get('questions', []))} questions")
            return {
                'success': True,
                'quiz': quiz_data
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            if 'response_text' in locals():
                logger.error(f"Response text length: {len(response_text)}, first 400 chars:")
                logger.error(response_text[:400])
            return {
                'success': False,
                'error': 'Failed to parse quiz data',
                'details': str(e)
            }
        except Exception as e:
            # Handle quota errors from Google's client explicitly
            try:
                from google.api_core.exceptions import ResourceExhausted
            except Exception:
                ResourceExhausted = None

            if ResourceExhausted and isinstance(e, ResourceExhausted):
                import re
                m = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', str(e))
                retry_seconds = int(m.group(1)) if m else None
                logger.warning(f"Quota exceeded for Gemini API: retry in {retry_seconds}s")

                return {
                    'success': False,
                    'error': 'quota_exceeded',
                    'details': str(e),
                    'retry_after_seconds': retry_seconds
                }

            logger.error(f"Quiz generation error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to generate quiz',
                'details': str(e)
            }
    
    def generate_flashcards(self, topic: str, num_cards: int = 10, language: str = 'english') -> Dict[str, Any]:
        """
        Generate concise, high-quality flashcards from topic or text content

        Args:
            topic: The topic or text content to generate flashcards from
            num_cards: Number of flashcards to generate (default: 10)
            language: Language for flashcards - 'english' or 'hindi' (default: 'english')

        Returns:
            Dictionary containing flashcard data
        """
        try:
            # Language-specific instruction
            if language.lower() == 'hindi':
                lang_instruction = "in Hindi language (देवनागरी script). All content must be in Hindi."
            else:
                lang_instruction = "in English language"
            
            prompt = f"""You are an AI flashcard generator for an EdTech platform.

Generate {num_cards} concise, high-quality flashcards {lang_instruction} from the following input:

INPUT CONTENT:
{topic}

FLASHCARD RULES (STRICT):
- Each flashcard must test conceptual understanding, not rote memorization
- Question must be clear and exam-oriented
- Answer must be short, precise, and factually correct
- Avoid duplicate or semantically identical questions
- Difficulty should be medium (student-friendly)
- Focus on key concepts, principles, and relationships

Return ONLY valid JSON in this format:
{{
    "title": "Flashcard Set - [Topic Summary]",
    "topic": "{topic[:100]}...",
    "language": "{language.lower()}",
    "total_cards": {num_cards},
    "cards": [
        {{
            "id": 1,
            "question": "Clear, exam-oriented question testing conceptual understanding?",
            "answer": "Short, precise, and factually correct answer.",
            "category": "Key concept or subtopic",
            "difficulty": "medium",
            "importance": "high|medium|low"
        }}
    ]
}}

IMPORTANT:
- Questions should require thinking, not just recall
- Answers should be comprehensive but concise
- Ensure variety in question types and concepts covered
- All flashcards must be unique and non-redundant
- All text must be in {lang_instruction}
"""

            logger.info(f"Generating {num_cards} conceptual flashcards for topic: {topic[:100]}... (language: {language})")
            response = self.model.generate_content(prompt)

            # Extract JSON from response
            response_text = response.text.strip()

            # Try to extract JSON from markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            flashcard_data = json.loads(response_text)

            # Validate and ensure required fields
            if 'cards' not in flashcard_data:
                raise ValueError("Missing 'cards' field in response")

            # Ensure language field is set
            flashcard_data['language'] = language.lower()
            
            # Ensure each card has required fields with defaults
            for i, card in enumerate(flashcard_data['cards']):
                card['id'] = card.get('id', i + 1)
                card['difficulty'] = card.get('difficulty', 'medium')
                card['importance'] = card.get('importance', 'medium')
                if 'category' not in card:
                    card['category'] = 'General'

            logger.info(f"Successfully generated {len(flashcard_data.get('cards', []))} conceptual flashcards")
            return {
                'success': True,
                'flashcards': flashcard_data
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                'success': False,
                'error': 'Failed to parse flashcard data',
                'details': str(e)
            }
        except Exception as e:
            # Handle quota-exceeded specifically
            try:
                from google.api_core.exceptions import ResourceExhausted
            except Exception:
                ResourceExhausted = None

            if ResourceExhausted and isinstance(e, ResourceExhausted):
                import re
                m = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', str(e))
                retry_seconds = int(m.group(1)) if m else None
                logger.warning(f"Quota exceeded for Gemini API (flashcards): retry in {retry_seconds}s")

                return {
                    'success': False,
                    'error': 'quota_exceeded',
                    'details': str(e),
                    'retry_after_seconds': retry_seconds
                }

            # Handle quota-exceeded specifically
            try:
                from google.api_core.exceptions import ResourceExhausted
            except Exception:
                ResourceExhausted = None

            if ResourceExhausted and isinstance(e, ResourceExhausted):
                import re
                m = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', str(e))
                retry_seconds = int(m.group(1)) if m else None
                logger.warning(f"Quota exceeded for Gemini API (flashcards): retry in {retry_seconds}s")
                return {
                    'success': False,
                    'error': 'quota_exceeded',
                    'details': str(e),
                    'retry_after_seconds': retry_seconds
                }

            logger.error(f"Flashcard generation error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to generate flashcards',
                'details': str(e)
            }
    


    def generate_from_document(self, document_text: str, content_type: str = 'quiz', 
                               num_items: int = 5) -> Dict[str, Any]:
        """
        Generate quiz or flashcards from document text
        
        Args:
            document_text: The text content from uploaded document
            content_type: Type of content to generate - 'quiz' or 'flashcards'
            num_items: Number of items to generate
        
        Returns:
            Dictionary containing generated content
        """
        if content_type == 'quiz':
            return self.generate_quiz(document_text, num_questions=num_items)
        else:
            return self.generate_flashcards(document_text, num_cards=num_items)
    
    def generate_study_material(self, document_text: str) -> Dict[str, Any]:
        """
        Generate comprehensive study material from sample paper/document
        
        Extracts:
        1. Important Topics (5-15 points)
        2. Important Concepts (8-20 points)
        3. Study Notes (10-20 bullet points)
        4. Sample Questions (10 descriptive questions)
        
        Args:
            document_text: The text content from uploaded sample paper
        
        Returns:
            Dictionary containing topics, concepts, notes, and questions
        """
        try:
            prompt = f"""You are an expert academic examiner and study material creator.

From the following sample paper/document text, generate comprehensive study material:

1. IMPORTANT TOPICS (5–15 high-level Flash Cards covered)
   - Should be clear subject areas or themes
   - Brief and focused

2. IMPORTANT CONCEPTS (8–20 key definitions or ideas)
   - Fundamental concepts students must understand
   - Core principles and theories

3. STUDY NOTES (10–20 concise bullet points)
   - Exam-focused notes based strictly on the paper
   - Clear, actionable points for revision
   - Include key formulas, definitions, or processes

4. SAMPLE QUESTIONS (10 descriptive/short-answer questions)
   - NO multiple choice questions
   - NO answers provided
   - Useful for revision and practice
   - Cover different difficulty levels

RULES:
- Base content STRICTLY on the provided text
- No hallucinations or extra content
- Be concise and exam-oriented
- Format as valid JSON

Please format the response as a JSON object with this structure:
{{
    "title": "Study Material Title based on content",
    "subject": "Main subject area",
    "topics": [
        "Topic 1",
        "Topic 2"
    ],
    "concepts": [
        {{
            "name": "Concept name",
            "description": "Brief explanation"
        }}
    ],
    "notes": [
        "Study note 1",
        "Study note 2"
    ],
    "questions": [
        {{
            "id": 1,
            "question": "Question text",
            "type": "descriptive"
        }}
    ]
}}

Document Text:
{document_text}
"""
            
            logger.info("Generating study material from document")
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Try to extract JSON from markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            study_material = json.loads(response_text)
            
            logger.info(f"Successfully generated study material with {len(study_material.get('topics', []))} topics")
            return {
                'success': True,
                'study_material': study_material
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                'success': False,
                'error': 'Failed to parse study material data',
                'details': str(e)
            }
        except Exception as e:
            # Handle quota-exceeded specifically
            try:
                from google.api_core.exceptions import ResourceExhausted
            except Exception:
                ResourceExhausted = None

            if ResourceExhausted and isinstance(e, ResourceExhausted):
                import re
                m = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', str(e))
                retry_seconds = int(m.group(1)) if m else None
                logger.warning(f"Quota exceeded for Gemini API (study material): retry in {retry_seconds}s")
                return {
                    'success': False,
                    'error': 'quota_exceeded',
                    'details': str(e),
                    'retry_after_seconds': retry_seconds
                }

            logger.error(f"Study material generation error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to generate study material',
                'details': str(e)
            }
    
    def generate_daily_quiz(self, num_questions: int = 10, language: str = 'english') -> Dict[str, Any]:
        """
        Generate a daily general knowledge quiz with language support
        
        Args:
            num_questions: Number of questions to generate (default: 10)
            language: 'english' or 'hindi' (default: 'english')
        
        Returns:
            Dictionary containing quiz questions with varied categories
        """
        try:
            if language.lower() == 'hindi':
                prompt = f"""आप एक दैनिक सामान्य ज्ञान प्रश्नोत्तरी बनाएं जिसमें {num_questions} बहुविकल्पीय प्रश्न हों। सभी प्रश्न, विकल्प, व्याख्या और मजेदार तथ्य हिंदी भाषा में (देवनागरी लिपि में) हों।

विभिन्न श्रेणियों को कवर करें: विज्ञान, इतिहास, भूगोल, साहित्य, वर्तमान घटनाएं, खेल, प्रौद्योगिकी आदि।

प्रश्न दिलचस्प, शैक्षणिक और सामान्य दर्शकों के लिए उपयुक्त हों। आसान और मध्यम कठिनाई के प्रश्नों को मिलाएं।

कृपया प्रतिक्रिया को निम्नलिखित JSON संरचना में प्रारूपित करें:
{{
    "questions": [
        {{
            "question_text": "प्रश्न का पाठ यहाँ?",
            "options": [
                {{"id": "A", "text": "विकल्प A"}},
                {{"id": "B", "text": "विकल्प B"}},
                {{"id": "C", "text": "विकल्प C"}},
                {{"id": "D", "text": "विकल्प D"}}
            ],
            "correct_answer": "C",
            "category": "विज्ञान",
            "difficulty": "मध्यम",
            "explanation": "व्याख्या हिंदी में",
            "fun_fact": "मजेदार तथ्य हिंदी में"
        }}
    ]
}}

नियम:
- सभी सामग्री हिंदी (देवनागरी) में होनी चाहिए
- प्रश्न स्पष्ट और आकर्षक हों
- विभिन्न श्रेणियों का उपयोग करें
- कठिनाई को मिलाएं (ज्यादातर आसान और मध्यम)
"""
            else:
                prompt = f"""Generate a daily general knowledge quiz with {num_questions} multiple-choice questions covering various categories like Science, History, Geography, Literature, Current Events, Sports, Technology, etc.

Make the questions interesting, educational, and suitable for a general audience. Mix easy and medium difficulty questions.

Please format the response as a valid JSON object with the following structure:
{{
    "questions": [
        {{
            "question_text": "Question text here?",
            "options": [
                {{"id": "A", "text": "Option A text"}},
                {{"id": "B", "text": "Option B text"}},
                {{"id": "C", "text": "Option C text"}},
                {{"id": "D", "text": "Option D text"}}
            ],
            "correct_answer": "C",
            "category": "science",
            "difficulty": "medium",
            "explanation": "Explanation of the correct answer",
            "fun_fact": "An interesting related fact"
        }}
    ]
}}

Rules:
- Make questions clear and engaging
- Use varied categories: science, history, geography, general, current_events, sports, entertainment, technology
- Mix difficulty levels (mostly easy and medium)
- correct_answer should be "A", "B", "C", or "D"
- Include explanations and fun facts
- Ensure JSON is properly formatted
"""
            
            logger.info(f"Generating Daily Quiz with {num_questions} questions")
            response = self.model.generate_content(prompt)
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Try to extract JSON from markdown code blocks if present
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            quiz_data = json.loads(response_text)
            
            logger.info(f"Successfully generated {len(quiz_data.get('questions', []))} Daily Quiz questions")
            return {
                'success': True,
                'questions': quiz_data.get('questions', [])
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text}")
            return {
                'success': False,
                'error': 'Failed to parse Daily Quiz data',
                'details': str(e)
            }
        except Exception as e:
            logger.error(f"Daily Quiz generation error: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Failed to generate Daily Quiz',
                'details': str(e)
            }
    
    def extract_text_from_image(self, image_path: str) -> Dict[str, Any]:
        """
        Extract text from image using Gemini Vision API (no Tesseract needed)
        
        Args:
            image_path: Path to the image file
        
        Returns:
            Dictionary with extracted text or error
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file not found: {image_path}")
                return {
                    'success': False,
                    'error': 'Image file not found',
                    'text': ''
                }
            
            # Read image file and prepare for Gemini Vision API
            import base64
            with open(image_path, 'rb') as img_file:
                image_data = base64.standard_b64encode(img_file.read()).decode('utf-8')
            
            # Determine file extension
            file_ext = os.path.splitext(image_path)[1].lower()
            mime_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp'
            }
            mime_type = mime_type_map.get(file_ext, 'image/jpeg')
            
            logger.info(f"Extracting text from image: {image_path} (mime_type: {mime_type})")
            
            # Use Gemini to extract text from image
            prompt = """Extract ALL text visible in this image. 
Return the text exactly as it appears, preserving formatting where possible.
If no text is found, respond with 'NO_TEXT_FOUND'.
Return ONLY the extracted text, nothing else."""
            
            # Use Gemini Vision with inline image data (no file upload needed)
            image_part = {
                "mime_type": mime_type,
                "data": image_data
            }
            
            try:
                # Generate content with vision using inline image data
                response = self.model.generate_content([prompt, image_part])
                extracted_text = response.text.strip()
                
                if 'NO_TEXT_FOUND' in extracted_text:
                    logger.warning(f"No text found in image: {image_path}")
                    return {
                        'success': False,
                        'error': 'No text found in image',
                        'text': ''
                    }
                
                logger.info(f"Successfully extracted {len(extracted_text)} characters from image")
                return {
                    'success': True,
                    'error': None,
                    'text': extracted_text
                }
            except Exception as vision_error:
                logger.error(f"Vision extraction failed: {vision_error}")
                # Fallback to simpler approach
                logger.info("Trying fallback text extraction method...")
            
        except Exception as e:
            logger.error(f"Text extraction from image failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Failed to extract text from image: {str(e)}',
                'text': ''
            }
    
    def generate_text(self, prompt: str, max_tokens: int = 500) -> Dict[str, Any]:
        """
        Generate plain text response from Gemini API
        Used for Ask a Question feature and general text generation
        
        Args:
            prompt: The prompt to send to Gemini
            max_tokens: Maximum tokens in response (default: 500)
        
        Returns:
            Dictionary with success status, generated text, and metadata
        """
        try:
            if not self.model:
                return {
                    'success': False,
                    'error': 'Gemini model not initialized',
                    'text': ''
                }
            
            logger.info(f"Generating text with prompt length: {len(prompt)}")
            
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.7,
                    top_p=0.9,
                    top_k=40,
                ),
                safety_settings=[
                    {
                        "category": genai.types.HarmCategory.HARM_CATEGORY_UNSPECIFIED,
                        "threshold": genai.types.HarmBlockThreshold.BLOCK_NONE,
                    },
                ]
            )
            
            if response and hasattr(response, 'text'):
                text = response.text.strip()
                logger.info(f"Text generation successful, length: {len(text)}")
                
                return {
                    'success': True,
                    'text': text,
                    'tokens_used': len(text.split()),
                    'model': 'gemini-2.0-flash'
                }
            else:
                logger.warning("Empty response from Gemini")
                return {
                    'success': False,
                    'error': 'Empty response from model',
                    'text': ''
                }
        
        except Exception as e:
            logger.error(f"Text generation error: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to generate text: {str(e)}',
                'text': ''
            }


# Initialize singleton instance
gemini_service = GeminiService()
