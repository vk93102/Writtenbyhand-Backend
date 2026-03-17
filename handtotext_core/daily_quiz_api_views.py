from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from datetime import date
from .static_questions_bank import get_random_questions
from .models import (
    UserCoins,
    CoinTransaction,
    QuizSettings,
    DailyQuiz,
    DailyQuestion,
    UserDailyQuizAttempt,
)
import logging
import random
import uuid

logger = logging.getLogger(__name__)


@api_view(['GET'])
def get_daily_quiz(request):
    """
    Production-level: Fetch a random quiz with session storage
    
    Query params:
        user_id: str (default: 'anonymous')
        language: str (default: 'english', options: 'english', 'hindi')
        
    Returns:
        200 OK: {quiz_id, questions[], quiz_metadata}
        400 Bad Request: {error, message}
        500 Server Error: {error, message}
    """
    user_id = request.query_params.get('user_id', 'anonymous')
    language = request.query_params.get('language', 'english').lower()
    
    logger.info(f"[GET_DAILY_QUIZ] Request from user: {user_id} | Language: {language}")
    
    try:
        # Validate language parameter
        if language not in ['english', 'hindi']:
            logger.warning(f"[GET_DAILY_QUIZ] Invalid language: {language} - defaulting to english")
            language = 'english'
        
        # Get 5 truly random questions from static bank
        all_questions = get_random_questions(language=language, count=100)
        
        if not all_questions or len(all_questions) == 0:
            logger.error(f"[GET_DAILY_QUIZ] No questions found for language: {language}")
            return Response({
                'error': 'Quiz unavailable',
                'message': f'No questions available for language: {language}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Select random subset
        selected_questions = random.sample(all_questions, min(5, len(all_questions)))
        
        logger.info(f"[GET_DAILY_QUIZ] ✅ Generated quiz with {len(selected_questions)} questions for user {user_id} ({language})")
        
        # Store questions in session for later validation
        try:
            request.session['quiz_questions'] = [
                {
                    'id': idx + 1,
                    'correct': q.get('correct', -1),
                    'question': q.get('question', '')
                }
                for idx, q in enumerate(selected_questions)
            ]
            request.session.modified = True
            logger.debug(f"[GET_DAILY_QUIZ] Session updated with {len(selected_questions)} questions")
        except Exception as session_error:
            logger.error(f"[GET_DAILY_QUIZ] Failed to store questions in session: {session_error}")
            return Response({
                'error': 'Session error',
                'message': 'Failed to store quiz in session'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Generate unique quiz ID
        quiz_id = str(uuid.uuid4())
        request.session['quiz_id'] = quiz_id
        request.session.modified = True
        
        # Prepare response
        response_data = {
            'quiz_id': quiz_id,
            'quiz_metadata': {
                'quiz_type': 'random_questions',
                'total_questions': len(selected_questions),
                'difficulty': 'medium',
                'date': str(date.today()),
                'title': f'Random Knowledge Quiz ({language.capitalize()})',
                'description': 'Test your knowledge with random questions!',
                'language': language,
                'question_bank_size': 100,
                'coins_per_correct': QuizSettings.get_settings().daily_quiz_coins_per_correct,
            },
            'questions': [
                {
                    'id': idx + 1,
                    'question': q.get('question', ''),
                    'options': q.get('options', []),
                    'category': q.get('category', 'general'),
                    'difficulty': q.get('difficulty', 'medium'),
                }
                for idx, q in enumerate(selected_questions)
            ],
        }
        
        logger.info(f"[GET_DAILY_QUIZ] Returning quiz {quiz_id} to user {user_id}")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[GET_DAILY_QUIZ] Exception: {str(e)}", exc_info=True)
        return Response({
            'error': 'Internal server error',
            'message': 'Failed to generate quiz. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def start_daily_quiz(request):
    """
    Mark the Daily Quiz as started for a user
    """
    try:
        user_id = request.data.get('user_id', 'anonymous')
        language = request.data.get('language', 'english').lower()
        
        logger.info(f"[START_DAILY_QUIZ] User {user_id} started quiz ({language})")
        
        return Response({
            'success': True,
            'message': 'Quiz started. Answer the questions and submit.',
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"[START_DAILY_QUIZ] Error: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def submit_daily_quiz(request):
    """
    Production-level: Submit quiz answers, validate, and award coins
    
    Request body:
        {
            "user_id": str,
            "language": str (optional, default: 'english'),
            "answers": {str(question_id): int(answer_index), ...}
        }
        
    Returns:
        200 OK: {success, message, correct_count, total_questions, coins_earned, results[]}
        400 Bad Request: {error, message}
        500 Server Error: {error, message}
    """
    user_id = request.data.get('user_id', 'anonymous')
    language = request.data.get('language', 'english').lower()
    answers = request.data.get('answers', {})
    
    logger.info(f"[SUBMIT_DAILY_QUIZ] Submission from user: {user_id} | Language: {language}")
    
    try:
        # ===== INPUT VALIDATION =====
        if not answers or not isinstance(answers, dict):
            logger.warning(f"[SUBMIT_DAILY_QUIZ] Missing or invalid answers from user {user_id}")
            return Response({
                'error': 'Invalid request',
                'message': 'answers field is required and must be a dictionary'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ===== RETRIEVE SESSION DATA =====
        quiz_questions = request.session.get('quiz_questions', [])
        quiz_id = request.session.get('quiz_id', '')
        
        if not quiz_questions or len(quiz_questions) == 0:
            logger.warning(f"[SUBMIT_DAILY_QUIZ] No quiz in session for user {user_id}")
            return Response({
                'error': 'Session expired',
                'message': 'Quiz session not found. Please reload the quiz and try again.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.debug(f"[SUBMIT_DAILY_QUIZ] Retrieved {len(quiz_questions)} questions from session")
        
        # ===== ANSWER VALIDATION =====
        correct_count = 0
        results = []
        
        for idx, q_data in enumerate(quiz_questions):
            question_id = idx + 1
            
            # Get user answer - support both string and int keys
            user_answer = answers.get(str(question_id)) or answers.get(question_id)
            
            # Convert to int, handle invalid values
            try:
                user_answer_idx = int(user_answer) if user_answer is not None else -1
            except (ValueError, TypeError):
                logger.warning(f"[SUBMIT_DAILY_QUIZ] Invalid answer format for Q{question_id}: {user_answer}")
                user_answer_idx = -1
            
            # Get correct answer
            correct_idx = q_data.get('correct', -1)
            
            # Check if correct
            is_correct = user_answer_idx == correct_idx and user_answer_idx >= 0
            
            if is_correct:
                correct_count += 1
                logger.debug(f"[SUBMIT_DAILY_QUIZ] Q{question_id}: CORRECT (answer: {user_answer_idx})")
            else:
                logger.debug(f"[SUBMIT_DAILY_QUIZ] Q{question_id}: INCORRECT (user: {user_answer_idx}, correct: {correct_idx})")
            
            # Store result
            results.append({
                'question_id': question_id,
                'user_answer': user_answer_idx,
                'correct_answer': correct_idx,
                'is_correct': is_correct,
            })
        
        logger.info(f"[SUBMIT_DAILY_QUIZ] User {user_id}: {correct_count}/{len(quiz_questions)} CORRECT")
        
        # ===== CALCULATE & AWARD COINS =====
        settings = QuizSettings.get_settings()
        coins_per_correct = settings.daily_quiz_coins_per_correct
        coins_earned = correct_count * coins_per_correct
        
        logger.info(f"[SUBMIT_DAILY_QUIZ] Coins calculation: {correct_count} correct × {coins_per_correct} = {coins_earned} coins")
        
        # Store coins in database (atomic transaction for consistency)
        try:
            with transaction.atomic():
                user_coins, created = UserCoins.objects.get_or_create(
                    user_id=user_id,
                    defaults={'total_coins': 0, 'lifetime_coins': 0}
                )
                
                old_balance = user_coins.total_coins
                user_coins.add_coins(
                    coins_earned,
                    reason=f"Daily Quiz ({language}) - {correct_count}/{len(quiz_questions)} correct (quiz_id: {quiz_id})"
                )
                new_balance = user_coins.total_coins
                
                logger.info(f"[SUBMIT_DAILY_QUIZ] Coins updated for user {user_id}: {old_balance} → {new_balance}")
        except Exception as coin_error:
            logger.error(f"[SUBMIT_DAILY_QUIZ] Failed to update coins: {coin_error}", exc_info=True)
            return Response({
                'error': 'Database error',
                'message': 'Failed to save coins. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # ===== CLEAN UP SESSION =====
        try:
            if 'quiz_questions' in request.session:
                del request.session['quiz_questions']
            if 'quiz_id' in request.session:
                del request.session['quiz_id']
            request.session.modified = True
            logger.debug(f"[SUBMIT_DAILY_QUIZ] Session cleared for user {user_id}")
        except Exception as session_error:
            logger.warning(f"[SUBMIT_DAILY_QUIZ] Failed to clear session: {session_error}")
        
        # ===== RETURN SUCCESS RESPONSE =====
        response_data = {
            'success': True,
            'message': f'Quiz submitted! You got {correct_count}/{len(quiz_questions)} correct and earned {coins_earned} coins.',
            'quiz_id': quiz_id,
            'correct_count': correct_count,
            'total_questions': len(quiz_questions),
            'coins_earned': coins_earned,
            'results': results,
            'user_coins': new_balance,
            'timestamp': str(date.today())
        }
        
        logger.info(f"[SUBMIT_DAILY_QUIZ] ✅ Success: User {user_id} quiz_id {quiz_id} - {correct_count}/{len(quiz_questions)} correct, +{coins_earned} coins")
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"[SUBMIT_DAILY_QUIZ] Exception: {str(e)}", exc_info=True)
        return Response({
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_user_coins(request):
    """
    Get user's coin balance and stats
    """
    user_id = request.query_params.get('user_id', 'anonymous')
    
    try:
        user_coins = UserCoins.objects.filter(user_id=user_id).first()
        
        if not user_coins:
            return Response({
                'user_id': user_id,
                'total_coins': 0,
                'lifetime_coins': 0,
                'coins_spent': 0,
            }, status=status.HTTP_200_OK)
        
        # Get recent transactions
        recent_transactions = CoinTransaction.objects.filter(
            user_coins=user_coins
        ).order_by('-created_at')[:10]
        
        transactions_data = [{
            'amount': t.amount,
            'type': t.transaction_type,
            'reason': t.reason,
            'created_at': t.created_at,
        } for t in recent_transactions]
        
        return Response({
            'user_id': user_id,
            'total_coins': user_coins.total_coins,
            'lifetime_coins': user_coins.lifetime_coins,
            'coins_spent': user_coins.coins_spent,
            'recent_transactions': transactions_data,
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_quiz_history(request):
    user_id = request.query_params.get('user_id', 'anonymous')
    limit = int(request.query_params.get('limit', 30))
    
    try:
        attempts = UserDailyQuizAttempt.objects.filter(
            user_id=user_id
        ).select_related('daily_quiz').order_by('-started_at')[:limit]
        
        history_data = []
        for attempt in attempts:
            history_data.append({
                'date': attempt.daily_quiz.date,
                'quiz_title': attempt.daily_quiz.title,
                'correct_count': attempt.correct_count,
                'total_questions': attempt.total_questions,
                'score_percentage': attempt.score_percentage,
                'coins_earned': attempt.coins_earned,
                'completed_at': attempt.completed_at,
            })
        
        total_attempts = attempts.count()
        total_coins_earned = sum(a.coins_earned for a in attempts)
        avg_score = sum(a.score_percentage for a in attempts) / total_attempts if total_attempts > 0 else 0
        
        return Response({
            'user_id': user_id,
            'history': history_data,
            'stats': {
                'total_attempts': total_attempts,
                'total_coins_earned': total_coins_earned,
                'average_score': round(avg_score, 2),
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_daily_quiz_attempt_detail(request):
    user_id = request.query_params.get('user_id', 'anonymous')
    quiz_id = request.query_params.get('quiz_id')

    if not quiz_id:
        return Response({'error': 'quiz_id is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        daily_quiz = DailyQuiz.objects.get(id=quiz_id, is_active=True)
        attempt = UserDailyQuizAttempt.objects.filter(daily_quiz=daily_quiz, user_id=user_id).first()

        if not attempt or not attempt.completed_at:
            return Response({'error': 'No completed attempt found for this user and quiz'}, status=status.HTTP_404_NOT_FOUND)

        questions = list(DailyQuestion.objects.filter(daily_quiz=daily_quiz).order_by('order')[:attempt.total_questions])
        results = []
        for idx, q in enumerate(questions, 1):
            user_answer_idx = attempt.answers.get(str(idx), -1)
            correct_idx = ord(q.correct_answer.upper()) - ord('A') if q.correct_answer else -1
            options = q.options if isinstance(q.options, list) else []
            user_answer_text = options[user_answer_idx] if 0 <= user_answer_idx < len(options) else 'No answer'
            correct_answer_text = options[correct_idx] if 0 <= correct_idx < len(options) else q.correct_answer

            results.append({
                'question_id': idx,
                'question': q.question_text,
                'options': options,
                'user_answer': user_answer_text,
                'user_answer_index': user_answer_idx,
                'correct_answer': correct_answer_text,
                'correct_answer_index': correct_idx,
                'is_correct': (user_answer_idx == correct_idx),
                'explanation': q.explanation,
                'fun_fact': q.fun_fact or '',
                'category': q.category,
            })

        return Response({
            'success': True,
            'quiz_id': str(daily_quiz.id),
            'date': str(daily_quiz.date),
            'results': results,
            'correct_count': attempt.correct_count,
            'total_questions': attempt.total_questions,
            'score_percentage': attempt.score_percentage,
            'coins_earned': attempt.coins_earned,
            'completed_at': attempt.completed_at,
        }, status=status.HTTP_200_OK)

    except DailyQuiz.DoesNotExist:
        return Response({'error': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error fetching attempt detail: {e}", exc_info=True)
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_quiz_settings(request):
    try:
        try:
            from .models import QuizSettings
            settings = QuizSettings.get_settings()
        except Exception as e:
            logger.warning(f"QuizSettings model not yet initialized: {e}")
            settings = None
        
        if settings:
            return Response({
                'success': True,
                'settings': {
                    'daily_quiz': {
                        'attempt_bonus': settings.daily_quiz_attempt_bonus,
                        'coins_per_correct': settings.daily_quiz_coins_per_correct,
                        'perfect_score_bonus': settings.daily_quiz_perfect_score_bonus,
                    },
                    'pair_quiz': {
                        'enabled': settings.pair_quiz_enabled,
                        'session_timeout': settings.pair_quiz_session_timeout,
                        'max_questions': settings.pair_quiz_max_questions,
                    },
                    'coin_system': {
                        'coin_to_currency_rate': float(settings.coin_to_currency_rate),
                        'min_coins_for_redemption': settings.min_coins_for_redemption,
                    }
                },
                'updated_at': settings.updated_at.isoformat() if settings.updated_at else None,
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': True,
                'settings': {
                    'daily_quiz': {
                        'attempt_bonus': 5,
                        'coins_per_correct': 5,
                        'perfect_score_bonus': 10,
                    },
                    'pair_quiz': {
                        'enabled': True,
                        'session_timeout': 30,
                        'max_questions': 20,
                    },
                    'coin_system': {
                        'coin_to_currency_rate': 0.10,
                        'min_coins_for_redemption': 10,
                    }
                },
                'updated_at': None,
                'note': 'Using default settings - database not fully initialized',
            }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error fetching quiz settings: {e}", exc_info=True)
        return Response({
            'success': True,
            'settings': {
                'daily_quiz': {
                    'attempt_bonus': 5,
                    'coins_per_correct': 5,
                    'perfect_score_bonus': 10,
                },
                'pair_quiz': {
                    'enabled': True,
                    'session_timeout': 30,
                    'max_questions': 20,
                },
                'coin_system': {
                    'coin_to_currency_rate': 0.10,
                    'min_coins_for_redemption': 10,
                }
            },
            'updated_at': None,
            'note': 'Using fallback default settings',
        }, status=status.HTTP_200_OK)
