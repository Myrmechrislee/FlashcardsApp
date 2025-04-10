from flask import Blueprint, render_template, request, abort, redirect, session, flash
import db, requests

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route("/")
def server_dashboard():
    data = {
        'user_count': db.get_user_count(),
        'topics_count': db.get_topics_count()
    }
    return render_template("admin/server.html", **data)
@bp.route("/users")
def users_view():
    search_query = request.args.get('search', '')
    return render_template('admin/users.html', 
                        users=db.search_users(search_query),
                        search_query=search_query)

@bp.route('/users/edit/<user_id>', methods=['GET', 'POST'])
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
    
    return render_template('admin/edit-user.html', user=user)
@bp.route('/users/verify/<user_id>')
def verify_user(user_id):
    db.verify_user(user_id)
    return redirect("/admin/users")
@bp.route('/users/delete/<user_id>', methods=["POST"])
def delete_user(user_id):
    db.delete_user(user_id)
    return redirect("/admin/users")

@bp.route('/topics')
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


@bp.route('/topics/delete/<topic_id>', methods=['POST'])
def admin_delete_topic(topic_id):
    success = db.delete_topic(topic_id)
    if success:
        flash('Topic deleted successfully', 'success')
    else:
        flash('Failed to delete topic', 'error')
    return redirect("/admin/topics")

@bp.route('/security-logs')
def security_logs():
    search_query = request.args.get('search', '')
    severity_filter = request.args.get('severity', "all")
    
    logs = db.search_security_logs(search_query, severity_filter)

    return render_template('admin/security-logs.html',
                        logs=logs,
                        current_severity=severity_filter,
                        search_query=search_query)

@bp.route('/ip-lookup/<ip>')
def ip_lookup(ip):
    url = f"http://ip-api.com/json/{ip}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        return response.json()  # Return the response as JSON
    except requests.exceptions.RequestException as e:
        print(f"Error making request: {e}")
        return None