from flask import Flask, request, abort, session, redirect
import db

def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="")
    @app.after_request
    def add_cache_headers(response):
        if request.path.endswith(('.png', '.jpg', '.jpeg')):
            # Cache for 1 week (604800 seconds)
            response.cache_control.max_age = 604800
            response.cache_control.no_cache = False
            response.add_etag()
        return response
    @app.before_request
    def authentication():
        # Skip authentication check for static files
        if request.endpoint == 'static':
            return
        
        # Get the view function that will handle the request
        view_func = app.view_functions.get(request.endpoint)
        
        if view_func is None:
            return
        
        # Check if the view has the authenticated decorator
        needs_auth = not getattr(view_func, 'no_authentication', False)

        if needs_auth:
            # Check if user is logged in
            if 'email' not in session:
                return redirect(f'/login?next={request.url}')  # Redirect to login page
            if not db.email_is_verified(session['email']) and request.endpoint not in ["validate_email_message", "signout", "send_verification_email"]:
                return redirect('/validate-email-message')
        
        # Check admin requirement
        if request.path.startswith("/admin") and not db.is_admin(session['email']):
            abort(403)

    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.secret_key = "ce4f9f579b2a22b536d9fa989b0847ce"
    app.config['SESSION_COOKIE_NAME'] = "flask_app_session"
    
    # Initialize Flask extensions here (if any)
    from .admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    from .topics import bp as topics_bp
    app.register_blueprint(topics_bp)
    
    return app