from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import logging
from .youtube_service import YouTubeService

logger = logging.getLogger(__name__)
youtube_service = YouTubeService()


class YouTubeSummarizerView(APIView):
    """
    API view to summarize YouTube videos
    Extracts transcript and generates AI summary
    """
    def post(self, request):
        try:
            video_url = request.data.get('video_url')
            if not video_url:
                return Response(
                    {'error': 'video_url is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Processing YouTube video: {video_url}")
            
            # Extract video ID from URL
            video_id = youtube_service.extract_video_id(video_url)
            if not video_id:
                return Response(
                    {
                        'error': 'Invalid YouTube URL format',
                        'details': 'Please provide a valid YouTube URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID)'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Extracted video ID: {video_id}")
            
            # Fetch transcript
            transcript_result = youtube_service.get_transcript(video_id)
            if not transcript_result.get('success'):
                logger.error(f"Failed to get transcript: {transcript_result.get('error')}")
                return Response(
                    {
                        'success': False,
                        'error': transcript_result.get('error'),
                        'details': transcript_result.get('details')
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            transcript = transcript_result.get('transcript')
            language = transcript_result.get('language', 'unknown')
            
            logger.info(f"Successfully fetched transcript ({language}) with {len(transcript)} segments")
            
            # Summarize transcript
            summary_result = youtube_service.summarize_transcript(transcript)
            if not summary_result.get('success'):
                logger.error(f"Failed to summarize transcript: {summary_result.get('error')}")
                return Response(
                    {
                        'success': False,
                        'error': summary_result.get('error'),
                        'details': summary_result.get('details')
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            summary = summary_result.get('summary')
            summary_type = summary_result.get('summary_type')
            
            logger.info(f"Successfully summarized transcript using {summary_type}")
            
            # Get video details if available
            video_details = youtube_service.get_video_details(video_id)
            if video_details:
                video_title = video_details.get('snippet', {}).get('title', 'Unknown Title')
                video_channel = video_details.get('snippet', {}).get('channelTitle', 'Unknown Channel')
            else:
                video_title = 'Unknown Title'
                video_channel = 'Unknown Channel'
            
            return Response({
                'success': True,
                'video_url': video_url,
                'video_id': video_id,
                'video_title': video_title,
                'channel': video_channel,
                'transcript': {
                    'language': language,
                    'segments_count': len(transcript),
                    'duration_text': f"{len(transcript)} text segments"
                },
                'summary': summary,
                'summary_type': summary_type,
                'message': 'Video successfully summarized'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in YouTubeSummarizerView: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VideoDetailsView(APIView):
    """
    API view to get YouTube video details
    """
    def get(self, request):
        try:
            video_id = request.query_params.get('video_id')
            video_url = request.query_params.get('video_url')
            
            # Extract video_id from URL if provided
            if video_url and not video_id:
                video_id = youtube_service.extract_video_id(video_url)
            
            if not video_id:
                return Response(
                    {
                        'error': 'video_id or video_url is required',
                        'details': 'Provide either video_id or a valid YouTube URL'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Fetching video details for: {video_id}")
            
            video_details = youtube_service.get_video_details(video_id)
            if not video_details:
                return Response(
                    {
                        'error': 'Video not found',
                        'details': 'Could not fetch details for this video'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Extract relevant information
            snippet = video_details.get('snippet', {})
            stats = video_details.get('statistics', {})
            
            return Response({
                'success': True,
                'video_id': video_id,
                'title': snippet.get('title'),
                'description': snippet.get('description'),
                'channel': snippet.get('channelTitle'),
                'published_at': snippet.get('publishedAt'),
                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url'),
                'statistics': {
                    'view_count': stats.get('viewCount', 0),
                    'like_count': stats.get('likeCount', 0),
                    'comment_count': stats.get('commentCount', 0)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in VideoDetailsView: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChannelInfoView(APIView):
    """
    API view to get YouTube channel information
    """
    def get(self, request):
        try:
            channel_id = request.query_params.get('channel_id')
            if not channel_id:
                return Response(
                    {'error': 'channel_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logger.info(f"Fetching channel info for: {channel_id}")
            
            channel_info = youtube_service.get_channel_info(channel_id)
            if not channel_info:
                return Response(
                    {
                        'error': 'Channel not found',
                        'details': 'Could not fetch information for this channel'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Extract relevant information
            snippet = channel_info.get('snippet', {})
            stats = channel_info.get('statistics', {})
            
            return Response({
                'success': True,
                'channel_id': channel_id,
                'title': snippet.get('title'),
                'description': snippet.get('description'),
                'published_at': snippet.get('publishedAt'),
                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url'),
                'statistics': {
                    'subscriber_count': stats.get('subscriberCount', 'hidden'),
                    'view_count': stats.get('viewCount', 0),
                    'video_count': stats.get('videoCount', 0)
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in ChannelInfoView: {str(e)}", exc_info=True)
            return Response(
                {
                    'error': 'Internal server error',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
