import tkinter as tk
from tkinter import ttk
import mysql.connector
from firebase import firebase
import pyrebase
# Initialize Tkinter GUI
root = tk.Tk()
root.title("KrUltra Database Manager")

# Firebase-prosjektets konfigurasjon
config = {
    "apiKey": "AIzaSyApppISgdtYgJbqg9iEhFzT8X1TIh2OHFo",
    "authDomain": "krultracr.firebaseapp.com",
    "databaseURL": "https://krultracr-default-rtdb.europe-west1.firebasedatabase.app",
    "storageBucket": "krultracr.appspot.com",
}

# Initialiser Firebase
firebase = pyrebase.initialize_app(config)

# Autentisering
auth = firebase.auth()
email = "torgeir.kruke@krultra.no"
password = "CKO)7Zhl2#gQZ7^ssqT{"
user = auth.sign_in_with_email_and_password(email, password)
user_id_token = user['idToken']

# Initialiser database-objektet
db = firebase.database()

# Function to connect to MariaDB
def connect_to_mariadb():
    try:
        mydb = mysql.connector.connect(
            host="krultrano02.mysql.domeneshop.no",
            port="3306",
            user="krultrano02",
            password="0seinking-himla-Audiolog-fjartan",
            database="krultrano02"
        )
        print("Connected to MariaDB")
        return mydb
    except Exception as e:
        print(f"Failed to connect to MariaDB: {e}")
        return None

# Function to fetch data from MariaDB
def fetch_data_from_mariadb():
    mydb = connect_to_mariadb()
    if mydb:
        mycursor = mydb.cursor()
        mycursor.execute("SELECT * FROM rfid_reader")
        result = mycursor.fetchall()
        for row in result:
            print(row)


def fetch_data_from_firebase():
    try:
        data = db.child("registrations").get(token=user_id_token).val()
        print(data)
    except Exception as e:
        print(f"Failed to fetch data from Firebase: {e}")
        return None


# Function to upload data to Firebase
def upload_to_firebase():
    try:
        db.child("testdata").push({"name": "John Doe"}, user['idToken'])
    except Exception as e:
        print(f"Failed to upload data to Firebase: {e}")
        return None
        

# Add buttons to trigger functions
ttk.Button(root, text="Connect to MariaDB", command=connect_to_mariadb).pack(pady=20)
ttk.Button(root, text="Fetch Data from MariaDB", command=fetch_data_from_mariadb).pack(pady=20)
ttk.Button(root, text="Upload to Firebase", command=upload_to_firebase).pack(pady=20)
ttk.Button(root, text="Fetch Data from Firebase", command=fetch_data_from_firebase).pack(pady=20)

root.mainloop()
