from flask import Flask, jsonify, request
import pymysql
import os
import time
from dotenv import load_dotenv
from helper_functions import connectDB
from bot import db_operation
from pathlib import Path

env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Initialize Flask
app = Flask(__name__)

''' Helper functions '''
def get_latest_query_time():
    try:
        with open('latest_query_time.txt', 'r') as f:
            lines = f.readlines()
            if not lines:
                return None
            return int(lines[-1].strip())
    except FileNotFoundError:
        return None

def append_latest_query_time():
    current_time = int(time.time())
    with open('latest_query_time.txt', 'a') as f:
        f.write(str(current_time) + '\n')

''' Routes '''
# Testing endpoint
@app.route("/test", methods=['GET'])
def hello():
    return jsonify({"message": "Hello World!"})

# Get all responses
@app.route('/responses', methods=['GET'])
def get_all_responses():
    query = '''
    SELECT r.*, u.username, u.email, u.status 
    FROM responses r
    LEFT JOIN users u ON r.user_id = u.id
    '''
    result = db_operation(query, fetch_all=True)
    return jsonify(result if result else [])

# Get response by ID
@app.route('/responses/<int:response_id>', methods=['GET'])
def get_response_by_id(response_id):
    query = '''
    SELECT r.*, u.username, u.email, u.status 
    FROM responses r
    LEFT JOIN users u ON r.user_id = u.id
    WHERE r.response_id = %s
    '''
    result = db_operation(query, [response_id], fetch_one=True)
    return jsonify(result if result else {})

# Get new responses since last call
@app.route('/responses/new', methods=['GET'])
def get_new_responses():
    last_time = get_latest_query_time()
    query = '''
    SELECT r.*, u.username, u.email, u.status 
    FROM responses r
    LEFT JOIN users u ON r.user_id = u.id
    WHERE r.submission_time IS NOT NULL
    '''
    
    if last_time:
        query += ' AND r.submission_time > %s'
        result = db_operation(query, [last_time], fetch_all=True)
    else:
        result = db_operation(query, fetch_all=True)
    
    append_latest_query_time()
    return jsonify(result if result else [])

# Start server
if __name__ == "__main__":
    # Initialize the latest query time file if it doesn't exist
    if not os.path.exists('latest_query_time.txt'):
        with open('latest_query_time.txt', 'w') as f:
            pass
    app.run(debug=True, host='0.0.0.0', port=5000)