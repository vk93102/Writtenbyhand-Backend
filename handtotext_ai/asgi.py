"""
ASGI config for handtotext_ai project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
import socketio
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "handtotext_ai.settings")

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

# Import Socket.IO server (after Django setup)
from question_solver.socketio_server import sio

# Combine Django and Socket.IO with proper routing
application = socketio.ASGIApp(
    sio, 
    django_asgi_app,
    socketio_path='socket.io'  # Explicitly set Socket.IO path
)

print("✅ ASGI Application initialized with Socket.IO support")
print("   Socket.IO endpoint: /socket.io/")
print("   Django endpoints: /api/*")


