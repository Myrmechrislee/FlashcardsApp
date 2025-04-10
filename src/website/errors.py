from flask import Blueprint, render_template, request, session, flash
import db, mail
from werkzeug.exceptions import InternalServerError
import security

bp = Blueprint('error', __name__, template_folder='/website/templates/HTTP Status Pages/')

@bp.route('/MakeInternalServerError')
@security.no_authentication
def error_500_generate():
    raise InternalServerError()
@bp.app_errorhandler(404)
def error_404_handler(err):
    return render_template("errors/404.html"), 404

@bp.app_errorhandler(403)
def error_403_handler(err):
    db.create_security_log("Attempted Forbidden Access",
                           session.get("email", "not registered"),
                           request.headers.get('X-Forwarded-For', request.remote_addr),
                           details=f"""There has been an restricted attempted access to {request.url}""",
                           severity=db.SecurityLogSeverity.High 
                           )
    return render_template("errors/403.html"), 403

@bp.app_errorhandler(500)
def error_500_handler(e):
    mail.send_error_email(session.get('email', 'not signed in'), bp, e)
    return render_template("errors/500.html"), 500