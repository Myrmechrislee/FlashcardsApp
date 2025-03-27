from flask import Flask, render_template, jsonify, request, redirect, Response, flash, session, send_file
import random, db, io, csv, pandas as pd, re, os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

app = Flask(__name__, static_folder="static", static_url_path="", template_folder="pages")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = "ce4f9f579b2a22b536d9fa989b0847ce"
app.config['SESSION_COOKIE_NAME'] = "flask_app_session"

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
SEND_EMAIL = os.environ.get("SENDER_EMAIL", "flashcards@leechengzhu.com")
app_url = os.environ.get("APP_URL", "http://localhost:8080/").rstrip('/')

@app.route('/topics', methods=["GET", "POST"])
def topics():
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    if not db.email_is_verified(session['email']):
        return redirect('/validate-email-message')
    return render_template("topics.html", user=db.get_user(session["email"]), topics=db.get_topics(session["email"]))

@app.route("/flash/<tid>/<qid>")
def flashcard(tid, qid):
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(tid)
    if topic == None:
        return "topic not found", 404
    if not db.has_access_to_topic(session["email"], tid):
        return "No access", 403
    questions = topic["questions"]
    question = [q for q in questions if str(q["id"]) == str(qid)]
    if len(question) == 0:
        return "question not found", 404
    return render_template("flash.html", t=db.get_topic(tid), question=question[0])

@app.route("/quiz/<tid>")
def quiz(tid):
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(tid)
    if topic == None:
        return "topic not found", 404
    if not db.has_access_to_topic(session["email"], tid):
        return "No access", 403
    
    questions = topic['questions']
    if request.args.get('randomize', default=False, type=bool):
        questions = random.sample(questions, len(questions))
    if request.args.get('skip-confident', default=False, type=bool):
        questions = [q for q in questions if int(q['confidence']) != 2]
    id = db.generate_quiz(session['email'], tid, questions)

    return redirect(f'/quizlet/{id}/{questions[0]["id"]}')

@app.route("/quizlet/<quizid>/<qid>")
def quizlet(quizid, qid):
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    if not db.has_access_to_quiz(session["email"], quizid):
        return "No access", 403
    quiz = db.get_quiz(quizid)
    if not quiz:
        return "Page not found", 404
    questions = quiz['questions']
    question = [q for q in questions if str(q['id']) == qid]
    if len(question) == 0:
        return "Question not found", 404
    return render_template("/quizlet.html", t=db.get_topic(quiz["topic_id"]), quizid=quizid, qid=qid, question=question[0], streak=db.get_streak(quizid))

@app.route("/answer-quizlet/<quizid>/<qid>")
def answer_quizlet(quizid, qid):
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    if not db.has_access_to_quiz(session["email"], quizid):
        return "No access", 403
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
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(tid)
    if topic == None:
        return "topic not found", 404
    if not db.has_access_to_topic(session["email"], tid):
        return "No access", 403
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
    if "email" not in session:
        return redirect(f'/?next={request.url}')
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
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(id)
    if topic == None:
        return 404
    if not db.has_access_to_topic(session["email"], id):
        return "No access", 403
    return render_template("topic-start.html", t=topic)

@app.route('/edit-topic/<id>', methods=['GET', 'POST'])
def edit_topic(id):
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(id)
    if topic == None:
        return "Topic not found", 404
    if not db.has_access_to_topic(session["email"], id):
        return "No access", 403
    
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
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(id)
    if topic == None:
        return "Topic not found", 404
    if not db.has_access_to_topic(session["email"], id):
        return "No access", 403
    db.delete_topic(id)
    return redirect("/topics")

@app.route("/export-csv/<id>")
def export_csv(id):
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(id)
    if topic == None:
        return "Topic not found", 404
    if not db.has_access_to_topic(session["email"], id):
        return "No access", 403
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
    if "email" not in session:
        return redirect(f'/?next={request.url}')
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
@app.route("/", methods=["GET", "POST"])
def login():
    if "email" in session:
        return redirect("/topics")
    if request.method == "POST":
        success, user = db.test_login(request.form["email"], request.form["password"])
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
    return redirect("/")
@app.route("/create-account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        if db.email_already_exists(request.form["email"]):
            flash("Email already exists", category="error")
        else:
            db.add_user(request.form["name"], request.form["email"], request.form["password"])
            verification_code = db.set_verification_code(request.form["email"])
            html_content = render_template('email_templates/confimation.html', verification_link=f'{app_url}/verify-email?token={verification_code}')
            msg = Mail(
                from_email=SEND_EMAIL,
                to_emails=request.form["email"],
                subject="Email Verification",
                html_content=html_content
            )
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            sg.send(msg)
            flash("Account successfully added! A verification message has been sent. Please check your email. ")
    return render_template("create-account.html")

@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():
    if "email" not in session:
        return redirect(f'/?next={request.url}')
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
        return "File not found", 404

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

    if "email" not in session:
        return redirect(f'/?next={request.url}')
    return render_template('message.html', title = 'Please Validate Your Email', body="""<p>We've sent a verification email to your inbox. Please check your email and click on the link to validate your account.</p>
        <p>If you didn't receive the email, you can <a href="/send-verification-email" class="link">resend the verification email</a>.</p>""")

@app.route('/send-verification-email')
def send_verification_email():
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    
    verification_code = db.set_verification_code(session['email'])
    html_content = render_template('email_templates/confimation.html', verification_link=f'{app_url}/verify-email?token={verification_code}')
    msg = Mail(
        from_email=SEND_EMAIL,
        to_emails=session['email'],
        subject="Email Verification",
        html_content=html_content
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(msg)
    return render_template('message.html', title='Email Sent', body="""<p>The verification has been sent. Please check your email. </p>
    """)
@app.route("/verify-email")
def verify_email():
    token_sent = request.args.get('token')
    if db.validate_code(token_sent):
        data = {
            "title": "Thank You!",
            "body": """Your email has been confirmed. You can now get started with the link below. Click <a href='/' class='link'>here</a> to get started. """,
        }
    else:
        data = {
            "header": "Link Expired",
            "body": """This verification link is out of date. Please use the most recent link sent to your email. Or you can click <a href='/send-verification-email' class='link'>here</a> to send another one. """,
        }
    
    return render_template('message.html', **data)

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template('forgot-password.html')
    email = request.form['email']
    if not db.email_already_exists(email):
        flash("Email isn't registered. ")
        return render_template('forgot-password.html')
    
    url = db.set_reset_password_link(email)
    html_content = render_template('email_templates/reset-password.html', reset_password_link=app_url + url)
    msg = Mail(
        from_email=SEND_EMAIL,
        to_emails=email,
        subject="Reset Password",
        html_content=html_content
    )
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    sg.send(msg)
    return render_template('message.html', title="Password Reset", body="The instructions to reset your password has been sent. Please check your email. ")

@app.route('/reset-password', methods=["GET", "POST"])
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
if __name__ == '__main__':
    app.run(debug=True)

