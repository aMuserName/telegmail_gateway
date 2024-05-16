import os
from apindital import create, get, send
from dotenv import load_dotenv
load_dotenv("..\..\.env")

TEST_FILE_PATH = os.getenv('TEST_FILE_PATH') 
FILE_CONTENT = open(TEST_FILE_PATH, 'rb')

data_for_creation = {"subject": "Tema", "tp_from": None, "tp_to": None, "phone": None}

# Test for creating a ticket
ticket = create(**data_for_creation)
assert ticket['params']['subject'] == data_for_creation["subject"], 'failed create' 

# Test for retrieving ticket info 
ticket_info = get(reuest_id=ticket['id'])
assert ticket_info['id'] == ticket['id'], 'failed get'

# Test for sending file with a ticket
ticket_id = ticket['id']
state = send(request_id=ticket_id, file=FILE_CONTENT, file_name="name of file")
assert state == 200,'failed send'
