from django.db import models
from django.utils import timezone
import uuid
from datetime import timedelta


class SubscriptionPlan(models.Model):
    """
    Pricing Plans for the EdTech platform
    - Free: 3 uses per feature
    - Basic: ₹1 for first month, then ₹99/month
    - Premium: ₹199 for first month, then ₹499/month (all features unlimited)
    """
    PLAN_TYPE_CHOICES = [
        ('free', 'FREE'),
        ('basic', 'BASIC'),
        ('premium', 'PREMIUM'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, choices=PLAN_TYPE_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Pricing
    first_month_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # ₹1 for premium
    recurring_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # ₹99 for premium
    currency = models.CharField(max_length=3, default='INR')
    
    # Feature Limits (null = unlimited)
    mock_test_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    quiz_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    pair_quiz_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    flashcards_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    ask_question_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    predicted_questions_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    previous_papers_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    pyq_features_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    youtube_summarizer_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    daily_quiz_limit = models.IntegerField(null=True, blank=True, help_text="null = unlimited")
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['first_month_price']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.display_name} - ₹{self.first_month_price}/₹{self.recurring_price}"
    
    def get_feature_dict(self):
        """Return feature limits as a dictionary"""
        return {
            'mock_test': self.mock_test_limit,
            'quiz': self.quiz_limit,
            'pair_quiz': self.pair_quiz_limit,
            'flashcards': self.flashcards_limit,
            'ask_question': self.ask_question_limit,
            'predicted_questions': self.predicted_questions_limit,
            'previous_papers': self.previous_papers_limit,
            'pyq_features': self.pyq_features_limit,
            'youtube_summarizer': self.youtube_summarizer_limit,
            'daily_quiz': self.daily_quiz_limit,
        }
    
    @staticmethod
    def initialize_default_plans():
        """Initialize default FREE, BASIC and PREMIUM plans"""
        # FREE Plan (Limited features, no payment)
        SubscriptionPlan.objects.get_or_create(
            name='free',
            defaults={
                'display_name': 'FREE Plan',
                'description': 'Free forever · Limited features · 3 uses per feature per month',
                'first_month_price': 0.00,
                'recurring_price': 0.00,
                'mock_test_limit': 3,
                'quiz_limit': 3,
                'flashcards_limit': 3,
                'ask_question_limit': 3,
                'predicted_questions_limit': 3,
                'youtube_summarizer_limit': 3,
                'pyq_features_limit': 3,
                'pair_quiz_limit': 0,
                'previous_papers_limit': 0,
                'daily_quiz_limit': 0,
            }
        )
        
        # BASIC Plan (₹1 for first month, ₹99/month thereafter)
        SubscriptionPlan.objects.get_or_create(
            name='basic',
            defaults={
                'display_name': 'BASIC Plan',
                'description': '₹1 for first month · ₹99/month from next month · Auto-debit enabled · Cancel anytime',
                'first_month_price': 1.00,
                'recurring_price': 99.00,
                'mock_test_limit': 10,
                'quiz_limit': 20,
                'flashcards_limit': 50,
                'ask_question_limit': 15,
                'predicted_questions_limit': 10,
                'youtube_summarizer_limit': 8,
                'pyq_features_limit': 30,
                'pair_quiz_limit': 0,
                'previous_papers_limit': 0,
                'daily_quiz_limit': 0,
            }
        )
        
        # PREMIUM Plan (₹199 for first month, ₹499/month thereafter - All features unlimited)
        SubscriptionPlan.objects.get_or_create(
            name='premium',
            defaults={
                'display_name': 'PREMIUM Plan',
                'description': '₹199 first month · ₹499/month · All features unlimited · Priority support',
                'first_month_price': 1.00,
                'recurring_price': 99.00,
                'mock_test_limit': None,  # Unlimited
                'quiz_limit': None,  # Unlimited
                'flashcards_limit': None,  # Unlimited
                'ask_question_limit': None,  # Unlimited
                'predicted_questions_limit': None,  # Unlimited
                'youtube_summarizer_limit': None,  # Unlimited
                'pyq_features_limit': None,  # Unlimited
                'pair_quiz_limit': None,
                'previous_papers_limit': None,
                'daily_quiz_limit': None,
            }
        )


class UserSubscription(models.Model):
    """Track user subscription status and feature limits"""
    PLAN_CHOICES = [
        ('free', 'FREE'),
        ('basic', 'BASIC'),
        ('premium', 'PREMIUM'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, unique=True)  # Can be device ID or user email
    plan = models.CharField(max_length=50, choices=PLAN_CHOICES, default='free')
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Feature usage tracking (monthly reset)
    mock_test_used = models.IntegerField(default=0)
    quiz_used = models.IntegerField(default=0)
    flashcards_used = models.IntegerField(default=0)
    ask_question_used = models.IntegerField(default=0)
    predicted_questions_used = models.IntegerField(default=0)
    youtube_summarizer_used = models.IntegerField(default=0)
    pyqs_used = models.IntegerField(default=0)
    pair_quiz_used = models.IntegerField(default=0)
    previous_papers_used = models.IntegerField(default=0)
    daily_quiz_used = models.IntegerField(default=0)
    
    # Razorpay Subscription fields
    razorpay_customer_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    subscription_status = models.CharField(
        max_length=50, 
        choices=[
            ('active', 'Active'),
            ('cancelled', 'Cancelled'),
            ('failed', 'Failed'),
            ('paused', 'Paused'),
        ],
        default='active'
    )
    
    # Subscription status
    is_trial = models.BooleanField(default=False)  # True if first month (₹1)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    
    # Billing dates
    subscription_start_date = models.DateTimeField(auto_now_add=True)
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    
    # Tracking
    usage_reset_date = models.DateTimeField(null=True, blank=True)  # Monthly reset date
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['plan']),
        ]
    
    def __str__(self):
        return f"{self.user_id} - {self.plan.upper()} Plan"
    
    def get_feature_limits(self):
        """Get feature limits based on plan"""
        # Get plan limits
        if self.subscription_plan:
            plan = self.subscription_plan
        else:
            # Fallback to default limits
            plan = SubscriptionPlan.objects.filter(name=self.plan).first()
            if not plan:
                return {}
        
        return {
            'mock_test': {'limit': plan.mock_test_limit, 'used': self.mock_test_used},
            'quiz': {'limit': plan.quiz_limit, 'used': self.quiz_used},
            'flashcards': {'limit': plan.flashcards_limit, 'used': self.flashcards_used},
            'ask_question': {'limit': plan.ask_question_limit, 'used': self.ask_question_used},
            'predicted_questions': {'limit': plan.predicted_questions_limit, 'used': self.predicted_questions_used},
            'youtube_summarizer': {'limit': plan.youtube_summarizer_limit, 'used': self.youtube_summarizer_used},
            'pyqs': {'limit': plan.pyq_features_limit, 'used': self.pyqs_used},
            'pair_quiz': {'limit': plan.pair_quiz_limit, 'used': self.pair_quiz_used},
            'previous_papers': {'limit': plan.previous_papers_limit, 'used': self.previous_papers_used},
            'daily_quiz': {'limit': plan.daily_quiz_limit, 'used': self.daily_quiz_used},
        }
    
    def can_use_feature(self, feature_name):
        """Check if user can use a feature"""
        limits = self.get_feature_limits()
        if feature_name not in limits:
            return True
        
        feature = limits[feature_name]
        if feature['limit'] is None:
            return True  # Unlimited
        
        return feature['used'] < feature['limit']
    
    def increment_feature_usage(self, feature_name):
        """Increment feature usage"""
        field_name = f'{feature_name}_used'
        if hasattr(self, field_name):
            current_value = getattr(self, field_name)
            setattr(self, field_name, current_value + 1)
            self.save()
    
    def reset_monthly_usage(self):
        """Reset monthly usage counters"""
        self.mock_test_used = 0
        self.quiz_used = 0
        self.flashcards_used = 0
        self.ask_question_used = 0
        self.predicted_questions_used = 0
        self.youtube_summarizer_used = 0
        self.pyqs_used = 0
        self.pair_quiz_used = 0
        self.previous_papers_used = 0
        self.daily_quiz_used = 0
        self.usage_reset_date = timezone.now()
        self.save()
    
    def get_next_billing_amount(self):
        """Get the amount for next billing cycle"""
        if self.is_trial and self.trial_end_date and timezone.now() < self.trial_end_date:
            # Still in trial, next billing will be regular price
            plan = self.subscription_plan or SubscriptionPlan.objects.filter(name=self.plan).first()
            return plan.recurring_price if plan else 99.00
        else:
            # Regular billing
            plan = self.subscription_plan or SubscriptionPlan.objects.filter(name=self.plan).first()
            return plan.recurring_price if plan else 99.00


class Payment(models.Model):
    """Track payment transactions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='payments')
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # 1.99 for premium
    currency = models.CharField(max_length=3, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    payment_method = models.CharField(max_length=50)
    transaction_id = models.CharField(max_length=255, unique=True)
    
    # Razorpay specific fields
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    
    billing_cycle_start = models.DateTimeField()
    billing_cycle_end = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Payment {self.transaction_id} - {self.status.upper()} (₹{self.amount})"


class FeatureUsageLog(models.Model):
    """Detailed log of feature usage"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(UserSubscription, on_delete=models.CASCADE, related_name='usage_logs')
    
    feature_name = models.CharField(max_length=50)  # 'ask_questions', 'quiz', 'flashcards'
    usage_type = models.CharField(max_length=20)  # 'image', 'text', 'file'
    input_size = models.IntegerField(help_text="Size in characters or bytes")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', '-created_at']),
            models.Index(fields=['feature_name']),
        ]
    
    def __str__(self):
        return f"{self.subscription.user_id} - {self.feature_name} ({self.created_at.date()})"


class Quiz(models.Model):
    """Store quiz sessions with metadata"""
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=50, choices=[
        ('youtube', 'YouTube'),
        ('text', 'Text'),
        ('image', 'Image'),
    ])
    source_id = models.CharField(max_length=255, blank=True)  # video_id or transcript_id
    summary = models.TextField()
    difficulty_level = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='intermediate')
    total_questions = models.IntegerField(default=5)
    estimated_time = models.IntegerField(help_text="Estimated time in minutes")
    keywords = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.total_questions} questions)"


class QuizQuestion(models.Model):
    """Store individual quiz questions"""
    QUESTION_TYPE_CHOICES = [
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
        ('matching', 'Matching'),
    ]
    DIFFICULTY_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    order = models.IntegerField()
    
    # For MCQ and True/False
    options = models.JSONField(default=list, blank=True)  # List of option dicts: [{"text": "...", "is_correct": bool}]
    correct_answer = models.CharField(max_length=500, blank=True)  # For short answer/essay
    
    # Explanation
    explanation = models.TextField(blank=True)
    hint = models.TextField(blank=True)
    
    # Difficulty at question level
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='intermediate')
    tags = models.JSONField(default=list, blank=True)  # Related topics/concepts
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['quiz', 'order']
        unique_together = ['quiz', 'order']
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."


class UserQuizResponse(models.Model):
    """Track user responses and scores"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='user_responses')
    session_id = models.CharField(max_length=255, default='anonymous')
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken = models.IntegerField(null=True, blank=True, help_text="Time taken in seconds")
    
    # Responses
    responses = models.JSONField(default=dict)  # {question_id: {"user_answer": "...", "is_correct": bool, "time_spent": seconds}}
    
    # Scoring
    score = models.FloatField(null=True, blank=True)  # Percentage
    correct_answers = models.IntegerField(default=0)
    total_answers = models.IntegerField(default=0)
    
    # Feedback
    feedback = models.TextField(blank=True)
    strengths = models.JSONField(default=list)  # Topics user performed well on
    weaknesses = models.JSONField(default=list)  # Topics needing improvement
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.session_id} - {self.quiz.title} ({self.score}%)"


class QuizSummary(models.Model):
    """Store quiz performance summaries"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='summaries')
    session_id = models.CharField(max_length=255, default='anonymous')
    
    # Overall stats
    attempts = models.IntegerField(default=0)
    best_score = models.FloatField(null=True, blank=True)
    average_score = models.FloatField(null=True, blank=True)
    
    # Performance analysis
    analysis = models.JSONField(default=dict)  # {
                                                 #   "overall_feedback": "...",
                                                 #   "topic_performance": {"topic": "score"},
                                                 #   "recommendations": ["..."],
                                                 #   "next_topics": ["..."]
                                                 # }
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Summary: {self.quiz.title} - Best: {self.best_score}%"


class UserCoins(models.Model):
    """Track user coins earned from Daily Quizzes and other activities"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, unique=True, db_index=True)
    total_coins = models.IntegerField(default=0)
    lifetime_coins = models.IntegerField(default=0)  # Total ever earned
    coins_spent = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-total_coins']
        verbose_name_plural = "User Coins"
    
    def __str__(self):
        return f"{self.user_id} - {self.total_coins} coins"
    
    def add_coins(self, amount, reason=""):
        """Add coins to user account"""
        self.total_coins += amount
        self.lifetime_coins += amount
        self.save()
        
        # Log the transaction
        CoinTransaction.objects.create(
            user_coins=self,
            amount=amount,
            transaction_type='earn',
            reason=reason
        )
    
    def spend_coins(self, amount, reason=""):
        """Spend coins from user account"""
        if self.total_coins >= amount:
            self.total_coins -= amount
            self.coins_spent += amount
            self.save()
            
            # Log the transaction
            CoinTransaction.objects.create(
                user_coins=self,
                amount=amount,
                transaction_type='spend',
                reason=reason
            )
            return True
        return False


class CoinTransaction(models.Model):
    """Log all coin transactions"""
    TRANSACTION_TYPES = [
        ('earn', 'Earned'),
        ('spend', 'Spent'),
        ('bonus', 'Bonus'),
        ('refund', 'Refund'),
        ('withdrawal', 'Withdrawal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_coins = models.ForeignKey(UserCoins, on_delete=models.CASCADE, related_name='transactions')
    amount = models.IntegerField()
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user_coins.user_id} - {self.transaction_type} {self.amount} coins"


class DailyQuiz(models.Model):
    """Daily GK quiz - one per day"""
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
        ('mixed', 'Mixed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='mixed')
    total_questions = models.IntegerField(default=10)
    coins_per_correct = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Daily Quizzes"
    
    def __str__(self):
        return f"Daily Quiz - {self.date} ({self.total_questions} questions)"
    
    @property
    def max_coins(self):
        """Maximum coins that can be earned from this quiz"""
        return self.total_questions * self.coins_per_correct


class DailyQuestion(models.Model):
    """Individual questions for Daily Quiz"""
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('moderate', 'Moderate'),
    ]
    
    CATEGORY_CHOICES = [
        ('general', 'General Knowledge'),
        ('current_events', 'Current Events'),
        ('science', 'Science'),
        ('history', 'History'),
        ('geography', 'Geography'),
        ('sports', 'Sports'),
        ('entertainment', 'Entertainment'),
        ('technology', 'Technology'),
        ('politics', 'Politics'),
        ('economics', 'Economics'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    daily_quiz = models.ForeignKey(DailyQuiz, on_delete=models.CASCADE, related_name='questions')
    order = models.IntegerField()
    
    question_text = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='general')
    difficulty = models.CharField(max_length=20, choices=DIFFICULTY_CHOICES, default='easy')
    
    # MCQ options (stored as JSON)
    options = models.JSONField(default=list)  # [{"id": "A", "text": "..."}, {"id": "B", "text": "..."}, ...]
    correct_answer = models.CharField(max_length=10)  # "A", "B", "C", or "D"
    
    explanation = models.TextField(blank=True)
    fun_fact = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['daily_quiz', 'order']
        unique_together = ['daily_quiz', 'order']
    
    def __str__(self):
        return f"Q{self.order}: {self.question_text[:50]}..."


class UserDailyQuizAttempt(models.Model):
    """Track user attempts on Daily Quizzes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    daily_quiz = models.ForeignKey(DailyQuiz, on_delete=models.CASCADE, related_name='attempts')
    user_id = models.CharField(max_length=255, db_index=True)
    
    # Results
    answers = models.JSONField(default=dict)  # {question_id: "A", ...}
    correct_count = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=10)
    score_percentage = models.FloatField(default=0.0)
    
    # Coins
    coins_earned = models.IntegerField(default=0)
    
    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-started_at']
        # Removed unique_together to allow multiple attempts per day
        indexes = [
            models.Index(fields=['user_id', '-started_at']),
            models.Index(fields=['daily_quiz', 'user_id']),  # Keep index for performance
        ]
    
    def __str__(self):
        return f"{self.user_id} - {self.daily_quiz.date} - {self.correct_count}/{self.total_questions} ({self.coins_earned} coins)"

class PasswordResetToken(models.Model):
    """Store password reset tokens for email-based reset"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='password_reset_token')
    token = models.CharField(max_length=255, unique=True)  # URL-safe token
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()  # Token expires after 24 hours
    is_used = models.BooleanField(default=False)  # One-time use token
    used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"Reset token for {self.user.email}"
    
    def is_valid(self):
        """Check if token is still valid (not expired and not used)"""
        return not self.is_used and timezone.now() < self.expires_at


class PairQuizSession(models.Model):
    """Store pair quiz session data for real-time collaboration"""
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Partner'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_code = models.CharField(max_length=10, unique=True, db_index=True)  # e.g., "QZ-84K9"
    
    # Participants
    host_user_id = models.CharField(max_length=255)
    partner_user_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Quiz configuration
    quiz_config = models.JSONField(default=dict)  # {subject, difficulty, numQuestions, etc.}
    questions = models.JSONField(default=list)  # Generated questions
    
    # Session state
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    current_question_index = models.IntegerField(default=0)
    
    # Answers
    host_answers = models.JSONField(default=dict)  # {questionIndex: selectedOption}
    partner_answers = models.JSONField(default=dict)
    
    # Timing
    timer_seconds = models.IntegerField(default=0)  # Shared timer
    host_time_taken = models.IntegerField(default=0)  # Individual tracking
    partner_time_taken = models.IntegerField(default=0)
    
    # Results
    host_score = models.FloatField(null=True, blank=True)
    partner_score = models.FloatField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()  # Auto-expire after 30 minutes
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_code']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['host_user_id']),
        ]
    
    def __str__(self):
        return f"Pair Quiz {self.session_code} - {self.status}"
    
    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.expires_at
    
    def generate_session_code(self):
        """Generate unique 6-character session code"""
        import random
        import string
        while True:
            code = 'QZ-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            if not PairQuizSession.objects.filter(session_code=code).exists():
                return code


class QuizSettings(models.Model):
    """Global settings for quiz rewards and configurations"""
    # Daily Quiz Coin Settings
    daily_quiz_attempt_bonus = models.IntegerField(
        default=5,
        help_text="Coins awarded for starting a daily quiz"
    )
    daily_quiz_coins_per_correct = models.IntegerField(
        default=5,
        help_text="Coins awarded per correct answer in daily quiz"
    )
    daily_quiz_perfect_score_bonus = models.IntegerField(
        default=10,
        help_text="Extra bonus coins for getting 100% score"
    )
    
    # Pair Quiz Settings
    pair_quiz_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable pair quiz feature"
    )
    pair_quiz_session_timeout = models.IntegerField(
        default=30,
        help_text="Session expiry time in minutes"
    )
    pair_quiz_max_questions = models.IntegerField(
        default=20,
        help_text="Maximum questions allowed per quiz"
    )
    
    # General Settings
    coin_to_currency_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.10,
        help_text="Conversion rate: 1 coin = X currency"
    )
    min_coins_for_redemption = models.IntegerField(
        default=10,
        help_text="Minimum coins required for redemption"
    )
    
    # Metadata
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=255, blank=True, null=True)
    
    class Meta:
        verbose_name = "Quiz Settings"
        verbose_name_plural = "Quiz Settings"
    
    def __str__(self):
        return "Quiz Settings (Global Configuration)"
    
    @classmethod
    def get_settings(cls):
        """Get or create singleton settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Prevent deletion
        pass


class CoinWithdrawal(models.Model):
    """Track coin withdrawal requests and UPI payouts (Platform → User)"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, db_index=True)
    
    # Withdrawal details
    coins_amount = models.IntegerField(help_text='Coins to withdraw (min: 100)')
    rupees_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='Amount in rupees (coins/10)')
    
    # UPI details (UPI-only payouts)
    upi_id = models.CharField(max_length=100, help_text='UPI ID for payout (e.g., user@paytm)')
    
    # Razorpay payout details
    razorpay_payout_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    razorpay_fund_account_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_contact_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    failure_reason = models.TextField(blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user_id} - {self.coins_amount} coins (₹{self.rupees_amount}) - {self.status}"


class RazorpayOrder(models.Model):
    """Track Razorpay payment orders"""
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('attempted', 'Attempted'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, db_index=True)
    
    # Razorpay order details
    razorpay_order_id = models.CharField(max_length=255, unique=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    razorpay_signature = models.CharField(max_length=500, blank=True, null=True)
    
    # Order details
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Amount in rupees
    amount_paise = models.IntegerField()  # Amount in smallest currency unit (paise)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='created')
    
    # Additional details
    receipt = models.CharField(max_length=255, blank=True, null=True)
    notes = models.JSONField(default=dict, blank=True)
    
    # Payment details
    payment_method = models.CharField(max_length=50, blank=True, null=True)  # 'card', 'upi', 'netbanking', etc.
    payment_email = models.EmailField(blank=True, null=True)
    payment_contact = models.CharField(max_length=20, blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['razorpay_order_id']),
        ]
    
    def __str__(self):
        return f"Order {self.razorpay_order_id} - {self.status} - ₹{self.amount}"
    
    def mark_as_paid(self, payment_id, signature):
        """Mark order as paid"""
        self.razorpay_payment_id = payment_id
        self.razorpay_signature = signature
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save()
    
    def mark_as_failed(self):
        """Mark order as failed"""
        self.status = 'failed'
        self.save()


# ============================================================================
# SUBSCRIPTION & PRICING MODELS (As per Product Spec)
# ============================================================================

class PlanSubscription(models.Model):
    """
    Track user subscription plans (FREE or PAID)
    Replaces UserSubscription for pricing model
    """
    PLAN_TYPE_CHOICES = [
        ('FREE', 'Free Plan'),
        ('PAID', 'Paid Plan'),
    ]
    
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('PAST_DUE', 'Past Due'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Plan details
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPE_CHOICES, default='FREE')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Razorpay subscription details
    razorpay_subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    razorpay_plan_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Billing cycle
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'plan_subscription'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['plan_type', 'status']),
            models.Index(fields=['razorpay_subscription_id']),
        ]
    
    def __str__(self):
        return f"{self.user_id} - {self.plan_type} ({self.status})"
    
    def activate_paid_plan(self, razorpay_subscription_id, razorpay_plan_id):
        """Activate paid plan"""
        self.plan_type = 'PAID'
        self.status = 'ACTIVE'
        self.razorpay_subscription_id = razorpay_subscription_id
        self.razorpay_plan_id = razorpay_plan_id
        self.activated_at = timezone.now()
        self.current_period_start = timezone.now()
        self.current_period_end = timezone.now() + timedelta(days=30)
        self.save()
        
        # Initialize usage quotas
        UsageQuota.objects.get_or_create(user_id=self.user_id)
    
    def downgrade_to_free(self):
        """Downgrade to free plan"""
        self.plan_type = 'FREE'
        self.status = 'ACTIVE'
        self.cancelled_at = timezone.now()
        self.save()
    
    def mark_past_due(self):
        """Mark subscription as past due"""
        self.status = 'PAST_DUE'
        self.save()
    
    def is_paid_active(self):
        """Check if user has active paid subscription"""
        return self.plan_type == 'PAID' and self.status == 'ACTIVE'


class UsageQuota(models.Model):
    """
    Track monthly usage limits for paid features
    Limits reset every billing cycle
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.CharField(max_length=255, unique=True, db_index=True)
    
    # Monthly usage counters (30 per month for paid users)
    quizzes_used = models.IntegerField(default=0)
    mock_tests_used = models.IntegerField(default=0)
    flashcards_used = models.IntegerField(default=0)
    predicted_questions_used = models.IntegerField(default=0)
    youtube_summaries_used = models.IntegerField(default=0)
    
    # Reset tracking
    last_reset_date = models.DateTimeField(auto_now_add=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'usage_quota'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id']),
        ]
    
    def __str__(self):
        return f"{self.user_id} - Quotas"
    
    def get_remaining(self, feature):
        """Get remaining usage for a feature"""
        MONTHLY_LIMIT = 30
        used = getattr(self, f'{feature}_used', 0)
        return max(0, MONTHLY_LIMIT - used)
    
    def can_use(self, feature):
        """Check if user can use a paid feature"""
        return self.get_remaining(feature) > 0
    
    def increment(self, feature):
        """Increment usage for a feature"""
        field_name = f'{feature}_used'
        if hasattr(self, field_name):
            current_value = getattr(self, field_name)
            setattr(self, field_name, current_value + 1)
            self.save()
    
    def reset_all(self):
        """Reset all monthly quotas"""
        self.quizzes_used = 0
        self.mock_tests_used = 0
        self.flashcards_used = 0
        self.predicted_questions_used = 0
        self.youtube_summaries_used = 0
        self.last_reset_date = timezone.now()
        self.save()


class SubscriptionPayment(models.Model):
    """
    Track subscription payment transactions
    """
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('authorized', 'Authorized'),
        ('captured', 'Captured'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(PlanSubscription, on_delete=models.CASCADE, related_name='payments')
    
    # Razorpay details
    razorpay_payment_id = models.CharField(max_length=255, unique=True)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=500, blank=True, null=True)
    
    # Amount details
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Amount in rupees
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='created')
    
    # Payment method
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    
    # Billing period this payment covers
    billing_period_start = models.DateTimeField()
    billing_period_end = models.DateTimeField()
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'subscription_payment'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', '-created_at']),
            models.Index(fields=['razorpay_payment_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Payment {self.razorpay_payment_id} - ₹{self.amount} ({self.status})"

# ============ UNITY ADS MODELS ============

class AdImpressionLog(models.Model):
    """
    Track every ad impression/view for analytics
    """
    PLATFORM_CHOICES = [
        ('ios', 'iOS'),
        ('android', 'Android'),
        ('web', 'Web'),
    ]
    
    AD_TYPE_CHOICES = [
        ('interstitial', 'Interstitial'),
        ('rewarded', 'Rewarded'),
        ('banner', 'Banner'),
    ]
    
    STATUS_CHOICES = [
        ('shown', 'Shown'),
        ('clicked', 'Clicked'),
        ('closed', 'Closed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='ad_impressions')
    ad_type = models.CharField(max_length=20, choices=AD_TYPE_CHOICES)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='ios')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='shown')
    
    # Ad Details
    feature = models.CharField(max_length=100, help_text="Feature that triggered the ad")
    unity_placement_id = models.CharField(max_length=100, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ad_impression_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['ad_type', '-created_at']),
            models.Index(fields=['feature']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Ad {self.ad_type} - {self.user.username} ({self.status})"


class FeatureAdConfig(models.Model):
    """
    Configure which features should show ads and how many times
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    feature_name = models.CharField(max_length=100, unique=True)
    feature_display_name = models.CharField(max_length=200)
    
    # Ad Configuration
    show_ad_after_use = models.BooleanField(default=True, help_text="Show ad after feature use")
    ad_type = models.CharField(max_length=20, choices=AdImpressionLog.AD_TYPE_CHOICES, default='interstitial')
    show_frequency = models.IntegerField(default=1, help_text="Show ad every N uses (1 = every use)")
    
    # Unity Placement IDs
    ios_placement_id = models.CharField(max_length=100, blank=True)
    android_placement_id = models.CharField(max_length=100, blank=True)
    
    # Skip conditions
    skip_for_premium = models.BooleanField(default=True)
    skip_if_ad_seen_today = models.BooleanField(default=False)
    max_ads_per_day = models.IntegerField(default=10)
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'feature_ad_config'
        ordering = ['feature_name']
        indexes = [
            models.Index(fields=['feature_name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.feature_display_name} (Frequency: {self.show_frequency}x)"


class UserAdLimitTracker(models.Model):
    """
    Track how many ads a user has seen today and per feature
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='ad_limit_tracker')
    
    # Daily tracking
    ads_shown_today = models.IntegerField(default=0)
    last_ad_reset = models.DateTimeField(auto_now_add=True)  # Reset daily
    
    # Feature tracking (JSON - feature_name: count)
    feature_use_counts = models.JSONField(default=dict, blank=True)
    
    # Latest ad time
    last_ad_shown = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_ad_limit_tracker'
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.ads_shown_today} ads today"
    
    def reset_daily_if_needed(self):
        """Reset daily ad count if it's a new day"""
        now = timezone.now()
        if (now - self.last_ad_reset).days >= 1:
            self.ads_shown_today = 0
            self.last_ad_reset = now
            self.save()
    
    def increment_feature_use(self, feature_name):
        """Increment feature use count"""
        if not self.feature_use_counts:
            self.feature_use_counts = {}
        
        if feature_name not in self.feature_use_counts:
            self.feature_use_counts[feature_name] = 0
        
        self.feature_use_counts[feature_name] += 1
        self.save()


class AdAnalytics(models.Model):
    """
    Aggregate analytics for ads
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Date grouping
    date = models.DateField(auto_now_add=True)
    hour = models.IntegerField(default=0)  # 0-23
    
    # Metrics
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    closes = models.IntegerField(default=0)
    failures = models.IntegerField(default=0)
    
    # Feature breakdown
    feature = models.CharField(max_length=100, blank=True)
    platform = models.CharField(max_length=10, choices=AdImpressionLog.PLATFORM_CHOICES, blank=True)
    
    class Meta:
        db_table = 'ad_analytics'
        ordering = ['-date', '-hour']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['feature']),
            models.Index(fields=['platform']),
        ]
        unique_together = [['date', 'hour', 'feature', 'platform']]
    
    def __str__(self):
        return f"Analytics {self.date} - {self.impressions} impressions"