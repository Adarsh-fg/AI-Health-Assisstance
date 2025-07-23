# --- START OF FILE app.py ---
from flask import Flask, send_from_directory , render_template, request, session, jsonify, redirect, url_for, flash, Response
import google.generativeai as genai
from werkzeug.utils import secure_filename
import markdown
import threading
import time
import os
from datetime import datetime, timedelta
from database import *
from functools import wraps
import pytz 
import json
from pywebpush import webpush, WebPushException
import random
from dotenv import load_dotenv
from bs4 import BeautifulSoup 
from markdownify import markdownify as md

load_dotenv()  # Load environment variables from .env file


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for session

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash-latest")

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY") 

if not VAPID_PUBLIC_KEY:
    print("FATAL ERROR: VAPID_PUBLIC_KEY is not set in the environment.")

VAPID_CLAIMS = {
    "sub": "mailto:adarshai5770@gmail.com" # Use your email
}

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True) 

# --- Custom Jinja Filter for Timezone Conversion ---
@app.template_filter('to_local_time')
def to_local_time(utc_dt_str, user_tz_name='UTC'):
    if not utc_dt_str:
        return ""
    try:
        # Define the format of the UTC datetime string from the database
        utc_dt = datetime.strptime(utc_dt_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        utc_tz = pytz.timezone('UTC')
        local_tz = pytz.timezone(user_tz_name or 'UTC') # FIX: Also ensure user_tz_name is not None here
        
        utc_dt = utc_tz.localize(utc_dt)
        local_dt = utc_dt.astimezone(local_tz)
        
        return local_dt.strftime('%Y-%m-%d %I:%M %p')
    except (ValueError, pytz.UnknownTimeZoneError):
        return utc_dt_str # Return original string if conversion fails

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# In app.py
@app.route('/save-subscription', methods=['POST'])
@login_required
def save_subscription():
    user_id = session.get('user_id')
    print(f"--- ROUTE: /save-subscription for user_id: {user_id} ---")
    if not user_id:
        return jsonify({'error': 'User not logged in'}), 401
    
    subscription_data = request.get_json()
    if not subscription_data:
        print("ERROR in /save-subscription: No JSON data received.")
        return jsonify({'error': 'No subscription data received'}), 400
    
    print(f"Received subscription data: {subscription_data}")
    save_push_subscription(user_id, json.dumps(subscription_data))
    print(f"SUCCESS: Subscription for user {user_id} saved.")
    return jsonify({'success': True}), 201


def trigger_push_notification_for_user(user_id, title, body):
    subscription_json = get_push_subscription(user_id)
    if subscription_json:
        try:
            webpush(
                subscription_info=json.loads(subscription_json),
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            return True
        except WebPushException as ex:
            print(f"Web push failed: {ex}")
            # This can happen if the subscription is expired.
            # You might want to delete the expired subscription here.
            return False
    return False

# A test route to check if everything works
@app.route('/send-push-test', methods=['POST'])
@login_required
def send_push_test():
    user_id = session['user_id']
    if trigger_push_notification_for_user(user_id, "HealthCare AI Test", "This is a test notification to check if the system is working!"):
        flash("Test push notification sent successfully!", "success")
    else:
        flash("Could not send push notification. Do you have a subscription saved?", "error")
    return redirect(url_for('settings'))

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = get_user_by_id(session['user_id'])
        if not user or not user['is_admin']:
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Context Processor to make user object and notifications available in all templates ---
@app.context_processor
def inject_global_vars():
    context = {
        'VAPID_PUBLIC_KEY': VAPID_PUBLIC_KEY,
        'current_user': None,
        'site_notifications': []
    }
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user:
            context['current_user'] = user
            session['user_timezone'] = user.get('timezone', 'UTC')
        
        # --- Notification Logic ---
        if user:
            user_tz_name = session.get('user_timezone', 'UTC')
            user_tz = pytz.timezone(user_tz_name)
            now_local = datetime.now(user_tz)

            # 1. Appointment Reminders
            appointments = get_user_appointments(user['id'])
            for appt in appointments:
                try:
                    appt_dt_str = f"{appt['date']} {appt['time']}"
                    appt_dt_naive = datetime.strptime(appt_dt_str, '%Y-%m-%d %H:%M')
                    appt_dt_local = user_tz.localize(appt_dt_naive)
                    
                    # Check if the appointment is in the future but within the next 24 hours
                    if now_local < appt_dt_local < (now_local + timedelta(hours=24)):
                        context['site_notifications'].append({
                            'type': 'appointment',
                            'message': f"Appointment with Dr. {appt['doctor_name']} is soon.",
                            'time': appt_dt_local.strftime('%I:%M %p Today')
                        })
                except (ValueError, TypeError):
                    continue # Skip if date/time format is wrong

            # 2. Medication Reminders (for today)
            today_weekday = now_local.strftime('%A').lower()
            reminders = get_user_reminders(user['id'])
            for reminder in reminders:
                if reminder.get('days') and today_weekday in reminder['days'].split(','):
                    try:
                        rem_time = datetime.strptime(reminder['time'], '%H:%M').time()
                        # Check if the reminder time is in the future today
                        if now_local.time() < rem_time:
                             context['site_notifications'].append({
                                'type': 'medication',
                                'message': f"Time for your medication: {reminder['med_name']}.",
                                'time': rem_time.strftime('%I:%M %p')
                            })
                    except (ValueError, TypeError):
                        continue
    context['VAPID_PUBLIC_KEY'] = VAPID_PUBLIC_KEY
    return context

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('.', 'service-worker.js')

def check_reminders_and_send_pushes():
    """
    This function will run in a background thread.
    It checks for due reminders every 60 seconds.
    """
    print("Reminder check thread started.")
    with app.app_context():
        while True:
            utc_now = datetime.now(pytz.utc)
            print(f"--- Running Reminder Check at {utc_now.isoformat()} ---")

            # --- 1. Pill Reminders Check (Existing Logic) ---
            due_pill_reminders = get_due_reminders(utc_now)
            if due_pill_reminders:
                print(f"Found {len(due_pill_reminders)} due pill reminders.")
                for reminder in due_pill_reminders:
                    user_id = reminder['user_id']
                    title = "Medication Reminder"
                    body = f"It's time to take your medication: {reminder['med_name']}."
                    print(f"Sending pill reminder to user {user_id}")
                    trigger_push_notification_for_user(user_id, title, body)
            
            # --- START: 2. APPOINTMENT REMINDERS CHECK (NEW LOGIC) ---
            due_appt_reminders = get_due_appointment_reminders(utc_now)
            if due_appt_reminders:
                print(f"Found {len(due_appt_reminders)} due appointment reminders.")
                for appt in due_appt_reminders:
                    user_id = appt['user_id']
                    
                    # Get user's timezone to format the time correctly in the message
                    user = get_user_by_id(user_id)
                    user_tz = pytz.timezone(user.get('timezone', 'UTC'))
                    appt_dt_naive = datetime.strptime(f"{appt['date']} {appt['time']}", '%Y-%m-%d %H:%M')
                    appt_dt_local = user_tz.localize(appt_dt_naive)
                    
                    title = "Appointment Reminder"
                    body = f"Your appointment with Dr. {appt['doctor_name']} is at {appt_dt_local.strftime('%I:%M %p')} today."
                    
                    print(f"Sending appointment reminder to user {user_id}")
                    trigger_push_notification_for_user(user_id, title, body)
            # --- END: 2. APPOINTMENT REMINDERS CHECK ---

            time.sleep(59)

def clean_and_format(text):
    # Basic sanitization or formatting if needed
    return markdown.markdown(text) if not text.strip().startswith("<") else text

def get_gemini_response(prompt, context=""):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error calling Gemini API: {str(e)}")
        return "I apologize, but I'm having trouble connecting to my knowledge base right now. Please try again in a moment."

# --- Mode Switching ---
@app.route('/set-mode/<mode>')
@login_required
def set_mode(mode):
    session['mode'] = mode
    if mode == 'mental':
        return redirect(url_for('mental_health_home'))
    return redirect(url_for('index'))


# --- Main Routes ---
@app.route("/home")
@login_required
def index():
    session['mode'] = 'physical' # Default to physical health mode
    # Sample health tips
    tips = [
        {
            "title": "Daily Exercise Essentials",
            "category": "Physical Health",
            "content": "Regular physical activity is crucial for maintaining a healthy body. Aim for at least 30 minutes of moderate exercise daily, including cardio, strength training, and flexibility exercises.",
            "image": "https://images.unsplash.com/photo-1518611012118-696072aa579a?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80",
            "link": "https://www.cdc.gov/physicalactivity/basics/index.htm"
        },
        {
            "title": "Balanced Nutrition Guide",
            "category": "Nutrition",
            "content": "A well-balanced diet includes fruits, vegetables, whole grains, lean proteins, and healthy fats. Learn how to create nutritious meals that support your overall health.",
            "image": "https://images.unsplash.com/photo-1490645935967-10de6ba17061?w=500&auto=format&fit=crop&q=60",
            "link": "https://www.nhs.uk/live-well/eat-well/how-to-eat-a-balanced-diet/eating-a-balanced-diet/"
        },
        {
            "title": "Quality Sleep Habits",
            "category": "Sleep Health",
            "content": "Good sleep is essential for physical and mental health. Discover tips for better sleep hygiene, including consistent sleep schedules and creating a restful environment.",
            "image": "https://images.unsplash.com/photo-1511295742362-92c96b1cf484?w=500&auto=format&fit=crop&q=60",
            "link": "https://www.sleepfoundation.org/sleep-hygiene"
        },
        {
            "title": "Stress Management Techniques",
            "category": "Mental Health",
            "content": "Chronic stress can impact your physical health. Learn effective stress management techniques including meditation, deep breathing, and regular relaxation practices.",
            "image": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=500&auto=format&fit=crop&q=60",
            "link": "https://www.apa.org/topics/stress"
        },
        {
            "title": "Hydration Importance",
            "category": "Physical Health",
            "content": "Proper hydration is vital for body function. Learn how much water you need daily and tips for staying hydrated throughout the day.",
            "image": "https://images.unsplash.com/photo-1548839140-29a749e1cf4d?w=500&auto=format&fit=crop&q=60",
            "link": "https://hsph.harvard.edu/news/the-importance-of-hydration/"
        },
        {
            "title": "Posture and Ergonomics",
            "category": "Physical Health",
            "content": "Maintaining good posture and proper ergonomics can prevent pain and injury. Get tips for correct sitting, standing, and lifting techniques.",
            "image": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=500&auto=format&fit=crop&q=60",
            "link": "https://www.osha.gov/ergonomics"
        },
    ]
    return render_template("index.html", tips=tips)

@app.route('/mental-health-home')
@login_required
def mental_health_home():
    session['mode'] = 'mental'
    user_id = session['user_id']
    journal_summary = get_journal_summary(user_id)
    
    mood_chart_data = {
        "labels": [datetime.strptime(entry['logged_at'], '%Y-%m-%d').strftime('%b %d') for entry in journal_summary],
        "data": [entry['mood'] for entry in journal_summary],
        "sentiments": [entry['sentiment'] for entry in journal_summary]
    }
    
    # --- THIS IS THE BLOCK TO UPDATE ---
    mental_health_tips = [
        {
            "title": "Practice Mindfulness Daily",
            "category": "Mindfulness",
            "image": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?q=80&w=1999&auto=format&fit=crop", # <-- UPDATED IMAGE 1
            "link": "https://www.mindful.org/what-is-mindfulness/"
        },
        {
            "title": "The Importance of Quality Sleep",
            "category": "Wellbeing",
            "image": "https://images.unsplash.com/photo-1444212477490-ca407925329e?q=80&w=2070&auto=format&fit=crop",
            "link": "https://www.nimh.nih.gov/health/topics/sleep-and-your-mental-health"
        },
        {
            "title": "Connect with Others",
            "category": "Social Health",
            "image": "https://images.unsplash.com/photo-1524250502761-1ac6f2e30d43?q=80&w=1976&auto=format=fit=crop", # <-- UPDATED IMAGE 3 (Good practice to update all)
            "link": "https://www.helpguide.org/articles/mental-health/building-better-mental-health.htm"
        },
    ]
    # --- END OF THE BLOCK TO UPDATE ---

    return render_template(
        'mental_health_home.html', 
        mood_chart_data=json.dumps(mood_chart_data),
        mental_health_tips=mental_health_tips
    )

@app.route('/journal', methods=['GET', 'POST'])
@login_required
def journal():
    user_id = session['user_id']
    if request.method == 'POST':
        mood = request.form.get('mood')
        entry_text = request.form.get('entry_text')
        gratitude_text = request.form.get('gratitude_text')
        
        if mood:
            sentiment = "Neutral" # Default sentiment
            if entry_text:
                try:
                    sentiment_prompt = f"Analyze the sentiment of the following text. Respond with only a single word: 'Positive', 'Negative', or 'Neutral'. Text: '{entry_text}'"
                    sentiment_response = get_gemini_response(sentiment_prompt)
                    if sentiment_response.strip() in ['Positive', 'Negative', 'Neutral']:
                        sentiment = sentiment_response.strip()
                except Exception as e:
                    print(f"Could not analyze sentiment: {e}")
                    sentiment = "Neutral"

            add_journal_entry(user_id, int(mood), entry_text, gratitude_text, sentiment)
            flash('Your journal entry has been saved.', 'success')
            return redirect(url_for('mental_health_home'))
        else:
            flash('Please select a mood to save your entry.', 'error')
    
    # Fetch data for the page
    today_entry = get_todays_journal_entry(user_id)
    history_entries = get_all_journal_entries(user_id)
    
    return render_template('journal.html', today_entry=today_entry, history_entries=history_entries)

@app.route('/relax')
@login_required
def relax():
    return render_template('relax.html')


@app.route('/memory-game')
@login_required
def memory_game():
    return render_template('memory_game.html')

@app.route('/zen-garden')
@login_required
def zen_garden():
    return render_template('zen_garden.html')

@app.route('/coloring-book')
@login_required
def coloring_book():
    return render_template('coloring_book.html')

@app.route('/guided-meditation')
@login_required
def guided_meditation():
    return render_template('guided_meditation.html')

@app.route('/affirmations')
@login_required
def affirmations():
    affirmation_list = [
        "I am resilient, strong, and brave.",
        "I choose to be happy and to love myself today.",
        "My feelings are valid, and I am allowed to feel them.",
        "I am in control of my own life.",
        "I am proud of myself and all that I have accomplished.",
        "I am capable of overcoming any challenge that comes my way.",
        "I release all doubts and insecurities about myself.",
        "Today, I will focus on the positive.",
        "I am worthy of love, happiness, and success.",
        "I am enough just as I am."
    ]
    # Select one to show on initial load
    initial_affirmation = random.choice(affirmation_list)
    
    # Pass the initial one AND the full list as JSON to the template
    return render_template(
        'affirmations.html', 
        affirmation=initial_affirmation,
        affirmations_json=json.dumps(affirmation_list)
    )

@app.route('/resources')
@login_required
def resources():
    return render_template('resources.html')

@app.route('/mindful-chat', methods=['GET', 'POST'])
@login_required
def mindful_chat():
    user_id = session['user_id']
    user_tz = session.get('user_timezone') or 'UTC'
    
    if request.method == 'POST':
        user_message = request.form.get("question", "")
        if user_message:
            add_mental_chat_message(user_id, 'user', user_message)
            db_history = get_mental_chat_history(user_id)
            conversation_history = "\n".join([f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}" for msg in db_history[-8:]])

            prompt = f"""
            You are 'MindWell', a supportive and empathetic AI assistant. Your purpose is NOT to give advice or solutions, but to act as a reflective sounding board. You are trained in basic mindfulness and Cognitive Behavioral Therapy (CBT) techniques to help users explore their own thoughts and feelings.
            **Your Core Directives:**
            1.  **NEVER Give Advice or Medical Diagnoses:** Do not tell the user what to do. Do not suggest diagnoses like "it sounds like you have anxiety." This is critical.
            2.  **ASK Open-Ended, Reflective Questions:** This is your primary tool. Guide the user to think deeper about their own statements.
                *   Good examples: "How did that make you feel?", "What was going through your mind when that happened?", "Is there another way to look at that thought?", "What does 'failure' mean to you in this context?", "Thank you for sharing that. Could you tell me more about that feeling of being overwhelmed?"
            3.  **Validate and Empathize First:** Always start your response by acknowledging the user's feelings.
                *   Good examples: "That sounds incredibly stressful.", "It takes courage to share that.", "I can hear how frustrating that situation must be."
            4.  **Keep it Gentle and Brief:** Your responses should be short, calm, and conversational. Avoid long paragraphs.
            5.  **CRITICAL SAFETY PROTOCOL:** If the user's message contains any direct or indirect mention of self-harm, suicide, wanting to die, harming others, or being in immediate crisis, you MUST respond ONLY with the following text and nothing else:
                "It sounds like you are going through a very difficult time, and I'm very concerned for your safety. It's important to talk to someone who can help right now. Please connect with people who can support you by calling or texting 988 in the USA and Canada, or by calling 111 in the UK. They are available 24/7. Please reach out to them."
            **Recent Conversation:**
            {conversation_history}
            **User's new message:** {user_message}
            **Your Task:** Generate the next empathetic, question-based response following all the rules above.
            """
            ai_response = get_gemini_response(prompt)
            add_mental_chat_message(user_id, 'bot', ai_response)
        return redirect(url_for('mindful_chat'))

    chat_history = get_mental_chat_history(user_id)
    if not chat_history:
        welcome_message = "Welcome. This is a safe space to reflect on your thoughts. What's on your mind right now?"
        add_mental_chat_message(user_id, 'bot', welcome_message)
        chat_history = get_mental_chat_history(user_id)

    for message in chat_history:
        message['timestamp'] = to_local_time(message['timestamp'], user_tz)

    # THIS IS THE ONLY LINE THAT NEEDED TO CHANGE IN THIS FUNCTION
    return render_template('mindful_chat.html', 
        chat_history=chat_history,
        title="Mindful Chat",
        subtitle="A space to reflect on your thoughts with a supportive AI.",
        form_action=url_for('mindful_chat')
    )

@app.route('/clear-mental-chat', methods=['POST'])
@login_required
def clear_mental_chat():
    user_id = session['user_id']
    clear_mental_chat_history(user_id)
    flash('Mindful chat history has been cleared.', 'success')
    return redirect(url_for('mindful_chat'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    
    # Data for At a Glance cards
    appointments = get_user_appointments(user_id)
    now = datetime.now(pytz.timezone(user.get('timezone', 'UTC')))
    next_appointment = None
    for appt in appointments:
        appt_dt = datetime.strptime(f"{appt['date']} {appt['time']}", '%Y-%m-%d %H:%M')
        if appt_dt > now.replace(tzinfo=None):
            next_appointment = appt
            break
            
    total_exercises = len(get_user_exercise_log(user_id))

    # Data for BMI Gauge
    bmi = None
    if user.get('weight') and user.get('height'):
        try:
            bmi = user['weight'] / ((user['height']/100) ** 2)
        except ZeroDivisionError:
            bmi = None

    # Data for Weight Trend chart
    weight_history = get_user_weight_history(user_id)
    weight_chart_data = {
        "labels": [w['logged_at'] for w in weight_history],
        "data": [w['weight'] for w in weight_history]
    }
    
    # Data for Exercise Activity chart
    exercise_summary = get_exercise_summary(user_id)
    # Create a dictionary for the last 7 days initialized to 0
    last_7_days = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    exercise_chart_data = {day: 0 for day in last_7_days}
    for summary in exercise_summary:
        exercise_chart_data[summary['day']] = round(summary['total_duration'] / 60, 1) # convert to minutes
    
    exercise_chart_data_final = {
        "labels": [datetime.strptime(d, '%Y-%m-%d').strftime('%a') for d in exercise_chart_data.keys()],
        "data": list(exercise_chart_data.values())
    }

    return render_template('dashboard.html', 
        next_appointment=next_appointment,
        total_exercises=total_exercises,
        bmi=bmi,
        weight_chart_data=json.dumps(weight_chart_data),
        exercise_chart_data=json.dumps(exercise_chart_data_final)
    )

@app.route("/symptom", methods=["GET", "POST"])
@login_required
def symptom():
    result = None
    if request.method == "POST":
        symptoms = request.form.get("symptoms", "")
        severity = request.form.get("severity", "")
        duration = request.form.get("duration", "")
        
        prompt = f"""You are a medical AI assistant. Based on the following information, provide a comprehensive analysis:

Symptoms: {symptoms}
Severity: {severity}
Duration: {duration}

Please provide a detailed analysis in the following format:

1. Possible Conditions:
   - List 3-5 most likely conditions based on the symptoms
   - Include brief descriptions of each condition
   - Note that these are possibilities, not diagnoses
   - Consider the severity and duration in your analysis

2. Recommended Actions:
   - List immediate steps the person should take
   - Include when to seek emergency care
   - Suggest when to schedule a doctor's appointment
   - Consider the severity level in recommendations

3. Home Care Tips:
   - List 3-5 safe home remedies for symptom relief
   - Include lifestyle modifications that might help
   - Note any activities to avoid
   - Consider the duration of symptoms in suggestions

4. Department of Doctor to Consult:
   - Suggest the appropriate medical department based on symptoms
   - Provide a brief description of the department's focus
   - Note any specific tests or procedures they might perform

5. Important Disclaimer:
   - Clearly state this is not medical advice
   - Emphasize the need for professional medical consultation
   - Include a note about emergency situations

Format the response in clean HTML with appropriate headings and styling. Make it easy to read and understand."""

        try:
            response = model.generate_content(prompt)
            result = response.text
        except Exception as e:
            result = f"Error: {str(e)}"
    
    return render_template("symptom.html", result=result)

# In app.py

@app.route("/assistant", methods=["GET", "POST"])
@login_required
def assistant():
    user_id = session['user_id']
    user_tz = session.get('user_timezone') or 'UTC'

    if request.method == "POST":
        user_message = request.form.get("question")
        if user_message:
            # Save user message to the PHYSICAL chat table
            add_physical_chat_message(user_id, "user", user_message)
            
            db_history = get_physical_chat_history(user_id)
            conversation_context = ""
            for msg in db_history[-6:]:
                role = "Patient" if msg["role"] == "user" else "Doctor"
                conversation_context += f"{role}: {msg['content']}\n"
            
            prompt = f"""You are a friendly and professional general practitioner AI. Respond to the patient's question about **physical health** in a warm, conversational manner while maintaining medical accuracy. 
            Guidelines for your response:
            1. Use a friendly, approachable tone.
            2. Explain medical terms in simple language.
            3. Provide practical advice when appropriate.
            4. If the question is about mental health, gently suggest they use the 'Mindful Chat' feature instead.
            5. Keep answers concise.
            Recent conversation history:
            {conversation_context}
            Patient's Question: {user_message}
            Please format your response in clean HTML without code block markers.
            """
            try:
                ai_response = get_gemini_response(prompt)
                clean_response = clean_and_format(ai_response)
                # Save bot response to the PHYSICAL chat table
                add_physical_chat_message(user_id, "bot", clean_response)
            except Exception as e:
                error_message = "I apologize, but I'm having trouble connecting right now. Please try again."
                add_physical_chat_message(user_id, "bot", error_message)
            
        return redirect(url_for('assistant'))
    
    chat_history = get_physical_chat_history(user_id)
    if not chat_history:
        welcome_message = "Hello! I am your general health assistant. How can I help you with your physical health questions today?"
        add_physical_chat_message(user_id, "bot", welcome_message)
        chat_history = get_physical_chat_history(user_id)

    for message in chat_history:
        message['timestamp'] = to_local_time(message['timestamp'], user_tz)

    return render_template("assistant.html", 
        chat_history=chat_history,
        title="Health Assistant Chat",
        subtitle="Chat with our AI for general physical health questions.",
        form_action=url_for('assistant')
    )

@app.route('/clear-physical-chat', methods=['POST'])
@login_required
def clear_physical_chat():
    user_id = session['user_id']
    clear_physical_chat_history(user_id)
    flash('Physical health chat history has been cleared.', 'success')
    return redirect(url_for('assistant'))

@app.route("/health-metrics", methods=["GET", "POST"])
@login_required
def health_metrics():
    result = None
    if request.method == "POST":
        age = int(request.form["age"])
        gender = request.form["gender"]
        cholesterol = int(request.form["cholesterol"])
        sugar = int(request.form["sugar"])
        systolic = int(request.form["systolic"])
        diastolic = int(request.form["diastolic"])

        prompt = f"""
You are a professional medical assistant AI. Based on the following patient health metrics, provide an easy-to-understand, medically informed analysis.

Patient Information:
- Age: {age}
- Gender: {gender}
- Cholesterol: {cholesterol} mg/dL
- Blood Sugar: {sugar} mg/dL
- Blood Pressure: {systolic}/{diastolic} mmHg

Please provide the following sections in your response:

- headings in blue color

1. <h3>Individual Metric Analysis</h3>
   - Analyze each metric (Cholesterol, Sugar, Blood Pressure)
   - Indicate whether it's Normal, Warning, or Dangerous in green , orange, or red respectively
   - Explain what that means in layman's terms
   - Include optimal range for the age and gender

2. <h3>Health Risk Summary</h3> 
   - Assess overall health risk based on the metrics
   - Mention potential health conditions (e.g. prediabetes, hypertension)

3. <h3>Recommended Next Steps</h3>
   - Suggest medical follow-ups (e.g. tests, doctor visit)
   - Offer lifestyle tips for improvement (diet, exercise, etc.)

4. <h3>Disclaimer</h3>
   - Clearly mention this is not a medical diagnosis
   - Advise consultation with a healthcare professional

Make sure the response is in clean, readable HTML format and without code block markers like ```html..
        """

        try:
            response = model.generate_content(prompt)
            result = clean_and_format(response.text)
        except Exception as e:
            result = f"Error: {str(e)}"
    
    return render_template("health_metrics.html", result=result)

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = get_user_by_email(email)
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_timezone'] = user.get('timezone') or 'UTC'
            log_history(user['id'], 'Security', 'User logged in.')
            return redirect(url_for('index'))
        
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        age = request.form.get('age')
        gender = request.form.get('gender')
        timezone = request.form.get('timezone') or 'UTC'
        
        user_id = create_user(name, email, password, age, gender, timezone)
        if user_id:
            session['user_id'] = user_id
            session['user_name'] = name
            session['user_timezone'] = timezone
            log_history(user_id, 'Security', 'User logged in for the first time.')
            return redirect(url_for('index'))
        
        return render_template('register.html', error='Email already registered')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_history(session['user_id'], 'Security', 'User logged out.')
    session.clear()
    return redirect(url_for('login'))

@app.route('/medications')
@login_required
def medications():
    user_id = session['user_id']
    medications_data = get_user_medications(user_id)
    reminders_data = get_user_reminders(user_id)
    # Convert comma-separated days string to a list for the template
    for r in reminders_data:
        if r['days']:
            r['days'] = r['days'].split(',')
    return render_template('medications.html', medications=medications_data, reminders=reminders_data)

@app.route('/appointments')
@login_required
def appointments():
    user_id = session['user_id']
    appointments_data = get_user_appointments(user_id)
    return render_template('appointments.html', appointments=appointments_data)


# --- API Routes for CRUD Operations ---
@app.route('/api/log-exercise', methods=['POST'])
@login_required
def api_log_exercise():
    user_id = session['user_id']
    data = request.get_json()
    if not data or not all(k in data for k in ['exerciseName', 'duration', 'calories']):
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    log_id = log_exercise_entry(
        user_id,
        data['exerciseName'],
        data['duration'],
        data['calories']
    )
    if log_id:
        return jsonify({'success': True, 'log_id': log_id})
    return jsonify({'success': False, 'error': 'Failed to log exercise'}), 500


# -- Appointments API --
@app.route('/api/appointments', methods=['POST'])
@login_required
def api_add_appointment():
    user_id = session['user_id']
    data = request.json
    appointment_id = add_appointment(
        user_id, data['doctorName'], data['specialty'], data['date'],
        data['time'], data['reason'], data['reminderTime']
    )
    if appointment_id:
        return jsonify({'success': True, 'id': appointment_id}), 201
    return jsonify({'error': 'Failed to add appointment'}), 400

@app.route('/api/appointments/<int:appointment_id>', methods=['PUT'])
@login_required
def api_update_appointment(appointment_id):
    user_id = session['user_id']
    data = request.json
    if update_appointment(appointment_id, user_id, data):
        return jsonify({'success': True})
    return jsonify({'error': 'Update failed or not authorized'}), 400

@app.route('/api/appointments/<int:appointment_id>', methods=['DELETE'])
@login_required
def api_delete_appointment(appointment_id):
    user_id = session['user_id']
    if delete_appointment(appointment_id, user_id):
        return jsonify({'success': True}), 200
    return jsonify({'error': 'Delete failed or not authorized'}), 400

# -- Medications API --
@app.route('/api/medications', methods=['POST'])
@login_required
def api_add_medication():
    user_id = session['user_id']
    data = request.json
    medication_id = add_medication(
        user_id, data['name'], data['dosage'], data['frequency'],
        data['startDate'], data.get('endDate')
    )
    if medication_id:
        return jsonify({'success': True, 'id': medication_id}), 201
    return jsonify({'error': 'Failed to add medication'}), 400

@app.route('/api/medications/<int:medication_id>', methods=['PUT'])
@login_required
def api_update_medication(medication_id):
    user_id = session['user_id']
    data = request.json
    if update_medication(medication_id, user_id, data):
        return jsonify({'success': True})
    return jsonify({'error': 'Update failed or not authorized'}), 400

@app.route('/api/medications/<int:medication_id>', methods=['DELETE'])
@login_required
def api_delete_medication(medication_id):
    user_id = session['user_id']
    if delete_medication(medication_id, user_id):
        return jsonify({'success': True}), 200
    return jsonify({'error': 'Delete failed or not authorized'}), 400

# -- Reminders API --
@app.route('/api/reminders', methods=['POST'])
@login_required
def api_add_reminder():
    user_id = session['user_id']
    data = request.json
    reminder_id = add_reminder(
        user_id, data['medName'], data['time'], data['days'], medication_id=None
    )
    if reminder_id:
        return jsonify({'success': True, 'id': reminder_id}), 201
    return jsonify({'error': 'Failed to add reminder'}), 400

@app.route('/api/reminders/<int:reminder_id>', methods=['PUT'])
@login_required
def api_update_reminder(reminder_id):
    user_id = session['user_id']
    data = request.json
    if update_reminder(reminder_id, user_id, data):
        return jsonify({'success': True})
    return jsonify({'error': 'Update failed or not authorized'}), 400

@app.route('/api/reminders/<int:reminder_id>', methods=['DELETE'])
@login_required
def api_delete_reminder(reminder_id):
    user_id = session['user_id']
    if delete_reminder(reminder_id, user_id):
        return jsonify({'success': True}), 200
    return jsonify({'error': 'Delete failed or not authorized'}), 400


@app.route('/bmi')
@login_required
def bmi():
    return render_template('bmi.html')

@app.route('/calculate-bmi', methods=['POST'])
@login_required
def calculate_bmi():
    try:
        data = request.get_json()
        height = float(data['height']) / 100  # Convert cm to meters
        weight = float(data['weight'])
        age = int(data['age'])
        gender = data['gender']
        
        # Calculate BMI
        bmi = weight / (height * height)
        
        # Determine BMI category
        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25:
            category = "Normal weight"
        elif bmi < 30:
            category = "Overweight"
        else:
            category = "Obese"
        
        # Generate health advice using Gemini
        prompt = f"""As a health expert, provide personalized health and diet advice for a {age}-year-old {gender} with a BMI of {bmi:.1f} ({category}).
        Include:
        1. Brief analysis of their current BMI status
        2. Specific dietary recommendations
        3. Exercise suggestions
        4. Lifestyle modifications
        5. Health risks to be aware of
        6. Tips for maintaining or achieving a healthy BMI
        
        Keep the advice practical, actionable, and encouraging. Format the response in clear sections.
        Make sure the response is in clean, readable HTML format and without code block markers like ```html."""
        
        response = model.generate_content(prompt)
        advice = response.text
        
        return jsonify({
            'success': True,
            'bmi': bmi,
            'category': category,
            'advice': advice
        })
        
    except Exception as e:
        print(f"Error calculating BMI: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error calculating BMI'
        }), 500

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_id = session['user_id']

    if request.method == 'POST':
        try:
            # First, get the current state of the user from the database
            current_user_data = get_user_by_id(user_id)
            
            # Start with the existing data
            data = dict(current_user_data)

            # Update with data from the form, checking if the key exists in the form
            for key in data.keys():
                if key in request.form:
                    data[key] = request.form[key]

            # Special handling for checkboxes and nullable fields
            data['notifications_enabled'] = 'notifications_enabled' in request.form
            data['weight'] = float(request.form['weight']) if request.form.get('weight') else None
            data['height'] = float(request.form['height']) if request.form.get('height') else None
            data['blood_sugar'] = int(request.form['blood_sugar']) if request.form.get('blood_sugar') else None
            data['systolic_bp'] = int(request.form['systolic_bp']) if request.form.get('systolic_bp') else None
            data['diastolic_bp'] = int(request.form['diastolic_bp']) if request.form.get('diastolic_bp') else None
            data['cholesterol'] = int(request.form['cholesterol']) if request.form.get('cholesterol') else None

            # Handle photo upload separately
            if 'photo' in request.files:
                file = request.files['photo']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    update_user_photo(user_id, unique_filename)

            if update_user_details(user_id, data):
                session['user_name'] = data['name']
                session['user_timezone'] = data['timezone']
                flash('Your settings have been updated successfully!', 'success')
            else:
                flash('There was an error updating your settings.', 'error')

        except (ValueError, TypeError) as e:
            print(f"Error updating settings: {e}")
            flash('Invalid data submitted. Please check your inputs.', 'error')
        
        # Redirect back to the same tab
        active_tab = request.form.get('active_tab', 'Profile')
        return redirect(url_for('settings', tab=active_tab))

    active_tab = request.args.get('tab', 'Profile')
    user = get_user_by_id(user_id)
    history_data = get_user_history(user_id)
    timezones = pytz.all_timezones
    user_tz = session.get('user_timezone', 'UTC')
    return render_template('settings.html', user=user, timezones=timezones, history=history_data, user_tz=user_tz, active_tab=active_tab)


@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    user_id = session['user_id']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    user = get_user_by_id(user_id)

    if not user['password'] == current_password:
        flash('Your current password does not match.', 'error')
    elif new_password != confirm_password:
        flash('New passwords do not match.', 'error')
    elif len(new_password) < 6: # Basic validation
        flash('New password must be at least 6 characters long.', 'error')
    else:
        update_user_password(user_id, new_password)
        flash('Your password has been changed successfully.', 'success')
        
    return redirect(url_for('settings', tab='History'))


@app.route('/health-review', methods=['GET', 'POST'])
@login_required
def health_review():
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    medications = get_user_medications(user_id)
    appointments = get_user_appointments(user_id)
    
    result = None
    bmi = None
    bmi_category = "N/A"

    # Calculate BMI if possible
    if user.get('weight') and user.get('height'):
        try:
            weight_kg = float(user['weight'])
            height_m = float(user['height']) / 100
            if height_m > 0:
                bmi = weight_kg / (height_m ** 2)
                if bmi < 18.5: bmi_category = "Underweight"
                elif bmi < 25: bmi_category = "Normal weight"
                elif bmi < 30: bmi_category = "Overweight"
                else: bmi_category = "Obese"
        except (ValueError, TypeError, ZeroDivisionError):
            pass

    if request.method == 'POST':
        # Create a display string for BMI to handle None case safely
        if bmi is not None:
            bmi_display_string = f"{bmi:.2f} ({bmi_category})"
        else:
            bmi_display_string = "N/A (Please provide weight and height)"
            
        # Create detailed data strings for the prompt
        med_list = "\n".join([f"- {m['name']} ({m['dosage']})" for m in medications]) or "None"
        appt_list = "\n".join([f"- Dr. {a['doctor_name']} ({a['specialty']}) on {a['date']}" for a in appointments]) or "None"

        prompt = f"""
        You are a holistic AI health advisor. Your goal is to provide a comprehensive, empathetic, and actionable health review based on all available user data.

        **USER'S COMPLETE HEALTH PROFILE:**

        **1. Personal & Biometric Data:**
        - Age: {user.get('age')}
        - Gender: {user.get('gender', 'Not specified')}
        - Weight: {user.get('weight', 'N/A')} kg
        - Height: {user.get('height', 'N/A')} cm
        - Calculated BMI: {bmi_display_string}
        - Blood Sugar: {user.get('blood_sugar') or 'Not set'} mg/dL
        - Blood Pressure: {user.get('systolic_bp') or 'N/A'}/{user.get('diastolic_bp') or 'N/A'} mmHg
        - Cholesterol: {user.get('cholesterol') or 'Not set'} mg/dL

        **2. Medical History:**
        - Blood Group: {user.get('blood_group', 'Not specified')}
        - Chronic Illnesses: {user.get('chronic_illnesses', 'None listed')}
        - Past Surgeries: {user.get('past_surgeries', 'None listed')}
        - Family Genetic Diseases: {user.get('genetic_diseases', 'None listed')}

        **3. Current Health Management:**
        - Last Health Check-up: {user.get('last_checkup_date', 'Not specified')}
        - Current Medications: {med_list}
        - Upcoming Appointments: {appt_list}

        **INSTRUCTIONS FOR ANALYSIS:**
        Analyze all the provided data to create a cohesive health review. **Crucially, incorporate the user's specific health metrics (Blood Sugar, Blood Pressure, Cholesterol) into your analysis.** Structure your response in clean HTML with <h4> headings for each section. Do not include ```html markers.

        **1. Holistic Health Summary:**
           Start with an encouraging overview that synthesizes the user's overall situation based on their BMI, age, and chronic conditions. Mention their key health metrics if available and what they generally indicate.

        **2. Key Areas of Focus:**
           - **Biometric Analysis:** This is the most important section. Analyze their BMI, Blood Pressure, Sugar, and Cholesterol levels in the context of their age and health history. Provide tailored, specific advice for each metric. For example, if blood pressure is high, suggest specific dietary changes like reducing sodium.
           - **Chronic Condition Management:** If there are chronic illnesses (e.g., 'Hypertension'), cross-reference them with the listed medications and the user's recorded biometrics (e.g., 'Blood Pressure: 145/90'). Offer supportive tips for managing these conditions.
           - **Medical History Insights:** Briefly comment on how past surgeries or genetic factors might influence current health priorities.

        **3. Preventative Care & Check-ups:**
           - Analyze the "Last Health Check-up" date. Recommend a general timeline for their next routine check-up.
           - If they have upcoming appointments, suggest key questions to ask their doctor related to their profile data (e.g., "Given my blood pressure reading of 145/90, what should be our primary focus?").

        **4. Actionable Health Plan:**
           Create a simple, bulleted list of the top 3-5 most impactful recommendations. These should be a mix of diet, exercise, and lifestyle tips derived from the complete analysis, including the new health metrics.

        **5. Important Disclaimer:**
           **MANDATORY:** Conclude with a clear, bolded disclaimer: "**This is an AI-generated analysis and is not a substitute for professional medical advice. Always consult with a qualified healthcare provider for any health concerns or before making any changes to your health regimen.**"
        """
        
        try:
            response = model.generate_content(prompt)
            html_result = clean_and_format(response.text)

            # 1. Save the generated HTML review to the new database table.
            save_health_review(user_id, html_result)
            
            # 2. Set the result for immediate display.
            result_for_display = html_result
            
            # 3. Inform the user.
            flash("Your new AI Health Analysis has been generated and saved! You can download it with your full report in Settings.", "success")
        except Exception as e:
            result = f"Error generating analysis: {str(e)}"

        # We render the template directly to show the new review immediately
        return render_template('health_review.html', user=user, bmi=bmi, bmi_category=bmi_category, 
                               medications=medications, appointments=appointments, result=result_for_display)

    # On a GET request, show the most recent review from the database.
    result_for_display = get_latest_health_review(user_id)

    return render_template('health_review.html', user=user, bmi=bmi, bmi_category=bmi_category, 
                           medications=medications, appointments=appointments, result=result_for_display)

@app.route('/exercise')
@login_required
def exercise():
    user = get_user_by_id(session['user_id'])
    # Default weight if not set, for calorie calculation
    user_weight = user.get('weight') if user.get('weight') else 70.0 

    # Added MET values for calorie calculation
    exercise_list = [
        {"name": "Push-ups", "desc": "A classic bodyweight exercise for upper body strength.", "video_id": "IODxDxX7oi4", "met": 8.0},
        {"name": "Squats", "desc": "Targets your legs and glutes. Essential for lower body strength.", "video_id": "aclHkVaku9U", "met": 5.0},
        {"name": "Plank", "desc": "A core-strengthening exercise that improves posture and stability.", "video_id": "ASdvN_XEl_c", "met": 2.5},
        {"name": "Jumping Jacks", "desc": "A full-body cardio exercise that gets your heart rate up.", "video_id": "c4DAnQ6DtF8", "met": 8.0},
        {"name": "Lunges", "desc": "Works the quadriceps, glutes, and hamstrings.", "video_id": "QOVaHwm-Q6U", "met": 4.0},
        {"name": "Crunches", "desc": "A popular abdominal exercise to build core strength.", "video_id": "Xyd_fa5zoEU", "met": 3.0},
        {"name": "Burpees", "desc": "A high-intensity, full-body exercise for cardio and strength.", "video_id": "auBLPXO8Fww", "met": 9.0},
        {"name": "Mountain Climbers", "desc": "A great cardio exercise that also engages your core.", "video_id": "nmwgirgXLYM", "met": 8.0},
        {"name": "Glute Bridge", "desc": "Strengthens the glutes and hamstrings, improving hip stability.", "video_id": "wPM8icPu6H8", "met": 2.5},
        {"name": "Bicycle Crunches", "desc": "Targets the rectus abdominis and obliques for a strong core.", "video_id": "9FGilc_pcYg", "met": 3.0},
        {"name": "High Knees", "desc": "A simple yet effective cardio exercise to warm up the body.", "video_id": "D0Gg22y8v4g", "met": 8.0},
        {"name": "Leg Raises", "desc": "An effective exercise for the lower abdominal muscles.", "video_id": "l4kQd9eWJmk", "met": 2.5},
        {"name": "Wall Sit", "desc": "Builds isometric strength and endurance in glutes, calves, and quadriceps.", "video_id": "y-wV4JuaQjs", "met": 3.0},
        {"name": "Bird Dog", "desc": "Improves stability, encourages a neutral spine, and relieves low back pain.", "video_id": "wiFNA3sqjCA", "met": 2.5},
        {"name": "Supermans", "desc": "Strengthens the lower back, glutes, and hamstrings.", "video_id": "z6PJMT2y8GQ", "met": 2.5}
    ]
    return render_template('exercise.html', exercises=exercise_list, user_weight=user_weight)

@app.route('/exercise-log')
@login_required
def exercise_log():
    logs = get_user_exercise_log(session['user_id'])
    user_tz = session.get('user_timezone') or 'UTC'
    return render_template('exercise_log.html', logs=logs, user_tz=user_tz)


@app.route('/diet-plan', methods=['GET', 'POST'])
@login_required
def diet_plan():
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    result_for_display = None # This will hold the HTML version for the page

    if request.method == 'POST':
        # --- (The logic for creating the prompt is the same) ---
        bmi_string = "Not available (update weight/height in settings)"
        if user.get('weight') and user.get('height'):
            try:
                weight_kg = float(user['weight'])
                height_m = float(user['height']) / 100
                bmi = weight_kg / (height_m ** 2)
                bmi_string = f"{bmi:.1f}"
            except (ValueError, TypeError, ZeroDivisionError):
                pass
        
        # This prompt is good, but we will explicitly ask for HTML for display
        prompt = f"""
        You are an expert AI nutritionist. Based on the user's complete health profile, create a detailed and balanced 1-day diet plan.

        **USER PROFILE:**
        - Age: {user.get('age', 'N/A')}
        - Gender: {user.get('gender', 'N/A')}
        - Weight: {user.get('weight', 'N/A')} kg
        - Height: {user.get('height', 'N/A')} cm
        - BMI: {bmi_string}
        - Blood Sugar: {user.get('blood_sugar') or 'Not set'} mg/dL
        - Blood Pressure: {user.get('systolic_bp') or 'N/A'}/{user.get('diastolic_bp') or 'N/A'} mmHg
        - Cholesterol: {user.get('cholesterol') or 'Not set'} mg/dL
        - Chronic Illnesses: {user.get('chronic_illnesses', 'None specified')}
        - Goal: General health and wellness. If health metrics are outside normal ranges (e.g., high blood pressure, high blood sugar), the diet should be tailored to help manage these conditions.

        **INSTRUCTIONS:**
        Generate a diet plan with sections for Breakfast, Lunch, Dinner, and two Snacks.
        For each food item, provide:
        1.  **Food Item:** The name of the food.
        2.  **Quantity:** A reasonable serving size.
        3.  **Nutrition (Approximate):** Key nutritional information like Calories, Protein (g), Carbs (g), and Fat (g).
        
        **FORMATTING:**
        - Use clean HTML. Use `<h4>` for meal names.
        - Present the diet plan in a structured table for each meal.
        - Start with a brief summary of the plan's goals.
        - End with a few general tips and the **MANDATORY** disclaimer.
        - Do not include ```html markers.

        """
        # END: NEW, DUAL-FORMAT PROMPT
        try:
            response = model.generate_content(prompt)
            html_result = response.text
            
            # Save the HTML result to the database
            if save_diet_plan(user_id, html_result):
                flash("Your new diet plan has been generated and saved successfully!", "success")
            else:
                flash("Error saving the new diet plan.", "error")
            
            result_for_display = html_result

        except Exception as e:
            flash(f"An error occurred while generating the diet plan: {e}", "error")
            
        return render_template('diet_plan.html', result=result_for_display)

    # On a GET request, fetch the HTML from the database for display
    result_for_display = get_latest_diet_plan(user_id)
    return render_template('diet_plan.html', result=result_for_display)

@app.route('/download-report')
@login_required
def download_report():
    user_id = session['user_id']
    user = get_user_by_id(user_id)
    
    # --- Gather all data for the report ---
    appointments = get_user_appointments(user_id)
    medications = get_user_medications(user_id)
    exercise_logs = get_user_exercise_log(user_id)
    journal_entries = get_all_journal_entries(user_id)
    latest_diet_plan = get_latest_diet_plan(user_id)
    latest_health_review_html = get_latest_health_review(user_id)

    # --- Start building the report string ---
    report_content = []
    report_content.append("=========================================")
    report_content.append(f" Health Report for: {user['name']}")
    report_content.append(f" Report Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_content.append("=========================================\n")

    # --- Personal & Biometric Information ---
    report_content.append("\n--- Personal & Biometric Information ---\n")
    report_content.append(f"User ID: {user['id']}")
    report_content.append(f"Email: {user['email']}")
    report_content.append(f"Age: {user.get('age', 'N/A')}")
    report_content.append(f"Gender: {user.get('gender', 'N/A').capitalize()}")
    report_content.append(f"Weight: {user.get('weight', 'N/A')} kg")
    report_content.append(f"Height: {user.get('height', 'N/A')} cm")
    report_content.append(f"Blood Group: {user.get('blood_group', 'N/A')}")
    report_content.append(f"Blood Sugar: {user.get('blood_sugar', 'N/A')} mg/dL")
    report_content.append(f"Blood Pressure: {user.get('systolic_bp', 'N/A')}/{user.get('diastolic_bp', 'N/A')} mmHg")
    report_content.append(f"Cholesterol: {user.get('cholesterol', 'N/A')} mg/dL")

    # --- Medical History ---
    report_content.append("\n\n--- Medical History ---\n")
    report_content.append(f"Chronic Illnesses: {user.get('chronic_illnesses', 'None listed')}")
    report_content.append(f"Past Surgeries: {user.get('past_surgeries', 'None listed')}")
    report_content.append(f"Family Genetic Diseases: {user.get('genetic_diseases', 'None listed')}")

    # --- Current Medications ---
    report_content.append("\n\n--- Current Medications ---\n")
    if medications:
        for med in medications:
            report_content.append(f"- {med['name']} ({med['dosage']}), Frequency: {med['frequency']}")
    else:
        report_content.append("No medications listed.")

    # --- Upcoming Appointments ---
    report_content.append("\n\n--- Upcoming Appointments ---\n")
    if appointments:
        for appt in appointments:
            report_content.append(f"- Dr. {appt['doctor_name']} ({appt['specialty']}) on {appt['date']} at {appt['time']}")
    else:
        report_content.append("No upcoming appointments.")

    # --- Exercise Log ---
    report_content.append("\n\n--- Exercise Log ---\n")
    if exercise_logs:
        for log in exercise_logs:
            duration_min = log['duration_seconds'] // 60
            duration_sec = log['duration_seconds'] % 60
            timestamp = to_local_time(log['completed_at'], user['timezone'])
            report_content.append(f"- {timestamp}: {log['exercise_name']} for {duration_min}m {duration_sec}s (Est. {log['calories_burned']:.1f} kcal)")
    else:
        report_content.append("No exercises logged.")

    # --- Journal History ---
    report_content.append("\n\n--- Journal History ---\n")
    if journal_entries:
        mood_emojis = {1: 'Sad', 2: 'Okay', 3: 'Neutral', 4: 'Good', 5: 'Great'}
        for entry in journal_entries:
            mood = mood_emojis.get(entry['mood'], 'Unknown')
            report_content.append(f"Date: {entry['logged_at']} | Mood: {mood}")
            if entry['entry_text']:
                report_content.append(f"  Thoughts: {entry['entry_text']}")
            if entry['gratitude_text']:
                report_content.append(f"  Grateful for: {entry['gratitude_text']}")
            report_content.append("-" * 20)
    else:
        report_content.append("No journal entries found.")

    
    report_content.append("\n\n--- Most Recent AI Health Review ---\n")
    if latest_health_review_html:
        # Use markdownify to convert the stored HTML to clean text
        review_text = md(latest_health_review_html, heading_style="ATX")
        report_content.append(review_text)
    else:
        report_content.append("No AI Health Review has been generated yet.")
        
    report_content.append("\n\n--- Most Recent Diet Plan ---\n")
    if latest_diet_plan:
        # Use markdownify to intelligently convert HTML to clean, readable Markdown
        plan_text = md(latest_diet_plan, heading_style="ATX")
        report_content.append(plan_text)
    else:
        report_content.append("No diet plan has been generated and saved yet.")
    # END: NEW CONVERSION LOGIC

    # ... (rest of the function to serve the file) ...
    final_report = "\n".join(report_content)
    filename = f"HealthReport_{user['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt"

    return Response(
        final_report,
        mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

# --- Admin Routes ---
@app.route('/admin')
@admin_required
def admin_dashboard():
    all_users = get_all_users()
    total_users = len(all_users)
    # You can add more stats here, e.g., total appointments, exercises logged, etc.
    return render_template('admin_dashboard.html', users=all_users, total_users=total_users)

@app.route('/admin/view_user/<int:user_id>')
@admin_required
def admin_view_user(user_id):
    user = get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    # You can fetch all of the user's data to display
    history = get_user_history(user_id)
    appointments = get_user_appointments(user_id)
    medications = get_user_medications(user_id)
    
    return render_template('admin_view_user.html', 
        user=user, 
        history=history,
        appointments=appointments,
        medications=medications)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    admin_id = session['user_id']
    if user_id == admin_id:
        flash("You cannot delete your own admin account.", "error")
        return redirect(url_for('admin_dashboard'))
    
    user_to_delete = get_user_by_id(user_id)
    if user_to_delete:
        delete_user_and_data(user_id)
        log_history(admin_id, 'Admin', f"Deleted user '{user_to_delete['name']}' (ID: {user_id}).")
        flash(f"Successfully deleted user {user_to_delete['name']} and all their data.", "success")
    else:
        flash("User not found.", "error")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_block/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_block(user_id):
    admin_id = session['user_id']
    if user_id == admin_id:
        flash("You cannot block your own admin account.", "error")
        return redirect(url_for('admin_dashboard'))

    user_to_block = get_user_by_id(user_id)
    if user_to_block:
        new_status = toggle_user_block_status(user_id)
        status_text = "Blocked" if new_status else "Unblocked"
        log_history(admin_id, 'Admin', f"{status_text} user '{user_to_block['name']}' (ID: {user_id}).")
        flash(f"Successfully {status_text.lower()} user {user_to_block['name']}.", "success")
    else:
        flash("User not found.", "error")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/add_user', methods=['POST'])
@admin_required
def admin_add_user():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    age = request.form.get('age')
    gender = request.form.get('gender')
    
    if not all([name, email, password, age, gender]):
        flash('All fields are required to add a new user.', 'error')
        return redirect(url_for('admin_dashboard'))

    user_id = create_user(name, email, password, age, gender)
    
    if user_id:
        log_history(session['user_id'], 'Admin', f"Created a new user: '{name}' (ID: {user_id}).")
        flash(f"Successfully created user '{name}'.", "success")
    else:
        flash(f"An account with the email '{email}' already exists.", "error")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/toggle_admin/<int:user_id>', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    admin_id = session['user_id']
    if user_id == admin_id:
        flash("You cannot remove your own admin status.", "error")
        return redirect(url_for('admin_dashboard'))

    user_to_promote = get_user_by_id(user_id)
    if user_to_promote:
        new_status = toggle_user_admin_status(user_id)
        status_text = "Promoted to Admin" if new_status else "Demoted to User"
        log_history(admin_id, 'Admin', f"{status_text}: '{user_to_promote['name']}' (ID: {user_id}).")
        flash(f"Successfully {status_text.lower()} user {user_to_promote['name']}.", "success")
    else:
        flash("User not found.", "error")
        
    return redirect(url_for('admin_dashboard'))

if __name__ == "__main__":
    init_db()
    
    reminder_thread = threading.Thread(target=check_reminders_and_send_pushes, daemon=True)
    reminder_thread.start()
    
    app.run(debug=True, use_reloader=False)
# --- END OF FILE app.py ---