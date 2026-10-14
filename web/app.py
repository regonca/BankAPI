from flask import Flask, request, jsonify
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt

app = Flask(__name__)  # Initialize Flask app
api = Api(app) # Initialize Flask-RESTful API

client = MongoClient('mongodb://db:27017/') # Connect to MongoDB (service name "db" in docker-compose)
db = client['BankAPI']  # Database name
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
                           'Own': 0,
                           "Debt": 0
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

def cashWithUser(username):  # Function to get user's cash
    cash = users.find_one({'username': username})['Own']  # Get user's cash from DB
    return cash

def debtWithUser(username):  # Function to get user's debt
    debt = users.find_one({'username': username})['Debt']  # Get user's debt from DB
    return debt

def generateReturnDictionary(status, message):  # Function to generate return dictionary
    retJson = {
        "status": status,
        "message": message
    }
    return retJson

def verifyCredentials(username, password):  # Function to verify user credentials
    if not UserExist(username):
        return generateReturnDictionary(301, "Invalid Username"), True  # User does not exist

    correct_pw = verifyPw(username, password)  # Verify password
    if not correct_pw:
        return generateReturnDictionary(302, "Invalid Password"), True  # Invalid password

    return None, False  # Credentials are valid

def changeAccount(username, cash_delta, debt_delta=0):  # Function to change user's cash and debt by a relative amount
    # $inc applies the change atomically and leaves the other fields (e.g. Debt) untouched
    users.update_one(
        {'username': username},
        {'$inc': {'Own': cash_delta, 'Debt': debt_delta}
        })

class Add(Resource):  # Define Add resource
    def post(self):
        # Get posted data from request
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['password']
        amount = int(postedData['amount'])  # Accept "200" or 200 in the JSON body

        retJson, error = verifyCredentials(username, password)  # Verify user credentials
        if error:
            return jsonify(retJson)  # Return error if credentials are invalid

        if amount <= 0:  # Check if amount is valid
            return jsonify(generateReturnDictionary(304, "Invalid amount to add"))  # Invalid amount

        changeAccount("BANK", -amount)  # Deduct amount from bank's cash
        changeAccount(username, amount)  # Add amount to user's cash

        return jsonify(generateReturnDictionary(200, "Amount added successfully to account"))

class Transfer(Resource):  # Define Transfer resource
    def post(self):
        # Get posted data from request
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['password']
        amount = int(postedData['amount'])  # Accept "200" or 200 in the JSON body
        to = postedData['to']  # Recipient username

        retJson, error = verifyCredentials(username, password)  # Verify user credentials
        if error:
            return jsonify(retJson)  # Return error if credentials are invalid

        if not UserExist(to):
            return jsonify(generateReturnDictionary(301, "Recipient username does not exist"))  # Recipient does not exist

        if to == username:  # Sending to yourself would mix up the balances
            return jsonify(generateReturnDictionary(306, "Cannot transfer to yourself"))  # Invalid recipient

        if amount <= 0:  # Check if amount is valid
            return jsonify(generateReturnDictionary(304, "Invalid amount to transfer"))  # Invalid amount

        cash = cashWithUser(username)  # Get user's cash

        if cash < amount:  # Check if user has enough cash
            return jsonify(generateReturnDictionary(305, "Insufficient funds"))  # Insufficient funds

        changeAccount("BANK", 1)  # Bank keeps a fee of 1
        changeAccount(to, amount - 1)  # Recipient receives amount minus the fee
        changeAccount(username, -amount)  # Deduct amount from user's cash

        return jsonify(generateReturnDictionary(200, "Amount transferred successfully"))

class Balance(Resource):  # Define Balance resource
    def post(self):
        # Get posted data from request
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['password']

        retJson, error = verifyCredentials(username, password)  # Verify user credentials
        if error:
            return jsonify(retJson)  # Return error if credentials are invalid

        # Return only the balance fields: the stored 'password' is a bcrypt hash in bytes,
        # which jsonify cannot serialize (caused the 500) and must not be exposed anyway
        retJson = users.find_one({'username': username}, {'_id': 0, 'username': 1, 'Own': 1, 'Debt': 1})

        return jsonify(retJson)  # Return user balance as JSON

class TakeLoan(Resource):  # Define TakeLoan resource
    def post(self):
        # Get posted data from request
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['password']
        amount = int(postedData['amount'])  # Accept "200" or 200 in the JSON body

        retJson, error = verifyCredentials(username, password)  # Verify user credentials
        if error:
            return jsonify(retJson)  # Return error if credentials are invalid

        if amount <= 0:  # Check if amount is valid
            return jsonify(generateReturnDictionary(304, "Invalid loan amount"))  # Invalid amount

        changeAccount(username, amount, amount)  # Add amount to user's cash and debt
        changeAccount("BANK", -amount)  # Deduct amount from bank's cash

        return jsonify(generateReturnDictionary(200, "Loan taken successfully"))

class PayLoan(Resource):  # Define PayLoan resource
    def post(self):
        # Get posted data from request
        postedData = request.get_json()  # Get JSON data from request
        username = postedData['username']
        password = postedData['password']
        amount = int(postedData['amount'])  # Accept "200" or 200 in the JSON body

        retJson, error = verifyCredentials(username, password)  # Verify user credentials
        if error:
            return jsonify(retJson)  # Return error if credentials are invalid

        if amount <= 0:  # Check if amount is valid
            return jsonify(generateReturnDictionary(304, "Invalid payment amount"))  # Invalid amount

        cash = cashWithUser(username)  # Get user's cash
        debt = debtWithUser(username)  # Get user's debt

        if amount > debt:  # Paying more than owed would leave a negative debt
            return jsonify(generateReturnDictionary(307, "Payment exceeds the loan debt"))  # Overpayment

        if cash < amount:  # Check if user has enough cash to pay loan
            return jsonify(generateReturnDictionary(303, "Insufficient funds to pay loan"))  # Insufficient funds

        changeAccount(username, -amount, -amount)  # Deduct amount from user's cash and debt
        changeAccount("BANK", amount)  # Add amount to bank's cash

        return jsonify(generateReturnDictionary(200, "Loan paid successfully"))

api.add_resource(Register, '/register')  # Add Register resource to API
api.add_resource(Add, '/add')  # Add Add resource to API
api.add_resource(Transfer, '/transfer')  # Add Transfer resource to API
api.add_resource(Balance, '/balance')  # Add Balance resource to API
api.add_resource(TakeLoan, '/takeloan')  # Add TakeLoan resource to API
api.add_resource(PayLoan, '/payloan')  # Add PayLoan resource to API

if __name__ == "__main__":  #
    app.run(host='0.0.0.0', port=5000)
