#!/usr/bin/env python3
from __future__ import print_function
import json, sys
import re
import argparse
import email
import imaplib
import send_email_and_update_list
import traceback



# If modifying these scopes, delete the file token.pickle.
SMTP_SERVERS = {"gmail":"imap.gmail.com", "ntu.edu": "outlook.office365.com"}
# SMTP_PORT   = 993


def main(inps):
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    download_script=inps.download_script
    # setup to load auig2 stuff
    with open(inps.auig2_credentials_json) as f:
        accounts = json.load(f)["accounts"]

    completed_dict = {"completed":[]}
    if inps.id_check_file:
        with open(inps.id_check_file) as f:
            completed_dict = json.load(f)

    with open(inps.email_acct_json) as f:
        email_acct = json.load(f)

    # get the right smtp server
    for key, value in SMTP_SERVERS.items():
        if key in email_acct["email"]:
            smtp_server = value
            break

    # results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=config['max_lookback']).execute()
    # messages = results.get('messages', [])

    try:

        mail = imaplib.IMAP4_SSL(smtp_server)
        mail.login(email_acct['email'], email_acct['password'])
        mail.select('inbox')
        type, data = mail.search(None, 'ALL')
        mail_ids = data[0]

        id_list = mail_ids.split()
        if len(id_list) < inps.max_lookback:
            lookback_ind = 0
        else:
            lookback_ind = -inps.max_lookback

        first_email_id = int(id_list[lookback_ind])
        latest_email_id = int(id_list[-1])

        print("lookback_ind:{}, first_email_id:{}, latest_email_id:{}".format(lookback_ind, first_email_id, latest_email_id))

        order_messages = []
        for i in range(latest_email_id, first_email_id, -1):
            typ, data = mail.fetch(str(i), '(RFC822)')

            for response_part in data:
                if isinstance(response_part, tuple):
                    try:
                        msg = email.message_from_string(response_part[1].decode('utf-8'))
                        email_body = get_text(msg)
                        email_subject = msg['subject'] if msg['subject'] else "None"
                        email_from = msg['from'] if msg['from'] else "None"
                        email_date = msg['date'] if msg['date'] else "None"
                    except Exception as e:
                        print("Got exception while reading email index {} : {}. \n Continuing..".format(i, str(e)))

                    email_body = email_body if email_body else "None"
                    print('{} | From:{} | Subject: {} '.format(email_date, email_from, email_subject))
                    if (("Please recieve your order" in email_subject) or ("Preparation Complete" in email_subject)) \
                            and 'jaxa' in email_body:
                        order_messages.append(msg)

    except Exception as e:
        traceback.print_exc()
        sys.exit(1)

    order_id_regex = re.compile(".*\(order ID: (\d+)\)")
    email_regex = re.compile(".*<(.*)>")
    ntu_mail_regex = re.compile("(.*@)(.*)(ntu.edu.sg)")

    for order_msg in order_messages:
        subject = order_msg['subject']
        auig2_order_id = order_id_regex.search(subject).group(1)
        sender = email_regex.search(order_msg['from']).group(1)
        if sender in accounts.keys():
            # Check if the sender of the AUIG2 message is an auig2 account holder (he/she fwd the mail)
            auig2_user = accounts[sender]
        else:
            # Sender is not AUIG2 aacount holder (most likely form JAXA), we will use the NTU email account as the regex
            ntu_mail_match = ntu_mail_regex.search(email_acct['email'])
            if ntu_mail_match:
                auig2_user = accounts["{}{}".format(ntu_mail_match.group(1),ntu_mail_match.group(3))]
            else:
                raise RuntimeError("Unable to find AUIG-2 user based on email: {}".format(email_acct['email']))


        if auig2_order_id not in completed_dict["completed"]:
            # we need to executing download
            msg = "Executing gekko download for ORDERID: {} EMAIL: {} AUIG_USERNAME: {}".format(auig2_order_id, sender, auig2_user['auig2_id'])
            print(msg)
            cmd = "qsub -v o={},u={},p={} {}".format(auig2_order_id,  auig2_user['auig2_id'], auig2_user['auig2_password'], download_script)
            print(cmd)
            # sp.check_call(cmd, shell=True) # TODO: bring this back to life later!

            # inps.message_type = 'submit'
            # inps.message_other = ''
            # inps.auig2_username = auig2_user['auig2_id']
            # inps.auig2_order_id = auig2_order_id
            # send_email_and_update_list.update_and_send(inps)


def get_text(msg):
    if msg.is_multipart():
        return get_text(msg.get_payload(0))
    else:
        return msg.get_payload(None, True).decode('utf-8')


#
def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser(description='log ratio to fpm')
    parser.add_argument('-a', '--auig2', dest='auig2_credentials_json', type=str,
                        help='json file with auig2 accounts and password', default='auig2_accounts.json')
    parser.add_argument('-ea','--emailacct', dest='email_acct_json', type=str, default='email_secrets.json',
                        help='json file with email accounts and password' )
    parser.add_argument('-lb', '--lookback', dest='max_lookback', type=int, default=50,
                        help='number of email messages to look back to search for AUIG-2 messages')
    parser.add_argument('-s','--script', dest='download_script', type=str, default='/home/share/insarscripts/download/auig2_download_unzip/auig2_download_unzip.pbs',
                        help='pbs script to execute' )
    parser.add_argument('-cid','--completed_ids', dest='id_check_file', type=str, default="",
                        help='specify json with list of completed ids to check dedups')
    return parser.parse_args()



if __name__ == '__main__':
    inps = cmdLineParse()

    main(inps)

