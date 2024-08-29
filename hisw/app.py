from flask import Flask, flash, redirect, render_template, request, session, jsonify
import openai
from datetime import timedelta
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required
from cs50 import SQL
#Configure application
app = Flask(__name__)

#Configure session to use filesystem
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=5)
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure library to use database
db = SQL("sqlite:///fitness.db")
# Set your OpenAI API key
openai.api_key = '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'

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/log", methods=["GET","POST"])
@login_required
def log():
    if request.method == "GET":
        return render_template("log.html")
    else:
        date = request.form.get("date")
        muscles = request.form.get("muscles")
        exercise_count = int(request.form.get("exercise_count"))
        existing_workout = db.execute("SELECT * FROM workouts WHERE date = ? AND user_id = ?", date, session["user_id"])
        if existing_workout:
            # Redirect to schedule or show a message
            flash("You have already logged a workout for this date. You can edit or delete it on the schedule page.")
            return redirect("/schedule")
        else:
            workout_id = db.execute("INSERT INTO workouts(date, target_muscles, user_id) VALUES(?,?,?)", date, muscles, session["user_id"])
            for i in range(exercise_count):
                exercise_name = request.form.get(f"exercise_{i}")
                sets = request.form.get(f"sets_{i}")
                weight = request.form.get(f"weight_{i}")
                db.execute("INSERT INTO exercises (workout_id, exercise_name, sets, weight) VALUES (?,?,?,?)", workout_id, exercise_name, sets, weight)

            flash("Logged")
            return render_template("log.html")

@app.route('/calculators', methods=["GET"])
@login_required
def calculators():
    return render_template("calculators.html")

@app.route("/schedule", methods=["GET","POST"])
@login_required
def schedule():
    workouts = []  # Initialize an empty list for workouts
    selected_date = None  # Initialize selected_date to None
    if request.method == "GET":
        return render_template("schedule.html")
    else:
        selected_date = request.form.get("date")
        workouts = db.execute(
        "SELECT exercises.id AS exercise_id, exercise_name, target_muscles, sets, weight FROM workouts JOIN exercises ON workouts.id = exercises.workout_id WHERE workouts.date=? AND workouts.user_id=?", selected_date, session["user_id"])
        return render_template("schedule.html", workouts=workouts, selected_date=selected_date)

@app.route("/delete_exercise/<int:exercise_id>", methods=["POST"])
@login_required
def delete_exercise(exercise_id):
    # Delete the exercise from the database
    db.execute("DELETE FROM exercises WHERE id = ?", exercise_id)

    # Redirect back to the schedule page with the same date to show updated exercises
    return redirect("/schedule")

@app.route("/edit_exercise/<int:exercise_id>", methods=["GET", "POST"])
@login_required
def edit_exercise(exercise_id):
    if request.method == "POST":
        # Handle form submission
        exercise_name = request.form.get("exercise_name")
        sets = request.form.get("sets")
        weight = request.form.get("weight")

        # Check that all fields are filled
        if not exercise_name or not sets or not weight:
            exercise = db.execute("SELECT * FROM exercises WHERE id = ?", exercise_id)
            return render_template("edit_exercise.html", exercise=exercise[0], error="All fields are required.")

        # Update the exercise in the database
        db.execute(
            "UPDATE exercises SET exercise_name = ?, sets = ?, weight = ? WHERE id = ?",
            exercise_name, sets, weight, exercise_id
        )
        return redirect("/schedule")

    # Handle GET request: Retrieve existing exercise data
    exercise = db.execute("SELECT * FROM exercises WHERE id = ?", exercise_id)
    if not exercise:
        return redirect("/schedule")

    return render_template("edit_exercise.html", exercise=exercise[0])


@app.route("/goals", methods=["GET", "POST"])
@login_required
def goals():
    if request.method == "GET":
        goals = db.execute("SELECT * FROM goals WHERE user_id =?", session["user_id"])
        return render_template("goals.html", goals=goals)
    else:
        goal = request.form.get("goal")
        target_date = request.form.get("target_date")
        user_id = session["user_id"]
        db.execute("INSERT INTO goals (goal, target_date, user_id) VALUES(?,?,?)", goal, target_date, user_id)
        return redirect("/goals")

@app.route("/delete_goal/<int:goal_id>", methods=["POST"])
@login_required
def delete_goal(goal_id):
    db.execute("DELETE FROM goals WHERE id =?", goal_id)
    return redirect("/goals")

@app.route("/complete_goal/<int:goal_id>", methods=["POST"])
@login_required
def complete_goal(goal_id):
    db.execute("UPDATE goals SET completed = 1 WHERE id = ?", goal_id)
    return redirect("/goals")

@app.route("/askai", methods=["GET","POST"])
@login_required
def askai():
    if request.method == "GET":
        return render_template("askai.html")
    else:
        user_input = request.form.get("question")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": user_input}
            ]
        )
        bot_reply = response['choices'][0]['message']['content']
    except openai.error.OpenAIError as e:
        bot_reply = f"Error: {e}"
    return jsonify({'answer': bot_reply})

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect("/")

@app.route("/login", methods=["GET", "POST"])
def login():
    # forget any user_id
    session.clear()

    # user reached route via POST( as by submitting a form)
    if request.method == "POST":
        #ensure email was submitted
        if not request.form.get("email"):
            return apology("must provide email", 403)
        #ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # query db for email
        rows = db.execute("SELECT * FROM users WHERE email = ?", request.form.get("email"))
        #ensure email exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid email and/or password", 403)

        #remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect("/")
    else:
        return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        #get details
        first_name = request.form.get("firstname")
        last_name = request.form.get("lastname")
        email = request.form.get("email")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        found = False
        #check blank field
        if not first_name or not last_name or not email or not password or not confirmation:
            return apology("Fill in missing field")
        #get email data from db
        rows=db.execute("SELECT email FROM users")
        #check password and confirmation match
        if password != confirmation:
            return apology("Password and confirmation not match")
        #check if email already existed
        for row in rows:
            if email == row["email"]:
                found = True
                return apology("email already exist")
        if found == False and password == confirmation:
            new_user = db.execute("INSERT INTO users (first_name, last_name, email, hash) VALUES (?,?,?,?)", first_name, last_name, email, generate_password_hash(password, method='pbkdf2', salt_length=16))
            session["user_id"] = new_user
            flash("Successful registered!")
            return redirect("/")
    else:
        return render_template("register.html")
