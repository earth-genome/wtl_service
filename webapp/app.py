from flask import Flask, render_template, json, request, redirect, url_for, session, flash
import firebase
import random
import os
from scraper import main
from datetime import datetime
from config import FIREBASE_URL

app = Flask(__name__)


# Connect to firebase database.
fb = firebase.FirebaseApplication(FIREBASE_URL, None)


@app.route('/scrape')
def scrape():
    # Scrape news stories, bucket into raw_geo and raw_no_geo tables based on
    # whether there were facilities that were extracted and geolocated from
    # the story
    main.process()


@app.route('/')
def home():
    if not session.get('logged_in'):
        return render_template('login.html')
    else:
        return redirect(url_for('classify'))

 
@app.route('/login', methods=['POST'])
def do_login():
    if request.form['password'] == 'organize' and request.form['username'] == 'resist':
        session['logged_in'] = True
    else:
        flash('wrong password!')
    return home()


@app.route('/classify')
def classify():

    try:
        # Grab the first unvetted story in the geolocated table
        params={
            'orderBy': '"vetted"', 
            'equalTo': 'false',
            'limitToFirst': 1
        }

        res = fb.get("/", "raw_geo", params=params)
        [idx] = res.keys()
        [content] = res.values()

        return render_template('classify.html', data=content['meta'], idx=idx)

    except:
        # TODO: make this better able to handle bad requests.  Note that if
        # there are no unvetted stories, the fb.get request yields a 400 (bad
        # request) error, which is indistinguishable from other firebase
        # errors.
        return render_template('noneleft.html')


@app.route('/vet_story/<int:idx>')
def bucket(idx):
    # Geo is an argument for whether the story has been geolocated
    geo = str(request.args.get('geo'))

    # Add index and time of classification to the Tier I screening list
    if geo == "true":
        fb.put("/tierI", idx, {'vettime': datetime.utcnow().isoformat()})

    # Update the original record in raw_geo to reflect that vetting took place
    fb.patch("/raw_geo/" + str(idx), {"vetted": True})

    # After posting and patching, return the template for classify to get a
    # new story and do this again.
    return redirect(url_for('classify'))


if __name__ == '__main__':
    app.secret_key = os.urandom(12)
    app.run(host='0.0.0.0', debug=True)
