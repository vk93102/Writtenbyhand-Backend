from django.contrib import admin
from . import models
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils import timezone
import json
import logging
from django.db.models import Sum

logger = logging.getLogger(__name__)


@admin.register(models.SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
	list_display = (
		'display_name', 'name', 'first_month_price', 'recurring_price', 'currency', 'is_active'
	)
	list_filter = ('is_active', 'name')
	search_fields = ('display_name', 'description')
	readonly_fields = ('created_at', 'updated_at')
	fieldsets = (
		('Basic Information', {
			'fields': ('name', 'display_name', 'description', 'is_active')
		}),
		('Pricing', {
			'fields': ('first_month_price', 'recurring_price', 'currency')
		}),
		('Feature Limits', {
			'fields': (
				'mock_test_limit', 'quiz_limit', 'pair_quiz_limit', 'flashcards_limit',
				'ask_question_limit', 'predicted_questions_limit', 'previous_papers_limit',
				'pyq_features_limit', 'youtube_summarizer_limit', 'daily_quiz_limit'
			),
			'description': 'Leave blank or null for unlimited access'
		}),
		('Timestamps', {
			'fields': ('created_at', 'updated_at')
		}),
	)


class PaymentInline(admin.TabularInline):
	model = models.Payment
	extra = 0
	readonly_fields = ('transaction_id', 'amount', 'currency', 'status', 'payment_method', 'created_at')


@admin.action(description='Reset monthly usage for selected subscriptions')
def reset_monthly_usage(modeladmin, request, queryset):
	for subscription in queryset:
		subscription.reset_monthly_usage()


@admin.register(models.UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
	list_display = (
		'user_id', 'plan', 'mock_test_used', 'quiz_used', 'flashcards_used',
		'subscription_status', 'subscription_start_date', 'subscription_end_date',
	)
	list_filter = ('plan', 'subscription_status')
	search_fields = ('user_id', 'razorpay_customer_id', 'razorpay_subscription_id')
	inlines = [PaymentInline]
	actions = [reset_monthly_usage]
	readonly_fields = ('created_at', 'updated_at', 'subscription_start_date', 'next_billing_date', 'razorpay_customer_id', 'razorpay_subscription_id')


@admin.register(models.Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ('transaction_id', 'subscription', 'amount', 'currency', 'status', 'payment_method', 'created_at')
	list_filter = ('status', 'payment_method')
	search_fields = ('transaction_id', 'subscription__user_id', 'razorpay_order_id', 'razorpay_payment_id')
	readonly_fields = ('created_at', 'updated_at')


@admin.register(models.FeatureUsageLog)
class FeatureUsageLogAdmin(admin.ModelAdmin):
	list_display = ('subscription', 'feature_name', 'usage_type', 'input_size', 'created_at')
	list_filter = ('feature_name', 'usage_type')
	search_fields = ('subscription__user_id',)
	readonly_fields = ('created_at',)


class QuizQuestionInline(admin.TabularInline):
	model = models.QuizQuestion
	extra = 0
	fields = ('order', 'question_type', 'question_text', 'difficulty', 'created_at')
	readonly_fields = ('created_at',)


@admin.register(models.Quiz)
class QuizAdmin(admin.ModelAdmin):
	list_display = ('title', 'source_type', 'difficulty_level', 'total_questions', 'estimated_time', 'created_at')
	search_fields = ('title', 'keywords')
	list_filter = ('source_type', 'difficulty_level')
	inlines = [QuizQuestionInline]
	readonly_fields = ('created_at', 'updated_at')


@admin.register(models.QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
	list_display = ('quiz', 'order', 'question_type', 'difficulty', 'created_at')
	list_filter = ('question_type', 'difficulty')
	search_fields = ('question_text', 'quiz__title')
	readonly_fields = ('created_at',)


@admin.register(models.UserQuizResponse)
class UserQuizResponseAdmin(admin.ModelAdmin):
	list_display = ('session_id', 'quiz', 'score', 'correct_answers', 'total_answers', 'started_at', 'completed_at')
	list_filter = ('quiz',)
	search_fields = ('session_id', 'quiz__title')
	readonly_fields = ('started_at', 'completed_at')


@admin.register(models.QuizSummary)
class QuizSummaryAdmin(admin.ModelAdmin):
	list_display = ('quiz', 'attempts', 'best_score', 'average_score', 'created_at')
	search_fields = ('quiz__title',)
	readonly_fields = ('created_at', 'updated_at')


# Re-register User with a slightly enhanced view in admin so admins can easily search by email
try:
	admin.site.unregister(User)
except Exception:
	pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email')


# Daily Quiz Admin

class CoinTransactionInline(admin.TabularInline):
    model = models.CoinTransaction
    extra = 0
    readonly_fields = ('amount', 'transaction_type', 'reason', 'created_at')
    can_delete = False


# UserCoins and CoinTransaction admin moved to bottom with withdrawal admin


class DailyQuestionInline(admin.TabularInline):
    model = models.DailyQuestion
    extra = 0
    fields = ('order', 'question_text', 'category', 'difficulty', 'correct_answer')
    ordering = ['order']
    can_delete = True


@admin.register(models.DailyQuiz)
class DailyQuizAdmin(admin.ModelAdmin):
    list_display = ('date', 'title', 'difficulty', 'total_questions', 'coins_per_correct', 'max_coins_display', 'is_active', 'created_at')
    list_filter = ('difficulty', 'is_active', 'date')
    search_fields = ('title', 'description')
    date_hierarchy = 'date'
    inlines = [DailyQuestionInline]
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('is_active',)
    
    fieldsets = (
        ('Quiz Info', {
            'fields': ('date', 'title', 'description', 'difficulty')
        }),
        ('Configuration', {
            'fields': ('total_questions', 'coins_per_correct', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def max_coins_display(self, obj):
        return obj.max_coins
    max_coins_display.short_description = 'Max Coins'


@admin.register(models.DailyQuestion)
class DailyQuestionAdmin(admin.ModelAdmin):
    list_display = ('question_preview', 'daily_quiz', 'order', 'category', 'difficulty', 'correct_answer', 'created_at')
    list_filter = ('category', 'difficulty', 'daily_quiz__date')
    search_fields = ('question_text', 'daily_quiz__title')
    readonly_fields = ('created_at',)
    list_per_page = 50
    
    fieldsets = (
        ('Question Details', {
            'fields': ('daily_quiz', 'order', 'question_text')
        }),
        ('Options & Answer', {
            'fields': ('options', 'correct_answer')
        }),
        ('Metadata', {
            'fields': ('category', 'difficulty', 'explanation', 'fun_fact')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def question_preview(self, obj):
        return obj.question_text[:80] + '...' if len(obj.question_text) > 80 else obj.question_text
    question_preview.short_description = 'Question'


@admin.register(models.UserDailyQuizAttempt)
class UserDailyQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'daily_quiz', 'correct_count', 'total_questions', 'score_percentage', 'coins_earned', 'completed_at')
    list_filter = ('daily_quiz__date', 'completed_at')
    search_fields = ('user_id', 'daily_quiz__title')
    readonly_fields = ('started_at', 'completed_at')
    date_hierarchy = 'started_at'


# Pair Quiz Admin

@admin.register(models.PairQuizSession)
class PairQuizSessionAdmin(admin.ModelAdmin):
    list_display = (
        'session_code', 
        'status_badge', 
        'host_user_short', 
        'partner_user_short', 
        'total_questions',
        'host_score',
        'partner_score',
        'created_at',
        'time_elapsed'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('session_code', 'host_user_id', 'partner_user_id')
    readonly_fields = (
        'id', 
        'session_code', 
        'created_at', 
        'started_at', 
        'completed_at',
        'expires_at',
        'time_elapsed_display',
        'questions_display',
        'host_answers_display',
        'partner_answers_display',
        'quiz_config_display'
    )
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Session Info', {
            'fields': ('id', 'session_code', 'status', 'quiz_config_display')
        }),
        ('Participants', {
            'fields': ('host_user_id', 'partner_user_id')
        }),
        ('Quiz Progress', {
            'fields': ('current_question_index', 'questions_display')
        }),
        ('Answers & Scores', {
            'fields': (
                'host_answers_display', 
                'partner_answers_display',
                'host_score',
                'partner_score',
                'host_time_taken',
                'partner_time_taken'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'started_at', 'completed_at', 'expires_at', 'time_elapsed_display')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'waiting': '#FFA500',
            'active': '#4CAF50',
            'completed': '#2196F3',
            'cancelled': '#F44336'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#999'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def host_user_short(self, obj):
        return obj.host_user_id[:20] + '...' if len(obj.host_user_id) > 20 else obj.host_user_id
    host_user_short.short_description = 'Host'
    
    def partner_user_short(self, obj):
        if obj.partner_user_id:
            return obj.partner_user_id[:20] + '...' if len(obj.partner_user_id) > 20 else obj.partner_user_id
        return '-'
    partner_user_short.short_description = 'Partner'
    
    def total_questions(self, obj):
        return len(obj.questions) if obj.questions else 0
    total_questions.short_description = 'Questions'
    
    def time_elapsed(self, obj):
        if obj.completed_at and obj.started_at:
            delta = obj.completed_at - obj.started_at
            minutes = delta.total_seconds() / 60
            return f"{minutes:.1f}m"
        return '-'
    time_elapsed.short_description = 'Duration'
    
    def time_elapsed_display(self, obj):
        if obj.completed_at and obj.started_at:
            delta = obj.completed_at - obj.started_at
            return f"{delta.total_seconds():.0f} seconds"
        return 'Not completed'
    time_elapsed_display.short_description = 'Time Elapsed'
    
    def questions_display(self, obj):
        if not obj.questions:
            return 'No questions'
        html = '<div style="max-height: 300px; overflow-y: auto;">'
        for idx, q in enumerate(obj.questions, 1):
            html += f'<p><strong>Q{idx}:</strong> {q.get("question", "N/A")[:100]}...</p>'
        html += '</div>'
        return mark_safe(html)
    questions_display.short_description = 'Questions Preview'
    
    def host_answers_display(self, obj):
        if not obj.host_answers:
            return 'No answers'
        return mark_safe('<pre>' + json.dumps(obj.host_answers, indent=2) + '</pre>')
    host_answers_display.short_description = 'Host Answers'
    
    def partner_answers_display(self, obj):
        if not obj.partner_answers:
            return 'No answers'
        return mark_safe('<pre>' + json.dumps(obj.partner_answers, indent=2) + '</pre>')
    partner_answers_display.short_description = 'Partner Answers'
    
    def quiz_config_display(self, obj):
        if not obj.quiz_config:
            return 'No config'
        return mark_safe('<pre>' + json.dumps(obj.quiz_config, indent=2) + '</pre>')
    quiz_config_display.short_description = 'Quiz Configuration'
    
    actions = ['cancel_sessions', 'delete_expired_sessions']
    
    @admin.action(description='Cancel selected sessions')
    def cancel_sessions(self, request, queryset):
        updated = queryset.filter(status__in=['waiting', 'active']).update(status='cancelled')
        self.message_user(request, f'{updated} session(s) cancelled.')
    
    @admin.action(description='Delete expired sessions')
    def delete_expired_sessions(self, request, queryset):
        from django.utils import timezone
        expired = queryset.filter(expires_at__lt=timezone.now())
        count = expired.count()
        expired.delete()
        self.message_user(request, f'{count} expired session(s) deleted.')

# Quiz Settings Admin (Singleton)

@admin.register(models.QuizSettings)
class QuizSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Daily Quiz Rewards', {
            'fields': (
                'daily_quiz_attempt_bonus',
                'daily_quiz_coins_per_correct',
                'daily_quiz_perfect_score_bonus'
            ),
            'description': 'Configure coin rewards for daily quiz'
        }),
        ('Pair Quiz Settings', {
            'fields': (
                'pair_quiz_enabled',
                'pair_quiz_session_timeout',
                'pair_quiz_max_questions'
            ),
            'description': 'Configure pair quiz behavior'
        }),
        ('Coin System', {
            'fields': (
                'coin_to_currency_rate',
                'min_coins_for_redemption'
            ),
            'description': 'Configure coin economy settings'
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('updated_at',)
    
    def has_add_permission(self, request):
        # Only allow one instance
        return not models.QuizSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of settings
        return False
    
    def changelist_view(self, request, extra_context=None):
        # Redirect to edit view if settings exist
        if models.QuizSettings.objects.exists():
            obj = models.QuizSettings.objects.first()
            from django.shortcuts import redirect
            return redirect('admin:question_solver_quizsettings_change', obj.pk)
        return super().changelist_view(request, extra_context)





@admin.register(models.UserCoins)
class UserCoinsAdmin(admin.ModelAdmin):
    """Admin interface for user coin balances"""
    
    list_display = ('user_id', 'total_coins_display', 'lifetime_coins', 'coins_spent', 'updated_at')
    search_fields = ('user_id',)
    ordering = ('-total_coins',)
    readonly_fields = ('user_id', 'total_coins', 'lifetime_coins', 'coins_spent', 'created_at', 'updated_at')
    
    def total_coins_display(self, obj):
        return format_html(
            '<strong style="color: #007bff; font-size: 14px;">{} coins</strong>',
            obj.total_coins
        )
    total_coins_display.short_description = 'Current Balance'
    total_coins_display.admin_order_field = 'total_coins'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    """Admin interface for coin transaction history"""
    
    list_display = ('id', 'user_display', 'amount_display', 'transaction_type', 'upi_info_display', 'reason', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('user_coins__user_id', 'reason', 'metadata')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'user_coins', 'amount', 'transaction_type', 'reason', 'created_at', 'metadata')
    
    def user_display(self, obj):
        return obj.user_coins.user_id
    user_display.short_description = 'User ID'
    
    def amount_display(self, obj):
        color = '#28a745' if obj.transaction_type == 'earn' else '#dc3545'
        prefix = '+' if obj.transaction_type == 'earn' else '-'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{} coins</span>',
            color, prefix, obj.amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def upi_info_display(self, obj):
        """Display UPI/Bank details for withdrawal transactions"""
        if obj.transaction_type == 'withdrawal' and obj.metadata:
            try:
                metadata = obj.metadata if isinstance(obj.metadata, dict) else json.loads(obj.metadata)
                upi_id = metadata.get('upi_id', '-')
                rupees = metadata.get('rupees_amount', '-')
                return format_html(
                    '<div style="font-size: 11px; line-height: 1.4;">'
                    '<strong>{}</strong><br/>'
                    '<small style="color: #6c757d;">₹{}</small>'
                    '</div>',
                    upi_id, rupees
                )
            except:
                return '-'
        return '-'
    upi_info_display.short_description = 'UPI / Amount'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.CoinWithdrawal)
class CoinWithdrawalAdmin(admin.ModelAdmin):
    """
    Professional admin interface for managing coin withdrawal requests.
    Provides comprehensive view and management of withdrawal lifecycle.
    """

    # List display with professional formatting
    list_display = (
        'id_display',
        'user_info_display',
        'amount_display',
        'upi_display',
        'status_badge',
        'created_at_display',
        'processed_at_display',
        'actions_display'
    )

    # Enhanced list filters
    list_filter = (
        'status',
        ('created_at', admin.DateFieldListFilter),
        ('processed_at', admin.DateFieldListFilter),
        'upi_id'
    )

    # Comprehensive search fields
    search_fields = (
        'id',
        'user_id',
        'upi_id',
        'admin_notes',
        'failure_reason'
    )

    # Professional ordering
    ordering = ('-created_at',)

    # Read-only fields for security
    readonly_fields = (
        'id',
        'user_id',
        'coins_amount',
        'rupees_amount',
        'upi_id',
        'bank_info_display',
        'razorpay_payout_id',
        'razorpay_fund_account_id',
        'razorpay_contact_id',
        'created_at',
        'updated_at',
        'processed_at',
        'completed_at'
    )

    # Organized fieldsets
    fieldsets = (
        ('Withdrawal Information', {
            'fields': ('id', 'user_id', 'coins_amount', 'rupees_amount', 'upi_id', 'bank_info_display'),
            'classes': ('wide',)
        }),
        ('Processing Status', {
            'fields': ('status', 'failure_reason', 'admin_notes'),
            'classes': ('wide',)
        }),
        ('Razorpay Details', {
            'fields': ('razorpay_payout_id', 'razorpay_fund_account_id', 'razorpay_contact_id'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at', 'completed_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # Custom actions
    actions = ['approve_withdrawal', 'reject_withdrawal']

    # List display methods for professional formatting
    def id_display(self, obj):
        """Display withdrawal ID with copy-friendly format"""
        return format_html(
            '<code style="font-family: monospace; font-size: 11px; background: #f8f9fa; padding: 2px 4px; border-radius: 3px;">{}</code>',
            str(obj.id)[:8] + '...'
        )
    id_display.short_description = 'ID'
    id_display.admin_order_field = 'id'

    def user_info_display(self, obj):
        """Display user information with balance"""
        try:
            user_coins = models.UserCoins.objects.get(user_id=obj.user_id)
            balance = user_coins.total_coins
            return format_html(
                '<div style="line-height: 1.2;">'
                '<strong>{}</strong><br/>'
                '<small style="color: #6c757d;">Balance: {} coins</small>'
                '</div>',
                obj.user_id, balance
            )
        except models.UserCoins.DoesNotExist:
            return format_html(
                '<div style="line-height: 1.2;">'
                '<strong>{}</strong><br/>'
                '<small style="color: #dc3545;">No balance record</small>'
                '</div>',
                obj.user_id
            )
    user_info_display.short_description = 'User'
    user_info_display.admin_order_field = 'user_id'

    def amount_display(self, obj):
        """Display amounts professionally"""
        rupees_formatted = f"₹{float(obj.rupees_amount):.2f}"
        return format_html(
            '<div style="text-align: right; line-height: 1.2;">'
            '<strong style="color: #28a745; font-size: 14px;">{}</strong><br/>'
            '<small style="color: #6c757d;">{} coins</small>'
            '</div>',
            rupees_formatted, obj.coins_amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'rupees_amount'

    def upi_display(self, obj):
        """Display UPI ID and Bank details professionally"""
        # Extract bank name from UPI ID (part after @)
        bank_code = obj.upi_id.split('@')[1] if '@' in obj.upi_id else 'Unknown'
        
        # Map common bank codes to readable names
        bank_names = {
            'okhdfcbank': 'HDFC Bank',
            'okaxis': 'Axis Bank',
            'okicici': 'ICICI Bank',
            'oksbi': 'SBI',
            'sbi': 'SBI',
            'hdfc': 'HDFC Bank',
            'paytm': 'Paytm',
            'ybl': 'Phonepe',
            'airtel': 'Airtel Pay',
            'googlepay': 'Google Pay'
        }
        
        bank_name = bank_names.get(bank_code.lower(), bank_code.upper())
        
        return format_html(
            '<div style="line-height: 1.4;">'
            '<div style="font-family: monospace; background: #e9ecef; padding: 4px 8px; border-radius: 4px; font-size: 12px; margin-bottom: 4px;">'
            '<strong>UPI:</strong> {}'
            '</div>'
            '<div style="padding: 4px 0; font-size: 12px;">'
            '<strong>Bank:</strong> <span style="background: #d4edda; padding: 2px 6px; border-radius: 3px;">{}</span>'
            '</div>'
            '</div>',
            obj.upi_id, bank_name
        )
    upi_display.short_description = 'UPI ID / Bank'
    upi_display.admin_order_field = 'upi_id'

    def status_badge(self, obj):
        """Display status with professional badges"""
        status_colors = {
            'pending': '#ffc107',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'failed': '#dc3545'
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase;">'
            '{}'
            '</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def created_at_display(self, obj):
        """Display creation time with relative time"""
        from django.utils.timesince import timesince
        time_ago = timesince(obj.created_at).split(',')[0]  # Get main time unit
        return format_html(
            '<div style="line-height: 1.2;">'
            '<strong>{}</strong><br/>'
            '<small style="color: #6c757d;">{} ago</small>'
            '</div>',
            obj.created_at.strftime('%b %d, %H:%M'),
            time_ago
        )
    created_at_display.short_description = 'Created'
    created_at_display.admin_order_field = 'created_at'

    def processed_at_display(self, obj):
        """Display processing time"""
        if obj.processed_at:
            return obj.processed_at.strftime('%b %d, %H:%M')
        elif obj.status in ['pending']:
            return format_html('<span style="color: #ffc107;">Pending</span>')
        else:
            return '-'
    processed_at_display.short_description = 'Processed'
    processed_at_display.admin_order_field = 'processed_at'

    def actions_display(self, obj):
        """Display quick action buttons"""
        if obj.status == 'pending':
            return format_html(
                '<div style="display: flex; gap: 4px;">'
                '<a href="#" onclick="approveWithdrawal(\'{}\')" '
                'style="background: #28a745; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none; font-size: 11px;">'
                '✓ Approve</a>'
                '<a href="#" onclick="rejectWithdrawal(\'{}\')" '
                'style="background: #dc3545; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none; font-size: 11px;">'
                '✗ Reject</a>'
                '</div>',
                obj.id, obj.id
            )
        elif obj.status == 'processing':
            return format_html(
                '<span style="color: #17a2b8; font-size: 11px;">Processing...</span>'
            )
        elif obj.status == 'completed':
            return format_html(
                '<span style="color: #28a745; font-size: 11px;">✓ Completed</span>'
            )
        elif obj.status == 'failed':
            return format_html(
                '<span style="color: #dc3545; font-size: 11px;">✗ Failed</span>'
            )
        return '-'
    actions_display.short_description = 'Actions'

    # Custom admin methods
    def get_queryset(self, request):
        """Optimize queryset with select_related for better performance"""
        return super().get_queryset(request).select_related()

    def changelist_view(self, request, extra_context=None):
        """Add statistics to changelist view"""
        extra_context = extra_context or {}

        # Get statistics
        queryset = self.get_queryset(request)
        total_withdrawals = queryset.count()
        pending_count = queryset.filter(status='pending').count()
        completed_count = queryset.filter(status='completed').count()
        failed_count = queryset.filter(status='failed').count()

        # Calculate total amounts
        total_pending_amount = queryset.filter(status='pending').aggregate(
            total=Sum('rupees_amount')
        )['total'] or 0

        total_completed_amount = queryset.filter(status='completed').aggregate(
            total=Sum('rupees_amount')
        )['total'] or 0

        extra_context.update({
            'total_withdrawals': total_withdrawals,
            'pending_count': pending_count,
            'completed_count': completed_count,
            'failed_count': failed_count,
            'total_pending_amount': f'₹{total_pending_amount:.2f}',
            'total_completed_amount': f'₹{total_completed_amount:.2f}',
        })

        return super().changelist_view(request, extra_context)

    # JavaScript for quick actions
    class Media:
        js = ('admin/js/withdrawal_admin.js',)
        css = {
            'all': ('admin/css/withdrawal_admin.css',)
        }

    def approve_withdrawal(self, request, queryset):
        """
        Approve selected withdrawals and mark as completed.
        This action marks withdrawals as processed and ready for manual payment.
        """
        updated = 0
        for withdrawal in queryset:
            if withdrawal.status == 'pending':
                try:
                    # Update withdrawal status
                    withdrawal.status = 'completed'
                    withdrawal.processed_at = timezone.now()
                    withdrawal.completed_at = timezone.now()
                    withdrawal.admin_notes = (
                        f"Approved by {request.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    withdrawal.save()
                    updated += 1

                    # Log success
                    logger.info(
                        f"Withdrawal {withdrawal.id} approved by {request.user.username}. "
                        f"Amount: ₹{withdrawal.rupees_amount} to {withdrawal.upi_id}"
                    )

                    self.message_user(
                        request,
                        f"Withdrawal {str(withdrawal.id)[:8]}... approved. "
                        f"User {withdrawal.user_id} will receive ₹{withdrawal.rupees_amount} to {withdrawal.upi_id}",
                        level='SUCCESS'
                    )
                except Exception as e:
                    logger.error(f"Error approving withdrawal {withdrawal.id}: {str(e)}")
                    self.message_user(
                        request,
                        f"Error approving withdrawal {str(withdrawal.id)[:8]}...: {str(e)}",
                        level='ERROR'
                    )
            else:
                self.message_user(
                    request,
                    f"Cannot approve withdrawal {str(withdrawal.id)[:8]}... - status is {withdrawal.status}",
                    level='WARNING'
                )

        if updated > 0:
            self.message_user(
                request,
                f"Successfully approved {updated} withdrawal(s). Ready for manual payment processing.",
                level='SUCCESS'
            )

    approve_withdrawal.short_description = "✓ Approve selected withdrawals"

    def reject_withdrawal(self, request, queryset):
        """
        Reject selected withdrawals and automatically refund coins to users.
        This action reverses the coin deduction and creates audit trail.
        """
        from django.db import transaction
        updated = 0

        for withdrawal in queryset:
            if withdrawal.status in ['pending', 'processing']:
                try:
                    with transaction.atomic():
                        # Get and lock user coins record
                        user_coins = models.UserCoins.objects.select_for_update().get(
                            user_id=withdrawal.user_id
                        )

                        # Refund coins
                        original_balance = user_coins.total_coins
                        user_coins.total_coins += withdrawal.coins_amount
                        user_coins.coins_spent -= withdrawal.coins_amount
                        user_coins.save()

                        # Create transaction record for audit trail
                        models.CoinTransaction.objects.create(
                            user_coins=user_coins,
                            amount=withdrawal.coins_amount,
                            transaction_type='refund',
                            reason=f"Withdrawal rejected - refund for {withdrawal.id}"
                        )

                        # Update withdrawal status
                        withdrawal.status = 'failed'
                        withdrawal.failure_reason = (
                            f"Rejected by admin {request.user.username} on "
                            f"{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        withdrawal.processed_at = timezone.now()
                        withdrawal.save()

                        updated += 1

                        # Log the refund
                        logger.info(
                            f"Withdrawal {withdrawal.id} rejected by {request.user.username}. "
                            f"Refunded {withdrawal.coins_amount} coins to user {withdrawal.user_id}. "
                            f"Balance: {original_balance} → {user_coins.total_coins}"
                        )

                        self.message_user(
                            request,
                            f"Withdrawal {str(withdrawal.id)[:8]}... rejected. "
                            f"{withdrawal.coins_amount} coins refunded to user {withdrawal.user_id}",
                            level='SUCCESS'
                        )

                except models.UserCoins.DoesNotExist:
                    logger.error(f"User coins record not found for user {withdrawal.user_id}")
                    self.message_user(
                        request,
                        f"Cannot reject withdrawal {str(withdrawal.id)[:8]}... - user coins record not found",
                        level='ERROR'
                    )
                except Exception as e:
                    logger.error(f"Error rejecting withdrawal {withdrawal.id}: {str(e)}")
                    self.message_user(
                        request,
                        f"Error rejecting withdrawal {str(withdrawal.id)[:8]}...: {str(e)}",
                        level='ERROR'
                    )
            else:
                self.message_user(
                    request,
                    f"Cannot reject withdrawal {str(withdrawal.id)[:8]}... - status is {withdrawal.status}",
                    level='WARNING'
                )

        if updated > 0:
            self.message_user(
                request,
                f"Successfully rejected {updated} withdrawal(s) with automatic coin refunds.",
                level='SUCCESS'
            )

    reject_withdrawal.short_description = "✗ Reject selected withdrawals (refunds coins)"

    def has_add_permission(self, request):
        """Disable adding withdrawals directly - they must be created through API"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deleting withdrawals for audit trail integrity"""
        return False
