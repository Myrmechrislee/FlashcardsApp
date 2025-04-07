from flask import Blueprint, render_template, request, redirect, session, flash, abort, send_file
import db, security, mail, io, re

bp = Blueprint('auth', __name__, url_prefix='', template_folder='/website/templates/auth')

@bp.route("/login", methods=["GET", "POST"])
@security.no_authentication
def login():
    if "email" in session:
        return redirect("/topics")
    if request.method == "POST":
        success, user = db.test_login(request.form["email"], request.headers.get('X-Forwarded-For', request.remote_addr), request.form["password"])
        if success:
            session["email"] = user["email"]
            session["name"] = user["name"]
            r = request.args.get("next", "/topics")
            return redirect(r)
        else:
            flash("Incorrect email or password. ", "error")
    return render_template("auth/login.html")
@bp.route("/signout")
def signout():
    session.clear()
    return redirect("/login")
@bp.route("/create-account", methods=["GET", "POST"])
@security.no_authentication
def create_account():
    if request.method == "POST":
        if db.email_already_exists(request.form["email"]):
            flash("Email already exists", category="error")
        else:
            db.add_user(request.form["name"], request.form["email"], request.form["password"], request.headers.get('X-Forwarded-For', request.headers.get('X-Forwarded-For', request.remote_addr)))
            mail.send_verification_email(request.form["email"])
            flash("Account successfully added! A verification message has been sent. Please check your email. ")
    return render_template("auth/create-account.html")

@bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new-password')
        confirm_password = request.form.get('confirm-password')

        if new_password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
        else:
            db.update_password(session["email"], new_password)
            flash('Password changed successfully!', 'success')
    return render_template("auth/change-password.html")

@bp.route('/validate-email-message')
def validate_email_message():
    return render_template('message.html', title = 'Please Validate Your Email', body="""<p>We've sent a verification email to your inbox. Please check your email and click on the link to validate your account.</p>
        <p>If you didn't receive the email, you can <a href="/send-verification-email" class="link">resend the verification email</a> or you can try another account by first <a href="/signout" class="link">signing out</a>.</p>""")

@bp.route('/send-verification-email')
def send_verification_email():
    mail.send_verification_email(session['email'])
    return render_template('message.html', title='Email Sent', body="""<p>The verification has been sent. Please check your email. </p>
    """)
@bp.route("/verify-email")
@security.no_authentication
def verify_email():
    token_sent = request.args.get('token')
    if db.validate_code(token_sent):
        data = {
            "title": "Thank You!",
            "body": """Your email has been confirmed. You can now get started with the link below. Click <a href='/login' class='link'>here</a> to get started. """,
        }
    else:
        data = {
            "header": "Link Expired",
            "body": """This verification link is out of date. Please use the most recent link sent to your email. Or you can click <a href='/send-verification-email' class='link'>here</a> to send another one. """,
        }
    
    return render_template('message.html', **data)

@bp.route("/forgot-password", methods=["GET", "POST"])
@security.no_authentication
def forgot_password():
    if request.method == "GET":
        return render_template('auth/forgot-password.html')
    email = request.form['email']
    if not db.email_already_exists(email):
        flash("Email isn't registered. ")
        return render_template('auth/forgot-password.html')
    mail.send_password_reset_link(email)
    return render_template('message.html', title="Password Reset", body="The instructions to reset your password has been sent. Please check your email. ")

@bp.route('/reset-password', methods=["GET", "POST"])
@security.no_authentication
def reset_password():
    tokens = request.args['tokens']
    if request.method == "GET":
        if not db.reset_password_code_exists(tokens):
            return render_template('message.html', title="Password Reset", body="Invalid tokens, try checking if this is your most recent email. You can also send another from <a href='/forgot-password' class='link'>here</a>. ")
        if not db.reset_password_upto_date(tokens):
            return render_template('message.html', title="Password Reset", body="Your link is no longer valid, it was only valid for up to 5 minutes. You can also send another from <a href='/forgot-password' class='link'>here</a>. ")
        return render_template('auth/reset-password.html')
    else:
        if request.form['new-password'] != request.form['confirm-password']:
            flash("Passwords do not match. ")
        else:
            db.reset_password(tokens, request.form['new-password'])
            flash('Password updated. ')
            return render_template('auth/reset-password.html')

@bp.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if request.method == "POST":
        try:
            if "profile-pic" in request.files:
                file = request.files.get("profile-pic")
                if file.filename != "":
                    db.update_profile_picture(session["email"], file)
                email = request.form.get("email")
                if email != session["email"]:
                    if db.email_already_exists(email):
                        flash("Email already exists", "error")
                        return render_template("auth/edit-profile.html", user=db.get_user(session["email"]))
                    if re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email) is None:
                        flash("Invalid email address", "error")
                        return render_template("auth/edit-profile.html", user=db.get_user(session["email"]))
                    db.update_email(session["email"], email)
                    session["email"] = email
                name = request.form.get("name")
                db.update_name(session["email"], name)
        except Exception as e:
            flash("There has been a problem updating your account", "error")
        else:
            flash("Account successfully updated!", "success")
    return render_template("auth/edit-profile.html", user=db.get_user(session["email"]))

@bp.route("/uploads/<file_id>")
def uploads(file_id):
    file = db.get_upload(file_id)
    rsp = send_file(io.BytesIO(file.read()), mimetype=file.content_type)
    rsp.cache_control.max_age = 604800
    rsp.cache_control.no_cache = False
    return rsp
    