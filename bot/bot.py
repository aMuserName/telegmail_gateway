import os
import random
import smtplib
import string
# TODO: convert image to pdg
import img2pdf

import telebot
from telebot import types
from classes import User, Connection, Letter
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText
from email.utils import formatdate
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

MAIL_ADDRESS = os.getenv('MAIL_ADDRESS')
BOT_MAIL_ADDRESS = os.getenv('BOT_MAIL_ADDRESS')
BOT_MAIL_PASS = os.getenv('BOT_MAIL_PASS')
MAIL_SUBJECT = os.getenv('MAIL_SUBJECT')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))

CHAT_ID = int(os.getenv('CHAT_ID'))
NAME = int(os.getenv('NAME'))
SURNAME = int(os.getenv('SURNAME'))
EMAIL = int(os.getenv('EMAIL'))
DB_PATH = os.getenv('DB_PATH')

bot = telebot.TeleBot(BOT_TOKEN)
conn = Connection(DB_PATH)

# create user table in sqlite on a start
var = conn.create_table('users')

# upload all current user stored in DB
user_dict = {}
user_table_curs = conn.get_rows('users')
for user_row in user_table_curs.fetchall():
    obj = User(user_row[NAME], user_row[SURNAME], user_row[EMAIL], registered=True)
    user_dict[user_row[CHAT_ID]] = obj


def read_photo(photo_name):
    with open(photo_name, 'rb') as new_file:
        return new_file.read()


# START HERE
@bot.message_handler(commands=['help', 'start'])
def start(message):
    greetings, user = "", None
    row = conn.get_user_by_chat_id(message.chat.id)
    if not row:
        markup = create_markup(("Обратная связь",))
    else:
        greetings = ', ' + row[NAME] + ' ' + row[SURNAME]
        markup = create_markup(("Обратная связь", 'Сформировать заявку'))
    bot.reply_to(message, f"Привет{greetings}! Я ваш бот-помошник. Помогу быстро сформировать заявку.",
                 reply_markup=markup)


def get_document_by_file_id(message):
    if message.photo:
        file_id = message.photo[-1].file_id  # last or first???????
        file_name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)) # random key
    else:
        file_id = message.document.file_id
        file_name = message.document.file_name
    print('fileID = ', file_id, 'file_name = ', file_name)
    file = bot.get_file(file_id)
    return file_name, bot.download_file(file.file_path)


def create_markup(button_texts):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for text in button_texts:
        but = types.KeyboardButton(text)
        markup.add(but)
    return markup


# TODO: a few attachment
@bot.message_handler(
    content_types=['document', 'photo'])
def process_content_step(message):
    empty = False
    if message.text and message.text == 'Пропустить':
        empty = True
    elif message.text and message.text == 'Отменить':
        bot.register_next_step_handler(message, start)
        user_dict[message.chat.id].letter = None
        return
    elif not message.document and not message.photo:
        msg = bot.reply_to(message, "Пожалуйста, прикрепите pdf, jpeg, png-файл.")
        bot.register_next_step_handler(msg, process_content_step)
        return

    user = user_dict[message.chat.id]
    markup = create_markup(('Отменить', 'Пропустить'))
    if user.letter.attachs == {}:  # if there are no attachments (TODO: merge to conditions)
        if update_attachs(message, user, 'CMR', 'CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ)', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ИНВОЙС: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR'}:
        if update_attachs(message, user, 'Invoice', 'ИНВОЙС', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ): ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR', 'Invoice'}:
        if update_attachs(message, user, 'Specific', 'СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ)', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ПАКИНГ ЛИСТ: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific'}:
        if update_attachs(message, user, 'Parking_l', 'ПАКИНГ ЛИСТ', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ПАСПОРТ ВОДИТЕЛЯ: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l'}:
        if update_attachs(message, user, 'Driver_pasp', 'ПАСПОРТ ВОДИТЕЛЯ', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ТЕХПАСПОРТ НА ТЯГАЧ: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp'}:
        if update_attachs(message, user, 'Track', 'ТЕХПАСПОРТ НА ТЯГАЧ', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ТЕХПАСПОРТ НА ПОЛУПРИЦЕП: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp', 'Track'}:
        if update_attachs(message, user, 'Trailer', 'ТЕХПАСПОРТ НА ПОЛУПРИЦЕП', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ( СВИДЕТЕЛЬТВО ПОД ПЛОМБАМИ): ',
                           reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp', 'Track',
                                             'Trailer'}:
        if update_attachs(message, user, 'Cert', 'СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ( СВИДЕТЕЛЬТВО ПОД ПЛОМБАМИ)', empty):
            return
        msg = bot.reply_to(message, ('Прикрепите СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА\n'
                                     '( ЕСЛИ ТРАНЗИТ ПОД ТАМОЖЕННФМ ПЕРЕВОЗЧИКОМ): '), reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    elif set(user.letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp', 'Track',
                                             'Trailer', 'Cert'}:
        if update_attachs(message, user, 'Carrier', ('СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА \n',
                                                     '( ЕСЛИ ТРАНЗИТ ПОД ТАМОЖЕННФМ ПЕРЕВОЗЧИКОМ)'), empty):
            return
        markup = create_markup(('Да', 'Нет, выбрать другие'))
        bot.send_message(message.chat.id, 'Я получил такие документы:')

        # send all got files and its names
        # TODO: document_name
        filtered_files = dict([item for item in user.letter.attachs.items() if item[1] is not None])
        user.letter.attachs = filtered_files
        for key, file_tuple in user.letter.attachs.items():
            bot.send_document(message.chat.id, caption=file_tuple[0], document=file_tuple[1])

        bot.send_message(message.chat.id, 'Список документов верный?', reply_markup=markup)
    return


def update_attachs(message, user, key, error_str, empty, func=process_content_step):
    try:
        file_name, downloaded_file = get_document_by_file_id(message) if not empty else (None, None)
        item = {key: None} if empty else {key: [file_name, downloaded_file]}
        user.letter.attachs.update(item)
        return False
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     f'Прикрепите {error_str}: ')
                           )
        bot.register_next_step_handler(msg, func)
        return True


# Handle all sent text messages.
@bot.message_handler(content_types=['text'])
def get_text_message(message):
    if message.text == 'Обратная связь':
        if message.chat.id in user_dict.keys():
            msg = bot.reply_to(message, 'Напишите то, что хотели бы передать:')
            bot.register_next_step_handler(msg, process_body_step)
        else:
            msg = bot.reply_to(message, ("Вы еще не зарегистрированы.\n Можете написать нам письмо, "
                                         "и специалисты свяжуться с вами в ближайшее время!\n"
                                         # "Если Вы по другому вопросу, то можете написать мне, я отправлю его оператору.\n"
                                         "Напишите свой телефон для обратной связи::"))
            bot.register_next_step_handler(msg, process_telephone_step)
    elif message.text == 'Сформировать заявку':
        try:
            row = conn.get_user_by_chat_id(message.chat.id)
            msg = bot.reply_to(message, (f"Приступим к формированию заявкки!\n"
                                         f"{row[NAME]}, напишите пост отправления: ")
                               )
            bot.register_next_step_handler(msg, process_src_step)
        except TypeError:
            msg = bot.reply_to(message, ("Вы еще не зарегистрированы.\n Можете написать нам письмо, "
                                         "и специалисты свяжуться с вами в ближайшее время!\n"
                                         "Напишите свой телефон для обратной связи::")
                               )
            bot.register_next_step_handler(msg, process_telephone_step)
    elif (message.text == 'Да' or message.text == 'Всё верно' or
          message.text == 'Отправить без вложений' or message.text == 'Отправить'):  # if directly this pressed - test case
        bot.send_message(message.chat.id, "Формирую заявку.")  # Отправляю

        # SMTP send
        user = user_dict[message.chat.id]
        if user.registered:
            body = (f"Пост отправления: {user.letter.src}\n"
                    f"Пост назначения:: {user.letter.dest}")
        else:
            body = user.letter.body
        files = list(user.letter.attachs.values())
        mail_subj = f"Заявка от User{message.chat.id}"
        senderrors = send_mail(BOT_MAIL_ADDRESS, MAIL_ADDRESS, mail_subj, body, BOT_MAIL_PASS, files)
        if user.registered:
            markup = create_markup(('Сформировать заявку', 'Обратная связь'))
        else:
            markup = create_markup(('Обратная связь',))
        if not senderrors:
            bot.send_message(message.chat.id, 'Заявка успешно отправлена. Скоро вернусь с ответом.',
                             reply_markup=markup)
        else:
            print('SMTP send errors: ', senderrors)
            bot.send_message(message.chat.id, 'Что-то пошло не так. Давай начнем заново.',
                             reply_markup=markup)

    elif message.text == 'Нет':
        msg = bot.reply_to(message, "Давайте начнем сначала.\nYНапишите пост отправления: ")
        bot.register_next_step_handler(msg, process_content_step)
    elif message.text == 'Прикрепить':
        msg = bot.reply_to(message, "Прикрепите вложение:")
        bot.register_next_step_handler(msg, process_attach_step)
    elif message.text == 'Нет, выбрать другие':
        msg = bot.reply_to(message, ('Прикрепи необходимые документы '
                                     '1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ)')
                           )
        bot.register_next_step_handler(msg, process_content_step)
    else:
        bot.reply_to(message, " Я вас не понимаю. Попробуйте /start")


def process_src_step(message):
    try:
        chat_id = message.chat.id
        src = message.text
        user = user_dict[chat_id]
        user.letter = Letter(src)
        msg = bot.reply_to(message, 'Напишите пост назначения: ')
        bot.register_next_step_handler(msg, process_dest_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Напишите пост отправления: ')
                           )
        bot.register_next_step_handler(msg, process_src_step)


def process_dest_step(message):
    try:
        chat_id = message.chat.id
        dest = message.text
        user = user_dict[chat_id]
        user.letter.dest = dest
        markup = create_markup(('Отменить', 'Пропустить'))
        msg = bot.reply_to(message, ('Прикрепи необходимые документы '
                                     '1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ)'),
                           reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Напишите пост назначения: ')
                           )
        bot.register_next_step_handler(msg, process_dest_step)


def process_confirm_step(message):
    try:
        chat_id = message.chat.id
        downloaded_file = read_photo(f"image_{chat_id}.jpg")
        bot.send_photo(chat_id, downloaded_file)
        # да - нет markup
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_yes = types.KeyboardButton("Да")
        markup.add(btn_yes)
        btn_no = types.KeyboardButton('Нет')
        markup.add(btn_no)
        bot.send_message(message.chat.id, 'Это то самое фото?": ', reply_markup=markup)
    except Exception as e:
        msg = bot.reply_to(message, 'Что-то пошло не так. Давай начнем заново.')
        bot.register_next_step_handler(msg, process_confirm_step)


def process_telephone_step(message):
    try:
        chat_id = message.chat.id
        telephone = message.text
        if not str(telephone).isdigit():
            msg = bot.reply_to(message, ('Некорректный телефон. Попробуйте еще раз. \n'
                                         'Напишите еще раз свой номер телефона (только цифры, без +):')
                               )
            bot.register_next_step_handler(msg, process_telephone_step)
            return
        user = User(None, phone=telephone, registered=False)
        user_dict.update({chat_id: user})
        msg = bot.reply_to(message, 'Напишите то, что хотели бы передать:')
        bot.register_next_step_handler(msg, process_body_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     "Напишите еще раз:")
                           )
        bot.register_next_step_handler(msg, process_telephone_step)


def process_body_step(message):
    try:
        chat_id = message.chat.id
        body = message.text
        letter = Letter(src=None)
        letter.body = body
        user_dict[chat_id].letter = letter
        markup = create_markup(('Отправить без вложений', 'Прикрепить'))
        bot.send_message(chat_id, 'Прикрепить вложениe?', reply_markup=markup)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     "Напишите еще раз:")
                           )
        bot.register_next_step_handler(msg, process_body_step)


@bot.message_handler(content_types=['document', 'photo'])
def process_attach_step(message):
    try:
        chat_id = message.chat.id
        user = user_dict[chat_id]
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        if update_attachs(message, user, key, 'вложение', False, process_attach_step):
            return
        markup = create_markup(('Отправить', 'Прикрепить'))
        bot.send_message(chat_id, 'Прикрепить еще вложениe?', reply_markup=markup)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     'Прикрепите вложение:')
                           )
        bot.register_next_step_handler(msg, process_attach_step)


def process_phone_step(message):
    try:
        chat_id = message.chat.id
        phone = message.text
        user = user_dict[chat_id]
        # if not re.match(r'^([\s\d]+)$', phone):
        if not str(phone).isdigit():
            msg = bot.reply_to(message, ('Некорректный телефон. Попробуйте еще раз. \n'
                                         '3. Напишите свой номер телефона (только цифры, без +):')
                               )
            bot.register_next_step_handler(msg, process_phone_step)
            return
        user.phone = phone
        msg = bot.reply_to(message, ('Рады знакомству ' + user.name + ' ' + user.surname + '.\n'
                                                                                           'Ваш телефон: ' + user.phone + '.\n')
                           )
    except Exception as e:  # TODO: to detail exceptions
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     '3. Напишите свой номер телефона:')
                           )
        bot.register_next_step_handler(msg, process_phone_step)
        return

    # insert into database
    conn.set_row(msg.chat.id, user.name, user.surname, int(user.phone), 'users')

    markup = create_markup(('Сформировать заявку',))
    bot.send_message(message.chat.id, "Теперь можно приступить к формированию заявки.", reply_markup=markup)


def send_mail(send_from, send_to, subject, text, password, files=None,
              server=SMTP_SERVER, port=SMTP_PORT):
    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = send_to
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(text))

    # TODO: either photo or document
    for file_tuple in files:
        attach = MIMEApplication(file_tuple[1])
        attach.add_header('content-disposition', 'attachment', filename=file_tuple[0])
        msg.attach(attach)

    with smtplib.SMTP(server, port) as server:
        server.ehlo()
        server.starttls()  # Upgrade the connection to secure
        server.login(send_from, password)
        senderros = server.send_message(msg)
        print("Email sent successfully!")
    return senderros


bot.enable_save_next_step_handlers(delay=2)


# Load next_step_handlers from save file (default "./.handlers-saves/step.save")
# WARNING It will work only if enable_save_next_step_handlers was called!
bot.load_next_step_handlers()

bot.infinity_polling()


# Handle all sent photos of type 'image/jpeg' and 'image/png'.
# @bot.message_handler(func=lambda message: message.document.mime_type in ('image/png', 'image/jpeg'),
#    content_types=['photo'])
# @bot.message_handler(func=lambda message: True, content_types=['photo'])
# DEPRECATED


def process_photo_step(message):
    try:
        chat_id = message.chat.id
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_yes = types.KeyboardButton('Всё верно')
        markup.add(btn_yes)
        btn_no = types.KeyboardButton('Нет, не то')
        markup.add(btn_no)

        # get photo from user
        photo = message.photo
        fileID = message.photo[-1].file_id
        print('fileID = ', fileID)
        file = bot.get_file(fileID)
        print('Path = ', file)
        downloaded_file = bot.download_file(file.file_path)
        with open(f"image_{chat_id}.jpg", 'wb') as new_file:
            new_file.write(downloaded_file)

        user = user_dict[chat_id]
        user.letter.photo = downloaded_file
        msg = bot.reply_to(message, 'У меня такое фото: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_confirm_step)
    except Exception as e:
        msg = bot.reply_to(message, 'Что-то пошло не так. Давай начнем заново. \nПрикреепи Фото')
        bot.register_next_step_handler(msg, process_photo_step)
