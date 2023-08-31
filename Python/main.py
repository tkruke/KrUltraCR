# Description: This file contains the main program for the KrUltra Database Manager.

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
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

# Function to handle "Exit"
def exit_app():
    root.destroy()

# Function to handle "Upload New event Data"
def upload_new_event_data():
    response = messagebox.askyesno("Advarsel", "NB: ALLE EKSISTERENDE DATA SLETTES! Vil du fortsette?")
    if response:
        fetch_and_display_active_events()

# Function to fetch and display active events
def fetch_and_display_active_events():
    mydb = connect_to_mariadb()
    if mydb:
        mycursor = mydb.cursor()
        sql_query = "SELECT id, long_name, year, edition FROM event WHERE status=1"
        mycursor.execute(sql_query)
        active_events = mycursor.fetchall()

        if active_events:
            # Display events for the user to select, we will implement this function next
            display_event_selection(active_events)
        else:
            messagebox.showinfo("Ingen aktive løp", "Det finnes ingen aktive løp i databasen.")


# Function to display active events for user selection
def display_event_selection(active_events):
    event_window = tk.Toplevel(root)
    event_window.title("Velg et aktivt løp")
    
    tk.Label(event_window, text="Velg et løp fra listen:").pack()
    
    event_var = tk.StringVar()
    event_var.set("Velg et løp")
    
    event_menu = ttk.Combobox(event_window, textvariable=event_var, values=[event[1] for event in active_events])
    event_menu.pack()
    
    def select_event():
        selected_event = event_var.get()
        if selected_event != "Velg et løp":
            selected_event_id = next((event[0] for event in active_events if event[1] == selected_event), None)
            if selected_event_id is not None:
                # Proceed to Step 2 to upload data to Firebase
                upload_event_data_to_firebase(selected_event_id, event_window)
            event_window.destroy()

    tk.Button(event_window, text="Velg", command=select_event).pack()


# Function to upload runners data to Firebase
def upload_runners_data_to_firebase(event_id):
    try:
        mydb = connect_to_mariadb()
        if mydb:
            mycursor = mydb.cursor()
            query = """
            SELECT 
                race.name AS race_name,
                person.first_name AS participant_first_name,
                person.last_name AS participant_last_name,
                participant.bib AS participant_bib,
                rfid_tag.uid AS rfid_uid
            FROM race
            JOIN participant ON race.id = participant.race_id
            JOIN person ON participant.person_id = person.id
            JOIN participant_tag ON participant.id = participant_tag.participant_id
            JOIN rfid_tag ON participant_tag.rfid_tag_id = rfid_tag.id
            WHERE race.event_id = %s AND race.status = 1
            AND participant.status = 1 AND rfid_tag.status = 1;
            """
            mycursor.execute(query, (event_id,))
            rows = mycursor.fetchall()
            
            # Create a list of dictionaries to hold the runner data
            runner_data = {}
            for row in rows:
                rfid_uid = row[4]
                runner_data[rfid_uid] = {
                    'race_name': row[0],
                    'participant_first_name': row[1],
                    'participant_last_name': row[2],
                    'participant_bib': row[3], 
                }
              
            # Upload to Firebase
            db.child("runners").set(runner_data, token=user_id_token)
            
            print("Successfully uploaded runners data to Firebase.")
            
    except Exception as e:
        print(f"Failed to upload runners data to Firebase: {e}")
        return None


# Function to upload event data to Firebase
def upload_event_data_to_firebase(selected_event_id, event_window):
    # Step 2.1: Fetch data from MariaDB
    mydb = connect_to_mariadb()
    if mydb:
        mycursor = mydb.cursor()
        sql_query = """
        SELECT rfid_reader.checkpoint_id, rfid_reader.chip_id, rfid_reader.description, 
        event.id, rfid_reader.name, rfid_reader.status, checkpoint.name, checkpoint.description, checkpoint.minimum_split,
        checkpoint.start_cp, checkpoint.finish_cp, checkpoint.repeat_cp
        FROM event 
        JOIN checkpoint ON event.id = checkpoint.event_id 
        JOIN rfid_reader ON checkpoint.id = rfid_reader.checkpoint_id 
        WHERE event.id = %s
        """
        mycursor.execute(sql_query, (selected_event_id,))
        rfid_readers_db = mycursor.fetchall()
        
        # Step 2.2: Delete existing data in Firebase
        db.child("rfid_readers").remove(token=user_id_token)
        
        # Step 2.3: Upload new event data to Firebase
        rfid_readers_list = []
        for reader in rfid_readers_db:
            reader_data = {
                "checkpoint_id": reader[0],
                "chip_id": reader[1],
                "cru_description": reader[2],
                "event_id": reader[3],
                "name": reader[4],
                "status": reader[5],
                "checkpoint": reader[6],
                "cp_description": reader[7],
                "minimum_split": reader[8],
                "start": reader[9],
                "finish": reader[10],
                "repeat": reader[11],
            }
            rfid_readers_list.append(reader_data)

        db.child("rfid_readers").set(rfid_readers_list, token=user_id_token)

        # Step 2.4: Upload runners data to Firebase
        upload_runners_data_to_firebase(selected_event_id)
        
        print("Successfully uploaded data to Firebase")
        messagebox.showinfo("Suksess", "Dataene ble lastet opp til Firebase.")
        event_window.destroy()

        # Spør brukeren om å slette eksisterende registreringer
        delete_registrations = messagebox.askyesno("Slett registreringer", "Ønsker du også å slette alle tidligere registreringer?")
        if delete_registrations:
            try:
                db.child("registrations").remove(token=user_id_token)  # Slett alle data under "registrations"
                messagebox.showinfo("Suksess", "Alle registreringer ble fjernet.")
            except Exception as e:
                messagebox.showerror("Feil", f"Klarte ikke å slette registreringer: {e}")
    else:
        messagebox.showerror("Feil", "Klarte ikke å koble til MariaDB.")
        
# Create buttons for the main menu
upload_button = ttk.Button(root, text="Last opp data for nytt løp", command=upload_new_event_data)
exit_button = ttk.Button(root, text="Avslutt", command=exit_app)

# Place the buttons on the window
upload_button.grid(row=0, column=0, padx=10, pady=10)
exit_button.grid(row=1, column=0, padx=10, pady=10)


root.mainloop()
