"""
Ads System Models for EdTech Platform
Handles ad impressions, tracking, and user ad preferences
"""
from django.db import models
from django.utils import timezone
import uuid
from datetime import timedelta


class AdCampaign(models.Model):
    """Ad campaigns and configurations"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Campaign config
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Unity Ads specific
    unity_game_id = models.CharField(max_length=255, help_text="iOS Game ID")
    unity_placement_id = models.CharField(max_length=255, help_text="Unity Placement ID")
    ad_type = models.CharField(
        max_length=20,
        choices=[
            ('interstitial', 'Interstitial'),
            ('rewarded', 'Rewarded Video'),
            ('banner', 'Banner'),
        ],
        default='interstitial'
    )
    
    # Frequency capping
    max_ads_per_day = models.IntegerField(default=5, help_text="Max ads shown per user per day")
    min_gap_between_ads = models.IntegerField(default=300, help_text="Minimum gap in seconds between ads")
    
    # Dates
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.ad_type})"


class AdImpression(models.Model):
    """Track each ad impression (when an ad is shown to a user)"""
    IMPRESSION_STATUS = [
        ('shown', 'Shown'),
        ('clicked', 'Clicked'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
        ('failed', 'Failed to Load'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # User & Campaign
    user_id = models.CharField(max_length=255, db_index=True)
    campaign = models.ForeignKey(AdCampaign, on_delete=models.CASCADE, related_name='impressions')
    
    # Device info
    device_id = models.CharField(max_length=255, blank=True)
    platform = models.CharField(
        max_length=20,
        choices=[('ios', 'iOS'), ('android', 'Android')],
        default='android'
    )
    app_version = models.CharField(max_length=50, blank=True)
    
    # Ad details
    status = models.CharField(max_length=20, choices=IMPRESSION_STATUS, default='shown')
    feature_used = models.CharField(
        max_length=50,
        choices=[
            ('quiz', 'Quiz'),
            ('daily_quiz', 'Daily Quiz'),
            ('mock_test', 'Mock Test'),
            ('ask_question', 'Ask Question'),
            ('flashcards', 'Flashcards'),
            ('pyq', 'Previous Year Questions'),
            ('youtube_summarizer', 'YouTube Summarizer'),
            ('pair_quiz', 'Pair Quiz'),
            ('predicted_questions', 'Predicted Questions'),
        ],
        help_text="Feature after which ad was shown"
    )
    
    # Timing
    shown_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True, help_text="Duration watched for rewarded ads")
    
    # Metadata
    is_rewarded_completed = models.BooleanField(default=False)
    reward_claimed = models.BooleanField(default=False)
    reward_amount = models.IntegerField(default=0, help_text="Coins/reward earned")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-shown_at']
        indexes = [
            models.Index(fields=['user_id', 'shown_at']),
            models.Index(fields=['status']),
            models.Index(fields=['platform']),
        ]
    
    def __str__(self):
        return f"Ad {self.id} - {self.user_id} ({self.status})"


class AdSchedule(models.Model):
    """Configure when/after which features to show ads"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(AdCampaign, on_delete=models.CASCADE, related_name='schedules')
    
    # Feature & timing
    feature = models.CharField(
        max_length=50,
        choices=[
            ('quiz', 'Quiz'),
            ('daily_quiz', 'Daily Quiz'),
            ('mock_test', 'Mock Test'),
            ('ask_question', 'Ask Question'),
            ('flashcards', 'Flashcards'),
            ('pyq', 'Previous Year Questions'),
            ('youtube_summarizer', 'YouTube Summarizer'),
            ('pair_quiz', 'Pair Quiz'),
            ('predicted_questions', 'Predicted Questions'),
        ]
    )
    
    # Trigger configuration
    show_after_feature_completion = models.BooleanField(
        default=True,
        help_text="Show ad after user completes this feature"
    )
    delay_seconds = models.IntegerField(
        default=0,
        help_text="Delay before showing ad (seconds)"
    )
    probability = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.0,
        help_text="Probability to show ad (0.0 to 1.0)"
    )
    
    # Targeting
    target_free_users_only = models.BooleanField(
        default=True,
        help_text="Only show ads to free users (not premium subscribers)"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['feature']
        unique_together = ('campaign', 'feature')
        indexes = [
            models.Index(fields=['feature']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.campaign.name} - After {self.feature}"


class UserAdPreference(models.Model):
    """Store user's ad preferences and viewing history"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Ad preferences
    ads_enabled = models.BooleanField(default=True)
    ads_opted_in = models.BooleanField(default=True)
    
    # Frequency tracking (daily)
    ads_shown_today = models.IntegerField(default=0)
    last_ad_shown_at = models.DateTimeField(null=True, blank=True)
    ads_shown_last_reset = models.DateTimeField(auto_now_add=True)
    
    # Frequency tracking (all-time)
    total_ads_shown = models.IntegerField(default=0)
    total_ads_completed = models.IntegerField(default=0)
    total_rewards_earned = models.IntegerField(default=0)
    
    # Blocked ads
    blocked_campaign_ids = models.JSONField(default=list, help_text="List of campaign IDs to not show")
    
    # User status
    is_premium = models.BooleanField(default=False)
    last_subscription_check = models.DateTimeField(auto_now_add=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['is_premium']),
        ]
    
    def __str__(self):
        return f"Ad Preference - {self.user_id}"
    
    def reset_daily_ad_count(self):
        """Reset daily ad count at midnight"""
        now = timezone.now()
        if (now - self.ads_shown_last_reset).days >= 1:
            self.ads_shown_today = 0
            self.ads_shown_last_reset = now
            self.save()
    
    def can_show_ad(self, campaign, max_ads_per_day):
        """Check if ad can be shown based on frequency caps"""
        self.reset_daily_ad_count()
        
        # Check if ads are enabled for this user
        if not self.ads_enabled or not self.ads_opted_in:
            return False
        
        # Premium users don't see ads
        if self.is_premium:
            return False
        
        # Check if campaign is blocked
        if str(campaign.id) in self.blocked_campaign_ids:
            return False
        
        # Check daily limit
        if self.ads_shown_today >= max_ads_per_day:
            return False
        
        # Check time gap between ads
        if self.last_ad_shown_at:
            time_gap = (timezone.now() - self.last_ad_shown_at).total_seconds()
            if time_gap < campaign.min_gap_between_ads:
                return False
        
        return True
    
    def record_ad_shown(self):
        """Record that an ad was shown to this user"""
        self.ads_shown_today += 1
        self.total_ads_shown += 1
        self.last_ad_shown_at = timezone.now()
        self.save()
    
    def record_ad_completed(self, reward_amount=0):
        """Record completed ad view and rewards"""
        self.total_ads_completed += 1
        self.total_rewards_earned += reward_amount
        self.save()


class AdAnalytics(models.Model):
    """Aggregated analytics for ad campaigns"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.OneToOneField(AdCampaign, on_delete=models.CASCADE, related_name='analytics')
    
    # Metrics
    total_impressions = models.IntegerField(default=0)
    total_clicks = models.IntegerField(default=0)
    total_completed = models.IntegerField(default=0)
    total_skipped = models.IntegerField(default=0)
    total_failed = models.IntegerField(default=0)
    
    # Rates
    click_through_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # %
    
    # Revenue
    total_rewards_distributed = models.IntegerField(default=0)
    
    # Dates
    date = models.DateField(auto_now_add=True, unique_for_date='campaign')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        return f"Analytics - {self.campaign.name} ({self.date})"
    
    def calculate_rates(self):
        """Calculate CTR and completion rate"""
        if self.total_impressions > 0:
            self.click_through_rate = (self.total_clicks / self.total_impressions) * 100
            self.completion_rate = (self.total_completed / self.total_impressions) * 100
            self.save()
