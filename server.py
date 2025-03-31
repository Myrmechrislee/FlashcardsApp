from flask import Flask, render_template, jsonify, request, redirect, Response, flash, session, send_file, abort
from functools import wraps
import random, db, io, csv, pandas as pd, re, mail, security

app = Flask(__name__, static_folder="static", static_url_path="", template_folder="pages")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = "ce4f9f579b2a22b536d9fa989b0847ce"
app.config['SESSION_COOKIE_NAME'] = "flask_app_session"

@app.route('/topics', methods=["GET", "POST"])
def topics():
    return render_template("topics.html", user=db.get_user(session["email"]), topics=db.get_topics(session["email"]), is_admin=db.get_user(session['email'])['is_admin'])

@app.route("/flash/<tid>/<qid>")
def flashcard(tid, qid):
    topic = db.get_topic(tid)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], tid):
        abort(403)
    questions = topic["questions"]
    question = [q for q in questions if str(q["id"]) == str(qid)]
    if len(question) == 0:
        abort(404)
    return render_template("flash.html", t=db.get_topic(tid), question=question[0])

@app.route("/quiz/<tid>")
def quiz(tid):
    topic = db.get_topic(tid)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], tid):
        abort(403)
    questions = topic['questions']
    if request.args.get('randomize', default=False, type=bool):
        questions = random.sample(questions, len(questions))
    if request.args.get('skip-confident', default=False, type=bool):
        questions = [q for q in questions if int(q['confidence']) != 2]
    id = db.generate_quiz(session['email'], tid, questions)

    return redirect(f'/quizlet/{id}/{questions[0]["id"]}')

@app.route("/quizlet/<quizid>/<qid>")
def quizlet(quizid, qid):
    if not db.has_access_to_quiz(session["email"], quizid):
        abort(403)
    quiz = db.get_quiz(quizid)
    if not quiz:
        abort(404)
    questions = quiz['questions']
    question = [q for q in questions if str(q['id']) == qid]
    if len(question) == 0:
        abort(404)
    return render_template("/quizlet.html", t=db.get_topic(quiz["topic_id"]), quizid=quizid, qid=qid, question=question[0], streak=db.get_streak(quizid))

@app.route("/answer-quizlet/<quizid>/<qid>")
def answer_quizlet(quizid, qid):
    if not db.has_access_to_quiz(session["email"], quizid):
        abort(403)
    response = request.args.get("response")
    if response not in ["yes", "no"]:
        return jsonify({
            'error': 'Bad Request',
            'message': 'The response is not yes or no.'
        }), 400
    response = response.lower()
    next = db.update_quiz_response(quizid, qid, response == "yes")
    if next:
        return redirect(f"/quizlet/{quizid}/{next['id']}")
    db.finish_quiz(quizid)
    return redirect(f"/quiz-results/{quizid}")

@app.route("/quiz-results/<quizid>")
def quiz_results(quizid):
    return render_template('quiz-results.html', **db.get_quiz_stats(quizid))
@app.route("/flash/<tid>")
def flash_card_infinite(tid):
    topic = db.get_topic(tid)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], tid):
        abort(403)
    topic = db.get_topic(tid)
    question = random.choice(topic["questions"])
    return redirect(f"/flash/{tid}/{question['id']}")
    

@app.route("/submitconfidence", methods=["POST"])
def submit_confidence():
    data = request.get_json()
    if 'confidence' in data and 'qid' in data and 'tid' in data:
        m = db.update_confidence(data["tid"], data["qid"], data["confidence"])
        return jsonify({"message": "success"})
    else:
        message = jsonify({"error": "Missing 'qid', 'tid' or 'confidence' property"})
        return message, 400
@app.route("/add-topic", methods=["GET", "POST"])
def add_topic():
    if request.method == "POST":
        db.add_topic(
            session["email"],
            request.form.get('title'),
            request.form.getlist('questions[]'),
            request.form.getlist('answers[]'))
        return redirect("/topics")
    else:
        return render_template("add-topic.html")

@app.route("/topic-start/<id>")
def topic_start(id):
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], id):
        abort(403)
    return render_template("topic-start.html", t=topic)

@app.route('/edit-topic/<id>', methods=['GET', 'POST'])
def edit_topic(id):
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], id):
        abort(403)
    
    if request.method == 'POST':
        title = request.form['title']
        questions = request.form.getlist('questions[]')
        answers = request.form.getlist('answers[]')
        
        if not title or not all(questions) or not all(answers):
            return "All fields must be filled", 400
        
        db.edit_topic(id, request.form)
        topic=db.get_topic(id)
    
    return render_template('edit-topic.html', topic=topic)

@app.route("/delete-topic/<id>")
def delete_topic(id):
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], id):
        abort(403)
    db.delete_topic(id)
    return redirect("/topics")

@app.route("/export-csv/<id>")
def export_csv(id):
    topic = db.get_topic(id)
    if topic == None:
        abort(404)
    if not db.has_access_to_topic(session["email"], id):
        abort(403)
    questions = topic["questions"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["id", "question", "answer", "confidence"])
    for q in questions:
        w.writerow([q["id"], q["question"], q["answer"], q["confidence"]])
    out.seek(0)
    return Response(out, mimetype="text/csv", headers={
        "Content-Disposition": f"attachment;filename={topic['title']}.csv"
    })

@app.route("/import-topic", methods=["GET", "POST"])
def import_topic():
    if request.method == "POST":
        title = request.form.get('title')
        file = request.files.get('csv-file')
        if not title or not file:
            flash("No title and CSV. ", "errors")
            return render_template("import-menu.html")

        if not file.filename.endswith('.csv'):
            flash("Please upload a valid CSV file!", "error")
            return render_template("import-menu.html")
        df = pd.read_csv(file)
        if "question" not in df.columns or "answer" not in df.columns:
            flash("No question or answer column in csv. ", "error")
            return render_template("import-menu.html")
        q = db.import_topic(session["email"], title, df)
        flash(f"Successfully imported topic '{title}' with {q} questions!", "success")
    return render_template("import-menu.html")
@app.route("/login", methods=["GET", "POST"])
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
    return render_template("login.html")
@app.route("/signout")
def signout():
    session.clear()
    return redirect("/login")
@app.route("/create-account", methods=["GET", "POST"])
@security.no_authentication
def create_account():
    if request.method == "POST":
        if db.email_already_exists(request.form["email"]):
            flash("Email already exists", category="error")
        else:
            db.add_user(request.form["name"], request.form["email"], request.form["password"], request.headers.get('X-Forwarded-For', request.headers.get('X-Forwarded-For', request.remote_addr)))
            mail.send_verification_email(request.form["email"])
            flash("Account successfully added! A verification message has been sent. Please check your email. ")
    return render_template("create-account.html")

@app.route("/edit-profile", methods=["GET", "POST"])
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
                        return render_template("edit-profile.html", user=db.get_user(session["email"]))
                    if re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email) is None:
                        flash("Invalid email address", "error")
                        return render_template("edit-profile.html", user=db.get_user(session["email"]))
                    db.update_email(session["email"], email)
                    session["email"] = email
                name = request.form.get("name")
                db.update_name(session["email"], name)
        except Exception as e:
            flash("There has been a problem updating your account", "error")
        else:
            flash("Account successfully updated!", "success")
    return render_template("edit-profile.html", user=db.get_user(session["email"]))

@app.route("/uploads/<file_id>")
def uploads(file_id):
    try:
        file = db.get_upload(file_id)
        return send_file(io.BytesIO(file.read()), mimetype=file.content_type)
    except Exception as e:
        abort(404)

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new-password')
        confirm_password = request.form.get('confirm-password')

        if new_password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
        else:
            db.update_password(session["email"], new_password)
            flash('Password changed successfully!', 'success')
    return render_template("change-password.html")
@app.route('/validate-email-message')
def validate_email_message():
    return render_template('message.html', title = 'Please Validate Your Email', body="""<p>We've sent a verification email to your inbox. Please check your email and click on the link to validate your account.</p>
        <p>If you didn't receive the email, you can <a href="/send-verification-email" class="link">resend the verification email</a> or you can try another account by first <a href="/signout" class="link">signing out</a>.</p>""")

@app.route('/send-verification-email')
def send_verification_email():
    mail.send_verification_email(session['email'])
    return render_template('message.html', title='Email Sent', body="""<p>The verification has been sent. Please check your email. </p>
    """)
@app.route("/verify-email")
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

@app.route("/forgot-password", methods=["GET", "POST"])
@security.no_authentication
def forgot_password():
    if request.method == "GET":
        return render_template('forgot-password.html')
    email = request.form['email']
    if not db.email_already_exists(email):
        flash("Email isn't registered. ")
        return render_template('forgot-password.html')
    mail.send_password_reset_link(email)
    return render_template('message.html', title="Password Reset", body="The instructions to reset your password has been sent. Please check your email. ")

@app.route('/reset-password', methods=["GET", "POST"])
@security.no_authentication
def reset_password():
    tokens = request.args['tokens']
    if request.method == "GET":
        if not db.reset_password_code_exists(tokens):
            return render_template('message.html', title="Password Reset", body="Invalid tokens, try checking if this is your most recent email. You can also send another from <a href='/forgot-password' class='link'>here</a>. ")
        if not db.reset_password_upto_date(tokens):
            return render_template('message.html', title="Password Reset", body="Your link is no longer valid, it was only valid for up to 5 minutes. You can also send another from <a href='/forgot-password' class='link'>here</a>. ")
        return render_template('reset-password.html')
    else:
        if request.form['new-password'] != request.form['confirm-password']:
            flash("Passwords do not match. ")
        else:
            db.reset_password(tokens, request.form['new-password'])
            flash('Password updated. ')
            return render_template('reset-password.html')

@app.errorhandler(404)
def error_404_handler(err):
    return render_template("HTTP Status Pages/404.html")

@app.errorhandler(403)
def error_403_handler(err):
    db.create_security_log("Attempted Forbidden Access",
                           session.get("email", "not registered"),
                           request.headers.get('X-Forwarded-For', request.remote_addr),
                           details=f"""There has been an restricted attempted access to {request.url}""",
                           severity=db.SecurityLogSeverity.High 
                           )
    return render_template("HTTP Status Pages/403.html")

@app.errorhandler(500)
def error_500_handler(e):
    mail.send_error_email(session['email'], app, e)
    return render_template("HTTP Status Pages/500.html")

@app.route("/admin")
def server_dashboard():
    data = {
        'user_count': db.get_user_count(),
        'topics_count': db.get_topics_count()
    }
    return render_template("admin/server.html", **data)
@app.route("/admin/users")

def users_view():
    search_query = request.args.get('search', '')
    return render_template('/admin/users.html', 
                        users=db.search_users(search_query),
                        search_query=search_query)

@app.route('/admin/users/edit/<user_id>', methods=['GET', 'POST'])

def edit_user(user_id):
    user=db.get_user_by_id(user_id)
    if not user:
        abort(404)
    if request.method == 'POST':
        # Handle form submission
        if str(db.get_user(session["email"])['_id']) == user_id:
            session["email"] = request.form['email']
        db.edit_user(user_id, request)

        return redirect('/admin/users')
    
    return render_template('/admin/edit-user.html', user=user)
@app.route('/admin/users/verify/<user_id>')

def verify_user(user_id):
    db.verify_user(user_id)
    return redirect("/admin/users")
@app.route('/admin/users/delete/<user_id>', methods=["POST"])

def delete_user(user_id):
    db.delete_user(user_id)
    return redirect("/admin/users")

@app.route('/admin/topics')
def manage_topics():
    # Get search query from URL parameters
    search_query = request.args.get('search', '').strip()
    
    # Get topics from database
    topics = db.search_topics(search_query)
    for t in topics:
        t["user_name"] = db.get_topic_holders(t['_id'])
    return render_template(
        'admin/topics.html',
        topics=topics,
        search_query=search_query
    )


@app.route('/admin/topics/delete/<topic_id>', methods=['POST'])
def admin_delete_topic(topic_id):
    success = db.delete_topic(topic_id)
    if success:
        flash('Topic deleted successfully', 'success')
    else:
        flash('Failed to delete topic', 'error')
    return redirect("/admin/topics")

@app.route('/admin/security-logs')
def security_logs():
    search_query = request.args.get('search', '')
    severity_filter = request.args.get('severity', "all")
    
    logs = db.search_security_logs(search_query, severity_filter)

    return render_template('/admin/security-logs.html',
                        logs=logs,
                        current_severity=severity_filter,
                        search_query=search_query)

@app.before_request
def before_request():
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
    if request.path.startswith("/admin") and not db.get_user(session['email'])['is_admin']:
        abort(403)
@app.route('/')
@security.no_authentication
def home():
    return render_template('visitors/index.html') 

@app.route('/about')
@security.no_authentication
def about():
    return render_template('visitors/about.html')

@app.route('/privacy')
@security.no_authentication
def privacy():
    return render_template('visitors/privacy.html')

@app.route('/terms')
@security.no_authentication
def terms():
    return render_template('visitors/terms.html')

@app.route('/contact', methods=["GET", "POST"])
@security.no_authentication
def contact():
    if request.method == "POST":
        mail.send_contact_email(request.form['subject'], f"From: {request.form['name']}\nEmail: {request.form['email']}\nMessage: {request.form['message']}")
        flash('Thank you for your message! We will get back to you soon.', 'success')
    return render_template('visitors/contact-us.html')
if __name__ == '__main__':
    app.run(debug=True)

