from flask import Flask, render_template, request, redirect, url_for, session
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import datetime
from flask_mail import Mail, Message


app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Configure MongoDB
app.config["MONGO_URI"] = "mongodb://localhost:27017/event_management"
mongo = PyMongo(app)

# Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'rraoksolves@gmail.com'
app.config['MAIL_PASSWORD'] = '@007ksolvesRuchir'  # Use app-specific password or environment variable for security
app.config['MAIL_DEFAULT_SENDER'] = 'rraoksolves@gmail.com'

mail = Mail(app)

# Route for registration (for both user and admin)
@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # Role can be 'user' or 'admin'
        
        user = {
            "name": name,
            "email": email,
            "password": password,  # In production, hash the password
            "role": role,
            "rsvp_events": []
        }
        mongo.db.users.insert_one(user)
        
        session['user_id'] = str(user['_id'])
        session['role'] = role
        
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('list_events'))
    
    return render_template('register.html')

@app.route('/event/<event_id>')
def event_detail(event_id):
    # Logic to fetch the event by event_id and display its details
    event = mongo.db.events.find_one({'_id': ObjectId(event_id)})
    if event:
        return render_template('event_detail.html', event=event)
    else:
        return "Event not found", 404


# Route for login``
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = mongo.db.users.find_one({"email": email, "password": password})
        
        if user:
            session['user_id'] = str(user['_id'])
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('list_events'))
        else:
            return "Invalid credentials"
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # Clear session
    return redirect(url_for('login'))

# Route for the admin dashboard
@app.route('/admin')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        events = mongo.db.events.find()
        events_list = []
        for event in events:
            # Convert attendees ObjectIds to actual user details
            attendees = mongo.db.users.find({'_id': {'$in': event['attendees']}})
            event_dict = {
                **event,
                '_id': str(event['_id']),
               
                'attendees': list(attendees)  # Fetch attendees details
            }
            events_list.append(event_dict)
        return render_template('admin_dashboard.html', events=events_list)
    return redirect(url_for('login'))


@app.route('/event/edit/<event_id>', methods=['GET', 'POST'])
def edit_event(event_id):
    event = mongo.db.events.find_one({'_id': ObjectId(event_id)})

    if request.method == 'POST':
        # Update the event based on form input
        updated_event = {
            'name': request.form.get('name'),
            'description': request.form.get('description'),
            'location': request.form.get('location')
        }

        mongo.db.events.update_one({'_id': ObjectId(event_id)}, {'$set': updated_event})
        return redirect(url_for('admin_dashboard'))  # Redirect to admin dashboard after editing

    return render_template('edit_event.html', event=event)

# Route to create an event (Admin only)
@app.route('/events/create', methods=['GET', 'POST'])
def create_event():
    if 'role' in session and session['role'] == 'admin':
        if request.method == 'POST':
            event_name = request.form['name']
            description = request.form['description']
    
            location = request.form['location']
            
            event = {
                "name": event_name,
                "description": description,
               
                "location": location,
                "created_by": session['user_id'],
                "attendees": []
            }
            mongo.db.events.insert_one(event)
            return redirect(url_for('admin_dashboard'))
        
        return render_template('create_event.html')
    return redirect(url_for('login'))

# Route to manage attendees (Admin only)
@app.route('/events/<event_id>/manage_attendees', methods=['GET', 'POST'])
def manage_attendees(event_id):
    if 'role' in session and session['role'] == 'admin':
        event = mongo.db.events.find_one({"_id": ObjectId(event_id)})
        
        # Fetch the details of attendees (if any)
        attendees = []
        if event['attendees']:
            attendee_ids = event['attendees']  # List of ObjectIds
            attendees = list(mongo.db.users.find({'_id': {'$in': attendee_ids}}))
        
        return render_template('manage_attendees.html', event=event, attendees=attendees)
    return redirect(url_for('login'))

# User functionality to view events and RSVP
@app.route('/events')
def list_events():
    if 'role' in session:
        events = mongo.db.events.find()
        return render_template('list_events.html', events=events)
    return redirect(url_for('login'))

# RSVP for an event (Users only)
@app.route('/events/<event_id>/rsvp', methods=['POST'])
def rsvp(event_id):
    if 'role' in session and session['role'] == 'user':
        user_id = session['user_id']
        event = mongo.db.events.find_one({"_id": ObjectId(event_id)})

        if ObjectId(user_id) not in event['attendees']:
            mongo.db.events.update_one(
                {"_id": ObjectId(event_id)},
                {"$push": {"attendees": ObjectId(user_id)}}
            )
            mongo.db.users.update_one(
                {"_id": ObjectId(user_id)},
                {"$push": {"rsvp_events": ObjectId(event_id)}}
            )
        return redirect(url_for('list_events'))
    return redirect(url_for('login'))

# Functionality for sending reminders (Admin only)
@app.route('/events/<event_id>/send_reminder', methods=['POST'])
def send_reminder(event_id):
    if 'role' in session and session['role'] == 'admin':
        event = mongo.db.events.find_one({"_id": ObjectId(event_id)})
        attendee_ids = event['attendees']
        attendees = mongo.db.users.find({'_id': {'$in': attendee_ids}})



        # Loop through attendees and send reminder emails
        for attendee in attendees:
            msg = Message(
                subject=f"Reminder for {event['name']} Event",
                recipients=[attendee['email']],
                body=f"Hi {attendee['name']},\n\nThis is a reminder for the event '{event['name']}' happening at {event['location']}.\n\nBest regards,\nEvent Management Team"
            )
            mail.send(msg)

        return redirect(url_for('manage_attendees', event_id=event_id))
    return redirect(url_for('login'))


@app.route('/events/<event_id>/delete', methods=['POST'])
def delete_event(event_id):
    if 'role' in session and session['role'] == 'admin':
        # Delete the event from the database
        mongo.db.events.delete_one({'_id': ObjectId(event_id)})
        
        # Redirect to the admin dashboard after deletion
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
