#!/usr/bin/env python
from __future__ import print_function
import json
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib, ssl

# If modifying these scopes, delete the file token.pickle.
SMTP_SERVERS = {"gmail":"smtp.gmail.com", "ntu.edu": "smtp.office365.com"}
# SMTP_PORT = 993


def update_and_send(inps):
    complete = 'complete' in inps.message_type
    auig2_order_id = inps.auig2_order_id
    auig2_username = inps.auig2_username

    # Load credentials from auig2
    with open(inps.auig2_credentials_json) as f:
        accounts = json.load(f)["accounts"]

    # Find which email to send to based on auig2 username
    send_to_email = ''
    for key, value in accounts.items():
        if value["auig2_id"] == auig2_username:
            send_to_email = key
            break

    if complete:
        message = "Gekko download job completed for ORDERID: {} AUIG_USERNAME: {} EMAIL: {} \n {} ".format(auig2_order_id,
                                                                                                           auig2_username,
                                                                                                           send_to_email,
                                                                                                           inps.message_other)
        # Update completed_id file if downlaod job completed and complete_id file specified
        if inps.id_check_file:
            with open(inps.id_check_file) as f:
                completed_dict = json.load(f)

            completed_dict["completed"].append(inps.auig2_order_id)

            with open(inps.id_check_file, 'w') as f:
                json.dump(completed_dict, f, indent=2, sort_keys=True)

    else:
        message = "Gekko download job submitted for ORDERID: {} AUIG_USERNAME: {} EMAIL: {} \n {}".format(auig2_order_id,
                                                                                                           auig2_username,
                                                                                                           send_to_email,
                                                                                                           inps.message_other)
    with open(inps.email_acct_json) as f:
        email_acct = json.load(f)

    for key, value in SMTP_SERVERS.items():
        if key in email_acct["email"]:
            smtp_server = value
            break

    print(message)
    email_msg = create_message(send_to_email, send_to_email, "[AUIG2-Gekko] orderid {} update".format(auig2_order_id), message)
    print("Sending message: %s" % email_msg)
    send_message_smtp(smtp_server, email_acct, send_to_email, email_msg)



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



def send_message_smtp(smtp_server, sender_email, receiver_email, message):
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
    parser.add_argument('-a', '--auig2', dest='auig2_credentials_json', type=str,
                        help='json file with auig2 accounts and password', default='auig2_accounts.json')
    parser.add_argument('-ea', '--emailacct', dest='email_acct_json', type=str, default='email_secrets.json',
                        help='json file with gmail accounts and password')
    parser.add_argument('-cid', '--completed_ids', dest='id_check_file', type=str, default="",
                        help='specify json with list of completed ids if check is desired')
    parser.add_argument('-mt', '--message_type', dest='message_type', type=str, default="submit",
                        help='message type to send. Options: submit | complete')
    parser.add_argument('-mo', '--message_other', dest='message_other', type=str, default="",
                        help='a freeform string to append to the message ')
    parser.add_argument('-o', '--auig2_orderid', dest='auig2_order_id', type=str, default="",
                        help='auig2 order_id')
    parser.add_argument('-u', '--auig2_username', dest='auig2_username', type=str, default="",
                        help='auig2 username')
    return parser.parse_args()


if __name__ == '__main__':
    inps = cmdLineParse()

    update_and_send(inps)
