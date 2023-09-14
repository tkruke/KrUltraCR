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
        messagebox.showerror("Error", f"Failed to upload runners data to Firebase: {e}")
        return None


# Function to upload event data to Firebase
def upload_event_data_to_firebase(selected_event_id):
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
                "crus_description": reader[2],
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
        
        print("Successfully uploaded event data to Firebase")
        messagebox.showinfo("Success", "Event data uploaded to Firebase.")
        # event_window.destroy()

        # # Spør brukeren om å slette eksisterende registreringer
        # delete_registrations = messagebox.askyesno("Slett registreringer", "Ønsker du også å slette alle tidligere registreringer?")
        # if delete_registrations:
        #     try:
        #         db.child("registrations").remove(token=user_id_token)  # Slett alle data under "registrations"
        #         messagebox.showinfo("Suksess", "Alle registreringer ble fjernet.")
        #     except Exception as e:
        #         messagebox.showerror("Feil", f"Klarte ikke å slette registreringer: {e}")
    else:
        messagebox.showerror("Error", "Unable to connect to database (MariaDB).")


def upload_selected_event_to_firebase():
    selected_items = events_tree.selection()

    if len(selected_items) != 1:
        messagebox.showwarning("Valg av event", "Vennligst velg ett event for opplasting.")
        return

    selected_event_id = events_tree.item(selected_items[0])['values'][0]

    answer = messagebox.askyesno("Bekreftelse", "Er du sikker? Eksisterende data fjernes!")
    if answer:
        upload_event_data_to_firebase(selected_event_id)  # Kall eksisterende funksjon med valgt event ID


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
        fetch_races()
        # mycursor.execute("SELECT id, name FROM race WHERE status=1")
        # races = mycursor.fetchall()
        # # Adding rows to the Treeview
        # for race in races:
        #     races_tree.insert("", "end", values=race)
        # # Grid the Treeview
        # races_tree.grid(row=0, column=0, sticky="nsew", in_=frame_races)

        # For Checkpoints
        fetch_checkpoints()
        # mycursor.execute("SELECT id, name, start_cp, finish_cp, repeat_cp, event_id FROM checkpoint WHERE status=1")
        # checkpoints = mycursor.fetchall()
        # # Adding rows to the Treeview
        # for checkpoint in checkpoints:
        #     checkpoints_tree.insert("", "end", values=checkpoint)
        # # Grid the Treeview
        # checkpoints_tree.grid(row=0, column=0, sticky="nsew", in_=frame_checkpoints)

        # For CR Units
        fetch_crus()
        # mycursor.execute("SELECT name, description, cr_in, cr_out, cr_in_out, checkpoint_id, rfid_reader_chip_id, rfid_reader_id FROM event_cru")
        # crus = mycursor.fetchall()
        # # Adding rows to the Treeview
        # for cru in crus:
        #     crus_tree.insert("", "end", values=cru)
        # # Grid the Treeview
        # crus_tree.grid(row=0, column=0, sticky="nsew", in_=frame_crus)

        # For Participants
        fetch_participants()
        # mycursor.execute("""
        #     SELECT participant_first_name, participant_last_name, race_name, participant_bib, 
        #         rfid_uid, rfid_label, event_id, race_id 
        #     FROM race_participant 
        #     ORDER BY CAST(participant_bib AS UNSIGNED)""")
        # participants = mycursor.fetchall()
        # for participant in participants:
        #     participants_tree.insert("", "end", values=participant)
        # # Grid the Treeview
        # participants_tree.grid(row=0, column=0, sticky="nsew", in_=frame_participants)

        # For Registrations
        fetch_registrations()


def fetch_races():
    global mydb
    selected_event_items = events_tree.selection()

    params = []

    # Bygg SQL-spørringen basert på de valgte verdiene
    races_query = "SELECT id, name FROM race WHERE 1=1"  # Basis for spørringen

    # Hvis noen events er valgt, legg til event_id i spørringen
    if selected_event_items:
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_event_items]
        print("selected_event_ids", selected_event_ids)
        races_query += " AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
        params.extend(selected_event_ids)

     # Kjør SQL-spørringen, hent data, og fyll Treeview
    try:
        if mydb:
            mycursor = mydb.cursor()
            mycursor.execute(races_query, tuple(params))
            races = mycursor.fetchall()
            # Tøm races-tabellen
            for race in races_tree.get_children():
                races_tree.delete(race)
            # Fyll races-tabellen med de filtrerte resultatene
            for race in races:
                races_tree.insert("", "end", values=race)
            
            races_tree.grid(row=0, column=0, sticky="nsew", in_=frame_races)
        else:
            messagebox.showerror("Error", "Unable to connect to database (MariaDB).")
    except mysql.connector.Error as err:
        if err.msg == "MySQL Connection not available":
            mydb = connect_to_mariadb() # Prøv å koble til på nytt
            if mydb:
                fetch_races()
            else:
                messagebox.showerror("Database Error", "Failed to reconnect to the database.")
        else:
            messagebox.showerror("Database Error", str(err))

def fetch_checkpoints():
    global mydb
    selected_event_items = events_tree.selection()

    params = []

    # Bygg SQL-spørringen basert på de valgte verdiene
    checkpoints_query = "SELECT id, name, start_cp, finish_cp, repeat_cp, event_id FROM checkpoint WHERE status=1"  # Basis for spørringen

    # Hvis noen events er valgt, legg til event_id i spørringen
    if selected_event_items:
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_event_items]
        print("selected_event_ids", selected_event_ids)
        checkpoints_query += " AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
        params.extend(selected_event_ids)

    # Kjør SQL-spørringen, hent data, og fyll Treeview
    try:
        if mydb:
            mycursor = mydb.cursor()
            mycursor.execute(checkpoints_query, tuple(params))
            checkpoints = mycursor.fetchall()
            # Tøm checkpoints-tabellen
            for checkpoint in checkpoints_tree.get_children():
                checkpoints_tree.delete(checkpoint)
            # Fyll checkpoints-tabellen med de filtrerte resultatene
            for checkpoint in checkpoints:
                checkpoints_tree.insert("", "end", values=checkpoint)
            
            checkpoints_tree.grid(row=0, column=0, sticky="nsew", in_=frame_checkpoints)
        else:
            messagebox.showerror("Error", "Unable to connect to database (MariaDB).")
    except mysql.connector.Error as err:
        if err.msg == "MySQL Connection not available":
            mydb = connect_to_mariadb() # Prøv å koble til på nytt
            if mydb:
                fetch_checkpoints()
            else:
                messagebox.showerror("Database Error", "Failed to reconnect to the database.")
        else:
            messagebox.showerror("Database Error", str(err))

def fetch_crus():
    global mydb
    selected_event_items = events_tree.selection()

    params = []

    # Bygg SQL-spørringen basert på de valgte verdiene
    crus_query = "SELECT name, description, cr_in, cr_out, cr_in_out, checkpoint_id, rfid_reader_chip_id, rfid_reader_id FROM event_cru WHERE 1=1"  # Basis for spørringen

    # Hvis noen events er valgt, legg til event_id i spørringen
    if selected_event_items:
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_event_items]
        print("selected_event_ids", selected_event_ids)
        crus_query += " AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
        params.extend(selected_event_ids)

    # Kjør SQL-spørringen, hent data, og fyll Treeview
    try:
        if mydb:
            mycursor = mydb.cursor()
            mycursor.execute(crus_query, tuple(params))
            crus = mycursor.fetchall()
            # Tøm crus-tabellen
            for cru in crus_tree.get_children():
                crus_tree.delete(cru)
            # Fyll crus-tabellen med de filtrerte resultatene
            for cru in crus:
                crus_tree.insert("", "end", values=cru)
            
            crus_tree.grid(row=0, column=0, sticky="nsew", in_=frame_crus)
        else:
            messagebox.showerror("Error", "Unable to connect to database (MariaDB).")
    except mysql.connector.Error as err:
        if err.msg == "MySQL Connection not available":
            mydb = connect_to_mariadb() # Prøv å koble til på nytt
            if mydb:
                fetch_crus()
            else:
                messagebox.showerror("Database Error", "Failed to reconnect to the database.")
        else:
            messagebox.showerror("Database Error", str(err))
    
def fetch_participants():
    global mydb
    selected_event_items = events_tree.selection()
    selected_race_items = races_tree.selection()

    params = []

    # Bygg SQL-spørringen basert på de valgte verdiene
    participants_query = "SELECT participant_first_name, participant_last_name, race_name, participant_bib, rfid_uid, rfid_label FROM race_participant WHERE 1=1"
    # Hvis noen events er valgt, legg til event_id i spørringen
    if selected_event_items:
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_event_items]
        print("selected_event_ids", selected_event_ids)
        participants_query += " AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
        params.extend(selected_event_ids)

    # Gjør tilsvarende for races
    if selected_race_items:
        selected_race_ids = [races_tree.item(item)['values'][0] for item in selected_race_items]
        participants_query += " AND race_id IN (%s)" % ', '.join(['%s'] * len(selected_race_ids))
        params.extend(selected_race_ids)

    # Kjør SQL-spørringen, hent data, og fyll Treeview
    try:
        if mydb:
            mycursor = mydb.cursor()
            mycursor.execute(participants_query, tuple(params))
            participants = mycursor.fetchall()
            # Tøm participants-tabellen
            for participant in participants_tree.get_children():
                participants_tree.delete(participant)
            # Fyll participants-tabellen med de filtrerte resultatene
            for participant in participants:
                participants_tree.insert("", "end", values=participant)
            
            participants_tree.grid(row=0, column=0, sticky="nsew", in_=frame_participants)
        else:
            messagebox.showerror("Error", "Unable to connect to database (MariaDB).")
    except mysql.connector.Error as err:
        if err.msg == "MySQL Connection not available":
            mydb = connect_to_mariadb() # Prøv å koble til på nytt
            if mydb:
                fetch_participants()
            else:
                messagebox.showerror("Database Error", "Failed to reconnect to the database.")
        else:
            messagebox.showerror("Database Error", str(err))

# Function to fetch registrations from database
def fetch_registrations():
    global mydb
    selected_event_items = events_tree.selection()
    selected_race_items = races_tree.selection()
    selected_checkpoint_items = checkpoints_tree.selection()
    selected_crus_items = crus_tree.selection()
    selected_participant_items = participants_tree.selection()

    params = []

    # Bygg SQL-spørringen basert på de valgte verdiene 
    registrations_query = """
        SELECT id, rfid_reader_chip_id, rfid_tag_uid, adjusted_reader_time, 
            checkpoint_id, cp_name, checkpoint_name, event_id, race_id, label, first_name, last_name 
        FROM registration_view 
        WHERE 1=1
        """  # Basis for spørringen

    # Hvis noen events er valgt, legg til event_id i spørringen
    if selected_event_items:
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_event_items]
        print("selected_event_ids", selected_event_ids)
        registrations_query += " AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
        params.extend(selected_event_ids)

    # Gjør tilsvarende for races, checkpoints, og CR units...
    if selected_race_items:
        selected_race_ids = [races_tree.item(item)['values'][0] for item in selected_race_items]
        registrations_query += " AND race_id IN (%s)" % ', '.join(['%s'] * len(selected_race_ids))
        params.extend(selected_race_ids)

    if selected_checkpoint_items:
        selected_checkpoint_ids = [checkpoints_tree.item(item)['values'][0] for item in selected_checkpoint_items]
        registrations_query += " AND checkpoint_id IN (%s)" % ', '.join(['%s'] * len(selected_checkpoint_ids))
        params.extend(selected_checkpoint_ids)

    if selected_crus_items:
        selected_crus_ids = [crus_tree.item(item)['values'][6] for item in selected_crus_items]
        registrations_query += " AND rfid_reader_chip_id IN (%s)" % ', '.join(['%s'] * len(selected_crus_ids))
        params.extend(selected_crus_ids)

    if selected_participant_items:
        selected_participant_bibs = [participants_tree.item(item)['values'][3] for item in selected_participant_items]
        registrations_query += " AND bib IN (%s)" % ', '.join(['%s'] * len(selected_participant_bibs))
        params.extend(selected_participant_bibs)

    # Kjør SQL-spørringen, hent data, og fyll Treeview
    try:
        if mydb:
            mycursor = mydb.cursor()
            mycursor.execute(registrations_query, tuple(params))
            registrations = mycursor.fetchall()
            # Tøm registrations-tabellen
            for registration in registrations_tree.get_children():
                registrations_tree.delete(registration)
            # Fyll registrations-tabellen med de filtrerte resultatene
            for registration in registrations:
                registrations_tree.insert("", "end", values=registration)
            
            registrations_tree.grid(row=0, column=0, sticky="nsew", in_=frame_registrations)
        else:
            messagebox.showerror("Error", "Unable to connect to database (MariaDB).")
    except mysql.connector.Error as err:
        if err.msg == "MySQL Connection not available":
            mydb = connect_to_mariadb() # Prøv å koble til på nytt
            if mydb:
                fetch_registrations()
            else:
                messagebox.showerror("Database Error", "Failed to reconnect to the database.")
        else:
            messagebox.showerror("Database Error", str(err))


def on_event_selected(event):
    # global mydb
    # if mydb:
    #     # Hent valgte rader
    #     selected_items = events_tree.selection()
        
    #     # Hent event_id fra de valgte radene
    #     selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_items]

    #     # Hent rader fra race_participants basert på valgte event_id(s)
    #     try:
    #         mycursor = mydb.cursor()

            # Hent rader fra race basert på valgte event_id(s)
            fetch_races()
            # query_races = "SELECT id, name FROM race WHERE status=1 AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
            # mycursor.execute(query_races, tuple(selected_event_ids))
            # races = mycursor.fetchall()
            # # Tøm Races-tabellen
            # for race in races_tree.get_children():
            #     races_tree.delete(race)
            # # Fyll Races-tabellen med de filtrerte resultatene
            # for race in races:
            #     races_tree.insert("", "end", values=race)

            # Hent rader fra checkpoint basert på valgte event_id(s)
            fetch_checkpoints()
            # query_checkpoints = "SELECT id, name, start_cp, finish_cp, repeat_cp, event_id FROM checkpoint WHERE status=1 AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
            # mycursor.execute(query_checkpoints, tuple(selected_event_ids))
            # checkpoints = mycursor.fetchall()
            # # Tøm Checkpoints-tabellen
            # for checkpoint in checkpoints_tree.get_children():
            #     checkpoints_tree.delete(checkpoint)
            # # Fyll Checkpoints-tabellen med de filtrerte resultatene
            # for checkpoint in checkpoints:
            #     checkpoints_tree.insert("", "end", values=checkpoint)

            # Hent rader fra event_cru basert på valgte event_id(s)
            fetch_crus()
            # query_cru = """
            # SELECT name, description, cr_in, cr_out, cr_in_out, checkpoint_id, rfid_reader_chip_id, rfid_reader_id 
            # FROM event_cru 
            # WHERE event_id IN (%s)
            # """ % ', '.join(['%s'] * len(selected_event_ids))
            # mycursor.execute(query_cru, tuple(selected_event_ids))
            # crus = mycursor.fetchall()
            # # Tøm CR Units-tabellen
            # for cru in crus_tree.get_children():
            #     crus_tree.delete(cru)
            # # Fyll CR Units-tabellen med de filtrerte resultatene
            # for cru in crus:
            #     crus_tree.insert("", "end", values=cru)

            # Hent rader fra race_participants basert på valgte event_id(s)
            fetch_participants()
            # query_participants = """
            # SELECT participant_first_name, participant_last_name, race_name, 
            #     participant_bib, rfid_uid, rfid_label 
            # FROM race_participant 
            # WHERE event_id IN (%s)
            # ORDER BY CAST(participant_bib AS UNSIGNED)
            # """ % ', '.join(['%s'] * len(selected_event_ids))
            # mycursor.execute(query_participants, tuple(selected_event_ids))
            # participants = mycursor.fetchall()
            # # Tøm Participants-tabellen
            # for participant in participants_tree.get_children():
            #     participants_tree.delete(participant)
            # # Fyll Participants-tabellen med de filtrerte resultatene
            # for participant in participants:
            #     participants_tree.insert("", "end", values=(participant[0], participant[1], participant[2], participant[3], participant[4], participant[5]))

            # Hent rader fra registration_view basert på valgte event_id(s)
            fetch_registrations()

    #     except mysql.connector.Error as err:
    #         if err.msg == "MySQL Connection not available":
    #             mydb = connect_to_mariadb() # Prøv å koble til på nytt
    #             if mydb:
    #                 on_event_selected(event)  # Prøv funksjonen på nytt
    #             else:
    #                 messagebox.showerror("Database Error", "Failed to reconnect to the database.")
    #         else:
    #             messagebox.showerror("Database Error", str(err))
    # else:
    #     messagebox.showerror("Error", "Unable to connect to database (MariaDB).")

def on_race_selected(race):
    # global mydb
    # if mydb:
    #     # Hent valgte rader
    #     selected_items = races_tree.selection()
        
    #     # Hent event_id fra de valgte radene
    #     selected_race_ids = [races_tree.item(item)['values'][0] for item in selected_items]
    #     print("selected_race_ids", selected_race_ids)

        # Hent rader fra participant basert på valgte event_id(s)
        fetch_participants()
        fetch_registrations()
        # try:
        #     mycursor = mydb.cursor()
        #     query = ("SELECT participant_first_name, participant_last_name, race_name, participant_bib, rfid_uid, rfid_label, race_id "
        #         "FROM race_participant WHERE race_id IN (%s) "
        #         "ORDER BY CAST(participant_bib AS UNSIGNED)") % ', '.join(['%s'] * len(selected_race_ids))
        #     mycursor.execute(query, tuple(selected_race_ids))
        #     participants = mycursor.fetchall()

        #     # Tøm Participants-tabellen
        #     for participant in participants_tree.get_children():
        #         participants_tree.delete(participant)

        #     # Fyll Participants-tabellen med de filtrerte resultatene
        #     for participant in participants:
        #         participants_tree.insert("", "end", values=participant)
        # except mysql.connector.Error as err:
        #     if err.msg == "MySQL Connection not available":
        #         mydb = connect_to_mariadb() # Prøv å koble til på nytt
        #         if mydb:
        #             on_race_selected(race)  # Prøv funksjonen på nytt
        #         else:
        #             messagebox.showerror("Database Error", "Failed to reconnect to the database.")
        #     else:
        #         messagebox.showerror("Database Error", str(err))
    # else:
    #     messagebox.showerror("Error", "Unable to connect to database (MariaDB).")

def on_checkpoint_selected(checkpoint):
    fetch_registrations()

def on_cru_selected(cru):
    fetch_registrations()

def on_participant_selected(participant):
    fetch_registrations()

# # Create the labels for the tables
events_label = tk.Label(root, text="Events", font=("Arial", 12, "bold"))
races_label = tk.Label(root, text="Races", font=("Arial", 12, "bold"))
checkpoints_label = tk.Label(root, text="Checkpoints", font=("Arial", 12, "bold"))
crus_label = tk.Label(root, text="CR Units", font=("Arial", 12, "bold"))
participants_label = tk.Label(root, text="Participants", font=("Arial", 12, "bold"))
registrations_label = tk.Label(root, text="Registrations", font=("Arial", 12, "bold"))


# Place the labels above their respective frames
events_label.grid(row=0, column=1, pady=(10,0))
races_label.grid(row=0, column=2, pady=(10,0))
checkpoints_label.grid(row=0, column=3, pady=(10,0))
crus_label.grid(row=0, column=4, pady=(10,0))
participants_label.grid(row=2, column=1, pady=(10,0))
registrations_label.grid(row=0, column=5, pady=(10,0))

# Create the frames for the tables
frame_events = tk.Frame(root)
frame_events.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")
frame_races = tk.Frame(root)
frame_races.grid(row=1, column=2, padx=5, pady=5, sticky="nsew")
frame_checkpoints = tk.Frame(root)
frame_checkpoints.grid(row=1, column=3, padx=5, pady=5, sticky="nsew")
frame_crus = tk.Frame(root)
frame_crus.grid(row=1, column=4, padx=5, pady=5, sticky="nsew")
frame_participants = tk.Frame(root)
frame_participants.grid(row=3, column=1, padx=5, pady=5, sticky="nsew", columnspan=4)
frame_registrations = tk.Frame(root)
frame_registrations.grid(row=1, column=5, padx=5, pady=5, sticky="nsew", rowspan=3)


## Opprett Treeview-widget for hver tabell
# Opprett Treeview-widget for events-tabell
events_tree = ttk.Treeview(root, height=8)
events_tree["columns"] = ("id", "long_name", "year", "edition")
events_tree["displaycolumns"] = ("long_name", "year")
events_tree["show"] = "headings"  # Removes the first empty column
events_tree.column("long_name", width=100, anchor="w")
events_tree.column("year", width=50, anchor="center")
events_tree.heading("long_name", text="Event Name", anchor="w")
events_tree.heading("year", text="Year", anchor="center")
events_tree.bind("<<TreeviewSelect>>", on_event_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Opprett Treeview-widget for races-tabell
races_tree = ttk.Treeview(root, height=8)
races_tree["columns"] = ("id", "name")
races_tree["displaycolumns"] = ("name")
races_tree["show"] = "headings"  # Removes the first empty column
races_tree.column("name", width=100)
races_tree.heading("name", text="Race Name", anchor="w")
races_tree.bind("<<TreeviewSelect>>", on_race_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Opprett Treeview-widget for checkpoints-tabell
checkpoints_tree = ttk.Treeview(root, height=8)
checkpoints_tree["columns"] = ("id", "name", "start_cp", "finish_cp", "repeat_cp", "event_id")
checkpoints_tree["displaycolumns"] = ("name", "start_cp", "finish_cp", "repeat_cp")
checkpoints_tree["show"] = "headings"  # Removes the first empty column 
checkpoints_tree.column("name", width=150, anchor="w")
checkpoints_tree.column("start_cp", width=10, anchor="center")
checkpoints_tree.column("finish_cp", width=10, anchor="center")
checkpoints_tree.column("repeat_cp", width=10, anchor="center")
checkpoints_tree.heading("name", text="CP", anchor="w")
checkpoints_tree.heading("start_cp", text="S", anchor="center")
checkpoints_tree.heading("finish_cp", text="F", anchor="center")
checkpoints_tree.heading("repeat_cp", text="R", anchor="center")
checkpoints_tree.bind("<<TreeviewSelect>>", on_checkpoint_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Opprett Treeview-widget for cru-tabell
crus_tree = ttk.Treeview(root, height=8)
crus_tree["columns"] = ("name", "description", "cr_in", "cr_out", "cr_in_out", "checkpoint_id", "rfid_reader_chip_id", "rfid_reader_id")
crus_tree["displaycolumns"] = ("name", "description", "cr_in", "cr_out", "cr_in_out")
crus_tree["show"] = "headings"  # Removes the first empty column
crus_tree.column("name", width=100, anchor="w")
crus_tree.column("description", width=150, anchor="w")
crus_tree.column("cr_in", width=10, anchor="center")
crus_tree.column("cr_out", width=10, anchor="center")
crus_tree.column("cr_in_out", width=10, anchor="center")
crus_tree.heading("name", text="CRU", anchor="w")
crus_tree.heading("description", text="Description", anchor="w")
crus_tree.heading("cr_in", text="I", anchor="center")
crus_tree.heading("cr_out", text="O", anchor="center")
crus_tree.heading("cr_in_out", text="IO", anchor="center")
crus_tree.bind("<<TreeviewSelect>>", on_cru_selected)   # Bind hendelsen for radvalg i Events-tabellen

#Opprett Treeview-widget for participant-tabell
participants_tree = ttk.Treeview(root, height=20)
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
participants_tree.bind("<<TreeviewSelect>>", on_participant_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Opprett Treeview-widget for registrations-tabell
registrations_tree = ttk.Treeview(root, height=35)
registrations_tree["columns"] = ("id", "rfid_reader_chip_id", "rfid_tag_uid", "adjusted_reader_time", 
    "checkpoint_id", "cp_name", "checkpoint_name", "event_id", "race_id", "label", "first_name", "last_name")
registrations_tree["displaycolumns"] = ("id", "rfid_tag_uid", "adjusted_reader_time", "cp_name", "label", "first_name", "last_name")
registrations_tree["show"] = "headings"  # Removes the first empty column
registrations_tree.column("id", width=50, anchor="center")
registrations_tree.column("rfid_tag_uid", width=100, anchor="center")
registrations_tree.column("adjusted_reader_time", width=150, anchor="center")
registrations_tree.column("cp_name", width=50, anchor="center")
registrations_tree.column("label", width=50, anchor="center")
registrations_tree.column("first_name", width=100, anchor="w")
registrations_tree.column("last_name", width=100, anchor="w")
registrations_tree.heading("id", text="ID", anchor="w")
registrations_tree.heading("rfid_tag_uid", text="RFID UID", anchor="center")
registrations_tree.heading("adjusted_reader_time", text="Time", anchor="center")
registrations_tree.heading("cp_name", text="CP", anchor="center")
registrations_tree.heading("label", text="Label", anchor="center")
registrations_tree.heading("first_name", text="First Name", anchor="w")
registrations_tree.heading("last_name", text="Last Name", anchor="w")

# Opprett Scrollbar-widgets
scrollbar_events_vertical = tk.Scrollbar(frame_events, orient="vertical")
scrollbar_events_horizontal = tk.Scrollbar(frame_events, orient="horizontal")
scrollbar_races_vertical = tk.Scrollbar(frame_races, orient="vertical")
scrollbar_races_horizontal = tk.Scrollbar(frame_races, orient="horizontal")
scrollbar_checkpoints_vertical = tk.Scrollbar(frame_checkpoints, orient="vertical")
scrollbar_checkpoints_horizontal = tk.Scrollbar(frame_checkpoints, orient="horizontal")
scrollbar_crus_vertical = tk.Scrollbar(frame_crus, orient="vertical")
scrollbar_crus_horizontal = tk.Scrollbar(frame_crus, orient="horizontal")
scrollbar_participants_vertical = tk.Scrollbar(frame_participants, orient="vertical")
scrollbar_participants_horizontal = tk.Scrollbar(frame_participants, orient="horizontal")
scrollbar_registrations_vertical = tk.Scrollbar(frame_registrations, orient="vertical")
scrollbar_registrations_horizontal = tk.Scrollbar(frame_registrations, orient="horizontal")


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
crus_tree.config(yscrollcommand=scrollbar_crus_vertical.set)
scrollbar_crus_vertical.config(command=crus_tree.yview)
crus_tree.config(xscrollcommand=scrollbar_crus_horizontal.set)
scrollbar_crus_horizontal.config(command=crus_tree.xview)
participants_tree.config(yscrollcommand=scrollbar_participants_vertical.set)
scrollbar_participants_vertical.config(command=participants_tree.yview)
participants_tree.config(xscrollcommand=scrollbar_participants_horizontal.set)
scrollbar_participants_horizontal.config(command=participants_tree.xview)
registrations_tree.config(yscrollcommand=scrollbar_registrations_vertical.set)
scrollbar_registrations_vertical.config(command=registrations_tree.yview)
registrations_tree.config(xscrollcommand=scrollbar_registrations_horizontal.set)
scrollbar_registrations_horizontal.config(command=registrations_tree.xview)


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

# For crus_tree og dens scrollbars:
crus_tree.grid(row=0, column=0, sticky="nsew", in_=frame_crus)
scrollbar_crus_vertical.grid(row=0, column=1, sticky="ns", in_=frame_crus)
scrollbar_crus_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_crus)
# Konfigurer grid-oppførselen for frame_crus:
frame_crus.grid_rowconfigure(0, weight=1)
frame_crus.grid_columnconfigure(0, weight=1)

# For participants_tree og dens scrollbars:
participants_tree.grid(row=0, column=0, sticky="nsew", in_=frame_participants)
scrollbar_participants_vertical.grid(row=0, column=1, sticky="ns", in_=frame_participants)
scrollbar_participants_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_participants)
# Konfigurer grid-oppførselen for frame_participants:
frame_participants.grid_rowconfigure(0, weight=1)
frame_participants.grid_columnconfigure(0, weight=1)

# For registrations_tree og dens scrollbars:
registrations_tree.grid(row=0, column=0, sticky="nsew", in_=frame_registrations)
scrollbar_registrations_vertical.grid(row=0, column=1, sticky="ns", in_=frame_registrations)
scrollbar_registrations_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_registrations)
# Konfigurer grid-oppførselen for frame_registrations:
frame_registrations.grid_rowconfigure(0, weight=1)
frame_registrations.grid_columnconfigure(0, weight=1)

# Create buttons for the main menu
upload_button = ttk.Button(root, text="Upload selected event", command=upload_selected_event_to_firebase)
# get_registrations_button = ttk.Button(root, text="Download registrations", command=fetch_registrations_from_firebase)
exit_button = ttk.Button(root, text="Exit", command=exit_app)
# Place the buttons on the window
upload_button.grid(row=4, column=1, padx=10, pady=10)
# get_registrations_button.grid(row=4, column=2, padx=10, pady=10)
exit_button.grid(row=4, column=4, padx=10, pady=10)


mydb = connect_to_mariadb()
fetch_data_from_database()

root.mainloop()
