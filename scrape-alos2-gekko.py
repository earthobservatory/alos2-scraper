#!/usr/bin/env python
from __future__ import print_function
import json
import pickle
import re
import os.path
import argparse
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from base64 import urlsafe_b64encode
from email.mime.text import MIMEText
# from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
# from apiclient import errors
import smtplib, ssl


# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']


def main(config):
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config['credentials_key'], SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])
    #
    # if not labels:
    #     print('No labels found.')
    # else:
    #     print('Labels:')
    #     for label in labels:
    #         print(label['name'])

    # setup to load auig2 stuff
    with open(config['auig2_accounts']) as f:
        accounts = json.load(f)["accounts"]

    with open(config['completed_ids']) as f:
        completed_dict = json.load(f)

    with open(config['gmail_acct']) as f:
        gmail_acct = json.load(f)

    order_id_regex = re.compile(".*\(order ID: (\d+)\)")
    email_regex = re.compile(".*<(.*)>")

    results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=50).execute()
    messages = results.get('messages', [])


    order_messages = []
    print(len(messages))
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()
        subject = getValueFromHeaderList("Subject", msg)
        if "Please recieve your order" in subject and 'jaxa' in msg['snippet']:
            order_messages.append(msg)


    for order_msg in order_messages:
        subject = getValueFromHeaderList("Subject", order_msg)
        auig2_order_id = order_id_regex.search(subject).group(1)
        sender = email_regex.search(getValueFromHeaderList("From", order_msg)).group(1)
        auig2_user = accounts[sender]

        if auig2_order_id not in completed_dict["completed"]:
            # we need to executing download
            msg = "Executing gekko download for ORDERID: {} EMAIL: {} AUIG_USERNAME: {}".format(auig2_order_id, sender, auig2_user['auig2_id'])
            print(msg)
            completed_dict["completed"].append(auig2_order_id)
            email_msg = create_message("no-reply@ntu.edu.sg", sender, "[auig2 download] orderid {}".format(auig2_order_id), msg)
            print("Sending message: %s" % email_msg)
            send_message_smtp(gmail_acct, sender, email_msg)

    #rewrite completed id list
    with open(config['completed_ids'], 'w') as f:
        json.dump(completed_dict, f, indent=2, sort_keys=True)





def getValueFromHeaderList(name, msg):
    for field in msg['payload']['headers']:
        if field['name'] == name:
            return field['value']


def create_message(sender, to, subject, message_text):
    """Create a message for an email.
    Args:
      sender: Email address of the sender.
      to: Email address of the receiver.
      subject: The subject of the email message.
      message_text: The text of the email message.
    Returns:
      An object containing a base64url encoded email object.
    """
    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Bcc"] = sender

    message.attach(MIMEText(message_text, "plain"))
    return message.as_string()

def send_message(service, user_id, message):
    """Send an email message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      message: Message to be sent.

    Returns:
      Sent Message.
    """

    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                   .execute())
        print('Message Id: %s' % message['id'])
        return message
    except Exception as error:
        print('An error occurred: %s' % error)


def send_message_smtp(sender_email, receiver_email,  message):
    smtp_server = "smtp.gmail.com"
    port = 587  # For starttls
    # Create a secure SSL context
    context = ssl.create_default_context()

    # Try to log in to server and send email
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.ehlo()  # Can be omitted
        server.starttls(context=context)  # Secure the connection
        server.ehlo()  # Can be omitted
        server.login(sender_email["email"], sender_email["password"])
        server.sendmail(sender_email["email"], receiver_email, message)
    except Exception as e:
        # Print any error messages to stdout
        print(e)
    finally:
        server.quit()

def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser(description='log ratio to fpm')
    parser.add_argument('-a', '--auig2', dest='auig2_credentials_json', type=str, required=True,
                        help='json file with auig2 accounts and password', default='secrets.json')
    parser.add_argument('-gk', '--gmailkey', dest='credentials_json', type=str, default='credentials.json',
                        help='json credentials file for this script to access gmail API')
    parser.add_argument('-ga','--gmailacct', dest='gmail_acct_json', type=str, default='email_secrets.json',
                        help='json file with gmail accounts and password' )
    return parser.parse_args()



if __name__ == '__main__':
    inps = cmdLineParse()
    config = {'gmail_acct': inps.gmail_acct_json,
              'credentials_key': inps.credentials_json,
              'auig2_accounts': inps.auig2_credentials_json,
              'completed_ids': 'completed_ids.json'}

    main(config)
