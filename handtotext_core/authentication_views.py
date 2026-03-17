"""
Google OAuth Authentication Views
Handles login, signup, and token management
"""

import os
import json
import requests
import jwt
from datetime import datetime, timedelta
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class GoogleOAuthCallbackView(APIView):
    """
    Handle Google OAuth callback and exchange authorization code for tokens
    """

    @method_decorator(csrf_exempt)
    def post(self, request):
        """
        Exchange Google authorization code for access token
        Expected payload: {'code': 'authorization_code', 'provider': 'google', 'guest_user_id': 'optional_guest_id'}
        """
        try:
            code = request.data.get('code')
            provider = request.data.get('provider', 'google')
            guest_user_id = request.data.get('guest_user_id')  # Optional guest user ID for coin transfer

            if not code:
                return Response(
                    {'error': 'Authorization code is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if provider != 'google':
                return Response(
                    {'error': 'Invalid provider'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Exchange authorization code for tokens from Google
            google_tokens = self._exchange_code_for_tokens(code)
            if not google_tokens:
                return Response(
                    {'error': 'Failed to exchange authorization code'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get user info from Google ID token or userinfo endpoint
            user_info = self._get_user_info_from_google(google_tokens)
            if not user_info:
                return Response(
                    {'error': 'Failed to retrieve user information'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create or update user in database
            user, created = self._get_or_create_user(user_info, provider)

            # Transfer guest coins if guest_user_id provided
            coins_transferred = 0
            if guest_user_id and guest_user_id != str(user.id):
                coins_transferred = self._transfer_guest_coins(guest_user_id, str(user.id))

            # Generate JWT tokens
            tokens = self._generate_jwt_tokens(user)

            response_data = {
                'success': True,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                },
                'tokens': tokens,
                'is_new_user': created,
            }

            if coins_transferred > 0:
                response_data['coins_transferred'] = coins_transferred
                response_data['message'] = f'Welcome! {coins_transferred} coins from your guest session have been transferred to your account.'

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'Google OAuth callback error: {str(e)}')
            return Response(
                {'error': 'Authentication failed', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _exchange_code_for_tokens(self, code):
        """
        Exchange authorization code for Google tokens
        """
        try:
            token_url = 'https://oauth2.googleapis.com/token'
            
            payload = {
                'code': code,
                'client_id': os.getenv('GOOGLE_OAUTH_CLIENT_ID'),
                'client_secret': os.getenv('GOOGLE_OAUTH_CLIENT_SECRET'),
                'redirect_uri': os.getenv('GOOGLE_OAUTH_REDIRECT_URI'),
                'grant_type': 'authorization_code',
            }

            response = requests.post(token_url, data=payload)
            response.raise_for_status()
            
            return response.json()

        except requests.RequestException as e:
            logger.error(f'Token exchange error: {str(e)}')
            return None

    def _get_user_info_from_google(self, tokens):
        """
        Get user information from Google using access token or ID token
        """
        try:
            # Try to decode ID token first (more efficient)
            id_token = tokens.get('id_token')
            if id_token:
                # Decode without verification (Google tokens are trusted)
                import base64
                # Split the JWT and decode the payload
                parts = id_token.split('.')
                if len(parts) == 3:
                    # Add padding if necessary
                    payload = parts[1]
                    padding = 4 - len(payload) % 4
                    if padding != 4:
                        payload += '=' * padding
                    
                    decoded = base64.urlsafe_b64decode(payload)
                    user_info = json.loads(decoded)
                    return user_info

            # Fallback: use userinfo endpoint
            userinfo_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
            headers = {'Authorization': f"Bearer {tokens.get('access_token')}"}
            
            response = requests.get(userinfo_url, headers=headers)
            response.raise_for_status()
            
            return response.json()

        except Exception as e:
            logger.error(f'Get user info error: {str(e)}')
            return None

    def _get_or_create_user(self, user_info, provider):
        """
        Get or create user from OAuth user info
        """
        email = user_info.get('email')
        first_name = user_info.get('given_name', '')
        last_name = user_info.get('family_name', '')
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
            }
        )
        
        # Store OAuth provider info
        if created:
            user.oauth_provider = provider
            user.save()
        
        return user, created

    def _transfer_guest_coins(self, guest_user_id, authenticated_user_id):
        """
        Transfer coins from guest user to authenticated user
        Returns the number of coins transferred
        """
        from .models import UserCoins, CoinTransaction
        from django.db import transaction

        try:
            # Get guest user coins
            guest_coins = UserCoins.objects.filter(user_id=guest_user_id).first()
            if not guest_coins or guest_coins.total_coins <= 0:
                logger.info(f"No coins to transfer from guest user {guest_user_id}")
                return 0

            coins_to_transfer = guest_coins.total_coins

            with transaction.atomic():
                # Get or create authenticated user coins
                auth_coins, created = UserCoins.objects.get_or_create(
                    user_id=authenticated_user_id,
                    defaults={'total_coins': 0, 'lifetime_coins': 0}
                )

                # Transfer coins
                auth_coins.total_coins += coins_to_transfer
                auth_coins.lifetime_coins += coins_to_transfer
                auth_coins.save()

                # Create transaction record for the transfer
                CoinTransaction.objects.create(
                    user_coins=auth_coins,
                    transaction_type='bonus',
                    amount=coins_to_transfer,
                    reason=f'Coins transferred from guest session {guest_user_id}'
                )

                # Clear guest user coins
                guest_coins.total_coins = 0
                guest_coins.save()

                logger.info(f"Transferred {coins_to_transfer} coins from guest user {guest_user_id} to authenticated user {authenticated_user_id}")

            return coins_to_transfer

        except Exception as e:
            logger.error(f"Error transferring guest coins from {guest_user_id} to {authenticated_user_id}: {str(e)}")
            return 0

    def _generate_jwt_tokens(self, user):
        """
        Generate access and refresh JWT tokens
        """
        jwt_secret = os.getenv('JWT_SECRET', settings.SECRET_KEY)
        jwt_algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        expiration_hours = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))
        refresh_expiration_days = int(os.getenv('REFRESH_TOKEN_EXPIRATION_DAYS', '7'))

        now = datetime.utcnow()
        access_payload = {
            'user_id': user.id,
            'email': user.email,
            'username': user.username,
            'iat': now,
            'exp': now + timedelta(hours=expiration_hours),
            'type': 'access',
        }

        refresh_payload = {
            'user_id': user.id,
            'iat': now,
            'exp': now + timedelta(days=refresh_expiration_days),
            'type': 'refresh',
        }

        access_token = jwt.encode(access_payload, jwt_secret, algorithm=jwt_algorithm)
        refresh_token = jwt.encode(refresh_payload, jwt_secret, algorithm=jwt_algorithm)

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': expiration_hours * 3600,
        }


class TokenRefreshView(APIView):
    """
    Refresh access token using refresh token
    """

    def post(self, request):
        """
        Expected payload: {'refresh_token': 'token'}
        """
        try:
            refresh_token = request.data.get('refresh_token')
            if not refresh_token:
                return Response(
                    {'error': 'Refresh token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            jwt_secret = os.getenv('JWT_SECRET', settings.SECRET_KEY)
            jwt_algorithm = os.getenv('JWT_ALGORITHM', 'HS256')

            # Decode refresh token
            payload = jwt.decode(refresh_token, jwt_secret, algorithms=[jwt_algorithm])
            
            if payload.get('type') != 'refresh':
                return Response(
                    {'error': 'Invalid token type'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get user and generate new access token
            user = User.objects.get(id=payload['user_id'])
            tokens = self._generate_jwt_tokens(user)

            return Response({
                'success': True,
                'tokens': tokens,
            }, status=status.HTTP_200_OK)

        except jwt.ExpiredSignatureError:
            return Response(
                {'error': 'Refresh token has expired'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except jwt.InvalidTokenError:
            return Response(
                {'error': 'Invalid refresh token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f'Token refresh error: {str(e)}')
            return Response(
                {'error': 'Failed to refresh token'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _generate_jwt_tokens(self, user):
        """
        Generate access and refresh JWT tokens
        """
        jwt_secret = os.getenv('JWT_SECRET', settings.SECRET_KEY)
        jwt_algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        expiration_hours = int(os.getenv('JWT_EXPIRATION_HOURS', '24'))
        refresh_expiration_days = int(os.getenv('REFRESH_TOKEN_EXPIRATION_DAYS', '7'))

        now = datetime.utcnow()
        access_payload = {
            'user_id': user.id,
            'email': user.email,
            'username': user.username,
            'iat': now,
            'exp': now + timedelta(hours=expiration_hours),
            'type': 'access',
        }

        refresh_payload = {
            'user_id': user.id,
            'iat': now,
            'exp': now + timedelta(days=refresh_expiration_days),
            'type': 'refresh',
        }

        access_token = jwt.encode(access_payload, jwt_secret, algorithm=jwt_algorithm)
        refresh_token = jwt.encode(refresh_payload, jwt_secret, algorithm=jwt_algorithm)

        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': 'Bearer',
            'expires_in': expiration_hours * 3600,
        }


class UserProfileView(APIView):
    """
    Get user profile - requires valid JWT token
    """

    def get(self, request):
        """
        Get authenticated user profile
        Header: Authorization: Bearer <access_token>
        """
        try:
            # Get token from header
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if not auth_header.startswith('Bearer '):
                return Response(
                    {'error': 'Missing or invalid Authorization header'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            token = auth_header.split(' ')[1]
            jwt_secret = os.getenv('JWT_SECRET', settings.SECRET_KEY)
            jwt_algorithm = os.getenv('JWT_ALGORITHM', 'HS256')

            # Decode token
            payload = jwt.decode(token, jwt_secret, algorithms=[jwt_algorithm])
            
            user = User.objects.get(id=payload['user_id'])
            
            # Get user coins
            from .models import UserCoins, CoinWithdrawal
            from django.db.models import Sum
            
            user_coins = UserCoins.objects.filter(user_id=str(user.id)).first()
            total_coins = user_coins.total_coins if user_coins else 0
            lifetime_coins = user_coins.lifetime_coins if user_coins else 0
            
            # Get total withdrawn (completed withdrawals only)
            withdrawal_stats = CoinWithdrawal.objects.filter(
                user_id=str(user.id),
                status='completed'
            ).aggregate(
                total_coins=Sum('coins_amount'),
                total_rupees=Sum('rupees_amount')
            )
            
            total_withdrawn_coins = withdrawal_stats['total_coins'] or 0
            total_withdrawn_rupees = float(withdrawal_stats['total_rupees'] or 0)

            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'date_joined': user.date_joined.isoformat(),
                    'coins': total_coins,
                    'lifetime_coins': lifetime_coins,
                    'total_withdrawn_coins': total_withdrawn_coins,
                    'total_withdrawn_rupees': total_withdrawn_rupees,
                }
            }, status=status.HTTP_200_OK)

        except jwt.ExpiredSignatureError:
            return Response(
                {'error': 'Token has expired'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except jwt.InvalidTokenError:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f'Profile retrieval error: {str(e)}')
            return Response(
                {'error': 'Failed to retrieve profile'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LogoutView(APIView):
    """
    Logout endpoint - invalidates refresh token on client side
    """

    def post(self, request):
        """
        Logout user - client should discard tokens
        """
        return Response({
            'success': True,
            'message': 'Logged out successfully. Please discard your tokens.',
        }, status=status.HTTP_200_OK)
