import smtplib
import imaplib
import email
from email.mime.text import MIMEText
import os
from decouple import config

# Henter konfigurasjonsvariabler fra .env-filen
print("Loading configuration variables...")
# FIREBASE_API_KEY = config('FIREBASE_API_KEY')
# FIREBASE_AUTH_DOMAIN = config('FIREBASE_AUTH_DOMAIN')
# FIREBASE_DATABASE_URL = config('FIREBASE_DATABASE_URL')
# FIREBASE_STORAGE_BUCKET = config('FIREBASE_STORAGE_BUCKET')
# FIREBASE_EMAIL = config('FIREBASE_EMAIL')
# FIREBASE_PASSWORD = config('FIREBASE_PASSWORD')
# MARIADB_HOST = config('MARIADB_HOST')
# MARIADB_PORT = config('MARIADB_PORT')
# MARIADB_USER = config('MARIADB_USER')
# MARIADB_PASSWORD = config('MARIADB_PASSWORD')
# MARIADB_DATABASE = config('MARIADB_DATABASE')
SMTP_SERVER = config('DOMENESHOP_EMAIL_SMTP_SERVER')
SMTP_PORT = config('DOMENESHOP_EMAIL_SMTP_PORT')
IMAP_SERVER = config('DOMENESHOP_EMAIL_IMAP_SERVER')
IMAP_PORT = config('DOMENESHOP_EMAIL_IMAP_PORT')
ADMIN_USER = config('DOMENESHOP_EMAIL_USER1')
ADMIN_PASSWORD = config('DOMENESHOP_EMAIL_PASSWORD1')
ADMIN_ADDRESS = config('DOMENESHOP_EMAIL_ADDRESS1')
REGISTRATION_USER = config('DOMENESHOP_EMAIL_USER2')
REGISTRATION_PASSWORD = config('DOMENESHOP_EMAIL_PASSWORD2')
REGISTRATION_ADDRESS = config('DOMENESHOP_EMAIL_ADDRESS2')

# Send e-post
def send_email(smtp_server, smtp_port, from_email, password, to_email, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(from_email, password)
        server.sendmail(from_email, to_email, msg.as_string())
    print('E-post sendt til: ' + to_email)
    print('Innhold:' +  msg.as_string())

# Les e-post og svar hvis betingelser oppfylles
def read_and_reply(imap_server, imap_port, user, password, smtp_server, smtp_port, from_email):
    conn = imaplib.IMAP4_SSL(imap_server, imap_port)
    conn.login(user, password)
    conn.select('inbox')

    status, data = conn.uid('search', None, 'UNSEEN')
    if status == 'OK':
        email_ids = data[0].split()
        for e_id in email_ids:
            status, msg_data = conn.uid('fetch', e_id, '(RFC822)')
            raw_email = msg_data[0][1]

            msg = email.message_from_bytes(raw_email)
            if msg['subject'] == 'Test':
                body = email.message_from_string(msg.get_payload()).get_payload()
                from_addr = body.split("fra:")[1].strip()

                send_email(smtp_server, smtp_port, from_email, password, from_addr,
                           'Test-svar', 'Hilsen KrUltra')
    conn.logout()

# SMTP og IMAP info fra Domeneshop
smtp_server = SMTP_SERVER
smtp_port = SMTP_PORT  # TLS
imap_server = IMAP_SERVER
imap_port = IMAP_PORT  # SSL

# Info for admin@krultra.no
admin_user = ADMIN_USER
admin_password = ADMIN_PASSWORD
admin_address = ADMIN_ADDRESS

# Info for registration@krultra.no
reg_user = REGISTRATION_USER
reg_password = REGISTRATION_PASSWORD
reg_address = REGISTRATION_ADDRESS

# Send en test e-post fra admin@krultra.no til registration@krultra.no
send_email(smtp_server, smtp_port, admin_address, admin_password, reg_address,
           'Test', 'Test sending og mottak av e-post fra: torgeir.kruke@gmail.com')

# Les e-post for registration@krultra.no og svar hvis nødvendig
read_and_reply(imap_server, imap_port, reg_user, reg_password, smtp_server, smtp_port, reg_address)
