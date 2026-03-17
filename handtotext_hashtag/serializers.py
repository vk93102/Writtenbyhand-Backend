from rest_framework import serializers


class VideoSummarySerializer(serializers.Serializer):
	"""
	Serializer for YouTube video summary requests
	"""

	video_url = serializers.URLField(required=True)
	include_transcript = serializers.BooleanField(default=True)
	summary_length = serializers.ChoiceField(
		choices=["short", "medium", "long"],
		default="medium",
	)


class VideoDetailsSerializer(serializers.Serializer):
	"""
	Serializer for YouTube video details
	"""

	video_id = serializers.CharField(required=True)
	title = serializers.CharField(read_only=True)
	description = serializers.CharField(read_only=True)
	channel_title = serializers.CharField(read_only=True)
	published_at = serializers.DateTimeField(read_only=True)
	view_count = serializers.IntegerField(read_only=True)
	like_count = serializers.IntegerField(read_only=True)
	duration = serializers.CharField(read_only=True)


class ChannelInfoSerializer(serializers.Serializer):
	"""
	Serializer for YouTube channel information
	"""

	channel_id = serializers.CharField(required=True)
	title = serializers.CharField(read_only=True)
	description = serializers.CharField(read_only=True)
	subscriber_count = serializers.IntegerField(read_only=True)
	video_count = serializers.IntegerField(read_only=True)
	view_count = serializers.IntegerField(read_only=True)