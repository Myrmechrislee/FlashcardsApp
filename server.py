from flask import Flask, render_template, jsonify, request, redirect, Response, flash, session, send_file
import random, db, io, csv, pandas as pd, re


app = Flask(__name__, static_folder="static", static_url_path="", template_folder="pages")
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.secret_key = "ce4f9f579b2a22b536d9fa989b0847ce"
app.config['SESSION_COOKIE_NAME'] = "flask_app_session"

@app.route('/topics', methods=["GET", "POST"])
def topics():
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    return render_template("topics.html", user=db.get_user(session["email"]), topics=db.get_topics(session["email"]))
@app.route("/flash/<tid>")
def flashcard(tid):
    if "email" not in session:
        return redirect(f'/?next={request.url}')
    topic = db.get_topic(tid)
    if topic == None:
        return "topic not found", 404
    if not db.has_access_to_topic(session["email"], tid):
        return "No access", 403
    question = random.choice(topic["questions"])
    return render_template("flash.html", t=db.get_topic(tid), question=question)

@app.route("/submitconfidence", methods=["POST"])
def submit_confidence():
    data = request.get_json()
    if 'confidence' in data and 'qid' in data and 'tid' in data:
        m = db.update_confidence(data["tid"], data["qid"], data["confidence"])
        print(m)
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
        return "topic not found", 404
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
        
        return redirect(f"/topic-start/{id}")
    
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
        db.add_user(request.form["name"], request.form["email"], request.form["password"])
        flash("Account successfully added!")
        return render_template("create-account.html")
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
            raise e
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
if __name__ == '__main__':
    app.run(debug=True)

