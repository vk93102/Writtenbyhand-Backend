from django.conf import settings
import logging
import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

logger = logging.getLogger(__name__)


class YouTubeService:
    """
    Service class for YouTube API interactions
    """
    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY
        self.base_url = 'https://www.googleapis.com/youtube/v3'
    
    def get_video_details(self, video_id):
        """
        Fetch video details from YouTube API
        """
        try:
            if not self.api_key:
                logger.warning("YouTube API key not configured")
                return None
            
            url = f"{self.base_url}/videos"
            params = {
                'part': 'snippet,contentDetails,statistics',
                'id': video_id,
                'key': self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('items'):
                return data['items'][0]
            return None
        except Exception as e:
            logger.error(f"Error fetching video details: {str(e)}")
            return None
    
    def get_channel_info(self, channel_id):
        """
        Fetch channel information from YouTube API
        """
        try:
            if not self.api_key:
                logger.warning("YouTube API key not configured")
                return None
            
            url = f"{self.base_url}/channels"
            params = {
                'part': 'snippet,statistics',
                'id': channel_id,
                'key': self.api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get('items'):
                return data['items'][0]
            return None
        except Exception as e:
            logger.error(f"Error fetching channel info: {str(e)}")
            return None
    
    def extract_video_id(self, url):
        try:
            if 'youtu.be/' in url:
                return url.split('youtu.be/')[1].split('?')[0]
            elif 'youtube.com/watch?v=' in url:
                return url.split('watch?v=')[1].split('&')[0]
            elif 'youtube.com/embed/' in url:
                return url.split('embed/')[1].split('?')[0]
            return None
        except Exception as e:
            logger.error(f"Error extracting video ID: {str(e)}")
            return None

    def get_transcript(self, video_id):
        try:
            logger.info(f"Fetching transcript for video ID: {video_id}")
            
            # Create API instance
            api = YouTubeTranscriptApi()
            
            # Try to fetch transcript (preferring English)
            try:
                transcript_data = api.fetch(video_id)
                logger.info(f"Successfully fetched transcript for {video_id}")
                # Convert to dict format
                transcript = [{'text': item.text, 'start': item.start, 'duration': item.duration} 
                             for item in transcript_data]
                return {
                    'success': True,
                    'transcript': transcript,
                    'language': 'en'
                }
            except NoTranscriptFound:
                # If English transcript not found, try to list available ones
                logger.warning(f"English transcript not found for {video_id}, trying other languages")
                try:
                    transcript_list = api.list(video_id)
                    
                    # Try to find Hindi transcript first
                    transcripts_to_try = [
                        ('hi', 'Hindi'),
                        ('en', 'English'),
                        ('es', 'Spanish'),
                        ('fr', 'French'),
                    ]
                    
                    found_transcript = None
                    found_lang = None
                    found_lang_name = None
                    
                    for lang_code, lang_name in transcripts_to_try:
                        try:
                            found_transcript = transcript_list.find_generated_transcript([lang_code])
                            found_lang = lang_code
                            found_lang_name = lang_name
                            logger.info(f"Found auto-generated {lang_name} ({lang_code}) transcript")
                            break
                        except:
                            try:
                                found_transcript = transcript_list.find_manually_created_transcript([lang_code])
                                found_lang = lang_code
                                found_lang_name = lang_name
                                logger.info(f"Found manually created {lang_name} ({lang_code}) transcript")
                                break
                            except:
                                continue
                    
                    if found_transcript:
                        transcript_data = found_transcript.fetch()
                        transcript = [{'text': item.text, 'start': item.start, 'duration': item.duration} 
                                     for item in transcript_data]
                        logger.info(f"Fetched {found_lang_name} transcript with {len(transcript)} segments")
                        return {
                            'success': True,
                            'transcript': transcript,
                            'language': found_lang
                        }
                    else:
                        raise Exception("No suitable transcript found")
                        
                except Exception as e:
                    logger.error(f"No transcripts available for {video_id}: {str(e)}")
                    return {
                        'success': False,
                        'error': 'No transcripts available for this video',
                        'details': 'The video does not have captions/subtitles enabled or they are disabled'
                    }
            
        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}")
            return {
                'success': False,
                'error': 'Transcripts disabled',
                'details': 'This video has transcripts disabled'
            }
        except Exception as e:
            logger.error(f"Error fetching transcript: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to fetch transcript',
                'details': str(e)
            }

    def summarize_transcript(self, transcript_list):
        """
        Summarize transcript using Gemini AI with timestamps and deep analysis
        """
        try:
            import sys
            import os
            from question_solver.services.gemini_service import gemini_service
            import datetime
            
            # Build transcript with timestamps
            transcript_with_timestamps = []
            for item in transcript_list:
                start_time = item.get('start', 0)
                minutes = int(start_time) // 60
                seconds = int(start_time) % 60
                timestamp = f"[{minutes:02d}:{seconds:02d}]"
                transcript_with_timestamps.append(f"{timestamp} {item['text']}")
            
            # Combine all transcript text
            full_text = ' '.join([item['text'] for item in transcript_list])
            full_text_with_ts = '\n'.join(transcript_with_timestamps)
            
            # Calculate total duration
            total_duration = transcript_list[-1].get('start', 0) + transcript_list[-1].get('duration', 0) if transcript_list else 0
            duration_minutes = int(total_duration) // 60
            duration_seconds = int(total_duration) % 60
            
            # Check if text is too long (Gemini has token limits)
            if len(full_text) > 50000:
                logger.warning("Transcript is very long, truncating to 50000 characters")
                full_text = full_text[:50000]
                # Also truncate the timestamped version
                full_text_with_ts = '\n'.join(transcript_with_timestamps[:min(500, len(transcript_with_timestamps))])
            
            logger.info(f"Summarizing {len(full_text)} characters of transcript with {len(transcript_list)} segments")
            
            # Use Gemini to summarize - create a detailed prompt for comprehensive analysis
            prompt = f"""Please provide an EXTREMELY DETAILED and COMPREHENSIVE summary of the following YouTube video transcript.

IMPORTANT: Include timestamps [MM:SS] for all key points, moments, and sections discussed.

Video Metadata:
- Total Duration: {duration_minutes:02d}:{duration_seconds:02d} minutes
- Total Segments: {len(transcript_list)} segments
- Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

The summary should include:

1. **EXECUTIVE SUMMARY** (2-3 sentences)
   - What is the video fundamentally about?
   - Main message and purpose

2. **VIDEO TIMELINE & KEY SECTIONS WITH TIMESTAMPS**
   - For each major topic/section, provide:
     - Exact timestamp [MM:SS] when section starts
     - What is being discussed
     - Key points and important details
     - Speaker's emphasis and tone
     - Duration of each section

3. **MAIN TOPIC AND CORE MESSAGE**
   - Primary subject matter
   - Central thesis or argument
   - Overall narrative flow

4. **DETAILED KEY POINTS** (Numbered, with timestamps)
   - Each point with its timestamp
   - Explanation of importance
   - Related context

5. **IMPORTANT CONCEPTS & DEFINITIONS** (with timestamps)
   - Each concept explained
   - Why it matters
   - Examples provided in the video

6. **STATISTICS, DATA & NUMBERS** (with timestamps)
   - All quantifiable information
   - Percentages, metrics, values
   - Sources mentioned

7. **QUOTES & NOTABLE STATEMENTS** (with exact timestamps)
   - Important quotes
   - Key statements or declarations
   - Speaker's emphasis

8. **VISUAL DESCRIPTIONS** (if mentioned with timestamps)
   - What was shown on screen
   - Visual aids or demonstrations
   - Graphics or charts mentioned

9. **TARGET AUDIENCE**
   - Who is this video for?
   - Required background knowledge
   - Difficulty level

10. **KEY TAKEAWAYS** (5-10 main learnings)
    - What viewers should remember
    - Practical applications
    - Action items if any

11. **CHAPTER BREAKDOWN** (If applicable)
    - Introduction [00:00]
    - Body sections [MM:SS - MM:SS]
    - Conclusion [MM:SS]

12. **OVERALL ASSESSMENT**
    - Quality of content
    - Credibility and accuracy
    - Engagement level
    - Educational value
    - Entertainment value
    - Recommendations

13. **VIEWER QUESTIONS ANSWERED**
    - Common questions about the topic
    - Answers from the video

14. **RELATED TOPICS & SUGGESTIONS**
    - Topics mentioned but not deeply explored
    - Suggestions for further learning

FORMAT:
- Use clear markdown headers
- Use timestamps for all references
- Use bullet points for listelists
- Use numbered lists for sequential information
- Bold important terms and concepts
- Include time references for everything possible

TRANSCRIPT WITH TIMESTAMPS:
{full_text_with_ts}

Please analyze this comprehensively and provide a detailed, well-structured summary with timestamps for every key point."""
            
            try:
                # Try using Gemini API directly
                import google.generativeai as genai
                genai.configure(api_key=os.getenv('GEMINI_API_KEY', ''))
                model = genai.GenerativeModel('gemini-2.0-flash')
                response = model.generate_content(prompt)
                
                summary = response.text if response and hasattr(response, 'text') else str(response)
                
                return {
                    'success': True,
                    'summary': summary,
                    'summary_type': 'gemini_ai'
                }
            except Exception as gemini_err:
                logger.warning(f"Gemini direct call failed: {str(gemini_err)}, using fallback")
                return self._simple_summarize(transcript_list)
                
        except ImportError as ie:
            logger.warning(f"Import error: {str(ie)}, using simple summarization")
            return self._simple_summarize(transcript_list)
        except Exception as e:
            logger.error(f"Error summarizing transcript: {str(e)}")
            return self._simple_summarize(transcript_list)

    def _simple_summarize(self, transcript_list):
        """
        Simple fallback summarization based on extracting key sentences
        """
        try:
            # Get first 5 and last 5 lines as a simple summary
            if len(transcript_list) <= 10:
                summary_items = transcript_list
            else:
                summary_items = transcript_list[:5] + transcript_list[-5:]
            
            summary = ' '.join([item['text'] for item in summary_items])
            
            return {
                'success': True,
                'summary': summary,
                'summary_type': 'simple_extraction',
                'note': 'This is a simple summary. For better results, enable Gemini service.'
            }
        except Exception as e:
            logger.error(f"Error in simple summarization: {str(e)}")
            return {
                'success': False,
                'error': 'Failed to create summary',
                'details': str(e)
            }
