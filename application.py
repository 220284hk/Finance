import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    portfolio = db.execute('''SELECT symbol, quantity FROM buy WHERE user_id = :user_id;''', user_id = session["user_id"])
    final = {}
    for ele in portfolio:
        if ele["symbol"] in final:
            final[ele["symbol"]][1] += ele["quantity"]
        else:
            info = lookup(ele["symbol"])
            final[ele["symbol"]] = [info["name"], ele["quantity"], info["price"]]

    # Cleaning the portfolio in case the quantity is equal to 0
    list = []
    for stock in final:
        if final[stock][1] == 0:
            list.append(stock)

    for x in list:
        del final[x]

    del list

    # calculating total amount
    user_info = db.execute("SELECT * FROM users WHERE id = :user_id;", user_id = session["user_id"])

    # calculating total value of assets
    total = user_info[0]["cash"]
    for stock in final:
        total += final[stock][1] * final[stock][2]

    return render_template("index.html", portfolio=final, cash=user_info[0]["cash"], total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method=="GET":
        return render_template("buy.html")
    else:
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("Invalid stock name")
        else:
            # user info
            user_id = session["user_id"]
            user_info = db.execute("SELECT * FROM users WHERE id = :user_id;", user_id = user_id)
            # If the user does NOT have enough cash
            total_cost = lookup(symbol)["price"] * int(request.form.get("share"))
            if total_cost > user_info[0]["cash"]:
                return apology("Insufficient funds!")
            else:

                # debiting user's cash
                db.execute('''UPDATE users SET cash = :int
                            WHERE id = :id;''', int = user_info[0]["cash"] - total_cost, id = session["user_id"])

                # updating user's stock
                db.execute('''INSERT INTO buy (user_id, symbol, quantity, price)
                                VALUES (:id, :symbol, :quantity, :price);''',
                                id = session["user_id"], symbol = lookup(symbol)["symbol"],
                                quantity = int(request.form.get("share")),
                                price = lookup(symbol)["price"])

                return redirect("/")

@app.route("/history")
@login_required
def history():
    portfolio = db.execute('''SELECT symbol, quantity, price, "when" FROM buy WHERE user_id = :user_id;''', user_id = session["user_id"])
    return render_template("history.html", portfolio=portfolio)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method=="GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("Invalid stock name")
        else:
            return render_template("quoted.html", symbol = symbol, value = lookup(symbol)["price"])


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method=="GET":
        return render_template("register.html")
    else:
        users = db.execute("SELECT username FROM users")

        # info taken from the REGISTER page
        name = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Conditions to ensure new user is created
        if not name or not password or not confirmation:
            return apology("All inputs must be filled")
        elif password != confirmation:
            return apology("Password not consistent!")
        elif len(password) < 8:
            return apology("Password must be at least 8 characters")
        elif name == password:
            return apology("Password cannot be the same as username")
        elif name in password:
            return apology("Password cannot be in name")


        # Unique username
        for usernames in users:
            if name in usernames.values():
                return apology("That username is already taken!")

        db.execute('''INSERT INTO users (username, hash)
        VALUES (:x, :y);''', x = name, y = generate_password_hash(password))
        return render_template("login.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    portfolio = db.execute('''SELECT symbol, quantity FROM buy WHERE user_id = :user_id;''', user_id = session["user_id"])
    final = {}
    for ele in portfolio:
        if ele["symbol"] in final:
            final[ele["symbol"]][1] += ele["quantity"]
        else:
            info = lookup(ele["symbol"])
            final[ele["symbol"]] = [info["name"], ele["quantity"], info["price"]]

    # Cleaning the portfolio in case the quantity is equal to 0
    list = []
    for stock in final:
        if final[stock][1] == 0:
            list.append(stock)

    for x in list:
        del final[x]

    del list


    if request.method=="GET":
        return render_template("sell.html", portfolio=final)
    else:
        symbol = request.form.get("selected")
        share = int(request.form.get("share"))
        # amount sold for
        sell_value = share * final[symbol][2]

        if final[symbol][1] < share:
            return apology("INSUFFICIENT SHARES")
        else:
            db.execute('''INSERT INTO buy (user_id, symbol, quantity, price)
                VALUES (:id, :symbol, :quantity, :price);''',
                id = session["user_id"], symbol = symbol,
                quantity = -share,
                price = final[symbol][2])

            user_info = db.execute("SELECT cash FROM users WHERE id = :user_id;", user_id = session["user_id"])
            db.execute('''UPDATE users SET cash = :cash WHERE id = :id;''', cash = user_info[0]["cash"] + sell_value, id = session["user_id"])

            return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
