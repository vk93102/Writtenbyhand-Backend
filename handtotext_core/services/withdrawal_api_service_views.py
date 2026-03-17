"""
API Views for Withdrawal Service
Wraps WithdrawalService and AdminWithdrawalService for URL routing
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .withdrawal_service import WithdrawalService
from .admin_withdrawal_service import AdminWithdrawalService

logger = logging.getLogger(__name__)


# ============================================================================
# USER WITHDRAWAL ENDPOINTS
# ============================================================================

@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_withdrawal_request(request):
    """
    Create a new withdrawal request
    POST /api/withdrawal/create/
    
    Payload:
    {
        "coins_amount": 500,
        "upi_id": "user@upi"
    }
    """
    try:
        user_id = request.user.id
        coins_amount = request.data.get('coins_amount')
        upi_id = request.data.get('upi_id')
        
        result = WithdrawalService.create_withdrawal_request(
            user_id=user_id,
            coins_amount=coins_amount,
            upi_id=upi_id
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_201_CREATED)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f'Error creating withdrawal request: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["GET"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_withdrawal_history(request):
    """
    Get user's withdrawal history
    GET /api/withdrawal/history/
    """
    try:
        user_id = request.user.id
        
        result = WithdrawalService.get_withdrawal_history(user_id=user_id)
        
        return Response(result, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f'Error retrieving withdrawal history: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["GET"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_withdrawal_status(request, withdrawal_id):
    """
    Get status of a specific withdrawal
    GET /api/withdrawal/status/{withdrawal_id}/
    """
    try:
        user_id = request.user.id
        
        result = WithdrawalService.get_withdrawal_status(
            user_id=user_id,
            withdrawal_id=withdrawal_id
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        logger.error(f'Error retrieving withdrawal status: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_withdrawal(request, withdrawal_id):
    """
    Cancel a pending withdrawal request
    POST /api/withdrawal/cancel/{withdrawal_id}/
    """
    try:
        user_id = request.user.id
        
        result = WithdrawalService.cancel_withdrawal(
            user_id=user_id,
            withdrawal_id=withdrawal_id
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f'Error canceling withdrawal: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["GET"])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_withdrawals(request):
    """
    Get all pending withdrawals for the user
    GET /api/withdrawal/pending/
    """
    try:
        user_id = request.user.id
        
        result = WithdrawalService.get_pending_withdrawals(user_id=user_id)
        
        return Response(result, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f'Error retrieving pending withdrawals: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ============================================================================
# ADMIN WITHDRAWAL ENDPOINTS
# ============================================================================

@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_withdrawal(request, withdrawal_id):
    """
    Approve a withdrawal request (Admin only)
    POST /api/admin/withdrawal/approve/{withdrawal_id}/
    
    Payload (optional):
    {
        "admin_notes": "Approved for processing"
    }
    """
    try:
        admin_id = request.user.id
        admin_notes = request.data.get('admin_notes', '')
        
        result = AdminWithdrawalService.approve_withdrawal(
            withdrawal_id=withdrawal_id,
            admin_id=admin_id,
            admin_notes=admin_notes
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except PermissionError as e:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        logger.error(f'Error approving withdrawal: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_withdrawal(request, withdrawal_id):
    """
    Reject a withdrawal request (Admin only)
    POST /api/admin/withdrawal/reject/{withdrawal_id}/
    
    Payload:
    {
        "reason": "Invalid UPI ID",
        "admin_notes": "Check UPI details"
    }
    """
    try:
        admin_id = request.user.id
        reason = request.data.get('reason', '')
        admin_notes = request.data.get('admin_notes', '')
        
        result = AdminWithdrawalService.reject_withdrawal(
            withdrawal_id=withdrawal_id,
            admin_id=admin_id,
            reason=reason,
            admin_notes=admin_notes
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except PermissionError as e:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        logger.error(f'Error rejecting withdrawal: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["DELETE"])
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_withdrawal(request, withdrawal_id):
    """
    Delete a withdrawal request (Admin only)
    DELETE /api/admin/withdrawal/delete/{withdrawal_id}/
    """
    try:
        admin_id = request.user.id
        
        result = AdminWithdrawalService.delete_withdrawal(
            withdrawal_id=withdrawal_id,
            admin_id=admin_id
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except PermissionError as e:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        logger.error(f'Error deleting withdrawal: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@require_http_methods(["POST"])
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_completed(request, withdrawal_id):
    """
    Mark withdrawal as completed (Admin only)
    POST /api/admin/withdrawal/complete/{withdrawal_id}/
    """
    try:
        admin_id = request.user.id
        
        result = AdminWithdrawalService.mark_as_completed(
            withdrawal_id=withdrawal_id,
            admin_id=admin_id
        )
        
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        else:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
    
    except PermissionError as e:
        return Response({
            'success': False,
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        logger.error(f'Error marking withdrawal as completed: {str(e)}')
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
