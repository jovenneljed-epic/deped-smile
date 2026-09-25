import sys
from pathlib import Path

# Add project root directory to sys.path so app, smile_*, etc. resolve properly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import Flask WSGI app instance
from app import app as flask_app
from flask import redirect, url_for

# Define direct fallbacks for Vercel internal function paths
@flask_app.route('/api/index', methods=['GET', 'POST', 'PUT', 'DELETE'])
@flask_app.route('/api/index.py', methods=['GET', 'POST', 'PUT', 'DELETE'])
def vercel_index_root_fallback():
    return redirect(url_for('login_page'))

class VercelPathFixMiddleware:
    """
    Ensures that incoming requests rewritten by Vercel to /api/index or /api/index.py
    have their PATH_INFO properly routed to Flask's real URL endpoints.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith('/api/index.py'):
            environ['PATH_INFO'] = path[len('/api/index.py'):] or '/'
        elif path.startswith('/api/index'):
            environ['PATH_INFO'] = path[len('/api/index'):] or '/'
        return self.wsgi_app(environ, start_response)

# Expose WSGI callable for Vercel runtime
app = VercelPathFixMiddleware(flask_app)
