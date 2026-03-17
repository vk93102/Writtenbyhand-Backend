"""
Simple Email/Password Authentication Views
JWT token-based authentication system with password reset
"""

import jwt
import re
import secrets
from datetime import datetime, timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password, check_password
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

# Secret key for JWT (should be in settings.py for production)
JWT_SECRET = getattr(settings, 'SECRET_KEY', 'your-secret-key-change-this')
JWT_ALGORITHM = 'HS256'
JWT_EXP_DELTA_SECONDS = 60 * 60 * 24 * 7  # 7 days


def generate_jwt_token(user):
    """Generate JWT token for authenticated user"""
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(seconds=JWT_EXP_DELTA_SECONDS),
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def validate_jwt_token(token):
    """Validate JWT token and return user_id"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get('user_id'), payload
    except jwt.ExpiredSignatureError:
        return None, {'error': 'Token has expired'}
    except jwt.InvalidTokenError:
        return None, {'error': 'Invalid token'}


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    return True, "Password is valid"


@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    """
    User Registration with Email and Password
    POST /api/auth/register/
    Body: {
        "username": "user123",
        "email": "user@example.com",
        "password": "password123",
        "full_name": "John Doe" (optional)
    }
    """

    def post(self, request):
        try:
            username = request.data.get('username', '').strip()
            email = request.data.get('email', '').strip().lower()
            password = request.data.get('password', '')
            full_name = request.data.get('full_name', '').strip()

            # Validation
            if not username or not email or not password:
                return Response({
                    'success': False,
                    'error': 'Username, email, and password are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate username
            if len(username) < 3:
                return Response({
                    'success': False,
                    'error': 'Username must be at least 3 characters long'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not username.isalnum() and '_' not in username:
                return Response({
                    'success': False,
                    'error': 'Username can only contain letters, numbers, and underscores'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate email
            if not validate_email(email):
                return Response({
                    'success': False,
                    'error': 'Invalid email format'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate password
            is_valid, message = validate_password(password)
            if not is_valid:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if username already exists
            if User.objects.filter(username=username).exists():
                return Response({
                    'success': False,
                    'error': 'Username already taken'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if email already exists
            if User.objects.filter(email=email).exists():
                return Response({
                    'success': False,
                    'error': 'Email already registered'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Create user
            user = User.objects.create(
                username=username,
                email=email,
                password=make_password(password),
                first_name=full_name.split(' ')[0] if full_name else '',
                last_name=' '.join(full_name.split(' ')[1:]) if full_name and len(full_name.split(' ')) > 1 else ''
            )

            # Generate JWT token
            token = generate_jwt_token(user)

            # Create user coins record
            from .models import UserCoins
            UserCoins.objects.create(
                user_id=str(user.id),
                total_coins=0,
                lifetime_coins=0,
            )

            logger.info(f"New user registered: {username} ({email})")

            return Response({
                'success': True,
                'message': 'Registration successful',
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': f"{user.first_name} {user.last_name}".strip(),
                    'token': token,
                    'created_at': user.date_joined.isoformat()
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred during registration'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    """
    User Login with Email/Username and Password
    POST /api/auth/login/
    Body: {
        "username": "user123" or "email": "user@example.com",
        "password": "password123"
    }
    """

    def post(self, request):
        try:
            username_or_email = (
                request.data.get('username') or
                request.data.get('email') or
                request.data.get('identifier') or
                request.data.get('username_or_email', '')
            )
            username_or_email = (username_or_email or '').strip()
            password = request.data.get('password', '')

            logger.debug(f"Login attempt: username_or_email={username_or_email}, password_length={len(password)}")

            if not username_or_email or not password:
                return Response({
                    'success': False,
                    'error': 'Username/email and password are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Determine whether this is an email or username and perform case-insensitive lookup
            user = None
            if '@' in username_or_email:
                email_val = username_or_email.lower()
                try:
                    user = User.objects.filter(email__iexact=email_val).first()
                    logger.debug(f"Email lookup for: {email_val} -> {user and user.username}")
                except Exception:
                    user = None
            else:
                uname = username_or_email
                try:
                    user = User.objects.filter(username__iexact=uname).first()
                    logger.debug(f"Username lookup for: {uname} -> {user and user.username}")
                except Exception:
                    user = None

            # Invalid credentials - differentiate between user not found and wrong password
            if not user:
                logger.info(f"Login failed - no matching user for identifier: {username_or_email}")
                return Response({
                    'success': False,
                    'error': 'User not found. Please check your username/email or sign up for a new account.',
                    'error_code': 'USER_NOT_FOUND'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Use User method to check password (handles hashing)
            if not user.check_password(password):
                logger.info(f"Login failed - invalid password for user: {user.username}")
                return Response({
                    'success': False,
                    'error': 'Incorrect password. Please try again.',
                    'error_code': 'INVALID_PASSWORD'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Generate JWT token
            token = generate_jwt_token(user)

            # Get user coins
            from .models import UserCoins
            user_coins_obj, created = UserCoins.objects.get_or_create(
                user_id=str(user.id),
                defaults={'total_coins': 0, 'lifetime_coins': 0}
            )

            logger.info(f"User logged in: {user.username}")

            return Response({
                'success': True,
                'message': 'Login successful',
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': f"{user.first_name} {user.last_name}".strip(),
                    'token': token,
                    'coins': user_coins_obj.total_coins,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred during login'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class VerifyTokenView(APIView):
    """
    Verify JWT token and return user info
    GET /api/auth/verify/
    Headers: Authorization: Bearer <token>
    """

    def get(self, request):
        try:
            # Get token from header
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return Response({
                    'success': False,
                    'error': 'Invalid authorization header'
                }, status=status.HTTP_401_UNAUTHORIZED)

            token = auth_header.split(' ')[1]
            user_id, payload = validate_jwt_token(token)

            if not user_id:
                return Response({
                    'success': False,
                    'error': payload.get('error', 'Invalid token')
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Get user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get user coins
            from .models import UserCoins
            user_coins_obj, created = UserCoins.objects.get_or_create(
                user_id=str(user.id),
                defaults={'total_coins': 0, 'lifetime_coins': 0}
            )

            return Response({
                'success': True,
                'data': {
                    'user_id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': f"{user.first_name} {user.last_name}".strip(),
                    'coins': user_coins_obj.total_coins,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined.isoformat()
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return Response({
                'success': False,
                'error': 'Token verification failed'
            }, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(csrf_exempt, name='dispatch')
class ChangePasswordView(APIView):
    """
    Change user password using email (no token required)
    POST /api/auth/change-password/
    Body: {
        "email": "user@example.com",
        "old_password": "oldpass123",
        "new_password": "newpass123"
    }
    """

    def post(self, request):
        try:
            email = request.data.get('email', '').strip().lower()
            old_password = request.data.get('old_password', '')
            new_password = request.data.get('new_password', '')

            if not email or not old_password or not new_password:
                return Response({
                    'success': False,
                    'error': 'Email, old password, and new password are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get user by email
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'User not found with this email'
                }, status=status.HTTP_404_NOT_FOUND)

            # Verify old password
            if not check_password(old_password, user.password):
                return Response({
                    'success': False,
                    'error': 'Incorrect old password'
                }, status=status.HTTP_401_UNAUTHORIZED)

            # Validate new password
            is_valid, message = validate_password(new_password)
            if not is_valid:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)

            # Update password
            user.password = make_password(new_password)
            user.save()

            logger.info(f"Password changed for user: {user.username}")

            return Response({
                'success': True,
                'message': 'Password changed successfully'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Password change error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred while changing password'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class RequestPasswordResetView(APIView):
    """
    Request password reset via email
    POST /api/auth/request-password-reset/
    Body: {
        "email": "user@example.com"
    }
    Sends an email with a reset link
    """

    def post(self, request):
        try:
            email = request.data.get('email', '').strip().lower()

            if not email:
                return Response({
                    'success': False,
                    'error': 'Email is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if user exists
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # For security, don't reveal if email exists
                return Response({
                    'success': True,
                    'message': 'If an account with this email exists, you will receive a password reset link'
                }, status=status.HTTP_200_OK)

            # Generate reset token
            from .models import PasswordResetToken
            from django.utils import timezone
            
            # Invalidate old tokens
            PasswordResetToken.objects.filter(user=user, is_used=False).delete()
            
            reset_token = secrets.token_urlsafe(32)
            expires_at = timezone.now() + timedelta(hours=24)
            
            reset_obj = PasswordResetToken.objects.create(
                user=user,
                token=reset_token,
                expires_at=expires_at
            )

            # Build reset link (frontend URL)
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')
            reset_link = f"{frontend_url}/reset-password?token={reset_token}"

            # Send email
            try:
                send_mail(
                    subject='Password Reset Request',
                    message=(
                        "Hello %s,\n\n"
                        "We received a request to reset your password. Click the link below to reset it:\n\n"
                        "%s\n\n"
                        "This link will expire in 24 hours.\n\n"
                        "If you didn't request this, you can safely ignore this email.\n\n"
                        "Best regards,\nEdTech Support Team"
                    ) % (user.first_name or user.username, reset_link),
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@edtech.com'),
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                logger.info(f"Password reset email sent to: {email}")
            except Exception as e:
                logger.error(f"Failed to send reset email: {str(e)}")
                # Still return success to not reveal if email failed
                pass

            return Response({
                'success': True,
                'message': 'If an account with this email exists, you will receive a password reset link'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Password reset request error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred while processing your request'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ValidateResetTokenView(APIView):
    """
    Validate password reset token
    POST /api/auth/validate-reset-token/
    Body: {
        "token": "reset_token_here"
    }
    """

    def post(self, request):
        try:
            token = request.data.get('token', '').strip()

            if not token:
                return Response({
                    'success': False,
                    'error': 'Token is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            from .models import PasswordResetToken
            from django.utils import timezone

            try:
                reset_obj = PasswordResetToken.objects.get(token=token)
            except PasswordResetToken.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Invalid or expired token'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if token is valid
            if not reset_obj.is_valid():
                return Response({
                    'success': False,
                    'error': 'Token has expired or has already been used'
                }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'success': True,
                'data': {
                    'email': reset_obj.user.email,
                    'user_id': reset_obj.user.id,
                    'username': reset_obj.user.username
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred while validating token'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ResetPasswordView(APIView):
    """
    Reset password using reset token
    POST /api/auth/reset-password/
    Body: {
        "token": "reset_token_here",
        "new_password": "newpassword123"
    }
    """

    def post(self, request):
        try:
            token = request.data.get('token', '').strip()
            new_password = request.data.get('new_password', '')

            if not token or not new_password:
                return Response({
                    'success': False,
                    'error': 'Token and new password are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate new password
            is_valid, message = validate_password(new_password)
            if not is_valid:
                return Response({
                    'success': False,
                    'error': message
                }, status=status.HTTP_400_BAD_REQUEST)

            from .models import PasswordResetToken
            from django.utils import timezone

            try:
                reset_obj = PasswordResetToken.objects.get(token=token)
            except PasswordResetToken.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Invalid or expired token'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if token is valid
            if not reset_obj.is_valid():
                return Response({
                    'success': False,
                    'error': 'Token has expired or has already been used'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Update password
            user = reset_obj.user
            user.password = make_password(new_password)
            user.save()

            # Mark token as used
            reset_obj.is_used = True
            reset_obj.used_at = timezone.now()
            reset_obj.save()

            logger.info(f"Password reset successful for user: {user.username}")

            return Response({
                'success': True,
                'message': 'Password reset successfully. You can now login with your new password.'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            return Response({
                'success': False,
                'error': 'An error occurred while resetting password'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)