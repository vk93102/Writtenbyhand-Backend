"""
Quiz Service - Generates questions and summaries from transcripts using Gemini AI
"""

import os
import json
import logging
from typing import Dict, List, Any
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


class QuizService:
    """Generate quiz questions and summaries from content using Gemini AI"""
    
    MODEL_NAME = "gemini-2.5-flash"
    
    def generate_quiz_from_transcript(
        self,
        transcript: str,
        title: str = "Quiz",
        num_questions: int = 5,
        difficulty: str = "intermediate"
    ) -> Dict[str, Any]:
        """
        Generate a complete quiz from transcript with various question types
        
        Args:
            transcript: Full transcript text
            title: Quiz title
            num_questions: Number of questions to generate (5-15)
            difficulty: 'beginner', 'intermediate', or 'advanced'
        
        Returns:
            Dict with quiz data including questions, summary, metadata
        """
        try:
            if not GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY not configured")
                return {"error": "API key not configured"}
            
            # Truncate transcript if too long
            max_chars = 10000
            if len(transcript) > max_chars:
                transcript = transcript[:max_chars] + "..."
            
            num_questions = min(max(5, num_questions), 15)  # Ensure 5-15 range
            
            prompt = f"""You are an expert educator creating a comprehensive quiz from content.

TRANSCRIPT/CONTENT:
{transcript}

REQUIREMENTS:
1. Generate exactly {num_questions} diverse quiz questions
2. Question difficulty level: {difficulty}
3. Include variety of question types:
   - Multiple Choice (MCQ) - 40%
   - True/False - 30%
   - Short Answer - 30%

OUTPUT FORMAT (STRICT JSON):
{{
  "title": "{title}",
  "summary": "2-3 sentence summary of key points",
  "main_topics": ["topic1", "topic2", "topic3"],
  "learning_objectives": ["Understand...", "Identify...", "Explain..."],
  "estimated_time_minutes": {num_questions},
  "difficulty_level": "{difficulty}",
  "questions": [
    {{
      "id": 1,
      "type": "mcq",
      "question": "Question text?",
      "options": [
        {{"text": "Option A", "is_correct": false}},
        {{"text": "Option B", "is_correct": true}},
        {{"text": "Option C", "is_correct": false}},
        {{"text": "Option D", "is_correct": false}}
      ],
      "explanation": "Why B is correct...",
      "hint": "Consider...",
      "difficulty": "intermediate"
    }},
    {{
      "id": 2,
      "type": "true_false",
      "question": "Statement here?",
      "correct_answer": true,
      "explanation": "This is true because...",
      "hint": "Think about...",
      "difficulty": "beginner"
    }},
    {{
      "id": 3,
      "type": "short_answer",
      "question": "What is...?",
      "correct_answer": "Expected answer (10-50 words)",
      "explanation": "The correct answer demonstrates...",
      "hint": "Look for keywords like...",
      "difficulty": "intermediate"
    }}
  ],
  "keywords": ["word1", "word2", "word3"]
}}

QUALITY RULES:
- Questions should test understanding, not just memorization
- For MCQ: Make distractors plausible but clearly wrong
- Provide clear explanations for each answer
- Include helpful hints without revealing answers
- Ensure difficulty matches specified level
- All questions must be answerable from the transcript

IMPORTANT: Return ONLY valid JSON, no markdown, no code blocks, no explanations."""

            # Call Gemini API
            model = genai.GenerativeModel(self.MODEL_NAME)
            response = model.generate_content(prompt)
            
            if not response.text:
                logger.error("Empty response from Gemini API")
                return {"error": "Failed to generate quiz"}
            
            # Parse JSON response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            quiz_data = json.loads(response_text)
            
            # Validate structure
            if 'questions' not in quiz_data or not quiz_data['questions']:
                logger.error("Invalid quiz data structure")
                return {"error": "Invalid quiz structure generated"}
            
            return quiz_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {"error": f"Failed to parse quiz data: {str(e)}"}
        except Exception as e:
            logger.error(f"Error generating quiz: {e}")
            return {"error": f"Failed to generate quiz: {str(e)}"}
    
    def generate_quiz_summary_from_responses(
        self,
        quiz_title: str,
        responses: Dict[str, Any],
        questions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate detailed summary and feedback from quiz responses
        
        Args:
            quiz_title: Title of quiz
            responses: Dict of {question_id: {"user_answer": "...", "is_correct": bool}}
            questions: List of question objects
        
        Returns:
            Dict with detailed performance analysis and recommendations
        """
        try:
            if not GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY not configured")
                return {"error": "API key not configured"}
            
            # Calculate basic stats
            correct_count = sum(1 for r in responses.values() if r.get('is_correct'))
            total_questions = len(responses)
            score_percentage = (correct_count / total_questions * 100) if total_questions > 0 else 0
            
            # Identify weak areas
            wrong_questions = [
                q for q in questions 
                if responses.get(str(q.get('id', '')), {}).get('is_correct') == False
            ]
            
            # Build context for analysis
            questions_context = json.dumps(questions[:5], indent=2)  # Limit for token usage
            wrong_context = json.dumps(wrong_questions[:3], indent=2) if wrong_questions else "None"
            
            prompt = f"""You are an expert educational analyst providing detailed quiz feedback.

QUIZ DETAILS:
- Title: {quiz_title}
- Score: {score_percentage:.1f}% ({correct_count}/{total_questions})
- Topics Covered: [Based on questions provided]

SAMPLE QUESTIONS:
{questions_context}

INCORRECT RESPONSES:
{wrong_context}

Generate detailed analysis in JSON format:
{{
  "overall_feedback": "Encouraging but honest feedback about performance",
  "score_interpretation": "What this score means",
  "strengths": [
    "Area of strength demonstrated",
    "Another strength"
  ],
  "areas_for_improvement": [
    "Topic needing focus",
    "Concept to review"
  ],
  "topic_performance": {{
    "topic1": "70%",
    "topic2": "100%",
    "topic3": "40%"
  }},
  "study_recommendations": [
    "Specific action to improve",
    "Resource or method to try",
    "Concept to revisit"
  ],
  "next_steps": [
    "Take more advanced quiz on weak areas",
    "Study specific chapters",
    "Practice similar problems"
  ],
  "motivational_message": "Encouraging note about learning journey"
}}

Provide constructive, motivating feedback appropriate for a learner."""

            model = genai.GenerativeModel(self.MODEL_NAME)
            response = model.generate_content(prompt)
            
            if not response.text:
                logger.error("Empty response from Gemini API for summary")
                return {
                    "overall_feedback": f"You scored {score_percentage:.1f}% on this quiz.",
                    "score_interpretation": "Good effort! Keep practicing.",
                    "strengths": ["Completed the quiz"],
                    "areas_for_improvement": ["Review incorrect answers"],
                    "study_recommendations": ["Practice similar questions"],
                    "next_steps": ["Take another quiz"],
                    "motivational_message": "Keep learning!"
                }
            
            # Parse response
            response_text = response.text.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
            
            analysis = json.loads(response_text)
            analysis['score'] = score_percentage
            analysis['correct_answers'] = correct_count
            analysis['total_questions'] = total_questions
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in summary: {e}")
            return {
                "overall_feedback": "Quiz completed. Review your responses for improvement.",
                "score": score_percentage,
                "correct_answers": correct_count,
                "total_questions": total_questions
            }
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {
                "overall_feedback": "Quiz completed successfully.",
                "score": score_percentage,
                "correct_answers": correct_count,
                "total_questions": total_questions
            }
    
    def extract_key_concepts(self, transcript: str, num_concepts: int = 10) -> List[str]:
        """
        Extract key concepts and topics from transcript
        """
        try:
            if not GEMINI_API_KEY or len(transcript) < 100:
                return []
            
            transcript = transcript[:5000]  # Limit size
            
            prompt = f"""Extract exactly {num_concepts} key concepts/topics from this text. 
            Return as JSON array of strings, no other text.
            [{{"concept1", "concept2", ...}}]
            
TEXT:
{transcript}"""

            model = genai.GenerativeModel(self.MODEL_NAME)
            response = model.generate_content(prompt)
            
            if response.text:
                response_text = response.text.strip()
                if response_text.startswith('['):
                    concepts = json.loads(response_text)
                    return concepts[:num_concepts]
            
            return []
            
        except Exception as e:
            logger.error(f"Error extracting concepts: {e}")
            return []


# Create singleton instance
quiz_service = QuizService()
