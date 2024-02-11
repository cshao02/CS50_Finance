import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta

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
    """Show portfolio of stocks"""
    #compute holdings to display
    holdings = []
    grand_total = 0
    user_id = session.get("user_id")
    symbols = db.execute("SELECT DISTINCT symbol FROM purchases WHERE user_id = ?", user_id)
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash_for_display = usd(cash[0]["cash"])

    #create a list of dict called holdings storing keys: symbol, name, shares, price and total.
    for symbol in symbols:
        qty_buy = db.execute("SELECT SUM(quantity) FROM purchases WHERE symbol = ? and user_id = ?", symbol["symbol"], user_id)
        qty_sell = db.execute("SELECT SUM(quantity) FROM sell WHERE symbol = ? and user_id = ?", symbol["symbol"], user_id)
        if not qty_sell[0]["SUM(quantity)"]:
            qty_sell[0]["SUM(quantity)"] = 0
        quantity = qty_buy[0]["SUM(quantity)"] - qty_sell[0]["SUM(quantity)"]
        dic = lookup(symbol["symbol"])
        dic["shares"] = quantity
        dic["price_display"] = usd(dic["price"])
        total = quantity * dic["price"]
        dic["total"] = usd(total)
        grand_total += total
        holdings.append(dic)

    grand_total_display = usd(cash[0]["cash"] + grand_total)

    #transfer the list of data to html to display on webpage
    return render_template("portfolio.html", holdings = holdings, cash_for_display = cash_for_display, grand_total_display = grand_total_display)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        stock = lookup(symbol)
        if not symbol:
            return apology("Symbol needed", 70)
        if not stock:
            return apology("Symbol doesn't exist", 70)
        try:
            if int(shares) <= 0:
                return apology("Please buy some shares", 70)
        except ValueError:
            return apology("Please use whole numbers", 70)

        user_id = session.get("user_id")
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)

        #check if can buy
        spending = stock["price"] * int(shares)
        if spending > cash[0]["cash"]:
            return apology("Insufficient cash", 4000)
        money_left = cash[0]["cash"] - spending

        #make the purchase
        now = datetime.now() + timedelta(hours = 8)
        time_now = now.strftime('%Y-%m-%d %H:%M:%S')
        db.execute("UPDATE users SET cash = ? WHERE id = ?", money_left, user_id)
        db.execute("INSERT INTO purchases(user_id, symbol, quantity, price, datetime) VALUES(?, ?, ?, ?, ?)", user_id, stock["symbol"], shares, stock["price"], time_now)
        return redirect("/")

    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, quantity, price, datetime FROM purchases")
    return render_template("history.html")


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)

        #when symbol doesn't exist
        if not quote:
            return apology("Symbol doesn't exist", 70)
        else:
            return render_template("quoted.html", quote = quote)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        #Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        #Ensure unique username
        if len(rows) != 0:
            return apology("username taken", 403)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 403)

        # Ensure passwords match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords don't match", 403)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))

        return redirect("/login")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please select a symbol", 70)
        shares = request.form.get("shares")
        try:
            if int(shares) <= 0:
                return apology("Please sell some shares", 70)
        except ValueError:
            return apology("Please use whole numbers", 70)
        shares1 = int(shares)
        stock = lookup(symbol)
        user_id = session.get("user_id")

        #check if sale can be made
        qty_buy = db.execute("SELECT SUM(quantity) FROM purchases WHERE symbol = ? and user_id = ?", symbol, user_id)
        qty_sell = db.execute("SELECT SUM(quantity) FROM sell WHERE symbol = ? and user_id = ?", symbol, user_id)
        if not qty_sell[0]["SUM(quantity)"]:
            qty_sell[0]["SUM(quantity)"] = 0
        quantity = qty_buy[0]["SUM(quantity)"] - qty_sell[0]["SUM(quantity)"]
        if shares1 > quantity:
            return apology("know your limits", 1639)

        #make the sale
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        final_amt = cash[0]["cash"] + stock["price"] * shares1
        now = datetime.now() + timedelta(hours = 8)
        time_now = now.strftime('%Y-%m-%d %H:%M:%S')
        db.execute("UPDATE users SET cash = ? WHERE id = ?", final_amt, user_id)
        db.execute("INSERT INTO sell(user_id, symbol, quantity, price, datetime) VALUES(?, ?, ?, ?, ?)", user_id, stock["symbol"], shares1, stock["price"], time_now)

        return redirect("/")

    else:
        user_id = session.get("user_id")
        symbols = db.execute("SELECT DISTINCT symbol FROM purchases WHERE user_id = ?", user_id)
        return render_template("sell.html", symbols = symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)