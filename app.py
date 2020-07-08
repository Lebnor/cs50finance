from __future__ import print_function # In python 2.7
import os
import datetime
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_sqlalchemy import SQLAlchemy

from flask_session.__init__ import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
import sys
from helpers import apology, login_required, lookup, usd, hash_password, verify_password
import time
from jinja2 import Environment


# Configure application
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://igdlkwpccoxodr:6732c3b2ac8d712593e7818bd233010517aee52ba68692cc46d4fc4278e6803e@ec2-34-224-229-81.compute-1.amazonaws.com:5432/d2qihlacmibfub'
db = SQLAlchemy(app)

app.config['SECRET_KEY'] = 'agjiodfgmkldrgoiergdlfkmdfglkdfg'

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

environment = Environment()
environment.filters['usd'] = usd

@app.template_filter('ctime')
def timectime(s):
    return time.ctime(s) # datetime.datetime.fromtimestamp(s)

@app.template_filter()
def numberFormat(value):
    return '${:.2f}'.format(float(value))

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

os.environ.setdefault("API_KEY", "pk_18b94b2663e14472a0090cfcea4081ec")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# DB models
class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=False)
    hash = db.Column(db.String(255), nullable=False)
    cash = db.Column(db.Integer)

    def __repr__(self):
        return str(self.__dict__)


class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    symbol = db.Column(db.String(80), nullable=False)
    amount = db.Column(db.Integer)
    price = db.Column(db.Integer)
    date = db.Column(db.Integer)

    def __repr__(self):
        return str(self.__dict__)

@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    id = session['user_id']
    # user = db.execute("SELECT username FROM users WHERE id=?", session['user_id'])
    user = Users.query.filter_by(id=id).first()
    # stocks = db.execute("SELECT * FROM history WHERE user_id=?", session['user_id'])
    # stocks = History.query.filter_by(user_id=id).all()
    stocks = History.query.filter_by(user_id=id).all()
    print(stocks)
    user_stock = {}

    total = 0
    print("===stocks===", stocks)
    for item in stocks:
        print("===", item)
        total = total + item.price * item.amount
        symbol = item.symbol

        if  item.symbol in user_stock:

            user_stock[symbol]['amount'] = user_stock[symbol]['amount'] + item.amount
            user_stock[symbol]['total'] = round(item.price *  user_stock[symbol]['amount'], 2)

        else:
            user_stock[symbol] = {}
            user_stock[symbol]['symbol'] = item.symbol
            user_stock[symbol]['name'] = lookup(symbol)['name']
            user_stock[symbol]['amount'] = item.amount
            user_stock[symbol]['price'] = item.price
            user_stock[symbol]['total'] = item.price * item.amount

    print(user)
    # cash = db.execute("SELECT cash FROM users WHERE id=?", session['user_id'])[0]['cash']
    cash = Users.query.filter_by(id=id).first().cash
    
    
    print("===CASH===", cash)
    total = total + cash

    return render_template("index.html", user=user, stocks=user_stock.values(), cash=cash, total=usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        quantity = float(request.form.get("quantity"))
        symbol = request.form.get("symbol")

        # check symbol is real
        if not lookup(symbol):
            return apology("Enter a real company symbol")

        cost = lookup(symbol)['price'] * quantity
        # current_money = db.execute("SELECT cash FROM users WHERE id=?", session['user_id'])
        user = Users.query.filter_by(id=session['user_id']).first()
        current_money = user.cash
        print(current_money)
        print(cost)

        # not enough money
        if current_money - cost < 0:
            return apology("You don't have enough money!")
        else:
            # make the purchase
            user_id = session['user_id']
            now = time.time()

            # save purchase history
            purchase_history = History(user_id=user_id, symbol=symbol, amount=quantity, date=now, price=lookup(symbol)['price'])
            db.session.add(purchase_history)
            db.session.commit()

            # update user data
            updated_money = current_money - cost
            user.cash = updated_money
            db.session.commit()

            return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session['user_id']
    # data = db.execute("SELECT symbol, amount, price, date FROM history WHERE user_id=?", user_id)
    # print("  DATA", data)
    history = History.query.filter_by(user_id=user_id).all()
    data = []
    
    for row in history:
        data.append({
            'price' : row.price,
            'amount' : row.amount,
            'symbol' : row.symbol,
            'date' : time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(row.date))
        })

    return render_template("history.html", data=data)


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
        username = request.form.get("username")
        input = request.form.get("password")
        # entered_password = hash_password(input)
        user_password = Users.query.filter_by(username=username).first().hash
        # Ensure username exists and password is correct
        if not username:
            return apology("invalid username", 403)
        
        if not verify_password(user_password, input):
            return apology("Invalid password")

        # Remember which user has logged in
        session["user_id"] = Users.query.filter_by(username=username).first().id

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
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        stock = lookup(symbol)
        return render_template("quoted.html", stock=stock, term=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("register.html")

    else:
        username = request.form.get("username")
        password = request.form.get("password")

        if not username:
             return apology("Please enter a name.")

        if not password:
            return apology("Please enter a password")

        # Check name doesn't exist
        has_name = Users.query.filter_by(username=username).first()
        if has_name:
            return apology("Name already exists.")

        # Check password and confirm password match
        if not password == request.form.get("confirm-password"):
            return apology("Please make sure your passwords match.")

        # Hash the password
        pw_hash = hash_password(password)
        print("===PW_HASH===", pw_hash)

        # Insert the user into the databse
        newUser = Users(username=username, hash=pw_hash, cash="10000")
        db.session.add(newUser)
        db.session.commit()
        return redirect("/")



@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user_id = session['user_id']

    if request.method == "GET":
        # stocks = db.execute("SELECT DISTINCT symbol FROM history WHERE user_id=?", user_id)
        stocks = set(History.query.filter_by(user_id=user_id).all())

        all_history = History.query.all()
        options = []
        for item in all_history:
            if item.user_id == user_id and item.symbol.lower() not in options:
                options.append(item.symbol)
        print("STOCKS: ", stocks)
        return render_template("sell.html", stocks=options)

    else:
        sold_stock = request.form.get("symbol")
        sold_amount = float(request.form.get("amount"))
        print("  SOLD_AMOUNT", sold_amount)
        price = lookup(sold_stock)['price']
        now = time.time()
        # db.execute("INSERT into history (user_id, symbol, amount, price, date) VALUES (?, ?, ?, ?, ?)",
        # user_id, sold_stock, sold_amount * - 1, price, now)
        purchase_history = History(user_id=user_id, symbol=sold_stock, amount=(sold_amount * - 1), price=price, date=now)
        db.session.add(purchase_history)
        db.session.commit()
        # current_money = db.execute("SELECT cash FROM users WHERE id=?", user_id)[0]['cash']
        current_money = Users.query.filter_by(id=user_id).first().cash
        print("  CURRENT MONEY", current_money)
        money_updated = current_money + (sold_amount * price)
        # db.execute("UPDATE users SET cash=? WHERE id=?", money_updated, user_id)
        user = Users.query.filter_by(id=user_id).first()
        user.cash = money_updated
        db.session.commit()
        print("  ", sold_stock, sold_amount)
        return redirect("/")

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
