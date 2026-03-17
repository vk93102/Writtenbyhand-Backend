"""
URL configuration for question_solver app
"""

from django.urls import path
from .views import (
    QuestionSolverView, 
    HealthCheckView, 
    ServiceStatusView, 
    QuizGeneratorView, 
    FlashcardGeneratorView,
    StudyMaterialGeneratorView,
    QuizGenerateView,
    QuizSubmitView,
    QuizResultsView,
    QuizDetailView,
    PredictedQuestionsView
)
from .subscription_views import (
    SubscriptionStatusView,
    LogFeatureUsageView
)
from .auth_views import (
    GoogleOAuthCallbackView,
    TokenRefreshView,
    UserProfileView,
    LogoutView
)
from .simple_auth_views import (
    RegisterView,
    LoginView,
    VerifyTokenView,
    ChangePasswordView,
    RequestPasswordResetView,
    ValidateResetTokenView,
    ResetPasswordView
)
from .payment_views import (
    CreatePaymentOrderView,
    VerifyPaymentView,
    PaymentStatusView,
    PaymentHistoryView,
    RefundPaymentView,
    RazorpayKeyView
)
from .razorpay_views import (
    create_razorpay_order,
    verify_razorpay_payment,
    get_razorpay_key,
    get_payment_status,
    get_payment_history,
    request_coin_withdrawal,
    get_withdrawal_history,
    get_withdrawal_status,
    cancel_withdrawal,
    razorpay_webhook
)
from .withdrawal_views import (
    withdraw_coins,
    get_withdrawal_history,
    get_withdrawal_details,
    cancel_withdrawal
)
from .daily_quiz_views import (
    get_daily_quiz,
    start_daily_quiz,
    submit_daily_quiz,
    get_user_coins,
    get_quiz_history,
    get_daily_quiz_attempt_detail,
    get_quiz_settings,
)
from .pair_quiz_views import (
    CreatePairQuizView,
    JoinPairQuizView,
    PairQuizSessionView,
    CancelPairQuizView
)
from .premium_subscription_views import (
    GetSubscriptionPlansView
)
from .usage_api_views import (
    usage_dashboard,
    feature_status,
    check_feature_usage,
    record_feature_usage,
    subscription_status,
    usage_stats,
    real_time_usage,
    usage_history,
    test_feature_restriction,
    test_multiple_features,
    enforce_usage_check,
    feature_restriction_details
)
from .subscription_endpoints import (
    get_razorpay_key as get_razorpay_key_new
)
from .admin_users_views import (
    get_all_users,
    get_feature_users,
    get_user_detail,
    get_usage_analytics,
    search_users
)
from .ask_question_views import (
    ask_question_search,
    ask_question_with_sources,
    get_search_status
)

urlpatterns = [
    path('solve/', QuestionSolverView.as_view(), name='solve-question'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('status/', ServiceStatusView.as_view(), name='service-status'),
    
    # ✅ SPECIFIC QUIZ PATHS (MUST BE BEFORE GENERIC <str:quiz_id> PATTERNS)
    path('quiz/generate/', QuizGeneratorView.as_view(), name='generate-quiz'),
    path('quiz/create/', QuizGenerateView.as_view(), name='create-quiz'),
    path('quiz/settings/', get_quiz_settings, name='quiz-settings'),
    
    # Daily Quiz endpoints (MUST BE BEFORE generic quiz/<str:quiz_id>/ pattern)
    path('quiz/daily-quiz/', get_daily_quiz, name='daily-quiz'),
    path('quiz/daily-quiz/start/', start_daily_quiz, name='start-daily-quiz'),
    path('quiz/daily-quiz/submit/', submit_daily_quiz, name='submit-daily-quiz'),
    path('quiz/daily-quiz/coins/', get_user_coins, name='user-coins'),
    path('quiz/daily-quiz/history/', get_quiz_history, name='quiz-history'),
    path('quiz/daily-quiz/attempt/detail/', get_daily_quiz_attempt_detail, name='daily-quiz-attempt-detail'),
    
    # ✅ GENERIC QUIZ PATTERNS (AFTER SPECIFIC ONES)
    path('quiz/<str:quiz_id>/', QuizDetailView.as_view(), name='quiz-detail'),
    path('quiz/<str:quiz_id>/submit/', QuizSubmitView.as_view(), name='submit-quiz'),
    path('quiz/<str:response_id>/results/', QuizResultsView.as_view(), name='quiz-results'),
    
    path('predicted-questions/generate/', PredictedQuestionsView.as_view(), name='predicted-questions'),
    path('flashcards/generate/', FlashcardGeneratorView.as_view(), name='generate-flashcards'),
    path('study-material/generate/', StudyMaterialGeneratorView.as_view(), name='generate-study-material'),
    
    # Subscription and Pricing endpoints
    path('subscription/status/', SubscriptionStatusView.as_view(), name='subscription-status'),
    path('subscription/log-usage/', LogFeatureUsageView.as_view(), name='log-usage'),
    
    # Authentication endpoints (Google OAuth)
    path('auth/google/callback/', GoogleOAuthCallbackView.as_view(), name='google-oauth-callback'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    
    # Authentication endpoints (Email/Password)
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/verify/', VerifyTokenView.as_view(), name='verify-token'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/request-password-reset/', RequestPasswordResetView.as_view(), name='request-password-reset'),
    path('auth/validate-reset-token/', ValidateResetTokenView.as_view(), name='validate-reset-token'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    # Payment endpoints (Razorpay)
    path('payment/create-order/', CreatePaymentOrderView.as_view(), name='create-payment-order'),
    path('payment/verify/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('payment/status/', PaymentStatusView.as_view(), name='payment-status'),
    path('payment/history/', PaymentHistoryView.as_view(), name='payment-history'),
    path('payment/refund/', RefundPaymentView.as_view(), name='refund-payment'),
    path('payment/razorpay-key/', RazorpayKeyView.as_view(), name='razorpay-key'),
    
    # Razorpay Integration endpoints (New)
    path('razorpay/create-order/', create_razorpay_order, name='razorpay-create-order'),
    path('razorpay/verify-payment/', verify_razorpay_payment, name='razorpay-verify-payment'),
    path('razorpay/key/', get_razorpay_key, name='razorpay-get-key'),
    path('razorpay/status/<str:order_id>/', get_payment_status, name='razorpay-payment-status'),
    path('razorpay/history/', get_payment_history, name='razorpay-payment-history'),
    path('razorpay/webhook/', razorpay_webhook, name='razorpay-webhook'),
    
    # Razorpay Coin Withdrawal endpoints (Production-ready - Simplified)
    path('razorpay/withdraw/', withdraw_coins, name='razorpay-withdraw'),
    path('razorpay/withdraw/history/', get_withdrawal_history, name='razorpay-withdrawal-history'),
    path('razorpay/withdraw/status/', get_withdrawal_details, name='razorpay-withdrawal-status'),
    path('razorpay/withdraw/cancel/', cancel_withdrawal, name='razorpay-withdraw-cancel'),
    
    # Pair Quiz endpoints
    path('pair-quiz/create/', CreatePairQuizView.as_view(), name='create-pair-quiz'),
    path('pair-quiz/join/', JoinPairQuizView.as_view(), name='join-pair-quiz'),
    path('pair-quiz/<str:session_id>/', PairQuizSessionView.as_view(), name='pair-quiz-session'),
    path('pair-quiz/<str:session_id>/cancel/', CancelPairQuizView.as_view(), name='cancel-pair-quiz'),
    
    # Usage Dashboard & Feature Tracking endpoints (NEW)
    path('usage/dashboard/', usage_dashboard, name='usage-dashboard'),
    path('usage/feature/<str:feature_name>/', feature_status, name='feature-status'),
    path('usage/check/', check_feature_usage, name='check-feature-usage'),
    path('usage/record/', record_feature_usage, name='record-feature-usage'),
    path('usage/subscription/', subscription_status, name='usage-subscription-status'),
    path('usage/stats/', usage_stats, name='usage-stats'),
    
    # Real-time Usage Tracking endpoints (NEW)
    path('usage/real-time/', real_time_usage, name='usage-real-time'),
    path('usage/history/', usage_history, name='usage-history'),
    
    # Usage Restriction Test & Enforcement endpoints (NEW)
    path('usage/test/restriction/', test_feature_restriction, name='test-restriction'),
    path('usage/test/all-features/', test_multiple_features, name='test-all-features'),
    path('usage/enforce-check/', enforce_usage_check, name='enforce-usage-check'),
    path('usage/restriction/<str:feature_name>/', feature_restriction_details, name='feature-restriction-details'),
    
    # Admin Users Dashboard endpoints (NEW)
    path('admin/users/', get_all_users, name='admin-get-users'),
    path('admin/users/search/', search_users, name='admin-search-users'),
    path('admin/users/<str:user_id>/', get_user_detail, name='admin-user-detail'),
    path('admin/users/feature/<str:feature_name>/', get_feature_users, name='admin-feature-users'),
    path('admin/analytics/', get_usage_analytics, name='admin-analytics'),
    
    # ✅ NEW: Subscription & Pricing Management endpoints (Plan A & B)
    path('subscription/plans/', GetSubscriptionPlansView.as_view(), name='subscription-plans'),
    
    # ✅ NEW: Ask a Question - Search & Web Integration
    path('ask-question/search/', ask_question_search, name='ask-question-search'),
    path('ask-question/sources/', ask_question_with_sources, name='ask-question-sources'),
    path('ask-question/status/', get_search_status, name='search-status'),
]