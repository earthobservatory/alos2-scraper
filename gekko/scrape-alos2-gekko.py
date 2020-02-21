#!/usr/bin/env python3
from __future__ import print_function
import json, sys, os
import subprocess as sp
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
    # setup to load auig2 stuff
    pbs_script=os.path.abspath(inps.pbs_script)
    cred_file=os.path.abspath(inps.acct_cred_json)

    with open(cred_file) as f:
        all_accts = json.load(f)
        auig2_acct = all_accts["auig2_accounts"]
        email_acct = all_accts["email_account"]

    completed_dict = {"completed":[]}
    if inps.id_check_file:
        cid_file=os.path.abspath(inps.id_check_file)
        with open(cid_file) as f:
            completed_dict = json.load(f)
    else:
        cid_file=''

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
                        email_body = email_body if email_body else "None"
                        email_subject = msg['subject'] if msg['subject'] else "None"
                        email_from = msg['from'] if msg['from'] else "None"
                        email_date = msg['date'] if msg['date'] else "None"
                        email_to = msg['to'] if msg['to'] else "None"
                    except Exception as e:
                        print("Got exception while reading email index {} : {}. \n Continuing..".format(i, str(e)))

                    print('{} | From:{} | To: {}| Subject: {} '.format(email_date, email_from, email_to, email_subject))
                    if (("Please recieve your order" in email_subject) or ("Preparation Complete" in email_subject)) \
                            and 'jaxa' in email_body:
                        order_messages.append(msg)

    except Exception as e:
        traceback.print_exc()
        sys.exit(1)

    order_id_regex = re.compile(".*\(order ID: (\d+)\)")
    email_regex = re.compile(".*<(.*)>")

    for order_msg in order_messages:
        subject = order_msg['subject']
        subj_match=order_id_regex.search(subject)
        if subj_match:
            auig2_order_id = subj_match.group(1)
            sender = email_regex.search(order_msg['from']).group(1)
            receiver = email_regex.search(order_msg['to']).group(1)
            if sender in auig2_acct.keys():
                # Check if mail is forwarded. If it is, sender of the message is an auig2 account holder
                auig2_user = auig2_acct[sender]
            elif receiver in auig2_acct.keys():
                # Mail is not forwarded,  and might be likely from JAXA, hence use the receiver add as auig2 acct holder.
                auig2_user = auig2_acct[receiver]
            else:
                raise RuntimeError("Unable to find AUIG-2 user based on: {} or {}".format(sender, receiver))


            if auig2_order_id not in completed_dict["completed"]:
                # we need to executing download
                msg = "Executing gekko download for ORDERID: {} EMAIL: {} AUIG_USERNAME: {}".format(auig2_order_id, sender, auig2_user['auig2_id'])
                print(msg)
                cmd = "qsub -v o={},u={},p={},cred={},cid={} {}".format(auig2_order_id,  auig2_user['auig2_id'], auig2_user['auig2_password'], cred_file, cid_file, pbs_script)
                print(cmd)
                sp.check_call(cmd, shell=True)

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
    parser = argparse.ArgumentParser(description='scrapes emails look for orderid to download and submits jobs in gekko')
    parser.add_argument('-a', '--acct', dest='acct_cred_json', type=str,
                        help='json file with auig2 accounts, password and target email account', default='credentials.json')
    parser.add_argument('-lb', '--lookback', dest='max_lookback', type=int, default=50,
                        help='number of email messages to look back to search for AUIG-2 messages')
    parser.add_argument('-s','--script', dest='pbs_script', type=str, default='/home/share/insarscripts/download/auig2_download_unzip/auig2_download_unzip.pbs',
                        help='pbs script to execute' )    
    parser.add_argument('-cid','--completed_ids', dest='id_check_file', type=str, default="",
                        help='specify json with list of completed ids to check dedups')
    return parser.parse_args()



if __name__ == '__main__':
    inps = cmdLineParse()

    main(inps)

