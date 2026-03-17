from django.apps import AppConfig


class YoutubeSummarizerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'youtube_summarizer'
    verbose_name = 'YouTube Summarizer'

    def ready(self):
        """Import signal handlers when app is ready"""
        pass
