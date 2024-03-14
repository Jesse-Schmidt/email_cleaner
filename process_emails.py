import os.path
import base64
import json
import re
import time
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging
import requests
import sys
import datetime
from render_html import render_in_browser as ren

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly','https://www.googleapis.com/auth/gmail.modify', "https://mail.google.com/"]

def get_gmail_service():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(               
                # your creds file here. Please create json file as here https://cloud.google.com/docs/authentication/getting-started
                'my_cred_file.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def process_email(service, message, delete_list, leave_list, read_list=[]):
    updated = False
    prompt_string = "\nWould you like to \n1)Mark the email as read\n2)Mark all emails from this sender as read\n3)Skip the email\n4)Mark the sender as always being skipped\n5)Delete the Email\n6)Mark the sender as always being deleted\n7)View the body of the message before making a choice\n"
    try:
        msg = service.users().messages().get(userId='me', id=message['id']).execute()  
    except:
        return delete_list, leave_list, read_list, updated 
    print('_________________________')
    email_data = msg['payload']['headers']
    for values in email_data:
        name = values['name']
        if name == 'From':
            from_name= values['value']
            print("\n_________________________\nEmail is from:", from_name)  
            for elem in email_data:
                if elem['name'] == 'Subject':
                    print("Email Subject:", elem['value']) 
            if from_name in delete_list:
                print('Automatically deleting message') 
                msg = service.users().messages().trash(userId='me', id=message['id']).execute() 
            elif from_name in leave_list:
                print('Automatically skipping message')
            elif from_name in read_list:
                print('Automatically marking message as read')
                msg  = service.users().messages().modify(userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}).execute()
            else:
                # print(msg['payload'])
                finished_processing = False
                while not finished_processing:
                    user_choice = input(prompt_string)
                    if user_choice == '1':
                        print('Marking message as read')
                        msg  = service.users().messages().modify(userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}).execute()
                        finished_processing = True
                    elif user_choice == '2':
                        print('Marking all messages from this sender as read')
                        sender_list = []
                        if ' ' in from_name:
                            for i in get_all_emails_from_address(service, from_name.split(' ')[0]) + get_all_emails_from_address(service, from_name.split(' ')[1]):
                                if i not in sender_list:
                                    sender_list.append(i)
                        else:
                            sender_list = get_all_emails_from_address(service, from_name)
                        id_list = []
                        for temp in sender_list:
                            id_list.append(temp['id'])
                            if len(id_list) > 50:
                                msg = service.users().messages().batchModify(userId='me', body={'ids':id_list, 'removeLabelIds': ['UNREAD']}).execute() 
                                id_list = []
                        if len(id_list) > 0:
                            msg = service.users().messages().batchModify(userId='me', body={'ids':id_list, 'removeLabelIds': ['UNREAD']}).execute()
                        finished_processing = True
                        read_list.append(from_name)
                    elif user_choice == '3':
                        print("Skipping message")
                        finished_processing = True
                    elif user_choice == '4':
                        print('Marking sender as always being skipped')
                        leave_list.append(from_name)
                        finished_processing = True
                        updated = True
                    elif user_choice == '5':
                        print('Deleting message')
                        msg = service.users().messages().trash(userId='me', id=message['id']).execute() 
                        finished_processing = True
                    elif user_choice == '6':
                        print('Deleting message and marking the sender for automatic deletion')
                        sender_list = []
                        if ' ' in from_name:
                            for i in get_all_emails_from_address(service, from_name.split(' ')[0]) + get_all_emails_from_address(service, from_name.split(' ')[1]):
                                if i not in sender_list:
                                    sender_list.append(i)
                        else:
                            sender_list = get_all_emails_from_address(service, from_name)
                        id_list = []
                        for temp in sender_list:
                            id_list.append(temp['id'])
                            if len(id_list) > 50:
                                msg = service.users().messages().batchDelete(userId='me', body={'ids':id_list}).execute() 
                                id_list = []
                        if len(id_list) > 0:
                            msg = service.users().messages().batchDelete(userId='me', body={'ids':id_list}).execute()
                        delete_list.append(from_name)
                        finished_processing = True
                        updated = True
                    elif user_choice == '7':
                        if 'parts' in msg['payload']:    
                            for part in msg['payload']['parts']:
                                try:
                                    data = part['body']["data"]
                                    byte_code = base64.urlsafe_b64decode(data)

                                    text = byte_code.decode("utf-8")
                                    ren(text, browser='opera')
                                except BaseException as error:
                                    pass  
                        elif 'body' in msg['payload']:
                            try:
                                data = msg['payload']['body']["data"]
                                byte_code = base64.urlsafe_b64decode(data)

                                text = byte_code.decode("utf-8")
                                ren(text, browser='opera')
                            except BaseException as error:
                                pass  
                        else:
                            print('no email body found')
                    else:
                        print('Invalid user input, please just put the number and press enter')
    return delete_list, leave_list, read_list, updated

def get_all_emails_from_address(service, email_address):
    try:
        # Call the Gmail API
        current_page = 0
        messages = []
        get_next_page = True
        while get_next_page:
            print('getting inbox page')
            print('Current message count:', len(messages))
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], q="from:"+email_address, maxResults=500, pageToken=current_page).execute()
            messages += results.get('messages',[])
            if 'nextPageToken' in results:
                current_page = results['nextPageToken']
            else:
                get_next_page = False
        if not messages:
            print('No new messages.')
            return []
        else:
            print('Total message count:', len(messages))
            return messages
    except Exception as error:
        print(f'An error occurred: {error}')
    return []

def get_emails(service, inbox_query='is:unread'):
    try:
        # Call the Gmail API
        current_page = 0
        messages = []
        get_next_page = True
        while get_next_page:
            print('getting inbox page')
            print('Current message count:', len(messages))
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], q=inbox_query, maxResults=500, pageToken=current_page).execute()
            messages += results.get('messages',[])
            if 'nextPageToken' in results:
                current_page = results['nextPageToken']
            else:
                get_next_page = False
        if not messages:
            print('No new messages.')
            return []
        else:
            print('Total message count:', len(messages))
            return messages
    except Exception as error:
        print(f'An error occurred: {error}')
    return []

def get_auto_list(delete=True):
    delete_list = []
    file_path = ''
    if delete:
        file_path = './automatic_delete_list.txt'
    else:
        file_path = './automatic_leave_list.txt'
    with open(file_path, 'r') as file:
        for line in file.readlines():
            temp = line.strip()
            if temp not in delete_list:
                delete_list.append(temp)
    return delete_list

def write_auto_list(delete_list, delete=True):
    file_path = ''
    if delete:
        file_path = './automatic_delete_list.txt'
    else:
        file_path = './automatic_leave_list.txt'
    file = open(file_path, 'w')
    for line in delete_list:
        file.write(line + '\n')
    file.close()

def process_inbox(inbox_query='is:unread'):
    delete_list = get_auto_list()
    leave_list = get_auto_list(delete=False)
    read_list = []
    service = get_gmail_service()
    unread_inbox = get_emails(service, inbox_query)
    if len(unread_inbox) > 0:
        for message in unread_inbox:
            delete_list, leave_list, read_list, updated = process_email(service, message, delete_list, leave_list, read_list)
            if updated:
                write_auto_list(delete_list)
                write_auto_list(leave_list, delete=False)

if __name__ == '__main__':
    prompt = "Would you like to process new emails or the entire mailbox?\n1)Unread Emails\n2)Entire Mailbox\n"
    finished_choosing = False
    while not finished_choosing:
        first_choice = input(prompt)
        if first_choice == '1':
            print('Processing unread emails')
            process_inbox()  
            finished_choosing = True
        elif first_choice == '2':
            print('Processing your entire mailbox')
            process_inbox('')
            finished_choosing = True
        else:
            print('Invalid entry')