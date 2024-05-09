import sqlite3


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
    def __init__(self, name, surname=None, phone=None, registered=False):
        self.name = name
        self.surname = surname
        self.phone = phone
        self.letter = None
        self.registered = registered


class Letter:
    def __init__(self, src):
        self.body = None
        self.src = src
        self.dest = None
        self.attachs = {}
