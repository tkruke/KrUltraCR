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

# Create a frame for each table
def fetch_data_from_database():
    print("Fetching data from database...")
    # mydb = connect_to_mariadb()   # erstattet av global variabel
    if mydb:
        mycursor = mydb.cursor()

        # For Events
        mycursor.execute("SELECT id, long_name, year, edition FROM event WHERE status=1")
        events = mycursor.fetchall()
         # Adding rows to the Treeview
        for event in events:
            events_tree.insert("", "end", values=event)
        # Grid the Treeview
        events_tree.grid(row=0, column=0, sticky="nsew", in_=frame_events)

        # For Races
        mycursor.execute("SELECT id, name FROM race WHERE status=1")
        races = mycursor.fetchall()
        # Adding rows to the Treeview
        for race in races:
            races_tree.insert("", "end", values=race)
        # Grid the Treeview
        races_tree.grid(row=0, column=0, sticky="nsew", in_=frame_races)

        # For Checkpoints
        mycursor.execute("SELECT id, name, start_cp, finish_cp, repeat_cp, event_id FROM checkpoint WHERE status=1")
        checkpoints = mycursor.fetchall()
        # Adding rows to the Treeview
        for checkpoint in checkpoints:
            checkpoints_tree.insert("", "end", values=checkpoint)
        # Grid the Treeview
        checkpoints_tree.grid(row=0, column=0, sticky="nsew", in_=frame_checkpoints)

        # For CR Units
        mycursor.execute("SELECT name, checkpoint_id, cr_in, cr_out, cr_in_out, checkpoint_id FROM event_cru")
        crus = mycursor.fetchall()
        # Adding rows to the Treeview
        for cru in crus:
            cru_tree.insert("", "end", values=cru)
        # Grid the Treeview
        cru_tree.grid(row=0, column=0, sticky="nsew", in_=frame_cru)

        # For Participants
        mycursor.execute("SELECT participant_first_name, participant_last_name, race_name, participant_bib, rfid_uid, rfid_label, event_id, race_id FROM race_participant ORDER BY CAST(participant_bib AS UNSIGNED)")
        participants = mycursor.fetchall()
        for participant in participants:
            participants_tree.insert("", "end", values=participant)
        # Grid the Treeview
        participants_tree.grid(row=0, column=0, sticky="nsew", in_=frame_participants)

def on_event_selected(event):
    global mydb
    if mydb:
        # Hent valgte rader
        selected_items = events_tree.selection()
        
        # Hent event_id fra de valgte radene
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_items]

        # Hent rader fra race_participants basert på valgte event_id(s)
        try:
            mycursor = mydb.cursor()

            # Hent rader fra race basert på valgte event_id(s)
            query_races = "SELECT id, name FROM race WHERE status=1 AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
            mycursor.execute(query_races, tuple(selected_event_ids))
            races = mycursor.fetchall()
            # Tøm Races-tabellen
            for race in races_tree.get_children():
                races_tree.delete(race)
            # Fyll Races-tabellen med de filtrerte resultatene
            for race in races:
                races_tree.insert("", "end", values=race)

            # Hent rader fra checkpoint basert på valgte event_id(s)
            query_checkpoints = "SELECT id, name, start_cp, finish_cp, repeat_cp, event_id FROM checkpoint WHERE status=1 AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
            mycursor.execute(query_checkpoints, tuple(selected_event_ids))
            checkpoints = mycursor.fetchall()
            # Tøm Checkpoints-tabellen
            for checkpoint in checkpoints_tree.get_children():
                checkpoints_tree.delete(checkpoint)
            # Fyll Checkpoints-tabellen med de filtrerte resultatene
            for checkpoint in checkpoints:
                checkpoints_tree.insert("", "end", values=checkpoint)

            # Hent rader fra event_cru basert på valgte event_id(s)
            query_cru = "SELECT name, checkpoint_id, cr_in, cr_out, cr_in_out, checkpoint_id FROM event_cru WHERE event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
            mycursor.execute(query_cru, tuple(selected_event_ids))
            crus = mycursor.fetchall()
            # Tøm CR Units-tabellen
            for cru in cru_tree.get_children():
                cru_tree.delete(cru)
            # Fyll CR Units-tabellen med de filtrerte resultatene
            for cru in crus:
                cru_tree.insert("", "end", values=cru)

            # Hent rader fra race_participants basert på valgte event_id(s)
            query_participants = """
            SELECT participant_first_name, participant_last_name, race_name, 
                participant_bib, rfid_uid, rfid_label 
            FROM race_participant 
            WHERE event_id IN (%s)
            ORDER BY CAST(participant_bib AS UNSIGNED)
            """ % ', '.join(['%s'] * len(selected_event_ids))
            mycursor.execute(query_participants, tuple(selected_event_ids))
            participants = mycursor.fetchall()
            # Tøm Participants-tabellen
            for participant in participants_tree.get_children():
                participants_tree.delete(participant)
            # Fyll Participants-tabellen med de filtrerte resultatene
            for participant in participants:
                participants_tree.insert("", "end", values=(participant[0], participant[1], participant[2], participant[3], participant[4], participant[5]))

        except mysql.connector.Error as err:
            if err.msg == "MySQL Connection not available":
                mydb = connect_to_mariadb() # Prøv å koble til på nytt
                if mydb:
                    on_event_selected(event)  # Prøv funksjonen på nytt
                else:
                    messagebox.showerror("Database Error", "Failed to reconnect to the database.")
            else:
                messagebox.showerror("Database Error", str(err))
    else:
        messagebox.showerror("Feil", "Klarte ikke å koble til MariaDB.")

def on_race_selected(race):
    global mydb
    if mydb:
        # Hent valgte rader
        selected_items = races_tree.selection()
        
        # Hent event_id fra de valgte radene
        selected_race_ids = [races_tree.item(item)['values'][0] for item in selected_items]
        print("selected_race_ids", selected_race_ids)

        # Hent rader fra participant basert på valgte event_id(s)
        try:
            mycursor = mydb.cursor()
            query = ("SELECT participant_first_name, participant_last_name, race_name, participant_bib, rfid_uid, rfid_label, race_id "
                "FROM race_participant WHERE race_id IN (%s) "
                "ORDER BY CAST(participant_bib AS UNSIGNED)") % ', '.join(['%s'] * len(selected_race_ids))
            mycursor.execute(query, tuple(selected_race_ids))
            participants = mycursor.fetchall()

            # Tøm Participants-tabellen
            for participant in participants_tree.get_children():
                participants_tree.delete(participant)

            # Fyll Participants-tabellen med de filtrerte resultatene
            for participant in participants:
                participants_tree.insert("", "end", values=participant)
        except mysql.connector.Error as err:
            if err.msg == "MySQL Connection not available":
                mydb = connect_to_mariadb() # Prøv å koble til på nytt
                if mydb:
                    on_race_selected(race)  # Prøv funksjonen på nytt
                else:
                    messagebox.showerror("Database Error", "Failed to reconnect to the database.")
            else:
                messagebox.showerror("Database Error", str(err))
    else:
        messagebox.showerror("Feil", "Klarte ikke å koble til MariaDB.")


# # Create the labels for the tables
events_label = tk.Label(root, text="Events", font=("Arial", 12, "bold"))
races_label = tk.Label(root, text="Races", font=("Arial", 12, "bold"))
checkpoints_label = tk.Label(root, text="Checkpoints", font=("Arial", 12, "bold"))
cru_label = tk.Label(root, text="CR Units", font=("Arial", 12, "bold"))
participants_label = tk.Label(root, text="Participants", font=("Arial", 12, "bold"))


# Place the labels above their respective frames
events_label.grid(row=0, column=1, pady=(10,0))
races_label.grid(row=0, column=2, pady=(10,0))
checkpoints_label.grid(row=0, column=3, pady=(10,0))
cru_label.grid(row=0, column=4, pady=(10,0))
participants_label.grid(row=2, column=1, pady=(10,0))

# Create the frames for the tables
frame_events = tk.Frame(root)
frame_events.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
frame_races = tk.Frame(root)
frame_races.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")
frame_checkpoints = tk.Frame(root)
frame_checkpoints.grid(row=1, column=3, padx=5, pady=5, sticky="nsew")
frame_cru = tk.Frame(root)
frame_cru.grid(row=1, column=4, padx=5, pady=5, sticky="nsew")
frame_participants = tk.Frame(root)
frame_participants.grid(row=3, column=1, padx=5, pady=5, sticky="nsew", columnspan=2)

# Create buttons for the main menu
upload_button = ttk.Button(root, text="Last opp data for nytt løp", command=upload_new_event_data)
exit_button = ttk.Button(root, text="Avslutt", command=exit_app)
# Place the buttons on the window
upload_button.grid(row=4, column=1, padx=10, pady=10)
exit_button.grid(row=4, column=3, padx=10, pady=10)

# Opprett Treeview-widget for hver tabell
# Opprett Treeview-widget for events-tabell
events_tree = ttk.Treeview(root)
events_tree["columns"] = ("id", "long_name", "year", "edition")
events_tree["displaycolumns"] = ("long_name", "year")
events_tree["show"] = "headings"  # Removes the first empty column
events_tree.column("long_name", width=100, anchor="w")
events_tree.column("year", width=50, anchor="center")
events_tree.heading("long_name", text="Event Name", anchor="w")
events_tree.heading("year", text="Year", anchor="center")
events_tree.bind("<<TreeviewSelect>>", on_event_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Opprett Treeview-widget for races-tabell
races_tree = ttk.Treeview(root)
races_tree["columns"] = ("id", "name")
races_tree["displaycolumns"] = ("name")
races_tree["show"] = "headings"  # Removes the first empty column
races_tree.column("name", width=100)
races_tree.heading("name", text="Race Name", anchor="w")
races_tree.bind("<<TreeviewSelect>>", on_race_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Opprett Treeview-widget for checkpoints-tabell
checkpoints_tree = ttk.Treeview(root)
checkpoints_tree["columns"] = ("id", "name", "start_cp", "finish_cp", "repeat_cp", "event_id")
checkpoints_tree["displaycolumns"] = ("name", "start_cp", "finish_cp", "repeat_cp")
checkpoints_tree["show"] = "headings"  # Removes the first empty column 
checkpoints_tree.column("name", width=100, anchor="w")
checkpoints_tree.column("start_cp", width=10, anchor="center")
checkpoints_tree.column("finish_cp", width=10, anchor="center")
checkpoints_tree.column("repeat_cp", width=10, anchor="center")
checkpoints_tree.heading("name", text="CP", anchor="w")
checkpoints_tree.heading("start_cp", text="S", anchor="center")
checkpoints_tree.heading("finish_cp", text="F", anchor="center")
checkpoints_tree.heading("repeat_cp", text="R", anchor="center")

# Opprett Treeview-widget for cru-tabell
cru_tree = ttk.Treeview(root)
cru_tree["columns"] = ("name", "checkpoint_id", "cr_in", "cr_out", "cr_in_out", "checkpoint_id")
cru_tree["displaycolumns"] = ("name", "cr_in", "cr_out", "cr_in_out")
cru_tree["show"] = "headings"  # Removes the first empty column
cru_tree.column("name", width=100, anchor="w")
cru_tree.column("cr_in", width=10, anchor="center")
cru_tree.column("cr_out", width=10, anchor="center")
cru_tree.column("cr_in_out", width=10, anchor="center")
cru_tree.heading("name", text="CRU", anchor="w")
cru_tree.heading("cr_in", text="I", anchor="center")
cru_tree.heading("cr_out", text="O", anchor="center")
cru_tree.heading("cr_in_out", text="IO", anchor="center")

#Opprett Treeview-widget for participant-tabell
participants_tree = ttk.Treeview(root)
participants_tree["columns"] = ("participant_first_name", "participant_last_name", "race_name", "participant_bib", "rfid_uid", "rfid_label", "event_id", "race_id")
participants_tree["displaycolumns"] = ("participant_first_name", "participant_last_name", "race_name", "participant_bib", "rfid_uid", "rfid_label")
participants_tree["show"] = "headings"  # Removes the first empty column
participants_tree.column("participant_first_name", width=100, anchor="w")
participants_tree.column("participant_last_name", width=100, anchor="w")
participants_tree.column("race_name", width=100, anchor="w")
participants_tree.column("participant_bib", width=50, anchor="center")
participants_tree.column("rfid_uid", width=100, anchor="center")
participants_tree.column("rfid_label", width=60, anchor="center")
participants_tree.heading("participant_first_name", text="First Name", anchor="w")
participants_tree.heading("participant_last_name", text="Last Name", anchor="w" )
participants_tree.heading("race_name", text="Race Name", anchor="w")
participants_tree.heading("participant_bib", text="Bib", anchor="center")
participants_tree.heading("rfid_uid", text="RFID UID", anchor="center")
participants_tree.heading("rfid_label", text="Label", anchor="center")

# registrations_tree = ttk.Treeview(root)

# Opprett Scrollbar-widgets
scrollbar_events_vertical = tk.Scrollbar(frame_events, orient="vertical")
scrollbar_events_horizontal = tk.Scrollbar(frame_events, orient="horizontal")
scrollbar_races_vertical = tk.Scrollbar(frame_races, orient="vertical")
scrollbar_races_horizontal = tk.Scrollbar(frame_races, orient="horizontal")
scrollbar_checkpoints_vertical = tk.Scrollbar(frame_checkpoints, orient="vertical")
scrollbar_checkpoints_horizontal = tk.Scrollbar(frame_checkpoints, orient="horizontal")
scrollbar_cru_vertical = tk.Scrollbar(frame_cru, orient="vertical")
scrollbar_cru_horizontal = tk.Scrollbar(frame_cru, orient="horizontal")
scrollbar_participants_vertical = tk.Scrollbar(frame_participants, orient="vertical")
scrollbar_participants_horizontal = tk.Scrollbar(frame_participants, orient="horizontal")


# Knytt Scrollbar-widgets til Treeview-widgets
events_tree.config(yscrollcommand=scrollbar_events_vertical.set)
scrollbar_events_vertical.config(command=events_tree.yview)
events_tree.config(xscrollcommand=scrollbar_events_horizontal.set)
scrollbar_events_horizontal.config(command=events_tree.xview)
races_tree.config(yscrollcommand=scrollbar_races_vertical.set)
scrollbar_races_vertical.config(command=races_tree.yview)
races_tree.config(xscrollcommand=scrollbar_races_horizontal.set)
scrollbar_races_horizontal.config(command=races_tree.xview)
checkpoints_tree.config(yscrollcommand=scrollbar_checkpoints_vertical.set)
scrollbar_checkpoints_vertical.config(command=checkpoints_tree.yview)
checkpoints_tree.config(xscrollcommand=scrollbar_checkpoints_horizontal.set)
scrollbar_checkpoints_horizontal.config(command=checkpoints_tree.xview)
cru_tree.config(yscrollcommand=scrollbar_cru_vertical.set)
scrollbar_cru_vertical.config(command=cru_tree.yview)
cru_tree.config(xscrollcommand=scrollbar_cru_horizontal.set)
scrollbar_cru_horizontal.config(command=cru_tree.xview)
participants_tree.config(yscrollcommand=scrollbar_participants_vertical.set)
scrollbar_participants_vertical.config(command=participants_tree.yview)
participants_tree.config(xscrollcommand=scrollbar_participants_horizontal.set)
scrollbar_participants_horizontal.config(command=participants_tree.xview)


# For events_tree og dens scrollbars:
events_tree.grid(row=0, column=0, sticky="nsew", in_=frame_events)
scrollbar_events_vertical.grid(row=0, column=1, sticky="ns", in_=frame_events)
scrollbar_events_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_events)
# Konfigurer grid-oppførselen for frame_events:
frame_events.grid_rowconfigure(0, weight=1)    # La rad 0 vokse når vinduet endrer størrelse
frame_events.grid_columnconfigure(0, weight=1) # La kolonne 0 vokse når vinduet endrer størrelse

# For races_tree og dens scrollbars:
races_tree.grid(row=0, column=0, sticky="nsew", in_=frame_races)
scrollbar_races_vertical.grid(row=0, column=1, sticky="ns", in_=frame_races)
scrollbar_races_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_races)
# Konfigurer grid-oppførselen for frame_races:
frame_races.grid_rowconfigure(0, weight=1)
frame_races.grid_columnconfigure(0, weight=1)

# For checkpoints_tree og dens scrollbars:
checkpoints_tree.grid(row=0, column=0, sticky="nsew", in_=frame_checkpoints)
scrollbar_checkpoints_vertical.grid(row=0, column=1, sticky="ns", in_=frame_checkpoints)
scrollbar_checkpoints_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_checkpoints)
# Konfigurer grid-oppførselen for frame_checkpoints:
frame_checkpoints.grid_rowconfigure(0, weight=1)
frame_checkpoints.grid_columnconfigure(0, weight=1)

# For cru_tree og dens scrollbars:
cru_tree.grid(row=0, column=0, sticky="nsew", in_=frame_cru)
scrollbar_cru_vertical.grid(row=0, column=1, sticky="ns", in_=frame_cru)
scrollbar_cru_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_cru)
# Konfigurer grid-oppførselen for frame_cru:
frame_cru.grid_rowconfigure(0, weight=1)
frame_cru.grid_columnconfigure(0, weight=1)

# For participants_tree og dens scrollbars:
participants_tree.grid(row=0, column=0, sticky="nsew", in_=frame_participants)
scrollbar_participants_vertical.grid(row=0, column=1, sticky="ns", in_=frame_participants)
scrollbar_participants_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_participants)
# Konfigurer grid-oppførselen for frame_participants:
frame_participants.grid_rowconfigure(0, weight=1)
frame_participants.grid_columnconfigure(0, weight=1)


mydb = connect_to_mariadb()
fetch_data_from_database()

root.mainloop()
