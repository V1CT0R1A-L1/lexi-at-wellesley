"""
Author: Victoria Lee, based on work from Amy Fung & Cynthia Wang & Sofia Kobayashi & Helen Mao
Date: 03/29/2025
Description: The main Slack bot logic for the food delivery data collection project
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import json
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from datetime import datetime
from helper_functions import *
from gemini import *
import messenger
import re

## Load environment variables ##
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

### CONSTANTS ###
DB_NAME = os.environ.get('DB_NAME')
BOT_ID = WebClient(token=os.environ.get('SLACK_BOT_TOKEN')).api_call("auth.test")['user_id']

## Path configurations ##
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BLOCK_MESSAGES_DIR = os.path.join(PROJECT_ROOT, 'all_connected', 'block_messages')

## Load message blocks ##
def load_message_block(filename):
    with open(os.path.join(BLOCK_MESSAGES_DIR, filename), 'r', encoding='utf-8') as infile:
        return json.load(infile)

MESSAGE_BLOCKS = {
    'headers': load_message_block('headers.json'),
    'channel_welcome': load_message_block('channel_welcome_message.json'),
    'channel_created': load_message_block('channel_created_confirmation.json'),
    'main_channel_welcome_message': load_message_block('main_channel_welcome_message.json'), 
    'essential_questions': load_message_block('essential_questions.json')
}

# Initialize Slack app
app = App(
    token=os.environ.get('SLACK_BOT_TOKEN'),
    signing_secret=os.environ.get('TASK_BOT_SIGNING_SECRET')
)
client = WebClient(token=os.environ.get('SLACK_BOT_TOKEN'))

### HELPER FUNCTIONS ###
# Add these helper functions
def db_operation(query, params=None, fetch_one=False, fetch_all=False):
    """Generic database operation handler"""
    conn = None
    try:
        conn = connectDB(DB_NAME)
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(query, params or ())
            conn.commit()
            if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                return cursor.rowcount > 0
            elif fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            conn.commit()
            return True
    except Exception as e:
        print(f"Database error: {e}")
        return False
    finally:
        if conn:
            conn.close()

def get_all_users_info() -> dict:
    '''
    Helper function to get all users info from slack
    Takes a users array we get from slack which is a SlackResponse object type
    Returns a dict type containing same info with user id as key
    '''
    # Get users list (requires the users:read scope)
    result = client.users_list()

    # Get all user info in result
    users_array = result["members"]
    users_store = {}

    # Turn the SlackResponse object type into dict type
    for user in users_array:
        if user['deleted'] == False:
            # Key user info on their unique user ID
            user_id = user["id"]
            # Store the entire user object (you may not need all of the info)
            users_store[user_id] = user
    
    return users_store

def get_current_unix_time():
    return int(time.time())

def format_unix_time(timestamp, format_str="%Y-%m-%d %H:%M"):
    """Convert Unix timestamp to human-readable string"""
    if timestamp is None:
        return "[Not Provided]"
    return datetime.fromtimestamp(timestamp).strftime(format_str)

def parse_human_time_to_unix(time_str):
    """Convert user-input time to Unix timestamp"""
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        return int(dt.timestamp())
    except ValueError:
        try:
            dt = datetime.strptime(time_str, "%H:%M")  # Assume today's date
            dt = dt.replace(year=datetime.now().year, 
                           month=datetime.now().month,
                           day=datetime.now().day)
            return int(dt.timestamp())
        except:
            return None

def create_response_record(user_id, channel_id):
    return db_operation(
        """INSERT INTO responses 
           (user_id, channel_id, submission_time) 
           VALUES (%s, %s, CURRENT_TIMESTAMP)""",
        (user_id, channel_id)
    )

def format_field_for_display(field_name, value):
    """Convert field values to human-readable format"""
    if field_name.endswith('_time') and value:
        if isinstance(value, (int, float)):  # Handle Unix timestamp
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
        return value.strftime("%Y-%m-%d %H:%M") if hasattr(value, 'strftime') else str(value)
    return str(value) if value else "[Not Provided]"

### MESSAGE HANDLERS ###
@app.event("file_created")
def handle_file_created_events(body, logger):
    logger.info(body)

@app.event("message")
def handle_message(payload, say):
    """Handle text messages and messages with files"""
    print(json.dumps(payload, indent=2))

    channel_id = payload.get('channel')
    user_id = payload.get('user')
    text = payload.get('text', '').strip().lower()
    subtype = payload.get('subtype')
    
    if subtype == "channel_join":
        print(f"[CHANNEL JOIN] User {user_id} joined channel {channel_id}", datetime.now())
        return

    if user_id == BOT_ID:
        return

    print(f"[USER MESSAGE] Message from {user_id}: {text}", datetime.now())
    if text in ["help", "?"]:
        print(f"[HELP REQUEST] User {user_id} requested help", datetime.now())
        say(text="Here's how I can help you!",
            blocks=MESSAGE_BLOCKS["main_channel_welcome_message"]['blocks'])
        return
    else:
        say("triggered!")
        

@app.action("start_language_report")
def handle_start_language_report(ack, body, client):
    ack()
    user_id=body['user']['id']

    try:
        channel_name = f"lexi-report-{int(time.time())}"
        response = client.conversations_create(name=channel_name, is_private=True)
        channel_id = response["channel"]["id"]

        create_response_record(user_id, channel_id)
        client.conversations_invite(channel=channel_id, users=[user_id])
        print(f"[RESPONSE STARTED] User {user_id} started new conversation at {datetime.now()}")
        client.chat_postMessage(channel=user_id, text=f"Created private channel for your order: <#{channel_id}>")

        ask_essential_question(channel_id)
    except SlackApiError as e:
        print(f"Error creating channel: {e.response['error']}")
        client.chat_postMessage(
            channel=user_id,
            text="Sorry, I couldn't create a private channel for your report. Please try again."
        )

def ask_essential_question(channel_id):
    client.chat_postMessage(
        channel=channel_id,
        blocks=MESSAGE_BLOCKS['essential_questions']["blocks"]
    )

@app.action("general_area_select")
def handle_some_action(ack, body, logger):
    ack()
    logger.info(body)

@app.action("determination_methods_checkboxes")
def handle_some_action(ack, body, logger):
    ack()
    logger.info(body)

@app.action('submit_essential_questions')
def handle_submit_essential_questions(ack, body, client, logger):
    try:
        ack()
        
        print(f"Full state_values: {json.dumps(body['state']['values'], indent=2)}")
        channel_id = body.get('channel', {}).get('id') or body.get('container', {}).get('channel_id')
        if not channel_id:
            raise ValueError("Could not determine channel ID")
            
        user_id = body['user']['id']
        state_values = body['state']['values']

        general_area = None
        for block_id, block_data in state_values.items():
            if "general_area_select" in block_data:
                general_area = block_data["general_area_select"].get("selected_option", {}).get("value")
                break

        general_area_others = state_values.get("general_area_others_block", {}).get("general_area_others_input", {}).get("value", "")
        exact_location = state_values.get("exact_location_block", {}).get("exact_location_input", {}).get("value")
        language_heard = state_values.get("language_heard_block", {}).get("language_heard_input", {}).get("value")

        # Handle checkbox options
        checkbox_data = state_values.get("determination_methods_checkboxes", {}).get("determination_methods_checkboxes", {})
        determination_methods = checkbox_data.get("selected_options", [])
        method_values = {item["value"]: True for item in determination_methods}
        language_familiarity_others_description = state_values.get("language_familiarity_others_block", {}).get("language_familiarity_others_input", {}).get("value", "")

        # Prepare updates
        updates = {
            "general_area": general_area,
            "exact_location": exact_location,
            "language_heard": language_heard,
            **method_values
        }

        print(f"Extracted updates: {updates}")

        if general_area_others:
            updates["general_area_others"] = general_area_others
        if language_familiarity_others_description:
            updates["language_familiarity_others_description"] = language_familiarity_others_description

        print(f"Updated extracted updates: {updates}")

        # Update database
        if update_response(channel_id, updates):
            client.chat_postMessage(
                channel=channel_id,
                text="🎉 Thank you for your submission!",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "🎉 *Thank you for your submission!*\nYour language report has been recorded."
                        }
                    }
                ]
            )
        else:
            client.chat_postMessage(
                channel=channel_id,
                text="⚠️ Your submission cannot be stored. Please try again."
            )

    except Exception as e:
        logger.error(f"Error processing submission: {e}")
        # Send error message to user if channel_id is available
        if 'channel_id' in locals():
            client.chat_postMessage(
                channel=channel_id,
                text="⚠️ There was an error processing your submission. Our team has been notified."
            )

def update_response(channel_id, updates):
    if not updates:
        return False
    
    set_clause = ", ".join([f"{k} = %s" for k in updates])
    query = f"UPDATE responses SET {set_clause} WHERE channel_id = %s"
    params = list(updates.values()) + [channel_id]
    return db_operation(query, params)

def send_messages(channel_id, block=None, text=None):
    messenger.send_message(channel_id, block, text)

def send_welcome_message(users_list) -> None:
    '''
    Takes   A list containing all user ids or a dictionary with user ids as its keys. 
            currently using users_store returned by get_all_users_info()
    Sends welcoming message to all users
    '''
    active_users = messenger.get_active_users_list()
    for user_id in users_list:
        if BOT_ID != user_id and user_id in active_users:      
            try:
                print(f'IN Welcome: {user_id}', datetime.now())
                client.chat_postMessage(channel=f"@{user_id}", blocks = MESSAGE_BLOCKS["main_channel_welcome_message"]['blocks'], text="Welcome to Snack N Go!")
                print("Welcome!")
            except SlackApiError as e:
                assert e.response["ok"] is False and e.response["error"], f"Got an error: {e.response['error']}"

@app.event("team_join")
def handle_team_join(body, logger, say):
    logger.info("Team join event received!")
    logger.info(body)  # Log the entire payload for debugging
    user_store = get_all_users_info()
    messenger.add_users(user_store)
    user_id = body["event"]["user"]["id"]
    print(f"[NEW USER] User {user_id} joined the workspace", datetime.now())
    send_welcome_message([user_id])

@app.action("learn_more")
def handle_learn_more(ack, body, client):
    """Handle learn more request"""
    ack()
    user_id = body["user"]["id"]
    
    client.chat_postMessage(
        channel=user_id,
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Lexi hasn't implemented this button yet. "
                }
            }
        ]
    )

@app.event("message")
def handle_message_events(body, logger):
    """Handle general messages"""
    logger.info(body)

if __name__ == "__main__":
    # TODO? Figure out why team join doesnt work when app starts
    user_store = get_all_users_info()
    messenger.add_users(user_store)
    send_welcome_message(user_store.keys())
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()