"""
Production-Ready Coin Withdrawal API
Simple withdrawal system - deduct coins from user and create request for admin approval
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
import logging
import re
import uuid

from .models import UserCoins, CoinWithdrawal, CoinTransaction

logger = logging.getLogger(__name__)


def validate_upi_id(upi_id):
    """
    Validate UPI ID format: username@bankname
    Examples: user@okhdfcbank, name@ybl, mobile@airtel
    """
    if not upi_id or len(upi_id) < 5:
        return False
    
    upi_pattern = r'^[a-zA-Z0-9._-]+@[a-zA-Z0-9]+$'
    return bool(re.match(upi_pattern, upi_id))


@api_view(['POST'])
def withdraw_coins(request):
    """
    Create a coin withdrawal request - deduct coins immediately and send to admin panel
    
    Request body:
    {
        "user_id": "user_identifier",
        "amount": 500,  # minimum 100 coins
        "upi_id": "username@bankname"
    }
    
    Response (201 Created):
    {
        "success": true,
        "message": "Withdrawal request submitted successfully",
        "data": {
            "withdrawal_id": "uuid",
            "amount": 500,
            "upi_id": "username@bankname",
            "status": "pending",
            "remaining_coins": 1500,
            "created_at": "2026-01-09T15:30:00Z"
        }
    }
    
    Response (400 Bad Request):
    {
        "success": false,
        "error": "Invalid withdrawal amount",
        "details": "Minimum withdrawal is 100 coins"
    }
    """
    try:
        # Extract and validate request data
        user_id = request.data.get('user_id')
        amount = request.data.get('amount')
        upi_id = request.data.get('upi_id', '').strip()
        
        logger.info(f"[WITHDRAW] Request - User: {user_id}, Amount: {amount}, UPI: {upi_id}")
        
        # Validate required fields
        if not user_id:
            logger.warning("[WITHDRAW] Missing user_id")
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not amount:
            logger.warning("[WITHDRAW] Missing amount")
            return Response({
                'success': False,
                'error': 'amount is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not upi_id:
            logger.warning("[WITHDRAW] Missing upi_id")
            return Response({
                'success': False,
                'error': 'upi_id is required',
                'example': 'user@okhdfcbank'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate amount
        try:
            amount = int(amount)
        except (ValueError, TypeError):
            logger.warning(f"[WITHDRAW] Invalid amount format: {amount}")
            return Response({
                'success': False,
                'error': 'Invalid amount format',
                'details': 'Amount must be an integer'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        MIN_WITHDRAWAL = 100
        MAX_WITHDRAWAL = 100000
        
        if amount < MIN_WITHDRAWAL:
            logger.warning(f"[WITHDRAW] Amount too low: {amount}")
            return Response({
                'success': False,
                'error': 'Withdrawal amount too low',
                'details': f'Minimum withdrawal is {MIN_WITHDRAWAL} coins',
                'min_amount': MIN_WITHDRAWAL
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if amount > MAX_WITHDRAWAL:
            logger.warning(f"[WITHDRAW] Amount too high: {amount}")
            return Response({
                'success': False,
                'error': 'Withdrawal amount too high',
                'details': f'Maximum withdrawal is {MAX_WITHDRAWAL} coins',
                'max_amount': MAX_WITHDRAWAL
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate UPI ID
        if not validate_upi_id(upi_id):
            logger.warning(f"[WITHDRAW] Invalid UPI format: {upi_id}")
            return Response({
                'success': False,
                'error': 'Invalid UPI ID format',
                'details': 'UPI ID must be in format: username@bankname (e.g., user@okhdfcbank)',
                'example': 'user@okhdfcbank'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check user balance
        user_coins = UserCoins.objects.filter(user_id=user_id).first()
        if not user_coins:
            logger.warning(f"[WITHDRAW] User coins not found: {user_id}")
            return Response({
                'success': False,
                'error': 'User account not found',
                'available_coins': 0
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if user_coins.total_coins < amount:
            logger.warning(f"[WITHDRAW] Insufficient balance - User: {user_id}, Required: {amount}, Available: {user_coins.total_coins}")
            return Response({
                'success': False,
                'error': 'Insufficient coin balance',
                'details': f'You have {user_coins.total_coins} coins but requested {amount}',
                'available_coins': user_coins.total_coins
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create withdrawal request in atomic transaction
        with transaction.atomic():
            withdrawal_id = str(uuid.uuid4())
            rupees_amount = round(amount / 10, 2)  # 1 coin = 0.10 rupees
            
            # Create withdrawal record
            withdrawal = CoinWithdrawal.objects.create(
                id=withdrawal_id,
                user_id=user_id,
                coins_amount=amount,
                rupees_amount=rupees_amount,
                upi_id=upi_id,
                status='pending',
                admin_notes='Awaiting admin approval'
            )
            
            # Deduct coins immediately
            user_coins.total_coins -= amount
            user_coins.save()
            
            # Create transaction record
            CoinTransaction.objects.create(
                user_coins=user_coins,
                transaction_type='withdrawal',
                amount=amount,
                reason=f'Withdrawal request created - {withdrawal_id}'
            )
            
            logger.info(f"[WITHDRAW] Success - ID: {withdrawal_id}, User: {user_id}, Amount: {amount}, Coins: {user_coins.total_coins}")
        
        return Response({
            'success': True,
            'message': 'Withdrawal request submitted successfully. Admin will review and process your request.',
            'data': {
                'withdrawal_id': withdrawal_id,
                'amount': amount,
                'rupees_amount': float(rupees_amount),
                'upi_id': upi_id,
                'status': 'pending',
                'remaining_coins': user_coins.total_coins,
                'created_at': withdrawal.created_at.isoformat()
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"[WITHDRAW] Error: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_withdrawal_history(request):
    """
    Get withdrawal history for a user
    
    Query parameters:
    - user_id: User identifier (required)
    - limit: Number of records (default: 50, max: 100)
    - status: Filter by status (pending, processing, completed, failed)
    
    Response:
    {
        "success": true,
        "user_id": "user_id",
        "count": 5,
        "data": [
            {
                "id": "uuid",
                "amount": 500,
                "rupees_amount": 50.00,
                "upi_id": "user@okhdfcbank",
                "status": "pending",
                "created_at": "2026-01-09T15:30:00Z",
                "completed_at": null,
                "admin_notes": "..."
            }
        ]
    }
    """
    try:
        user_id = request.query_params.get('user_id')
        limit = int(request.query_params.get('limit', 50))
        status_filter = request.query_params.get('status')
        
        if not user_id:
            return Response({
                'success': False,
                'error': 'user_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        limit = min(limit, 100)
        
        logger.info(f"[HISTORY] Fetching for user: {user_id}, limit: {limit}, status: {status_filter}")
        
        # Query withdrawals
        query = CoinWithdrawal.objects.filter(user_id=user_id).order_by('-created_at')
        
        if status_filter:
            query = query.filter(status=status_filter)
        
        withdrawals = query[:limit]
        
        # Format response
        data = []
        for w in withdrawals:
            data.append({
                'id': str(w.id),
                'amount': w.coins_amount,
                'rupees_amount': float(w.rupees_amount),
                'upi_id': w.upi_id,
                'status': w.status,
                'created_at': w.created_at.isoformat(),
                'completed_at': w.completed_at.isoformat() if w.completed_at else None,
                'admin_notes': w.admin_notes
            })
        
        logger.info(f"[HISTORY] Found {len(data)} records for user {user_id}")
        
        return Response({
            'success': True,
            'user_id': user_id,
            'count': len(data),
            'data': data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[HISTORY] Error: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_withdrawal_details(request):
    """
    Get details of a specific withdrawal request
    
    Query parameters:
    - withdrawal_id: Withdrawal ID (required)
    
    Response:
    {
        "success": true,
        "data": {
            "id": "uuid",
            "user_id": "user_id",
            "amount": 500,
            "rupees_amount": 50.00,
            "upi_id": "user@okhdfcbank",
            "status": "pending",
            "created_at": "2026-01-09T15:30:00Z",
            "completed_at": null,
            "admin_notes": "..."
        }
    }
    """
    try:
        withdrawal_id = request.query_params.get('withdrawal_id')
        
        if not withdrawal_id:
            return Response({
                'success': False,
                'error': 'withdrawal_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"[DETAILS] Fetching: {withdrawal_id}")
        
        withdrawal = CoinWithdrawal.objects.filter(id=withdrawal_id).first()
        
        if not withdrawal:
            logger.warning(f"[DETAILS] Not found: {withdrawal_id}")
            return Response({
                'success': False,
                'error': 'Withdrawal not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            'success': True,
            'data': {
                'id': str(withdrawal.id),
                'user_id': withdrawal.user_id,
                'amount': withdrawal.coins_amount,
                'rupees_amount': float(withdrawal.rupees_amount),
                'upi_id': withdrawal.upi_id,
                'status': withdrawal.status,
                'created_at': withdrawal.created_at.isoformat(),
                'completed_at': withdrawal.completed_at.isoformat() if withdrawal.completed_at else None,
                'admin_notes': withdrawal.admin_notes,
                'failure_reason': withdrawal.failure_reason
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[DETAILS] Error: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def cancel_withdrawal(request):
    """
    Cancel a pending withdrawal request and refund coins
    
    Request body:
    {
        "withdrawal_id": "uuid",
        "reason": "optional cancellation reason"
    }
    
    Response:
    {
        "success": true,
        "message": "Withdrawal cancelled and coins refunded",
        "data": {
            "withdrawal_id": "uuid",
            "status": "cancelled",
            "refunded_coins": 500,
            "remaining_coins": 2000
        }
    }
    """
    try:
        withdrawal_id = request.data.get('withdrawal_id')
        reason = request.data.get('reason', 'User requested cancellation')
        
        if not withdrawal_id:
            return Response({
                'success': False,
                'error': 'withdrawal_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"[CANCEL] Attempting to cancel: {withdrawal_id}, Reason: {reason}")
        
        withdrawal = CoinWithdrawal.objects.filter(id=withdrawal_id).first()
        
        if not withdrawal:
            logger.warning(f"[CANCEL] Not found: {withdrawal_id}")
            return Response({
                'success': False,
                'error': 'Withdrawal not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Only pending withdrawals can be cancelled
        if withdrawal.status != 'pending':
            logger.warning(f"[CANCEL] Cannot cancel - Status: {withdrawal.status}, ID: {withdrawal_id}")
            return Response({
                'success': False,
                'error': f'Cannot cancel withdrawal with status: {withdrawal.status}',
                'current_status': withdrawal.status
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Refund coins in atomic transaction
        with transaction.atomic():
            user_coins = UserCoins.objects.get(user_id=withdrawal.user_id)
            user_coins.total_coins += withdrawal.coins_amount
            user_coins.save()
            
            # Update withdrawal status
            withdrawal.status = 'cancelled'
            withdrawal.admin_notes = f'Cancelled: {reason}'
            withdrawal.save()
            
            # Create refund transaction
            CoinTransaction.objects.create(
                user_coins=user_coins,
                transaction_type='refund',
                amount=withdrawal.coins_amount,
                reason=f'Withdrawal cancellation - {withdrawal_id}'
            )
            
            logger.info(f"[CANCEL] Success - ID: {withdrawal_id}, Refunded: {withdrawal.coins_amount}, Remaining: {user_coins.total_coins}")
        
        return Response({
            'success': True,
            'message': 'Withdrawal cancelled and coins refunded',
            'data': {
                'withdrawal_id': withdrawal_id,
                'status': 'cancelled',
                'refunded_coins': withdrawal.coins_amount,
                'remaining_coins': user_coins.total_coins
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[CANCEL] Error: {str(e)}", exc_info=True)
        return Response({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
