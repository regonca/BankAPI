from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt
import numpy as np
import requests

from keras.applications import InceptionV3
from keras.applications.inception_v3 import preprocess_input, decode_predictions
from keras.utils import img_to_array
from PIL import Image
from io import BytesIO

app = Flask(__name__)  # Initialize Flask app
api = Api(app) # Initialize Flask-RESTful API

# load the pre trained InceptionV3 model for image recognition
pretrained_model = InceptionV3(weights='imagenet')  # Load pre-trained InceptionV3 model

client = MongoClient('mongodb://db:27017/') # Connect to MongoDB (service name "db" in docker-compose)
db = client['ImageRecognition']  # Database name
users = db['Users']  # Collection name

def UserExist(username):  # Function to check if user exists
    if users.find_one({'username': username}):
        return True
    else:
        return False    

class Register(Resource): # Define Register resource 
    def post(self):
        # Get posted data from request
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['password']

        if UserExist(username):
            return jsonify(
                {'status': 301, 
                 'message': 'Invalid username, user already exists'
                })  

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())  # Hash the password
        
        # Store user data in the database
        users.insert_one({'username': username,
                           'password': hashed_pw,
                           'Tokens': 4
                         })  # Insert user
        return jsonify(
            {'status': 200, 
             'message': 'You successfully signed up for the API' 
            })  

def verifyPw(username, password):  # Function to verify password
    hashed_pw = users.find_one({'username': username})['password']  # Get hashed password from DB
    if bcrypt.checkpw(password.encode('utf-8'), hashed_pw):  # Check password
        return True
    else:
        return False

def countTokens(username):  # Function to count user tokens
    tokens = users.find_one({'username': username})['Tokens']           
    return tokens

class Classify(Resource):  # Define Classify resource       
    def post(self):
        # Get posted data from request 
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['password']
        url = postedData.get('url')  # Image URL (optional key so a missing field returns a message instead of a 500)

        if not UserExist(username):
            return jsonify(
                {'status': 301, 
                 'message': 'Invalid Username'
                })  

        hashed_pw = users.find_one({'username': username})['password']  # Get hashed password from DB

        if not bcrypt.checkpw(password.encode('utf-8'), hashed_pw):  # Check password
            return jsonify(
                {'status': 302, 
                 'message': 'Invalid Password'
                })  

        num_tokens = countTokens(username)  # Get user tokens
    
        if num_tokens <= 0:  # Check if user has enough tokens
            return jsonify(
                {'status': 303, 
                 'message': 'Not enough tokens'
                })  

        # Classify the image using the pre-trained InceptionV3 model
        try:
            if not url:
                return jsonify(
                    {'status': 400, 
                     'message': 'No URL provided'
                    })
            
            # Load the image from the provided URL
            response = requests.get(url, timeout=10)  # Fetch image from URL
            response.raise_for_status()  # Fail early on HTTP errors instead of decoding an error page
            img = Image.open(BytesIO(response.content)).convert('RGB')  # Open image (RGB: drops alpha / grayscale channels)
            img = img.resize((299, 299))  # Resize image to match InceptionV3 input size
            img_array = img_to_array(img)  # Convert image to array
            img_array = np.expand_dims(img_array, axis=0)  # Expand dimensions for model input
            img_array = preprocess_input(img_array)  # Preprocess image for InceptionV3

            # Pre process the image and make predictions using the pre-trained InceptionV3 model
            preds = pretrained_model.predict(img_array)  # Make prediction
            results = decode_predictions(preds, top=5)  # Decode predictions

            current_tokens = countTokens(username)  # Get current token count

            ret_json = {}
            for pred in results[0]:
                ret_json[pred[1]] = float(pred[2]*100)  # Store predictions in JSON format

            # ('952735', 'banana', 0.9999996423721313)
            
            users.update_one(
                {'username': username}, 
                {'$set': {'Tokens': current_tokens - 1}
                })  # Deduct one token

            return jsonify(
                {'status': 200, 
                 'predictions': ret_json,
                 'message': 'Image classified successfully'
                })  
        except Exception as e:
            return jsonify(
                {'status': 305, 
                 'message': f'Error processing image: {str(e)}'
                })

class Refill(Resource):  # Define Refill resource   
    def post(self):
        # Get posted data from request
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['admin_pw']
        amount = int(postedData['amount'])  # Accept "200" or 200 in the JSON body

        if not UserExist(username):
            return jsonify(
                {'status': 301, 
                 'message': 'Invalid Username'
                })  

        correct_pw = 'abc123'  # Admin password
        
        if password != correct_pw:  # Check admin password
            return jsonify(
                {'status': 302, 
                 'message': 'Incorrect Password'
                })  

        current_tokens = countTokens(username)  # Get current token count
        
        users.update_one(
            {'username': username}, 
            {'$set': {'Tokens': current_tokens + amount}
            })  # Refill tokens

        return jsonify(
            {'status': 200, 
             'message': 'Refilled successfully'
            })

api.add_resource(Register, '/register')  # Add Register resource to API
api.add_resource(Classify, '/classify')  # Add Detect resource to API
api.add_resource(Refill, '/refill')  # Add Refill resource to API   

if __name__ == "__main__":  # 
    app.run(host='0.0.0.0', port=5000)