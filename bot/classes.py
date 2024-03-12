import sqlite3
import random
import string
import magic

class Connection:
    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)

    def create_table(self, table):
        query = (f"CREATE TABLE IF NOT EXISTS {table} (chat_id INTEGER NOT NULL, "
                 f"name TEXT, surname TEXT, phone INTEGER, UNIQUE(chat_id));")
        return self.curs(query)

    # invariant to attributes ? worthy
    def set_row(self, chat_id, name, surname, phone, table):
        query = (f"INSERT INTO {table}(chat_id, name, surname, phone) VALUES"
                 f"({chat_id}, '{name}', '{surname}', {phone});")
        return self.curs(query)

    def get_rows(self, table):
        query = (f"SELECT * FROM users;")
        return self.conn.cursor().execute(query)

    def get_row_id_by_email(self, email):
        query = f"SELECT * FROM users WHERE email='{email}';"
        return self.curs(query)

    def get_user_by_chat_id(self, chat_id):
        query = f"SELECT * FROM users WHERE chat_id={chat_id};"
        return self.curs(query)

    def curs(self, query):
        cursor = self.conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        self.conn.commit()
        return row


class User:
    def __init__(self, phone=None, registered=False):
        self.phone = phone
        self.letters = []
        self.registered = registered
        self.chat_ids = set()
        self.sent = []
        self.number = None
        self.key = None


class Letter:
    def __init__(self, body=None, sort=None):
        self.body = body
        self.sort = sort
        self.attachs = {}
        self.sent = False
        self.edit = False

    def update_attachs(self, message, bot, empty, key=None):
        if key is None:
             key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        file_name, downloaded_file, file_type = self.get_document_by_file_id(message, bot, key) if not empty else (None, None)
        item = [file_name, downloaded_file, file_type]
        try:
            self.attachs[key].append(item)
        except KeyError:
            self.attachs.update({key: [item]})
        #item = {key: None} if empty else {key: [file_name, downloaded_file]}
        #self.attachs.update(item)

    def get_document_by_file_id(self, message, bot, key):
        if message.photo:
            file_id = message.photo[-1].file_id  # last or first???????
            file_name = key #''.join(random.choices(string.ascii_uppercase + string.digits, k=10))  # random key
            print('fileID = ', file_id, 'file_name = ', file_name)
            file = bot.get_file(file_id)
            return file_name, bot.download_file(file.file_path), 'photo'
        else:
            file_id = message.document.file_id
            file_name = key#message.document.file_name
            print('fileID = ', file_id, 'file_name = ', file_name)
            return file_name, file_id, 'doc'

        #bot.download_file(file.file_path)      
