# Description: This file contains the main program for the KrUltra Database Manager.

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import mysql.connector
from firebase import firebase
import pyrebase
from decouple import Config, config
import datetime
import pytz
import csv
import openpyxl
import os

# Henter konfigurasjonsvariabler fra .env-filen
print("Loading configuration variables...")
# config = Config(".env")
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


### Functions to upload and download data to/from Firebase

def upload_rfid_readers_to_firebase(event_id):
    try:
        sql_query = """
        SELECT rfid_reader.checkpoint_id, rfid_reader.chip_id, rfid_reader.description, 
        event.id, rfid_reader.name, rfid_reader.status, checkpoint.name, checkpoint.description, checkpoint.minimum_split,
        checkpoint.start_cp, checkpoint.finish_cp, checkpoint.repeat_cp
        FROM event 
        JOIN checkpoint ON event.id = checkpoint.event_id 
        JOIN rfid_reader ON checkpoint.id = rfid_reader.checkpoint_id 
        WHERE event.id = %s AND checkpoint.status = 1 AND rfid_reader.status = 1;
        """
        mycursor.execute(sql_query, (event_id,))
        rows = mycursor.fetchall()

        #  Upload new event data for rfid_readers to Firebase
        reader_data = {}
        i = 0
        for reader in rows:
            reader_data[i] = {
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
            i += 1
                    
        # Delete existing data in Firebase
        db.child("rfid_readers").remove(token=user_id_token)
        print("Successfully deleted existing RFID readers data in Firebase.")

        db.child("rfid_readers").set(reader_data, token=user_id_token)
        print("Successfully uploaded RFID readers data to Firebase.")

        return True

    except Exception as e:
        print(f"An error occurred: {e}")
        messagebox.showerror("Error", f"An error occurred: {e}")
        return False

def upload_runners_to_firebase(event_id):
    try:
        sql_query = """
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
        WHERE race.event_id = %s AND race.status = 1 AND participant.status = 1 AND rfid_tag.status = 1;
        """
        mycursor.execute(sql_query, (event_id,))
        rows = mycursor.fetchall()

        # Create a list of dictionaries to hold the runner data
        runner_data = {}
        for runner in rows:
            rfid_uid = runner[4]
            runner_data[rfid_uid] = {
                'race_name': runner[0],
                'participant_first_name': runner[1],
                'participant_last_name': runner[2],
                'participant_bib': runner[3], 
            }

        # Delete existing data in Firebase
        db.child("runners").remove(token=user_id_token)
        print("Successfully deleted existing runners data in Firebase.")

        # Upload new event data for runners to Firebase
        db.child("runners").set(runner_data, token=user_id_token)
        print("Successfully uploaded runners data to Firebase.")

        return True

    except Exception as e:
        print(f"An error occurred: {e}")
        messagebox.showerror("Error", f"An error occurred: {e}")
        return False
      
def upload_selected_event_to_firebase():
    selected_items = events_tree.selection()

    if len(selected_items) != 1:
        messagebox.showwarning("Valg av event", "Vennligst velg ett event for opplasting.")
        return False

    selected_event_id = events_tree.item(selected_items[0])['values'][0]

    answer = messagebox.askyesno("Bekreftelse", "Er du sikker? Eksisterende data fjernes!")
    if answer:
        if mydb:
            if (
                upload_rfid_readers_to_firebase(selected_event_id) and
                upload_runners_to_firebase(selected_event_id)
            ):
                print("Successfully uploaded event data to Firebase")
                messagebox.showinfo("Success", "Event data uploaded to Firebase.")
            else:
                print("An error occurred while uploading event data to Firebase.")
                messagebox.showerror("Error", "An error occurred while uploading event data to Firebase.")
        else:
            messagebox.showerror("Error", "Unable to connect to KrUltraCR (MariaDB) database.")

def fetch_and_store_from_firebase_to_sql():
    try:
        # mydb = connect_to_mariadb()   # erstattet av global variabel
        # mycursor = mydb.cursor()      # erstattet av global variabel

        # Hent registreringene fra Firebase
        print("Fetching registrations from Firebase...")
        registrations = db.child("registrations").get(token=user_id_token)

        number_inserted = 0
        number_updated = 0

        # Sjekk hver registrering mot SQL-databasen
        print("Checking registrations against the database...")
        # Registrations er et PyreResponse-objekt, vi må hente dataene som et dictionary
        registrations_dict = registrations.val()
        
        for key, registration in registrations_dict.items():
            mycursor.execute("SELECT * FROM registration WHERE firebase_key = %s", (key,))
            existing_registration = mycursor.fetchone()

            # Sjekk om vi har alle feltene, og sett standardverdier hvis nødvendig
            rfid_reader_id = registration.get('rfid_reader_id', None)
            rfid_reader_chip_id = registration.get('rfid_reader_chip_id', 0)
            rfid_tag_uid = registration.get('rfid_tag_uid', None)
            discoveredAt_ms = registration.get('discoveredAt', 0)
            timestamp_ms = registration.get('timestamp', discoveredAt_ms)
            reg_type = 1
            reg_status = 1
            reg_delay_ms = registration.get('reg_delay_ms', 0)
            firebase_status = registration.get('status', None)
            event_id = registration.get('event_id', None)

            # Konverter timestamp til datetime
            timestamp_sec = (timestamp_ms - reg_delay_ms) / 1000  # Konverter til sekunder
            reader_time = datetime.datetime.utcfromtimestamp(timestamp_sec)
            timezone = pytz.timezone('Europe/Oslo')
            reader_time_datetime = reader_time.replace(tzinfo=pytz.utc).astimezone(timezone)

            # Hvis den ikke eksisterer, legg den til i databasen
            if not existing_registration:
                sql = ("INSERT INTO registration "
                       "(rfid_reader_id, rfid_reader_chip_id, rfid_tag_uid, reader_time, "
                       "type, status, reg_delay_ms, firebase_key, firebase_status, event_id) "
                       "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                val = (rfid_reader_id, rfid_reader_chip_id, rfid_tag_uid, reader_time_datetime,
                       reg_type, reg_status, reg_delay_ms, key, firebase_status, event_id)
                        
                mycursor.execute(sql, val)
                mydb.commit()
                number_inserted += 1

            else:   # Hvis den eksisterer, oppdater den med alle data
                sql = ("UPDATE registration "
                       "SET rfid_reader_id = %s, rfid_reader_chip_id = %s, "
                       "rfid_tag_uid = %s, reader_time = %s, "
                       "type = %s, status = %s, reg_delay_ms = %s, "
                       "firebase_status = %s, event_id = %s "
                       "WHERE firebase_key = %s")
                val = (rfid_reader_id, rfid_reader_chip_id, rfid_tag_uid, reader_time_datetime,
                       reg_type, reg_status, reg_delay_ms, firebase_status, event_id, key)
                mycursor.execute(sql, val)
                mydb.commit()
                number_updated += 1

        print(f"Inserted {number_inserted} new registrations into the database.")
        print(f"Updated {number_updated} registrations in the database.")
        messagebox.showinfo("Success", f"Inserted {number_inserted} new registrations into the database.\nUpdated {number_updated} registrations in the database.")

    except Exception as e:
        print(f"An error occurred: {e}")
        messagebox.showerror("Error", f"An error occurred: {e}")


### Functions to edit data in the database
def open_edit_registration_window():
    selected_items = registrations_tree.selection()
    if len(selected_items) != 1:
        messagebox.showwarning("Select Registration", "Please choose exactly one registration for editing.")
        return

    selected_registration_id = registrations_tree.item(selected_items[0])['values'][0]
    create_edit_registration_window(selected_registration_id)

def create_edit_registration_window(registration_id):
    edit_registration_window = tk.Toplevel(root)
    edit_registration_window.title("Edit Registration")
    edit_registration_window.attributes("-topmost", "true")

    global mydb
    labels = ["ID", "CRU ID", "CRU Chip ID", "Tag", "Time", "Type", "Status", "SysTime", "Loop", "Reg. Delay"]


    def save_changes():
        # Hent oppdaterte verdier fra Entry widgets
        updated_data = [
            entries["CRU ID"].get() or None,  # Hvis feltet er tomt, sett inn None
            entries["CRU Chip ID"].get() or 0,
            entries["Tag"].get(),
            datetime.datetime.strptime(entries["Time"].get(), "%Y-%m-%d %H:%M:%S"),
            entries["Type"].get() or 1,
            entries["Status"].get() or 1,
            datetime.datetime.strptime(entries["SysTime"].get(), "%Y-%m-%d %H:%M:%S"),
            entries["Loop"].get() or None,
            entries["Reg. Delay"].get() or 0,
            entries["ID"].get()
        ]
        
        # Bygg UPDATE SQL-setning
        update_sql = """
        UPDATE registration 
        SET rfid_reader_id=%s, 
            rfid_reader_chip_id=%s, 
            rfid_tag_uid=%s, 
            reader_time=%s, 
            type=%s, 
            status=%s, 
            system_time=%s, 
            `loop`=%s, 
            reg_delay_ms=%s 
        WHERE id=%s
        """

        try:
            # Utfør UPDATE-setningen
            print("updated_data", updated_data)
            mycursor.execute(update_sql, tuple(updated_data))

            # Commit endringene til databasen
            mydb.commit()

            # Gi en bekreftelsesmelding til brukeren
            fetch_registrations()  # Oppdater Treeview-widget
            tk.messagebox.showinfo("Success", "Registration data updated successfully!")

        except mysql.connector.Error as err:
            # Gi en feilmelding til brukeren hvis det oppstår en feil
            tk.messagebox.showerror("Database Error", str(err))


    if mydb:
        # mycursor = mydb.cursor()

        try:
            # Henter data fra databasen basert på registration_id
            mycursor.execute("SELECT * FROM registration WHERE id = %s", (registration_id,))
            registration_data = mycursor.fetchone()
            print("registration_data", registration_data)
        
            # Labels
            for index, label in enumerate(labels):
                tk.Label(edit_registration_window, text=label).grid(row=index, column=0, sticky=tk.W, padx=10, pady=5)
            
            # Input fields (using Entry widget for all for simplicity)
            entries = {}
            for index, field in enumerate(registration_data):
                entries[labels[index]] = tk.Entry(edit_registration_window)
                entries[labels[index]].grid(row=index, column=1, padx=10, pady=5)
                if field is not None:
                    entries[labels[index]].insert(0, field)

            entries["ID"].config(state="disabled")  # Disable the ID field


            # Buttons
            print("buttons")
            save_button = tk.Button(edit_registration_window, text="Save", command=save_changes)
            save_button.grid(row=len(labels), column=0, padx=10, pady=10)
                        
            exit_button = tk.Button(edit_registration_window, text="Exit", command=edit_registration_window.destroy)
            exit_button.grid(row=len(labels), column=2, padx=10, pady=10)
        
        except mysql.connector.Error as err:
            if err.msg == "MySQL Connection not available":
                mydb = connect_to_mariadb() # Prøv å koble til på nytt
                if mydb:
                    create_edit_registration_window(registration_id)
                else:
                    messagebox.showerror("Database Error", "Failed to reconnect to the database.")
            else:
                messagebox.showerror("Database Error", str(err))
    
    else:
        tk.messagebox.showerror("Database Error", "Unable to connect to the database.")


### Functions to get data from the SQL database
def fetch_data_from_database():
    print("Fetching data from database...")
    fetch_events()
    fetch_races()
    fetch_checkpoints()
    fetch_crus()
    fetch_participants()
    fetch_registrations()

def fetch_events():
    global mydb
    if mydb:
        # mycursor = mydb.cursor()

        # For Events
        try:
            mycursor.execute("SELECT id, long_name, year, edition FROM event WHERE status=1")
            events = mycursor.fetchall()
            # Adding rows to the Treeview
            for event in events:
                events_tree.insert("", "end", values=event)
            # Grid the Treeview
            events_tree.grid(row=0, column=0, sticky="nsew", in_=frame_events)
        except mysql.connector.Error as err:
            if err.msg == "MySQL Connection not available":
                mydb = connect_to_mariadb() # Prøv å koble til på nytt
                if mydb:
                    fetch_data_from_database()
                else:
                    messagebox.showerror("Database Error", "Failed to reconnect to the database.")
            else:
                messagebox.showerror("Database Error", str(err))
    else:
        messagebox.showerror("Error", "Unable to connect to database (MariaDB).")

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
            # mycursor = mydb.cursor()
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
            # mycursor = mydb.cursor()
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
    crus_query = "SELECT id, name, description, rfid_reader_chip_id, cr_in, cr_out, cr_in_out, checkpoint_id, rfid_reader_id FROM event_cru WHERE 1=1"  # Basis for spørringen

    # Hvis noen events er valgt, legg til event_id i spørringen
    if selected_event_items:
        selected_event_ids = [events_tree.item(item)['values'][0] for item in selected_event_items]
        print("selected_event_ids", selected_event_ids)
        crus_query += " AND event_id IN (%s)" % ', '.join(['%s'] * len(selected_event_ids))
        params.extend(selected_event_ids)

    # Kjør SQL-spørringen, hent data, og fyll Treeview
    try:
        if mydb:
            # mycursor = mydb.cursor()
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
            # mycursor = mydb.cursor()
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
            # mycursor = mydb.cursor()
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
    
def generate_results():
    global mycursor  # Bruk global for å referere til den globale mycursor-variabelen

    # Opprett hovedvinduet
    root = tk.Tk()
    root.title("KrUltra Results")

    # Funksjon for å oppdatere løpene basert på valgt arrangement
    def update_races(event_id):
        if event_id == "All":
            race_var.set("All")
        else:
            mycursor.execute("SELECT r.id, CONCAT(e.short_name, ' - ', r.name) FROM event e LEFT JOIN race r ON e.id = r.event_id WHERE e.id = %s ORDER BY r.id DESC", (event_id,))
            race_choices = ["All"] + [f"{choice[0]} - {choice[1]}" for choice in mycursor.fetchall()]
            race_dropdown['menu'].delete(0, 'end')  # Fjern eksisterende alternativer
            for choice in race_choices:
                race_dropdown['menu'].add_command(label=choice, command=tk._setit(race_var, choice))

    # Dropdown-liste for arrangementer
    mycursor.execute("SELECT event.id, event.short_name FROM event ORDER BY event.id DESC")
    event_choices = ["All"] + [f"{choice[0]} - {choice[1]}" for choice in mycursor.fetchall()]
    event_var = tk.StringVar(root)
    event_var.set("All")
    event_dropdown = tk.OptionMenu(root, event_var, *event_choices, command=lambda event_id: update_races(event_id.split(" - ")[0]))
    event_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="w")
    event_label = tk.Label(root, text="Select Event:")
    event_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

    # Dropdown-liste for løp (race) - Deaktiver som standard
    race_var = tk.StringVar(root)
    race_var.set("All")
    race_dropdown = tk.OptionMenu(root, race_var, "All")
    race_dropdown.config(state='disabled')  # Deaktiver dropdown-listen
    race_dropdown.grid(row=1, column=1, padx=10, pady=10, sticky="w")
    race_label = tk.Label(root, text="Select Race:")
    race_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")

    # Funksjon for å aktivere dropdown-listen for løp (race)
    def enable_race_dropdown():
        race_dropdown.config(state='normal')  # Aktiver dropdown-listen

    # Dropdown-liste for å velge rapporttype
    mycursor.execute("SELECT id, CONCAT(name, ' (', CASE WHEN status = 0 THEN 'Inactive' ELSE 'Active' END, ')') FROM report")
    reports = mycursor.fetchall()
    report_choices = ["--- Select Report ---"] + [f"{report[0]} - {report[1]}" for report in reports]
    report_var = tk.StringVar(root)
    report_var.set("--- Select Report ---")
    report_dropdown = tk.OptionMenu(root, report_var, *report_choices)
    report_dropdown.grid(row=2, column=1, padx=10, pady=10, sticky="w")
    report_label = tk.Label(root, text="Select format:")
    report_label.grid(row=2, column=0, padx=10, pady=10, sticky="w")

    # Knapp for å kjøre rapport
    def run_report(selected_event, selected_race, selected_report):
        print(selected_event)
        print(selected_race)
        print(selected_report)
        if selected_report == "--- Select Report ---":
            messagebox.showerror("Error", "Please select a report.")
        elif selected_report == "1":
            generate_itra_report(selected_race)
        elif selected_report == "2":
            generate_KUTC_report(selected_event)
        # Legg til flere 'elif' for andre rapporter hvis nødvendig
        else:
            print("Invalid selected report")

    # Knapp for å kjøre rapport med valgte filtre
    run_button = tk.Button(root, text="Run report", command=lambda: run_report(event_var.get().split(" - ")[0], race_var.get().split(" - ")[0], report_var.get().split(" - ")[0]))
    run_button.grid(row=3, column=0, padx=10, pady=10, sticky="w")

    # Knapp for å avslutte
    exit_button = tk.Button(root, text="Exit", command=root.quit)
    exit_button.grid(row=3, column=1, padx=10, pady=10, sticky="e")

    # Aktiver løp (race) dropdown-listen når et arrangement er valgt
    event_var.trace_add('write', lambda *args: enable_race_dropdown())

    # Oppdater knappen for 'Run report' basert på valget av rapport
    def update_run_button(*args):
        selected_report = report_var.get()
        if selected_report == "--- Select Report ---":
            run_button.config(state="disabled")
        else:
            run_button.config(state="normal")

    # Lytt etter endringer i valget av rapport
    report_var.trace_add("write", update_run_button)


def generate_itra_report(selected_race):
    # Utfør SQL-spørringen
    sql_query = f"""
    SELECT
        CASE
            WHEN rank_num IS NOT NULL THEN rank_num
            ELSE 'DNF'
        END AS Ranking,
        CASE
            WHEN rank_num IS NOT NULL THEN 
                SEC_TO_TIME(time_diff_seconds)
            ELSE ''
        END AS Time,
        last_name AS `Family Name`,
        first_name AS `First Name`,
        LEFT(long_gender, 1) AS `Gender`,
        date_of_birth AS `Birthdate`,
        alpha3_code AS `Nationality`,
        address3 AS `city`,
        bib AS `bib number`,
        club AS `Team`,
        race_loops
    FROM (
        SELECT
            ROW_NUMBER() OVER (PARTITION BY bib ORDER BY adjusted_reader_time) AS rank_num,
            adjusted_reader_time,
            start_time,
            TIMESTAMPDIFF(SECOND, start_time, adjusted_reader_time) AS time_diff_seconds,
            last_name,
            first_name,
            long_gender,
            date_of_birth,
            alpha3_code,
            address3,
            bib,
            club,
            race_loops
        FROM registration_view
        WHERE race_id = {selected_race} AND finish_cp = 1
        ) ranked
    """

    mycursor.execute(sql_query)

    # Hent resultatene som en liste av poster
    results = mycursor.fetchall()
    print("results:", results)

    # Gå gjennom resultatene og finn bare én linje for hver løper
    runners_data = {}  # Et dictionary for å lagre data for hver løper

    for row in results:
        ranking, time, last_name, first_name, gender, birthdate, nationality, city, bib_number, team, race_loops = row

        # Konverter 'ranking' til en integer for sammenligning
        ranking = int(ranking)
        bib_number = int(bib_number)

        # Hvis løperen allerede er i dictionaryet
        if bib_number in runners_data:
            # Hvis dette resultatet er bedre (ranking == race_loops) enn det vi har, oppdater dataene
            if ranking == race_loops:
                runners_data[bib_number] = (ranking, time, last_name, first_name, gender, birthdate, nationality, city, bib_number, team)
        else:
            # Hvis løperen ikke er i dictionaryet, legg den til med nåværende data
            if ranking == race_loops:
                runners_data[bib_number] = (ranking, time, last_name, first_name, gender, birthdate, nationality, city, bib_number, team)
            else:
                runners_data[bib_number] = ('DNF', "", last_name, first_name, gender, birthdate, nationality, city, bib_number, team)

    # Sorter løperne etter tid, og plasser 'DNF' til slutt
    sorted_runners_data = sorted(runners_data.values(), key=lambda x: (x[0] if x[0] != 'DNF' else float('inf'), x[1]))

    # Gå gjennom `sorted_runners_data` og oppdater rankingen
    for i, runner_data in enumerate(sorted_runners_data):
        ranking, time, last_name, first_name, gender, birthdate, nationality, city, bib_number, team = runner_data

        # Hvis ranking er 'DNF', ikke endre den
        if ranking == 'DNF':
            break

        # Oppdater ranking med stigende løpenummer
        sorted_runners_data[i] = (i+1, time, last_name, first_name, gender, birthdate, nationality, city, bib_number, team)

    # Opprett en rotvindu for Tkinter
    root = tk.Tk()
    root.withdraw()  # Skjul rotvinduet

    # Spør brukeren om å velge en filplassering og filnavn
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])

    # Avslutt programmet hvis brukeren avbryter dialogvinduet
    if not file_path:
        print("Operasjonen ble avbrutt av brukeren.")
    else:
        # Opprett en ny Excel-arbeidsbok og få tak i det aktive arket
        workbook = openpyxl.Workbook()
        sheet = workbook.active

        # Legg til kolonneoverskrifter
        headers = ["Ranking", "Time", "Family Name", "First Name", "Gender", "Birthdate", "Nationality", "city", "bib number", "Team"]
        sheet.append(headers)

        # Legg til data i arket
        for runner_data in sorted_runners_data:
            sheet.append(runner_data)

        # Lagre Excel-arbeidsboken med det valgte filnavnet
        workbook.save(file_path)

    print(f"Rapporten er lagret som '{file_path}'.")
    messagebox.showinfo("Success", f"Rapporten er lagret som '{file_path}'.")

def generate_KUTC_report(selected_event):
    print("selected_event:", selected_event)
    global mycursor
    sql_query = f"""
    SELECT
        bib,
        first_name,
        last_name,
        club,
        alpha3_code as country,
        left(long_gender, 1) AS gender,
        YEAR(date_of_birth) AS year_of_birth,
        COUNT(*) AS loops,
        MAX(SEC_TO_TIME(TIMESTAMPDIFF(SECOND, start_time, adjusted_reader_time))) AS time,
        event_name,
        race_name,
        race_loops
    FROM registration_view
    WHERE 
        event_id = {selected_event} AND 
        finish_cp = 1 AND
        status = 1
    GROUP BY participant_id
    ORDER BY loops DESC, time ASC
    """

    mycursor.execute(sql_query)
    results = mycursor.fetchall()

    print("results:", results)

    ranked_results = []
    ranking = 1

    for row in results:
        bib, first_name, last_name, club, country, gender, year_of_birth, loops, time, event_name, race_name, race_loops = row
        ranked_results.append((event_name, ranking, first_name + " " + last_name, loops, time, int(bib), club, country, race_name))
        ranking += 1

    print("ranked_results:", ranked_results)

    # Opprett en rotvindu for Tkinter
    root = tk.Tk()
    root.withdraw()  # Skjul rotvinduet

    # Spør brukeren om å velge en filplassering og filnavn
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])

    # Avslutt programmet hvis brukeren avbryter dialogvinduet
    if not file_path:
        print("Operasjonen ble avbrutt av brukeren.")
    else:
        # Opprett en ny Excel-arbeidsbok og få tak i det aktive arket
        workbook = openpyxl.Workbook()
        sheet = workbook.active

        # Legg til kolonneoverskrifter
        headers = ["Event", "Ranking", "Name", "Loops", "Time", "Bib number", "Club", "Nationality", "Race"]
        sheet.append(headers)

        # Legg til data i arket
        for runner_data in ranked_results:
            sheet.append(runner_data)

        # Lagre Excel-arbeidsboken med det valgte filnavnet
        workbook.save(file_path)

    print(f"Rapporten er lagret som '{file_path}'.")
    messagebox.showinfo("Success", f"Rapporten er lagret som '{file_path}'.")



### Functions to filter data from the database based on user selections
def on_event_selected(event):
    fetch_races()
    fetch_checkpoints()
    fetch_crus()
    fetch_participants()
    fetch_registrations()

def on_race_selected(race):
    fetch_participants()
    fetch_registrations()

def on_checkpoint_selected(checkpoint):
    fetch_registrations()

def on_cru_selected(cru):
    fetch_registrations()

def on_participant_selected(participant):
    fetch_registrations()

def on_registration_selected(registration):
    selected_items = registrations_tree.selection()
    print("on_registration_selected", selected_items)
    if len(selected_items)  == 1:
        edit_registration_button.config(state='normal')
    else:
        edit_registration_button.config(state='disabled')


### GUI setup
# Create the labels for the tables
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
frame_participants.grid(row=3, column=1, padx=5, pady=5, sticky="nsew", rowspan=2, columnspan=4)
frame_registrations = tk.Frame(root)
frame_registrations.grid(row=1, column=5, padx=5, pady=5, sticky="nsew", rowspan=3)


## Create Treevies-widget for each table
# Create Treeview-widget for events-table
events_tree = ttk.Treeview(root, height=8)
events_tree["columns"] = ("id", "long_name", "year", "edition")
events_tree["displaycolumns"] = ("long_name", "year")
events_tree["show"] = "headings"  # Removes the first empty column
events_tree.column("long_name", width=100, anchor="w")
events_tree.column("year", width=50, anchor="center")
events_tree.heading("long_name", text="Event Name", anchor="w")
events_tree.heading("year", text="Year", anchor="center")
events_tree.bind("<<TreeviewSelect>>", on_event_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Create Treeview-widget for races-table
races_tree = ttk.Treeview(root, height=8)
races_tree["columns"] = ("id", "name")
races_tree["displaycolumns"] = ("name")
races_tree["show"] = "headings"  # Removes the first empty column
races_tree.column("name", width=100)
races_tree.heading("name", text="Race Name", anchor="w")
races_tree.bind("<<TreeviewSelect>>", on_race_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Create Treeview-widget for checkpoints-table
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

# Create Treeview-widget for crus-table
crus_tree = ttk.Treeview(root, height=8)
crus_tree["columns"] = ("id", "name", "description", "rfid_reader_chip_id", "cr_in", "cr_out", "cr_in_out", "checkpoint_id", "rfid_reader_id")
crus_tree["displaycolumns"] = ("id", "name", "description", "rfid_reader_chip_id", "cr_in", "cr_out", "cr_in_out")
crus_tree["show"] = "headings"  # Removes the first empty column
crus_tree.column("id", width=40, anchor="center")
crus_tree.column("name", width=60, anchor="w")
crus_tree.column("description", width=150, anchor="w")
crus_tree.column("rfid_reader_chip_id", width=150, anchor="center")
crus_tree.column("cr_in", width=10, anchor="center")
crus_tree.column("cr_out", width=10, anchor="center")
crus_tree.column("cr_in_out", width=10, anchor="center")
crus_tree.heading("id", text="ID", anchor="center")
crus_tree.heading("name", text="CRU", anchor="w")
crus_tree.heading("description", text="Description", anchor="w")
crus_tree.heading("rfid_reader_chip_id", text="Chip ID", anchor="center")
crus_tree.heading("cr_in", text="I", anchor="center")
crus_tree.heading("cr_out", text="O", anchor="center")
crus_tree.heading("cr_in_out", text="IO", anchor="center")
crus_tree.bind("<<TreeviewSelect>>", on_cru_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Create Treeview-widget for participants-table
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

# Create Treeview-widget for registrations-table
registrations_tree = ttk.Treeview(root, height=30)
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
registrations_tree.bind("<<TreeviewSelect>>", on_registration_selected)   # Bind hendelsen for radvalg i Events-tabellen

# Create Scrollbar-widgets
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

# Connect the Scrollbar-widgets to the Treeview-widgets
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


# For events_tree and its scrollbars:
events_tree.grid(row=0, column=0, sticky="nsew", in_=frame_events)
scrollbar_events_vertical.grid(row=0, column=1, sticky="ns", in_=frame_events)
scrollbar_events_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_events)
# Konfigurer grid-oppførselen for frame_events:
frame_events.grid_rowconfigure(0, weight=1)    # La rad 0 vokse når vinduet endrer størrelse
frame_events.grid_columnconfigure(0, weight=1) # La kolonne 0 vokse når vinduet endrer størrelse

# For races_tree and its scrollbars:
races_tree.grid(row=0, column=0, sticky="nsew", in_=frame_races)
scrollbar_races_vertical.grid(row=0, column=1, sticky="ns", in_=frame_races)
scrollbar_races_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_races)
# Konfigurer grid-oppførselen for frame_races:
frame_races.grid_rowconfigure(0, weight=1)
frame_races.grid_columnconfigure(0, weight=1)

# For checkpoints_tree and its scrollbars:
checkpoints_tree.grid(row=0, column=0, sticky="nsew", in_=frame_checkpoints)
scrollbar_checkpoints_vertical.grid(row=0, column=1, sticky="ns", in_=frame_checkpoints)
scrollbar_checkpoints_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_checkpoints)
# Konfigurer grid-oppførselen for frame_checkpoints:
frame_checkpoints.grid_rowconfigure(0, weight=1)
frame_checkpoints.grid_columnconfigure(0, weight=1)

# For crus_tree and its scrollbars:
crus_tree.grid(row=0, column=0, sticky="nsew", in_=frame_crus)
scrollbar_crus_vertical.grid(row=0, column=1, sticky="ns", in_=frame_crus)
scrollbar_crus_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_crus)
# Konfigurer grid-oppførselen for frame_crus:
frame_crus.grid_rowconfigure(0, weight=1)
frame_crus.grid_columnconfigure(0, weight=1)

# For participants_tree and its scrollbars:
participants_tree.grid(row=0, column=0, sticky="nsew", in_=frame_participants)
scrollbar_participants_vertical.grid(row=0, column=1, sticky="ns", in_=frame_participants)
scrollbar_participants_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_participants)
# Konfigurer grid-oppførselen for frame_participants:
frame_participants.grid_rowconfigure(0, weight=1)
frame_participants.grid_columnconfigure(0, weight=1)

# For registrations_tree and its scrollbars:
registrations_tree.grid(row=0, column=0, sticky="nsew", in_=frame_registrations)
scrollbar_registrations_vertical.grid(row=0, column=1, sticky="ns", in_=frame_registrations)
scrollbar_registrations_horizontal.grid(row=1, column=0, sticky="ew", in_=frame_registrations)
# Konfigurer grid-oppførselen for frame_registrations:
frame_registrations.grid_rowconfigure(0, weight=1)
frame_registrations.grid_columnconfigure(0, weight=1)

# Create buttons for the main menu
upload_event_button = ttk.Button(root, text="Upload selected event", command=upload_selected_event_to_firebase)
download_registrations_button = ttk.Button(root, text="Download registrations", command=fetch_and_store_from_firebase_to_sql)
edit_registration_button = ttk.Button(root, text="Edit", command=open_edit_registration_window)
generate_results_button = ttk.Button(root, text="Generate results", command=generate_results)
exit_button = ttk.Button(root, text="Exit", command=exit_app)

# Place the buttons on the window
upload_event_button.grid(row=5, column=1, padx=10, pady=10)
download_registrations_button.grid(row=5, column=2, padx=10, pady=10)
edit_registration_button.grid(row=4, column=5, padx=10, pady=10, sticky="w")
edit_registration_button.config(state='disabled')
generate_results_button.grid(row=5, column=5, padx=10, pady=10, sticky="w")
exit_button.grid(row=5, column=5, padx=10, pady=10, sticky="e")


mydb = connect_to_mariadb()
mycursor = mydb.cursor()
fetch_data_from_database()

root.mainloop() # Start the GUI
