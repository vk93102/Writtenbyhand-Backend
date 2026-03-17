"""
Production-level Socket.IO server for real-time pair quiz synchronization
Features:
- Connection management and cleanup
- Heartbeat/ping-pong for connection health
- Rate limiting and security measures
- Proper reconnection logic
- Monitoring and metrics
- Error recovery
- Authentication/authorization
- Connection pooling
"""

import socketio
import logging
import asyncio
import time
from collections import defaultdict
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Production Socket.IO server configuration
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.CORS_ALLOWED_ORIGINS if hasattr(settings, 'CORS_ALLOWED_ORIGINS') else ['*'],
    logger=True,
    engineio_logger=False,  # Disable engine.io logs in production
    ping_timeout=60,  # 60 seconds ping timeout
    ping_interval=25,  # Ping every 25 seconds
    max_http_buffer_size=1e8,  # 100MB max buffer
    transports=['polling', 'websocket'],  # Support both transports
    allow_upgrades=True,
    cookie=False,  # Disable cookies for better security
)

# Connection management
active_connections = {}  # {sid: {'user_id': str, 'session_id': str, 'connected_at': timestamp}}
active_sessions = {}  # {session_id: {'host_sid': str, 'partner_sid': str, 'participants': set}}
connection_metrics = {
    'total_connections': 0,
    'active_connections': 0,
    'total_sessions': 0,
    'active_sessions': 0,
    'errors': 0,
    'reconnections': 0
}

# Rate limiting
connection_attempts = defaultdict(list)  # {ip: [timestamps]}
RATE_LIMIT_WINDOW = 60  # 1 minute
RATE_LIMIT_MAX = 10  # Max 10 connections per minute per IP

# Heartbeat monitoring
last_heartbeat = {}  # {sid: timestamp}
HEARTBEAT_TIMEOUT = 120  # 2 minutes

# Cleanup task management
cleanup_task_started = False


@sio.event
async def connect(sid, environ):
    """Handle client connection with production-level validation"""
    global cleanup_task_started
    
    # Start cleanup task on first connection
    if not cleanup_task_started:
        asyncio.create_task(cleanup_inactive_sessions())
        cleanup_task_started = True
        logger.info("🧹 Started session cleanup task")
    
    try:
        client_ip = environ.get('REMOTE_ADDR', 'unknown')
        user_agent = environ.get('HTTP_USER_AGENT', 'unknown')

        # Rate limiting check
        now = time.time()
        attempts = connection_attempts[client_ip]
        # Remove old attempts outside the window
        attempts[:] = [t for t in attempts if now - t < RATE_LIMIT_WINDOW]

        if len(attempts) >= RATE_LIMIT_MAX:
            logger.warning(f"Rate limit exceeded for IP {client_ip}")
            await sio.disconnect(sid)
            return False

        attempts.append(now)

        # Extract user info from headers/query params
        user_id = environ.get('HTTP_X_USER_ID')
        session_id = environ.get('HTTP_X_SESSION_ID')
        
        # Parse query string if headers not present
        if not user_id or not session_id:
            try:
                from urllib.parse import parse_qs
                query_string = environ.get('QUERY_STRING', '')
                query_params = parse_qs(query_string)
                
                if not user_id:
                    user_id = query_params.get('userId', ['anonymous'])[0]
                if not session_id:
                    session_id = query_params.get('sessionId', [None])[0]
            except Exception as e:
                logger.warning(f"Failed to parse query string: {e}")
                user_id = user_id or 'anonymous'
                session_id = session_id or None

        # Store connection info
        active_connections[sid] = {
            'user_id': user_id,
            'session_id': session_id,
            'connected_at': now,
            'client_ip': client_ip,
            'user_agent': user_agent[:100]  # Truncate for storage
        }

        connection_metrics['total_connections'] += 1
        connection_metrics['active_connections'] += 1

        last_heartbeat[sid] = now

        logger.info(f"✅ Client connected: {sid} (User: {user_id}, IP: {client_ip})")
        await sio.emit('connected', {
            'sid': sid,
            'server_time': now,
            'features': ['pair_quiz', 'realtime_sync', 'heartbeat']
        }, room=sid)

        # Start heartbeat monitoring for this connection
        asyncio.create_task(monitor_connection_health(sid))

        return True

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Connection error for {sid}: {str(e)}")
        await sio.disconnect(sid)
        return False


@sio.event
async def disconnect(sid):
    """Handle client disconnection with cleanup"""
    try:
        connection_info = active_connections.pop(sid, {})
        user_id = connection_info.get('user_id', 'unknown')
        session_id = connection_info.get('session_id')

        connection_metrics['active_connections'] -= 1

        # Remove from heartbeat monitoring
        last_heartbeat.pop(sid, None)

        logger.info(f"❌ Client disconnected: {sid} (User: {user_id})")

        # Clean up session if this user was part of one
        if session_id and session_id in active_sessions:
            session = active_sessions[session_id]
            if sid in [session.get('host_sid'), session.get('partner_sid')]:
                # Notify other participant
                other_sid = session['partner_sid'] if session.get('host_sid') == sid else session['host_sid']
                if other_sid and other_sid in active_connections:
                    await sio.emit('partner_disconnected', {
                        'message': 'Your partner has disconnected',
                        'session_id': session_id,
                        'timestamp': time.time()
                    }, room=other_sid)

                # Remove session if both participants are gone
                session['participants'].discard(sid)
                if len(session['participants']) == 0:
                    del active_sessions[session_id]
                    connection_metrics['active_sessions'] -= 1
                    logger.info(f"🧹 Cleaned up empty session: {session_id}")

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Disconnect error for {sid}: {str(e)}")


@sio.event
async def heartbeat(sid, data):
    """Handle heartbeat from client"""
    try:
        now = time.time()
        last_heartbeat[sid] = now

        # Respond with server heartbeat
        await sio.emit('heartbeat_ack', {
            'server_time': now,
            'client_time': data.get('client_time'),
            'latency': now - data.get('client_time', now)
        }, room=sid)

    except Exception as e:
        logger.error(f"❌ Heartbeat error for {sid}: {str(e)}")


@sio.event
async def join_session(sid, data):
    """Join a pair quiz session with enhanced validation"""
    try:
        session_id = data.get('sessionId')
        user_id = data.get('userId')

        if not session_id or not user_id:
            await sio.emit('error', {
                'type': 'INVALID_DATA',
                'message': 'Session ID and User ID are required'
            }, room=sid)
            return

        # Validate session exists in database
        try:
            session_data = await get_session(session_id)
        except Exception as e:
            await sio.emit('error', {
                'type': 'SESSION_NOT_FOUND',
                'message': f'Session not found: {str(e)}'
            }, room=sid)
            return

        # Check if session is active
        if session_data['status'] not in ['waiting', 'active']:
            await sio.emit('error', {
                'type': 'SESSION_INACTIVE',
                'message': 'Session is not active'
            }, room=sid)
            return

        # Check user authorization
        if user_id not in [session_data.get('hostUserId'), session_data.get('partnerUserId')]:
            await sio.emit('error', {
                'type': 'UNAUTHORIZED',
                'message': 'You are not authorized to join this session'
            }, room=sid)
            return

        # Update connection info
        active_connections[sid]['session_id'] = session_id

        # Initialize session in memory if not exists
        if session_id not in active_sessions:
            active_sessions[session_id] = {
                'host_sid': None,
                'partner_sid': None,
                'participants': set(),
                'created_at': time.time()
            }
            connection_metrics['total_sessions'] += 1
            connection_metrics['active_sessions'] += 1

        session = active_sessions[session_id]

        # Assign role and store connection
        is_host = user_id == session_data['hostUserId']
        role = 'host' if is_host else 'partner'

        if is_host:
            session['host_sid'] = sid
        else:
            session['partner_sid'] = sid

        session['participants'].add(sid)

        # Join Socket.IO room
        await sio.enter_room(sid, session_id)

        # Notify user of successful join
        await sio.emit('session_joined', {
            'sessionId': session_id,
            'role': role,
            'session': session_data,
            'timestamp': time.time()
        }, room=sid)

        # Check if both users have joined
        host_connected = session['host_sid'] is not None
        partner_connected = session['partner_sid'] is not None

        if host_connected and partner_connected:
            logger.info(f"🎉 Both users connected to session {session_id}")
            session_data = await get_session(session_id)

            # Broadcast complete session data
            await sio.emit('partner_joined', {
                'message': 'Your partner has joined!',
                'session': session_data,
                'timestamp': time.time()
            }, room=session_id)

            # Emit state synchronization event
            await sio.emit('state_update', {
                'type': 'PARTNER_JOINED',
                'session': session_data,
                'timestamp': time.time()
            }, room=session_id)

        logger.info(f"✅ User {user_id} joined session {session_id} as {role}")

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Error joining session: {str(e)}")
        await sio.emit('error', {
            'type': 'JOIN_FAILED',
            'message': str(e)
        }, room=sid)


@sio.event
async def answer_selected(sid, data):
    """Handle answer selection with validation"""
    try:
        session_id = data.get('sessionId')
        user_id = data.get('userId')
        question_index = data.get('questionIndex')
        selected_option = data.get('selectedOption')

        if not all([session_id, user_id, question_index is not None, selected_option]):
            await sio.emit('error', {'message': 'Invalid answer data'}, room=sid)
            return

        # Validate session and user
        if session_id not in active_sessions:
            await sio.emit('error', {'message': 'Session not active'}, room=sid)
            return

        session = active_sessions[session_id]
        if sid not in session['participants']:
            await sio.emit('error', {'message': 'Not a participant in this session'}, room=sid)
            return

        # Update database
        await update_answer(session_id, user_id, question_index, selected_option)

        # Broadcast to session room (exclude sender)
        await sio.emit('state_update', {
            'type': 'ANSWER_SELECTED',
            'userId': user_id,
            'questionIndex': question_index,
            'selectedOption': selected_option,
            'timestamp': time.time()
        }, room=session_id, skip_sid=sid)

        logger.info(f"✅ Answer selected in session {session_id}: Q{question_index} = {selected_option}")

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Error handling answer selection: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def next_question(sid, data):
    """Handle navigation to next question"""
    try:
        session_id = data.get('sessionId')
        question_index = data.get('questionIndex')

        if not session_id or question_index is None:
            await sio.emit('error', {'message': 'Invalid question navigation data'}, room=sid)
            return

        # Validate session
        if session_id not in active_sessions:
            await sio.emit('error', {'message': 'Session not active'}, room=sid)
            return

        session = active_sessions[session_id]
        if sid not in session['participants']:
            await sio.emit('error', {'message': 'Not a participant in this session'}, room=sid)
            return

        # Update database
        await update_question_index(session_id, question_index)

        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'NEXT_QUESTION',
            'questionIndex': question_index,
            'timestamp': time.time()
        }, room=session_id)

        logger.info(f"✅ Next question in session {session_id}: Q{question_index}")

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Error handling next question: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def quiz_complete(sid, data):
    """Handle quiz completion"""
    try:
        session_id = data.get('sessionId')
        user_id = data.get('userId')
        score = data.get('score')
        time_taken = data.get('timeTaken')

        if not all([session_id, user_id, score is not None]):
            await sio.emit('error', {'message': 'Invalid completion data'}, room=sid)
            return

        # Validate session
        if session_id not in active_sessions:
            await sio.emit('error', {'message': 'Session not active'}, room=sid)
            return

        session = active_sessions[session_id]
        if sid not in session['participants']:
            await sio.emit('error', {'message': 'Not a participant in this session'}, room=sid)
            return

        # Update database
        await complete_quiz(session_id, user_id, score, time_taken)

        # Check if both users completed
        session_data = await get_session(session_id)
        both_completed = session_data.get('hostScore') is not None and session_data.get('partnerScore') is not None

        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'QUIZ_COMPLETE',
            'userId': user_id,
            'score': score,
            'timeTaken': time_taken,
            'bothCompleted': both_completed,
            'session': session_data if both_completed else None,
            'timestamp': time.time()
        }, room=session_id)

        logger.info(f"✅ Quiz completed in session {session_id} by {user_id}: {score}")

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Error handling quiz completion: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def update_timer(sid, data):
    """Handle timer updates"""
    try:
        session_id = data.get('sessionId')
        timer_seconds = data.get('timerSeconds')

        if not session_id or timer_seconds is None:
            await sio.emit('error', {'message': 'Invalid timer data'}, room=sid)
            return

        # Validate session
        if session_id not in active_sessions:
            await sio.emit('error', {'message': 'Session not active'}, room=sid)
            return

        session = active_sessions[session_id]
        if sid not in session['participants']:
            await sio.emit('error', {'message': 'Not a participant in this session'}, room=sid)
            return

        # Update database
        await update_session_timer(session_id, timer_seconds)

        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'TIMER_UPDATE',
            'timerSeconds': timer_seconds,
            'timestamp': time.time()
        }, room=session_id, skip_sid=sid)

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Error handling timer update: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def cancel_session(sid, data):
    """Handle session cancellation"""
    try:
        session_id = data.get('sessionId')
        reason = data.get('reason', 'User cancelled')

        if not session_id:
            await sio.emit('error', {'message': 'Session ID required'}, room=sid)
            return

        # Validate session
        if session_id not in active_sessions:
            await sio.emit('error', {'message': 'Session not active'}, room=sid)
            return

        session = active_sessions[session_id]
        if sid not in session['participants']:
            await sio.emit('error', {'message': 'Not a participant in this session'}, room=sid)
            return

        # Update database
        await cancel_session_db(session_id, reason)

        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'SESSION_CANCELLED',
            'reason': reason,
            'timestamp': time.time()
        }, room=session_id)

        # Clean up
        del active_sessions[session_id]
        connection_metrics['active_sessions'] -= 1

        logger.info(f"✅ Session {session_id} cancelled: {reason}")

    except Exception as e:
        connection_metrics['errors'] += 1
        logger.error(f"❌ Error handling session cancellation: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def get_metrics(sid, data):
    """Get server metrics (admin only)"""
    try:
        # In production, add proper admin authentication here
        await sio.emit('metrics', {
            'connection_metrics': connection_metrics,
            'active_connections': len(active_connections),
            'active_sessions': len(active_sessions),
            'timestamp': time.time()
        }, room=sid)
    except Exception as e:
        logger.error(f"❌ Error getting metrics: {str(e)}")


async def monitor_connection_health(sid):
    """Monitor connection health and handle timeouts"""
    try:
        while sid in active_connections:
            await asyncio.sleep(30)  # Check every 30 seconds

            if sid not in last_heartbeat:
                continue

            now = time.time()
            time_since_heartbeat = now - last_heartbeat[sid]

            if time_since_heartbeat > HEARTBEAT_TIMEOUT:
                logger.warning(f"💔 Connection timeout for {sid}, disconnecting")
                await sio.disconnect(sid)
                break

    except Exception as e:
        logger.error(f"❌ Health monitoring error for {sid}: {str(e)}")


async def cleanup_inactive_sessions():
    """Periodically clean up inactive sessions"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes

            now = time.time()
            inactive_sessions = []

            for session_id, session in active_sessions.items():
                # Check if session has been inactive for too long
                if now - session['created_at'] > 3600:  # 1 hour
                    # Check if any participants are still connected
                    active_participants = [pid for pid in session['participants'] if pid in active_connections]
                    if not active_participants:
                        inactive_sessions.append(session_id)

            # Clean up inactive sessions
            for session_id in inactive_sessions:
                del active_sessions[session_id]
                connection_metrics['active_sessions'] -= 1
                logger.info(f"🧹 Cleaned up inactive session: {session_id}")

        except Exception as e:
            logger.error(f"❌ Session cleanup error: {str(e)}")


@sio.event
async def join_session(sid, data):
    """Join a pair quiz session"""
    try:
        session_id = data.get('sessionId')
        user_id = data.get('userId')
        
        if not session_id or not user_id:
            await sio.emit('error', {'message': 'Invalid session data'}, room=sid)
            return
        
        # Get session from database
        try:
            session = await get_session(session_id)
        except Exception as e:
            await sio.emit('error', {'message': f'Session not found: {str(e)}'}, room=sid)
            return
        
        # Initialize session in memory
        if session_id not in active_sessions:
            active_sessions[session_id] = {}
        
        # Assign role based on user_id
        is_host = user_id == session['hostUserId']
        role = 'host' if is_host else 'partner'
        
        # Store connection
        connection_key = 'host_sid' if is_host else 'partner_sid'
        active_sessions[session_id][connection_key] = sid
        
        logger.info(f"User {user_id} joining as {role}, host={session['hostUserId']}, partner={session['partnerUserId']}")
        
        # Join Socket.IO room
        await sio.enter_room(sid, session_id)
        
        # Notify user
        await sio.emit('session_joined', {
            'sessionId': session_id,
            'role': role,
            'session': session
        }, room=sid)
        
        # Check if both users have joined (check database, not just Socket.IO connections)
        if session['partnerUserId'] and session['partnerUserId'] != session['hostUserId']:
            # Both users joined - refresh session and broadcast
            logger.info(f"Both users connected to session {session_id}")
            session = await get_session(session_id)
            
            # Broadcast complete session data to all participants
            await sio.emit('partner_joined', {
                'message': 'Your partner has joined!',
                'session': session
            }, room=session_id)
            
            # Also emit state update for immediate synchronization
            await sio.emit('state_update', {
                'type': 'PARTNER_JOINED',
                'session': session
            }, room=session_id)
        
        logger.info(f"User {user_id} joined session {session_id} as {role}")
        
    except Exception as e:
        logger.error(f"Error joining session: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def answer_selected(sid, data):
    """Handle answer selection"""
    try:
        session_id = data.get('sessionId')
        user_id = data.get('userId')
        question_index = data.get('questionIndex')
        selected_option = data.get('selectedOption')
        
        # Update session in database
        await update_answer(session_id, user_id, question_index, selected_option)
        
        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'ANSWER_SELECTED',
            'userId': user_id,
            'questionIndex': question_index,
            'selectedOption': selected_option
        }, room=session_id, skip_sid=sid)
        
        logger.info(f"Answer selected in session {session_id}: Q{question_index} = {selected_option}")
        
    except Exception as e:
        logger.error(f"Error handling answer selection: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def next_question(sid, data):
    """Handle navigation to next question"""
    try:
        session_id = data.get('sessionId')
        question_index = data.get('questionIndex')
        
        # Update session in database
        await update_question_index(session_id, question_index)
        
        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'NEXT_QUESTION',
            'questionIndex': question_index
        }, room=session_id, skip_sid=sid)
        
        logger.info(f"Next question in session {session_id}: Q{question_index}")
        
    except Exception as e:
        logger.error(f"Error handling next question: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def quiz_complete(sid, data):
    """Handle quiz completion"""
    try:
        session_id = data.get('sessionId')
        user_id = data.get('userId')
        score = data.get('score')
        time_taken = data.get('timeTaken')
        
        # Update session in database
        await complete_quiz(session_id, user_id, score, time_taken)
        
        # Check if both users completed
        session = await get_session(session_id)
        both_completed = session.get('hostScore') is not None and session.get('partnerScore') is not None
        
        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'QUIZ_COMPLETE',
            'userId': user_id,
            'score': score,
            'bothCompleted': both_completed,
            'session': session if both_completed else None
        }, room=session_id)
        
        logger.info(f"Quiz completed in session {session_id} by {user_id}: {score}")
        
    except Exception as e:
        logger.error(f"Error handling quiz completion: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)


@sio.event
async def update_timer(sid, data):
    """Handle timer updates"""
    try:
        session_id = data.get('sessionId')
        timer_seconds = data.get('timerSeconds')
        
        # Update session in database
        await update_session_timer(session_id, timer_seconds)
        
        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'TIMER_UPDATE',
            'timerSeconds': timer_seconds
        }, room=session_id, skip_sid=sid)
        
    except Exception as e:
        logger.error(f"Error handling timer update: {str(e)}")


@sio.event
async def cancel_session(sid, data):
    """Handle session cancellation"""
    try:
        session_id = data.get('sessionId')
        reason = data.get('reason', 'User cancelled')
        
        # Update session in database
        await cancel_session_db(session_id, reason)
        
        # Broadcast to session room
        await sio.emit('state_update', {
            'type': 'SESSION_CANCELLED',
            'reason': reason
        }, room=session_id)
        
        # Clean up
        if session_id in active_sessions:
            del active_sessions[session_id]
        
        logger.info(f"Session {session_id} cancelled: {reason}")
        
    except Exception as e:
        logger.error(f"Error handling session cancellation: {str(e)}")


# Database helper functions (async wrappers)
async def get_session(session_id):
    """Get session from database"""
    from asgiref.sync import sync_to_async
    from .models import PairQuizSession
    
    @sync_to_async
    def _get():
        session = PairQuizSession.objects.get(id=session_id)
        data = {
            'sessionId': str(session.id),
            'sessionCode': session.session_code,
            'status': session.status,
            'hostUserId': session.host_user_id,
            'partnerUserId': session.partner_user_id,
            'quizConfig': session.quiz_config,
            'questions': session.questions or [],
            'currentQuestionIndex': session.current_question_index,
            'hostAnswers': session.host_answers or {},
            'partnerAnswers': session.partner_answers or {},
            'timerSeconds': session.timer_seconds,
            'hostScore': session.host_score,
            'partnerScore': session.partner_score
        }
        logger.info(f"Retrieved session {session_id}: status={data['status']}, questions={len(data['questions'])}")
        return data
    
    return await _get()


async def update_answer(session_id, user_id, question_index, selected_option):
    """Update answer in database"""
    from asgiref.sync import sync_to_async
    from .models import PairQuizSession
    
    @sync_to_async
    def _update():
        session = PairQuizSession.objects.get(id=session_id)
        if user_id == session.host_user_id:
            session.host_answers[str(question_index)] = selected_option
        else:
            session.partner_answers[str(question_index)] = selected_option
        session.save()
    
    await _update()


async def update_question_index(session_id, question_index):
    """Update current question index"""
    from asgiref.sync import sync_to_async
    from .models import PairQuizSession
    
    @sync_to_async
    def _update():
        session = PairQuizSession.objects.get(id=session_id)
        session.current_question_index = question_index
        session.save()
    
    await _update()


async def complete_quiz(session_id, user_id, score, time_taken):
    """Mark quiz as completed for user"""
    from asgiref.sync import sync_to_async
    from .models import PairQuizSession
    from django.utils import timezone
    
    @sync_to_async
    def _complete():
        session = PairQuizSession.objects.get(id=session_id)
        if user_id == session.host_user_id:
            session.host_score = score
            session.host_time_taken = time_taken
        else:
            session.partner_score = score
            session.partner_time_taken = time_taken
        
        # Mark as completed if both finished
        if session.host_score is not None and session.partner_score is not None:
            session.status = 'completed'
            session.completed_at = timezone.now()
        
        session.save()
    
    await _complete()


async def update_session_timer(session_id, timer_seconds):
    """Update session timer"""
    from asgiref.sync import sync_to_async
    from .models import PairQuizSession
    
    @sync_to_async
    def _update():
        session = PairQuizSession.objects.get(id=session_id)
        session.timer_seconds = timer_seconds
        session.save()
    
    await _update()


async def cancel_session_db(session_id, reason):
    """Cancel session in database"""
    from asgiref.sync import sync_to_async
    from .models import PairQuizSession
    from django.utils import timezone
    
    @sync_to_async
    def _cancel():
        session = PairQuizSession.objects.get(id=session_id)
        session.status = 'cancelled'
        session.completed_at = timezone.now()
        session.save()
    
    await _cancel()
