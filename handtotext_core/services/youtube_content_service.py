"""
YouTube Service - Searches for educational concept videos
"""

import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class YouTubeService:
    def __init__(self):
        self.api_key = settings.YOUTUBE_API_KEY
        self.base_url = "https://www.googleapis.com/youtube/v3/search"
    
    def search_concept_videos(self, query, max_results=3):
        """
        Search for concept explanation videos on YouTube

        Args:
            query: Search query (concept/topic)
            max_results: Number of videos to return

        Returns:
            dict: {
                'success': boolean,
                'videos': list of video objects
            }
        """
        if not self.api_key:
            logger.error("YouTube API key not configured")
            return {
                'success': False,
                'error': 'YouTube API key not configured',
                'videos': []
            }

        try:
            # Enhance query for educational content
            enhanced_query = f"{query} tutorial explanation"

            params = {
                'part': 'snippet',
                'q': enhanced_query,
                'type': 'video',
                'maxResults': max_results,
                'key': self.api_key,
                'relevanceLanguage': 'en',
                'safeSearch': 'strict',
                'videoEmbeddable': 'true',
                'order': 'relevance'
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            videos = []
            if 'items' in data:
                for item in data['items']:
                    video = self._parse_video_item(item)
                    if video:
                        videos.append(video)

            return {
                'success': True,
                'videos': videos,
                'query': query,
                'count': len(videos)
            }

        except Exception as e:
            logger.error(f"YouTube search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'videos': []
            }
    
    def _parse_video_item(self, item):
        """
        Parse YouTube API video item
        """
        try:
            snippet = item.get('snippet', {})
            video_id = item.get('id', {}).get('videoId')
            
            if not video_id:
                return None
            
            return {
                'video_id': video_id,
                'title': snippet.get('title', ''),
                'description': snippet.get('description', ''),
                'thumbnail': snippet.get('thumbnails', {}).get('medium', {}).get('url', ''),
                'channel_title': snippet.get('channelTitle', ''),
                'published_at': snippet.get('publishedAt', ''),
                'url': f"https://www.youtube.com/watch?v={video_id}",
                'embed_url': f"https://www.youtube.com/embed/{video_id}"
            }
            
        except Exception as e:
            logger.error(f"Error parsing video item: {e}")
            return None
    
    def get_video_details(self, video_id):
        """
        Get detailed information about a specific video
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            dict: Video details including statistics
        """
        if not self.api_key:
            return None
        
        try:
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                'part': 'snippet,statistics,contentDetails',
                'id': video_id,
                'key': self.api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'items' in data and data['items']:
                item = data['items'][0]
                snippet = item.get('snippet', {})
                statistics = item.get('statistics', {})
                
                return {
                    'title': snippet.get('title', ''),
                    'description': snippet.get('description', ''),
                    'channel': snippet.get('channelTitle', ''),
                    'views': statistics.get('viewCount', '0'),
                    'likes': statistics.get('likeCount', '0'),
                    'duration': item.get('contentDetails', {}).get('duration', '')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting video details: {e}")
            return None
    
    def search_by_topic(self, topic, subject='general', max_results=3):
        """
        Search videos by educational topic with subject filter
        
        Args:
            topic: Educational topic
            subject: Subject area (math, physics, chemistry, etc.)
            max_results: Number of results
            
        Returns:
            dict: Search results
        """
        # Enhance query based on subject
        subject_keywords = {
            'math': 'mathematics explained',
            'physics': 'physics concept',
            'chemistry': 'chemistry tutorial',
            'biology': 'biology explanation',
            'general': 'educational tutorial'
        }
        
        keyword = subject_keywords.get(subject.lower(), 'tutorial')
        enhanced_query = f"{topic} {keyword}"
        
        return self.search_concept_videos(enhanced_query, max_results)


# Global instance
youtube_service = YouTubeService()
