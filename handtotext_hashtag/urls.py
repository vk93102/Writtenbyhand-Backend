"""
URL configuration for youtube_summarizer app
"""
from django.urls import path
from .views import (
    YouTubeSummarizerView,
    VideoDetailsView,
    ChannelInfoView,
)

app_name = 'youtube_summarizer'

urlpatterns = [
    path('summarize/', YouTubeSummarizerView.as_view(), name='summarize'),
    path('video-details/', VideoDetailsView.as_view(), name='video-details'),
    path('channel-info/', ChannelInfoView.as_view(), name='channel-info'),
]
