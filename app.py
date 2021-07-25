import os
import pdb
import re

from flask import Flask, render_template, request, flash, redirect, session, g, abort
import requests
from requests.api import get


#from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError


from forms import UserAddForm, LoginForm, MessageForm, UserUpdateForm
from models import db, connect_db, User, Message

from secret import API_BASE_URL, key, SECRET

##################  APPLE MUSIC ITEMS ###########################################



# You should keep your API key a secret (I'm keeping it here so you can run this app)



#######################################################################################


CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Get DB_URI from environ variable (useful for production/testing) or,
# if not set there, use development local db.
app.config['SQLALCHEMY_DATABASE_URI'] = (
    os.environ.get('DATABASE_URL', 'postgres:///socialmusic'))

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = True
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'SECRET')
#toolbar = DebugToolbarExtension(app)

connect_db(app)


##############################################################################
# User signup/login/logout


@app.before_request 
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""
   
    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])

    else:
        g.user = None


def do_login(user):
    """Log in user."""

    session[CURR_USER_KEY] = user.id

@app.route('/logout')
def do_logout():
    """Logout user."""

    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]
        flash('see you next time', 'success')
        return redirect('/login')


@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup.

    Create new user and add to DB. Redirect to home page.

    If form not valid, present form.

    If the there already is a user with that username: flash message
    and re-present form.
    """

    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()

        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)

        return redirect("/")

    else:
        return render_template('users/signup.html', form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""

    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data,
                                 form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)


@app.route('/logout')
def logout():
    """Handle logout of user."""

    # IMPLEMENT THIS


##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users.

    Can take a 'q' param in querystring to search by that username.
    """

    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)


@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""

    user = User.query.get_or_404(user_id)

    # snagging messages in order from the database;
    # user.messages won't be in order by default
    messages = (Message
                .query
                .filter(Message.user_id == user_id)
                .order_by(Message.timestamp.desc())
                .limit(100)
                .all())
    likes = [message.id for message in user.likes]
    return render_template('users/show.html', user=user, messages=messages, likes=likes)


@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    # return render_template('users/following.html', user=user)
    return render_template('users/following.html', user=user)



@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)


@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")


@app.route('/users/profile', methods=["GET", "POST"])
def profile():
    
    #user = User.query.get_or_404(user_id)
    form = UserUpdateForm()
    
    if form.validate_on_submit():
        try:
            user = User(username=form.username.data,
                        email=form.email.data,
                        image_url=form.image_url.data or User.image_url.default.arg,
                        header_image_url=form.header_image_url.data,
                        bio=form.bio.data,
                        password=form.password.data  
                        )
            db.session.add(user)
            
        
        except IntegrityError:
            flash("Username already taken", 'danger')
            return render_template('users/edit.html', form=form)
        db.session.commit()
        flash(f"Your profile Updated!!", "success")
        return redirect(f"/users/profile")

    return render_template('users/edit.html', form=form)
    

@app.route('/users/<int:user_id>/likes')
def show_likes(user_id):
    if not g.user:
        flash('Access unauthoried', 'danger')
        return redirect("/")
    user=User.query.get_or_404(user_id)
    return render_template('users/likes.html', user=user, likes=user.likes)


# @app.route('/messages/<int:message_id>/like', methods=['POST'])
# def add_like(message_id):
#     """Toggle a liked message for the currently-logged-in user."""

#     if not g.user:
#         flash("Access unauthorized.", "danger")
#         return redirect("/")

#     liked_message = Message.query.get_or_404(message_id)
#     if liked_message.user_id == g.user.id:
#         return abort(403)

#     user_likes = g.user.likes

#     if liked_message in user_likes:
#         g.user.likes = [like for like in user_likes if like != liked_message]
#     else:
#         g.user.likes.append(liked_message)

#     db.session.commit()

#     return redirect("/")



@app.route('/users/add_like/<int:message_id>', methods=["POST"])
def add_like(message_id):
    
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect('/')
    
    liked_message= Message.query.get_or_404(message_id)
    if liked_message.user_id == g.user.id:
        return redirect('/')
    
    user_likes=g.user.likes
    
    if liked_message in user_likes:
        g.user.likes=[like for like in user_likes if like !=liked_message]
    else:
        g.user.likes.append(liked_message)
    db.session.commit()
    return redirect("/")






@app.route("/users/<int:user_id>/profile", methods=["GET", "POST"])
def edit_user(user_id):
    """Show user edit form and handle edit."""

    user = User.query.get_or_404(user_id)
    form = UserUpdateForm()

    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.image_url=form.image_url.data 
        # user.header_image_url=form.header_image_url.data 
        user.bio=form.bio.data   
        user.password=form.password.data
        db.session.commit()
        flash(f"User {user.username} updated!", 'success')
        return redirect(f"/users/{user.id}")

    else:
        return render_template("users/edit.html", form=form)




    # IMPLEMENT THIS


@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")


##############################################################################
# Messages routes:

@app.route('/messages/new', methods=["GET", "POST"])
def messages_add():
    """Add a message:

    Show form if GET. If valid, update message and redirect to user page.
    """

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = MessageForm()

    if form.validate_on_submit():
        msg = Message(text=form.text.data)
        try:
            get_tracks(msg.text)
            
            g.user.messages.append(msg)
            db.session.commit()

            return redirect(f"/users/{g.user.id}")
        except:
            return redirect('messages/new.html')

    return render_template('messages/new.html', form=form)

# @app.route('/messages/new', methods=["GET","POST"])
# def messages_add():
#     """Add a message:

#     Show form if GET. If valid, update message and redirect to user page.
#     """

#     if not g.user:
#         flash("Access unauthorized.", "danger")
#         return redirect("/")

#     form = MessageForm()

#     # if form.validate_on_submit():
#     msg = Message(text=form.text.data)
#     #     songs=get_tracks(msg.text)
#     #     try:
            
            
            
#             # g.user.messages.append(msg)
#             # db.session.commit()

#         #     return render_template("/messages/mesIndex.html", songs=songs)
#         # except:
#         #     return redirect('messages/new.html')
        
#     # get_tracks(msg.text)
    
#     if not get_tracks(msg.text):
#         return redirect('messages/new.html')
#     else:
#         songs=get_tracks(msg.text)
        

#     return render_template('messages/mesIndex.html', form=form, songs=songs)


@app.route('/messages/<int:message_id>', methods=["GET"])
def messages_show(message_id):
    """Show a message."""

    msg = Message.query.get(message_id)
    
    
    tracks=get_tracks(msg.text)
    return render_template('messages/show.html', message=msg, tracks=tracks)


@app.route('/messages/<int:message_id>/delete', methods=["POST"])
def messages_destroy(message_id):
    """Delete a message."""

    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get(message_id)
    db.session.delete(msg)
    db.session.commit()

    return redirect(f"/users/{g.user.id}")



##################  APPLE MUSIC ITEMS ###########################################


# @app.route('/findSong')
# def list_users():
#     """Page with listing of users.

#     Can take a 'q' param in querystring to search by that username.
#     """

#     searchSong = request.args.get('f')

#     if not searchSong:
#         users = User.query.all()
#     else:
#         users = User.query.filter(User.username.like(f"%{search}%")).all()

#     return render_template('users/index.html', users=users)

def get_tracks(term):
    
    
    res = requests.get(
    API_BASE_URL, params={'term': term, 'limit':2})
    
    
    data=res.json()
    # if not data:
    #     messages=Message.query.all()
    #     return render_template('home.html', messages=messages)
    # else:
        
    singer=data["results"][0]["artistName"]
    songName=data["results"][0]["trackName"]
    single=data["results"][0]["previewUrl"]
    picture=data["results"][0]["artworkUrl100"]
    tracks={'singer':singer, 'songName':songName, 'single': single, 'picture':picture}
        
        
    return tracks
    
    
  






#####################################################################################


##############################################################################
# Homepage and error pages


@app.route('/')
def homepage():
    """Show homepage:

    - anon users: no messages
    - logged in: 100 most recent messages of followed_users
    """
    
   
    if g.user:
        following_ids = [f.id for f in g.user.following] + [g.user.id]
        messages = (Message
                    .query
                    .filter(Message.user_id.in_(following_ids))
                    .order_by(Message.timestamp.desc())
                    .limit(100)
                    .all())
        
       
        liked_msg_ids = [msg.id for msg in g.user.likes]

        return render_template('home.html', messages=messages, likes=liked_msg_ids)

    else:
        return render_template('home-anon.html')
    
    ######################################################################
######################  LIKES #####################################


    


##############################################################################
# Turn off all caching in Flask
#   (useful for dev; in production, this kind of stuff is typically
#   handled elsewhere)
#
# https://stackoverflow.com/questions/34066804/disabling-caching-in-flask

@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""

    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req


   