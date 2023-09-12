# Description: This file contains the main program for the KrUltra Database Manager.

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import mysql.connector
from firebase import firebase
import pyrebase
from decouple import config

# Henter konfigurasjonsvariabler fra .env-filen
FIREBASE_API_KEY = config('FIREBASE_API_KEY')
FIREBASE_AUTH_DOMAIN = config('FIREBASE_AUTH_DOMAIN')
FIREBASE_DATABASE_URL = config('FIREBASE_DATABASE_URL')
FIREBASE_STORAGE_BUCKET = config('FIREBASE_STORAGE_BUCKET')
FIREBASE_EMAIL = config('FIREBASE_EMAIL')
FIREBASE_PASSWORD = config('FIREBASE_PASSWORD')
MARIADB_HOST = config('MARIADB_HOST')
MARIADB_PORT = config('MARIADB_PORT')
MARIADB_USER = config('MARIADB_USER')
MARIADB_PASSWORD = config('MARIADB_PASSWORD')
MARIADB_DATABASE = config('MARIADB_DATABASE')


# Initialize Tkinter GUI
root = tk.Tk()
root.title("KrUltra Database Manager")

# Firebase-prosjektets konfigurasjon

config = {
    "apiKey": FIREBASE_API_KEY,
    "authDomain": FIREBASE_AUTH_DOMAIN,
    "databaseURL": FIREBASE_DATABASE_URL,
    "storageBucket": FIREBASE_STORAGE_BUCKET,
}

# Initialiser Firebase
firebase = pyrebase.initialize_app(config)

# Autentisering
auth = firebase.auth()
email = FIREBASE_EMAIL
password = FIREBASE_PASSWORD
user = auth.sign_in_with_email_and_password(email, password)
user_id_token = user['idToken']

# Initialiser database-objektene for Firebase
db = firebase.database()

# Function to connect to MariaDB
def connect_to_mariadb():
    try:
        mydb = mysql.connector.connect(
            host=MARIADB_HOST,
            port=MARIADB_PORT,
            user=MARIADB_USER,
            password=MARIADB_PASSWORD,
            database=MARIADB_DATABASE
        )
        print("Connected to MariaDB")
        return mydb
    except Exception as e:
        print(f"Failed to connect to MariaDB: {e}")
        return None

# Function to handle "Exit"
def exit_app():
    global mydb
    if mydb:
        mydb.close()
    root.destroy()

# Function to handle "Upload New event Data"
def upload_new_event_data():
    response = messagebox.askyesno("Advarsel", "NB: ALLE EKSISTERENDE DATA SLETTES! Vil du fortsette?")
    if response:
        fetch_and_display_active_events()

# Function to fetch and display active events
def fetch_and_display_active_events():
    # mydb = connect_to_mariadb()   # erstattet av global variabel
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
    else:
        messagebox.showerror("Feil", "Klarte ikke å koble til MariaDB.")


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
        # mydb = connect_to_mariadb()   # erstattet av global variabel
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
    # mydb = connect_to_mariadb()   # erstattet av global variabel
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


# Create the labels for the tables
events_label = tk.Label(root, text="Events", font=("Arial", 12, "bold"))
races_label = tk.Label(root, text="Races", font=("Arial", 12, "bold"))

# Place the labels above their respective frames
events_label.grid(row=0, column=1, pady=(10,0))
races_label.grid(row=0, column=2, pady=(10,0))

# Create the frames for the tables
frame_events = tk.Frame(root)
frame_events.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
frame_races = tk.Frame(root)
frame_races.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")


def fetch_data_from_database():
    print("Fetching data from database...")
    # mydb = connect_to_mariadb()   # erstattet av global variabel
    if mydb:
        mycursor = mydb.cursor()

        # For Events
        mycursor.execute("SELECT id, long_name, year, edition FROM event WHERE status=1")
        events = mycursor.fetchall()
        events_tree["columns"] = ("id", "long_name", "year", "edition")
        events_tree["displaycolumns"] = ("id", "long_name", "year")
        events_tree["show"] = "headings"  # Removes the first empty column
        # Configuring the columns
        events_tree.column("id", width=50)
        events_tree.column("long_name", width=100)
        events_tree.column("year", width=50)
        for col in events_tree["columns"]:
            events_tree.heading(col, text=col)
        # Adding rows to the Treeview
        for event in events:
            events_tree.insert("", "end", values=event)
        # Packing the Treeview
        events_tree.pack(in_=frame_events, side="left", fill="both", expand=True)

        # For Races
        mycursor.execute("SELECT id, name FROM race WHERE status=1")
        races = mycursor.fetchall()
        races_tree["columns"] = ("id", "name")
        races_tree["displaycolumns"] = ("id", "name")
        races_tree["show"] = "headings"  # Removes the first empty column
        # Configuring the columns
        races_tree.column("id", width=50)
        races_tree.column("name", width=100)
        for col in races_tree["columns"]:
            races_tree.heading(col, text=col)
        # Adding rows to the Treeview
        for race in races:
            races_tree.insert("", "end", values=race)
        # Packing the Treeview
        races_tree.pack(in_=frame_races, side="left", fill="both", expand=True)

def on_event_selected(event):
    if mydb:
        # Hent valgte rader
        selected_items = events_tree.selection()
        
        # Hent event_id fra de valgte radene
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_items]

        # Hent rader fra Races basert på valgte event_id(s)
        mycursor = mydb.cursor()
        query = "SELECT id, name FROM race WHERE status=1 AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
        mycursor.execute(query, tuple(selected_event_ids))
        races = mycursor.fetchall()

        # Tøm Races-tabellen
        for race in races_tree.get_children():
            races_tree.delete(race)

        # Fyll Races-tabellen med de filtrerte resultatene
        for race in races:
            races_tree.insert("", "end", values=race)
    else:
        messagebox.showerror("Feil", "Klarte ikke å koble til MariaDB.")    
        
# Create buttons for the main menu
upload_button = ttk.Button(root, text="Last opp data for nytt løp", command=upload_new_event_data)
exit_button = ttk.Button(root, text="Avslutt", command=exit_app)

# Place the buttons on the window
upload_button.grid(row=1, column=0, padx=10, pady=10)
exit_button.grid(row=2, column=0, padx=10, pady=10)

# Opprett Treeview-widget for hver tabell
events_tree = ttk.Treeview(root)
events_tree.bind("<<TreeviewSelect>>", on_event_selected)   # Bind hendelsen for radvalg i Events-tabellen
races_tree = ttk.Treeview(root)
# checkpoints_tree = ttk.Treeview(root)
# units_tree = ttk.Treeview(root)
# participants_tree = ttk.Treeview(root)
# registrations_tree = ttk.Treeview(root)

# Opprett filter-widget for hver tabell
events_filter = ttk.Combobox(root)
# checkpoints_filter = ttk.Combobox(root)
# units_filter = ttk.Combobox(root)
# participants_filter = ttk.Combobox(root)


mydb = connect_to_mariadb()
fetch_data_from_database()

root.mainloop()
