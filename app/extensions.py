"""
Flask extensions initialization
Shared instances for limiter and csrf to be used across blueprints.

These are created here (module import time) so blueprints can safely
reference them in decorators. The actual app binding happens in
simple_app.py via .init_app(app).
"""

import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Global extension instances (configured in simple_app.py)
_storage_uri = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')

# Allow hard disable via env (requested by user for heavy local usage)
_disable_limits = str(os.environ.get('DISABLE_RATE_LIMITS', '1')).lower() in ('1','true','yes','on')

if _disable_limits:
    # No-op limiter compatible with .init_app(), .limit and .exempt decorators
    class _NoopLimiter:
        def init_app(self, app):
            app.config['RATELIMIT_ENABLED'] = False
        def limit(self, *args, **kwargs):
            def _deco(f):
                return f
            return _deco
        def exempt(self, f):
            return f
    limiter = _NoopLimiter()
else:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[],  # no global defaults; opt-in per-route only
        storage_uri=_storage_uri,
    )

# CSRF Protection with fallback for missing Flask-WTF
try:
    from flask_wtf import CSRFProtect
    csrf = CSRFProtect()
    _csrf_available = True
except ImportError:
    # Fallback CSRF protection when Flask-WTF is not available
    class FallbackCSRFProtect:
        """Fallback CSRF protection that works without Flask-WTF"""

        def __init__(self):
            self._tokens = {}

        def init_app(self, app):
            """Initialize with Flask app"""
            @app.before_request
            def generate_csrf_token():
                """Generate a simple CSRF token for each request"""
                try:
                    from flask import request, has_request_context
                    import hashlib
                    import time

                    if has_request_context() and request:
                        # Use a simple approach without relying on session
                        # Generate a token based on remote address and timestamp
                        remote_addr = getattr(request, 'remote_addr', 'unknown')
                        timestamp = int(time.time() // 3600)  # Hour-based expiry
                        token_data = f"{remote_addr}:{timestamp}"
                        token = hashlib.sha256(token_data.encode()).hexdigest()[:32]

                        # Store in g context for this request (not on request object directly)
                        from flask import g
                        g.csrf_token = token
                except (RuntimeError, ImportError, AttributeError):
                    # Request context not available
                    pass

            @app.context_processor
            def inject_csrf_token():
                """Inject CSRF token into templates"""
                try:
                    from flask import g, has_request_context
                    if has_request_context():
                        token = getattr(g, 'csrf_token', '')
                        return {'csrf_token': lambda: token}
                    else:
                        return {'csrf_token': lambda: ''}
                except (RuntimeError, ImportError, AttributeError):
                    # Request context not available
                    return {'csrf_token': lambda: ''}

        def exempt(self, view):
            """Decorator to exempt views from CSRF protection"""
            view._csrf_exempt = True
            return view

    csrf = FallbackCSRFProtect()
    _csrf_available = False
