import os
import re
import smtplib
# TODO: convert image to pdg
import img2pdf
import asyncio
import threading
import time
import logging

import telebot
from telebot import types
from classes import User, Connection, Letter
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.utils import formatdate
from dotenv import load_dotenv
from functools import wraps
load_dotenv()

logging.basicConfig(format='%(asctime)s %(message)s',datefmt='%d-%m-%Y %H:%M:%S',level=logging.INFO)

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

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
conn = Connection(DB_PATH)

# create user table in sqlite on a start
var = conn.create_table('users')

# upload all current user stored in DB
user_dict = {}
user_timers = {}
# user_table_curs = conn.get_rows('users')
# for user_row in user_table_curs.fetchall():
#     obj = User(user_row[NAME], user_row[SURNAME], user_row[EMAIL], registered=True)
#     user_dict[user_row[CHAT_ID]] = obj

names =  {'CMR': '1. CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ)',
        'Invoice': '2. ИНВОЙС',
        'Specific': '3. СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ)',
        'Packing': '4. ПАКИНГ ЛИСТ',
        'Driver': '5. ПАСПОРТ ВОДИТЕЛЯ',
        'Track': '6. ТЕХПАСПОРТ НА ТЯГАЧ',
        'Trailer': '7. ТЕХПАСПОРТ НА ПОЛУПРИЦЕП',
        'Permission': '8. СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ', 
        'Carrier': '9. СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА',
        'Attach': 'Вложение'
        }

async def setTimeout(time, func):
    await asyncio.sleep(time)

def read_photo(photo_name):
    with open(photo_name, 'rb') as new_file:
        return new_file.read()

def decorator(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        global user_timers
        try:
            user_key, user = get_user_by_chat_id(user_dict, args[0].chat.id)
        except TypeError:
            logging.warning(f'User with chat id {args[0].chat.id} not found in users dictionary. Function call: {func.__name__}')
            #user = User(registered=False)
            #user.phone = None
            #user.chat_ids = args[0].chat.id
            #user_dict[args[0].chat.id] = user
            user = None 
        return func(*args, user, **kwargs)
    return wrap

# START HERE
@bot.message_handler(commands=['help', 'start'])
@decorator
def start(message, user):
    markup = create_markup(('Сформировать заявку', 'Обратная связь'))
    try:
        if user.registered:
            markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Заявки'))
    except AttributeError:
        markup = create_markup(('Сформировать заявку', 'Обратная связь'))
    bot.reply_to(message, f"Привет! Я ваш бот-помошник. Помогу быстро сформировать заявку.",
                 reply_markup=markup)


def get_string(stroka, beg_str):
    beg = stroka.index(beg_str)
    end = stroka.find('\n', beg)
    #print(beg)
    #print(end)
    #print(stroka[beg+6:end].strip())
    return stroka[beg+6:end].strip()


# Handle all sent text messages.
@bot.message_handler(content_types=['text'])
@decorator
def get_text_message(message, user):
    if message.text == 'Обратная связь':
        markup = create_markup(('Завершить работу', ))
        try:
            if not user.registered:
                msg = bot.reply_to(message, 
                                ("Напишите свой телефон для обратной связи:"), reply_markup=markup)
                bot.register_next_step_handler(msg, process_telephone_step, prev_message=message)
            elif user.registered:
                msg = bot.reply_to(message, 
                                ("Напишите то, что хотели бы передать:"), reply_markup=markup)
                bot.register_next_step_handler(msg, process_body_step)
        except AttributeError:
            msg = bot.reply_to(message, 
                                ("Напишите свой телефон для обратной связи:"), reply_markup=markup)
            bot.register_next_step_handler(msg, process_telephone_step, prev_message=message)
    elif message.text == 'Завершить работу':
        markup = create_markup(('Сформировать заявку', 'Обратная связь'))
        try:
            if user.registered:
                markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Заявки'))
        except AttributeError:
            markup = create_markup(('Сформировать заявку', 'Обратная связь'))
        bot.send_message(message.chat.id, ('До скорого.\n'))
        msg = bot.send_message(message.chat.id,
                                "Привет! Я ваш бот-помошник. Помогу быстро сформировать заявку.",
                                  reply_markup=markup)
    elif message.text == 'Сформировать заявку':
        markup = create_markup(('Завершить работу', ))
        try:
            if not user.registered:
                msg = bot.reply_to(message, (f"Прежде чем начать, напишите свой номер телефона.\n"),
                                reply_markup=markup)
                bot.register_next_step_handler(msg, process_telephone_step, prev_message=message)
            elif user.registered:
                msg = bot.reply_to(message, ("Приступим к формированию заявки!\n"
                                            # "Если Вы по другому вопросу, то можете написать мне, я отправлю его оператору.\n"
                                            "Напишите пост отправления:"), reply_markup=markup)
                user.number = None
                bot.register_next_step_handler(msg, process_src_step)
        except AttributeError:
            msg = bot.reply_to(message, (f"Прежде чем начать, напишите свой номер телефона.\n"),
                            reply_markup=markup)
            bot.register_next_step_handler(msg, process_telephone_step, prev_message=message)
    elif message.text == 'Изменить заявку аываыва':
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        try:
            number = -1
            user.letters[number].body = None
            user.letters[number].attachs = {}
        except AttributeError:
            number = None
            markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
            bot.send_message(message.chat.id, "Не удалось найти последнюю заявку.", reply_markup=markup)
            return
        msg = bot.reply_to(message, ("Приступим к формированию заявки!\n"
                                        # "Если Вы по другому вопросу, то можете написать мне, я отправлю его оператору.\n"
                                        "Напишите пост отправления:"))
        user.number = number
        bot.register_next_step_handler(msg, process_src_step)
    elif message.text == 'Изменить заявку':
        list_letters = [f'Заявка #{index}' for index, val in enumerate(user.sent) if val.sort == 'Заявка']
        markup = create_markup((*tuple(list_letters), 'Назад'))
        if list_letters != []:
            bot.send_message(message.chat.id, 'Выберете заявку:', reply_markup=markup)
        else:
            bot.send_message(message.chat.id, 'У вас пока нет отпрваленных заявок', reply_markup=markup)
    elif re.match('Заявка #\d+', message.text):
        matching = re.search(r'\d+', message.text)
        number = int(matching.group())
        user.number = number
        letter = user.sent[number]
        letter.edit = True
        letter.sent = False
        user.letters[number] = letter # copy sent ticket 
        bot.send_message(message.chat.id, 'Приступим к изменению.')
        markup = create_markup(('Дальше', 'Изменить'))
        src = get_string(letter.body, 'ления:')
        msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Пост отправления: {src}', reply_markup=markup)
        bot.register_next_step_handler(msg, process_src_step)
    elif message.text == 'Заявки':
        try:
            if user.registered:
                markup = create_markup(('Изменить заявку', 'Все заявки','Назад'))
            else:
                markup = create_markup(('Назад', ))
        except AttributeError:
            markup = create_markup(('Назад', ))
        bot.send_message(message.chat.id, ('Кнопка "Все заявки" - покажет все завяки\n'
                                           'Кнопка "Изменить заявку" - позволит изменить заявку'), reply_markup=markup)
    elif message.text == 'Назад':
        markup = create_markup(('Сформировать заявку', 'Обратная связь'))
        try:
            if user.registered:
                markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Заявки'))
        except AttributeError:
            markup = create_markup(('Сформировать заявку', 'Обратная связь'))
        msg = bot.send_message(message.chat.id, "Привет! Я ваш бот-помошник. Помогу быстро сформировать заявку.", reply_markup=markup)
    elif message.text == 'Все заявки':
        markup = create_markup(('Изменить заявку', 'Все заявки','Завершить работу'))
        if user.sent != []:
            bot.send_message(message.chat.id, 'Ваши отправленные заявки:')
            for index, letter in enumerate([letter for letter in user.sent if letter.sort == 'Заявка']):
                body = (f"{letter.sort} под №{index}\n"
                        f"{letter.body}\n")
                if letter.attachs != {}:
                    bot.send_message(message.chat.id, body + '\n Вложения:')
                    send_all_dcouments(letter, message.chat.id, names)
                else:
                    bot.send_message(message.chat.id, body + '\n Без вложений.')
            bot.send_message(message.chat.id, 'Это были все ваши отправленные заявки.', reply_markup=markup)
        else:
            bot.send_message(message.chat.id, 'Нет отправленных заявок', reply_markup=markup)
    elif message.text == 'Отправить заявку':  # if directly this pressed - test case
        # # сообщение: Ваше соообщение отправлено, наши специалисты скоро свяжутся с Вами.
        # user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        # #markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Отправленные заявки', 'Завершить работу'))
        # markup = create_markup(('Сформировать заявку',  'Заявки', 'Завершить работу'))
        # # SMTP send
        # list_senderrors = []
        # sent_number = len(user.sent)
        # for indx, letter in enumerate(user.letters): # поменить номер заявки в пуле
        #     bot.send_message(message.chat.id, "Формирую заявку.")  # Отправляю
        #     body = (f"Телефон: {user_key}\n"
        #             f"{letter.body}\n")
        #     # TODO: pythonic nested loop
        #     files = []
        #     for attach in letter.attachs.values():
        #         for index, page in enumerate(attach):
        #             page[0] = page[0] + f'_str_{index+1}'
        #             files.append(page)

        #     #files = list(page for page in attach for attach in letter.attachs.values())
        #     if letter.edit:
        #         mail_subj = f"Дополнение по {letter.sort} №{user.number} от User{message.chat.id}"
        #     else:
        #         mail_subj = f"{letter.sort} №{indx} от User{message.chat.id}"
        #     senderrors = send_mail(BOT_MAIL_ADDRESS, MAIL_ADDRESS, mail_subj, body, BOT_MAIL_PASS, files=files)
        #     list_senderrors.append(senderrors) if senderrors is not {} else list_senderrors  
        #     if not senderrors:
        #         bot.send_message(message.chat.id, f'Заявка №{indx} успешно отправлена.')
        #         letter.sent = True
        #         user.sent.insert(index, letter)                
        #     else:
        #         bot.send_message(message.chat.id, 'Не удалось отправить заявку.')
        # user.letters = [letter for letter in user.letters if not letter.sent]
        # if list_senderrors: # list of dict
        #     bot.send_message(message.chat.id, 'Заявка(и) успешно отправлена(и). Скоро вернусь с ответом.',
        #                      reply_markup=markup)
        #     bot.send_message(message.chat.id, ('Что будем делать дальше?\n'
        #                                        '(Выберите опцию ниже)'),
        #                      reply_markup=markup)
        # else:
        #     print('SMTP send errors: ', list_senderrors)
        #     bot.send_message(message.chat.id, ('Что-то пошло не так. Давайте начнем заново.\n'
        #                                        'Выберите опцию...'),
        #                      reply_markup=markup)
        pass
    elif message.text == 'Нет':
        msg = bot.reply_to(message, "Давайте начнем сначала.\nYНапишите пост отправления: ")
        bot.register_next_step_handler(msg, process_content_step)
    elif re.match('Изменить заявку#\d+', message.text):
        matching = re.search(r'\d+', message.text)
        try:
            number = int(matching.group()) - len(user.sent)
            user.letters[number].attachs = {}
        except AttributeError:
            number = None
            bot.send_message(message.chat.id, "Не удалось найти заявку с таким номером. Попробуйте еще раз.")
        msg = bot.reply_to(message, ("Приступим к формированию заявки!\n"
                                        # "Если Вы по другому вопросу, то можете написать мне, я отправлю его оператору.\n"
                                        "Напишите пост отправления:"))
        user.number = number
        bot.register_next_step_handler(msg, process_src_step)
    elif re.match('Заявка фвывфыв #\d+', message.text):
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        matching = re.search(r'\d+', message.text)
        number = int(matching.group()) - len(user.sent)
        letter = user.letters[int(number)]
        markup = create_markup((f"Изменить заявку#{int(number) + len(user.sent)}", "Назад"))
        bot.send_message(message.chat.id, message.text, reply_markup=markup)
        body = (f"{letter.body}\n")
        bot.send_message(message.chat.id, body + '\n Вложения:')
        send_all_dcouments(letter, message.chat.id, names)
    elif message.text == 'Заявки фвыфв':
        # TODO: to be DRY
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        letters = user.letters
        #list_letters = [f'Заявка #{index}' for index, val in enumerate(letters)]
        #markup = create_markup(('Отправить заявку', 'Сформировать заявку', 'Текущие заявки', 'Отправленные заявки'))
        markup = create_markup(('Текущие заявки', 'Отправленные заявки', 'Назад', 'Завершить работу'))
        bot.send_message(message.chat.id, ('Вы можете посмотреть все Ваши заявки.\n'
                                           'Кнопка "Текущие заявки" - отобразит все созданные заявки.\n'
                                           'Кнопка "Отправленные заявки" - отобразит все отправленные заявки.\n'),
                         reply_markup=markup)
        # TODO: to be DRY
    elif message.text == 'Назад вфыф':
        # TODO: to be DRY
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        letters = user.letters
        #list_letters = [f'Заявка #{index}' for index, val in enumerate(letters)]
        #markup = create_markup(('Отправить заявку', 'Сформировать заявку', 'Текущие заявки', 'Отправленные заявки'))
        markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Заявки', 'Завершить работу'))
        bot.send_message(message.chat.id, (#'Вы можете сформировать еще одну заявку.\n'
                                           'Кнопка "Оправить заявку" - отправит все созданные заявки.'),
                         reply_markup=markup)
        # TODO: to be DRY
    elif message.text == 'Заявки фвывфыв':
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        list_letters = [f'Заявка #{index + len(user.sent)}' for index, val in enumerate(user.letters)]
        markup = create_markup((*tuple(list_letters), 'Назад'))
        if user.letters != []:
            bot.send_message(message.chat.id, 'Ваши текущие заявки:')
            for index, letter in enumerate(user.letters):
                body = (f"Заявка под №{index + len(user.sent)}\n"
                        f"{letter.body}\n")
                bot.send_message(message.chat.id, body + '\n Вложения:')
                send_all_dcouments(letter, message.chat.id, names)
            bot.send_message(message.chat.id, 'Это были все ваши текущие заявки.', reply_markup=markup)
        else:
            bot.send_message(message.chat.id, 'У вас пока нет сформированных заявок', reply_markup=markup)
    else:
        bot.reply_to(message, " Я вас не понимаю. Попробуйте /start")


def create_markup(button_texts, presists=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, is_persistent=presists)
    for text in button_texts:
        but = types.KeyboardButton(text)
        markup.add(but)
    return markup


def create_inline_keyboard(text_callback_dict):
    keyboard = types.InlineKeyboardMarkup()
    for key, value in text_callback_dict.items():
        but = types.InlineKeyboardButton(text=key, callback_data=value)
        keyboard.add(but)
    return keyboard

# TODO: a few attachment
#@bot.message_handler(
    #content_types=['document', 'photo'])
def process_content_step(message, number=-1):
    empty = False
    if message.text and message.text == 'Пропустить':
        empty = True
    elif message.text and message.text == 'Отменить':
        bot.register_next_step_handler(message, start)
        del user_dict[message.chat.id].letter[number]
        return
    elif message.text and message.text == 'Да':
        # TODO: to be DRY
        bot.send_message(message.chat.id, 'Заявка сформирована.')
        user = user_dict[message.chat.id]
        letters = user.letters
        list_letters = [f'Заявка #{index + len(user.sent)}' for index, val in enumerate(letters)]
        markup = create_markup(('Отправить заявку', 'Сформировать заявку', 'Текущие заявки', 'Отправленные заявки', *tuple(list_letters)))
        bot.send_message(message.chat.id, (#'Вы можете сформировать еще одну заявку.\n '
                                           'Кнопка "Оправить заявку" - отправит все созданные заявки.'),
                         reply_markup=markup)
        return
        # TODO: to be DRY
    elif message.text == 'Нет, выбрать другие':
        msg = bot.reply_to(message, ('Прикрепи необходимые документы '
                                     '1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ)')
                           )
        bot.register_next_step_handler(msg, process_content_step)
    elif not message.document and not message.photo:
        msg = bot.reply_to(message, "Пожалуйста, прикрепите pdf, jpeg, png-файл.")
        bot.register_next_step_handler(msg, process_content_step, number)
        return

    user = user_dict[message.chat.id]
    letter = user.letters[number]
    markup = create_markup(('Отменить', 'Пропустить'))
    if letter.attachs == {}:  # if there are no attachments (TODO: merge to conditions)
        if update_attachs(message, user, 'CMR', 'CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ)', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ИНВОЙС: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR'}:
        if update_attachs(message, user, 'Invoice', 'ИНВОЙС', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ): ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR', 'Invoice'}:
        if update_attachs(message, user, 'Specific', 'СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ)', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ПАКИНГ ЛИСТ: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific'}:
        if update_attachs(message, user, 'Parking_l', 'ПАКИНГ ЛИСТ', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ПАСПОРТ ВОДИТЕЛЯ: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l'}:
        if update_attachs(message, user, 'Driver_pasp', 'ПАСПОРТ ВОДИТЕЛЯ', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ТЕХПАСПОРТ НА ТЯГАЧ: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp'}:
        if update_attachs(message, user, 'Track', 'ТЕХПАСПОРТ НА ТЯГАЧ', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите ТЕХПАСПОРТ НА ПОЛУПРИЦЕП: ', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp', 'Track'}:
        if update_attachs(message, user, 'Trailer', 'ТЕХПАСПОРТ НА ПОЛУПРИЦЕП', empty):
            return
        msg = bot.reply_to(message, f'Прикрепите СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ( СВИДЕТЕЛЬТВО ПОД ПЛОМБАМИ): ',
                           reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp', 'Track',
                                                  'Trailer'}:
        if update_attachs(message, user, 'Cert', 'СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ( СВИДЕТЕЛЬТВО ПОД ПЛОМБАМИ)', empty):
            return
        msg = bot.reply_to(message, ('Прикрепите СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА\n'
                                     '( ЕСЛИ ТРАНЗИТ ПОД ТАМОЖЕННФМ ПЕРЕВОЗЧИКОМ): '), reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    elif set(letter.attachs.keys()) == {'CMR', 'Invoice', 'Specific', 'Parking_l', 'Driver_pasp', 'Track',
                                                  'Trailer', 'Cert'}:
        if update_attachs(message, user, 'Carrier', ('СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА \n',
                                                     '( ЕСЛИ ТРАНЗИТ ПОД ТАМОЖЕННФМ ПЕРЕВОЗЧИКОМ)'), empty):
            return
        markup = create_markup(('Да', 'Нет, выбрать другие'))
        bot.send_message(message.chat.id, 'Я получил такие документы:')

        # send all got files and its names
        # TODO: document_name
        filtered_files = dict([item for item in letter.attachs.items() if item[1] is not None])
        letter.attachs = filtered_files
        for key, file_tuple in letter.attachs.items():
            bot.send_document(message.chat.id, caption=file_tuple[0], document=file_tuple[1])

        msg = bot.send_message(message.chat.id, 'Список документов верный?', reply_markup=markup)
        bot.register_next_step_handler(msg, process_content_step, number)
    return      


@decorator
def process_src_step(message, user):
    try:
        src = message.text
        if src == 'Завершить работу':
            markup = create_markup(('Да', 'Нет'))
            msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить формирование заявки?\n Все данные удалятся.', reply_markup=markup)
            bot.register_next_step_handler(msg, process_deletion_step, process_src_step, 'Src')
            return
        elif src == 'Дальше':
            markup = create_markup(('Дальше', 'Изменить'))
            dest = get_string(user.letters[user.number].body, 'чения:')
            msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Пост назначения: {dest}', reply_markup=markup)
            bot.register_next_step_handler(msg, process_dest_step) 
            return # go to dest step
        elif src == 'Изменить':
            msg = bot.reply_to(message, ("Напишите пост отправления:"), reply_markup=markup)
            bot.register_next_step_handler(msg, process_src_step)
            return
        src =  f"Пост отправления: {src}\n"
        if user.number is None:
            letter = Letter(body=src, sort='Заявка')
            user.letters.insert(len(user.sent) + len(user.letters), letter)
            user.number = len(user.letters) - 1 
        else: 
            letter = user.letters[user.number]
            letter.body = src
        if not letter.edit:
            msg = bot.reply_to(message, 'Напишите пост назначения: ')
            markup = create_markup(('Завершить работу', ))
            bot.register_next_step_handler(msg, process_dest_step)
        else:
            markup = create_markup(('Дальше', 'Изменить'))
            dest = get_string(user.letters[user.number].body, 'чения:')
            msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Пост назначения: {dest}', reply_markup=markup)
            bot.register_next_step_handler(msg, process_dest_step) 
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Напишите пост отправления: ')
                           )
        #bot.register_next_step_handler(msg, process_src_step, number) &+c6WzHK5;lEbG=#


def print_memo(chat_id, markup):
    msg = bot.send_message(chat_id, ('Ознакомьтесь с тем как прикреплять фотографии документов.\n'
                               '1. Нажать на скрепку\n' 
                               '2. Выбрать файл\n' 
                               '3. Нажать на «Выбрать из Галереи»\n'
                               '4. Выбрать необходимые страницы документа\n'
                               'Убедитесь, что фото сделаны в хорошем качестве и все поля читаемы\U0000203C\n\n'
                               'Настоятельно рекомендуем присылать сканы документов в PDF формате\U0000203C\n\n'),
                               reply_markup=markup)
    # TODO: relative path -> env path (absolute)
    memos = ['photo_memo_1.jpg', 'photo_memo_2.jpg']
    for memo in memos:
       bot.send_photo(chat_id, read_photo(memo))

    return msg


@decorator
def process_dest_step(message, user):
    try:
        letter = user.letters[user.number]
        dest = message.text
        if dest == 'Завершить работу':
            markup = create_markup(('Да', 'Нет'))
            msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить?\n Все данные удалятся.', reply_markup=markup)
            bot.register_next_step_handler(msg, process_deletion_step, process_dest_step, 'Dest')
            return
        elif dest == 'Дальше':
            user.key = 'CMR'
            markup = create_markup(('Дальше', 'Изменить'))
            msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Вложения по: 1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ):', reply_markup=markup)
            send_all_dcouments(letter, message.chat.id, names, certain='CMR')
            bot.register_next_step_handler(msg, process_cmr_step) 
            return # go to dest step
        elif dest == 'Изменить':
            msg = bot.reply_to(message, ("Напишите пост назначения:"))
            bot.register_next_step_handler(msg, process_dest_step)
            return
        dest = f"Пост назначения:: {dest}\n"
        letter.body = letter.body + dest
        if not letter.edit: 
            user.key = 'CMR'
            markup = create_markup(('Ознакомился', 'Завершить работу'))
            msg = print_memo(message.chat.id, markup)
            # msg = b#ot.reply_to(message, ('Инструкция здесь.'),
            #             reply_markup=markup)
            bot.register_next_step_handler(msg, process_memo_step)
        else:
            markup = create_markup(('Дальше', 'Изменить'))
            msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Вложения по: 1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ):', reply_markup=markup)
            send_all_dcouments(letter, message.chat.id, names, certain='CMR')
            bot.register_next_step_handler(msg, process_cmr_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Напишите пост назначения: ')
                           )
        #bot.register_next_step_handler(msg, process_dest_step, number)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        if call.data == "but_next_doc":
            bot.send_message(call.message.chat.id, "Вы нажали на первую кнопку.")
        if call.data == "but_quit":
            bot.send_message(call.message.chat.id, "Вы нажали на вторую кнопку.")
            keyboard = create_inline_keyboard({"Следующий документ":"but_next_doc",
                                               "Прикрепить еще страницу":"but_next_doc",
                                               "Завершить работу":"but_quit"})
            bot.edit_message_reply_markup(call.from_user.id, call.message.message_id, reply_markup=keyboard)


def process_memo_step(message):
    try:
        if message.text == 'Ознакомился':
            #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'))
            markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
            #keyboard = create_inline_keyboard({"Следующий документ":"but_next_doc", "Завершить работу":"but_quit"})
            msg = bot.reply_to(message, ('Прикрепите необходимые документы.\n'
                                        '\U0000203CНеобходимо прикреплять фото документов как вложения\U0000203C\n'
                                        '1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ):'),
                            reply_markup=markup)
            bot.register_next_step_handler(msg, process_cmr_step)
        elif message.text == 'Завершить работу':
            markup = create_markup(('Да', 'Нет'))
            msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить?\n Все данные удалятся.', reply_markup=markup)
            bot.register_next_step_handler(msg, process_deletion_step, process_memo_step, 'Memo')
        else:
            markup = create_markup(('Ознакомился', 'Завершить работу'))
            msg = bot.send_message(message.chat.id, 'Я вас не понимаю, Вы ознакомились?\n', reply_markup=markup)
            bot.register_next_step_handler(msg, process_memo_step)
            
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Напишите пост назначения: ')
                           )

def process_deletion_step(message, prev_step_handler, sort):
    # TODO: to make a universal approach to src/dest/attach cancellation
    try:
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
    except TypeError:
        user_key, user = None, None
    if message.text == 'Да' and sort in ('Telephone', 'Body', 'Src', 'Dest', 'Message', 'Memo'):
        markup = create_markup(('Сформировать заявку', 'Обратная связь'))
        if user:
            if user.registered:
                markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Заявки'))
        bot.reply_to(message, f"Привет! Я ваш бот-помошник. Помогу быстро сформировать заявку.",
                 reply_markup=markup)
        try:
            user.letters = []
        except AttributeError:
            pass
    elif message.text == 'Да' and sort == 'Attachment':
        del user.letters[user.number]
        markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Завершить работу'))
        bot.send_message(message.chat.id, 'Я удалил заявку. Выберите опцию ниже.', reply_markup=markup)
    elif message.text == 'Нет' and sort == 'Attachment': 
        bot.send_message(message.chat.id, 'Продолжим.')
        # TODO: retrive all documents related to the step
        #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'))
        markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
        msg = bot.reply_to(message, ('Прикрепите необходимые документы.\n'
                                     f'{names[user.key]}'), reply_markup=markup)
        bot.register_next_step_handler(msg, prev_step_handler)
    elif message.text == 'Нет' and sort == 'Telephone':
        bot.send_message(message.chat.id, 'Продолжим.')
        markup = create_markup(('Завершить работу', ))
        msg = bot.reply_to(message, "Напишите свой телефон для обратной связи:", reply_markup=markup)
        bot.register_next_step_handler(msg, prev_step_handler)
    elif message.text == 'Нет' and sort == 'Body': 
        bot.send_message(message.chat.id, 'Продолжим.')
        markup = create_markup(('Завершить работу', ))
        msg = bot.reply_to(message, "Напишите то, что хотели бы передать:", reply_markup=markup)
        bot.register_next_step_handler(msg, prev_step_handler)
    elif message.text == 'Нет' and sort == 'Src':  
        bot.send_message(message.chat.id, 'Продолжим.')
        markup = create_markup(('Завершить работу', ))
        msg = bot.reply_to(message, "Напишите пост отправления:" , reply_markup=markup)
        bot.register_next_step_handler(msg, prev_step_handler)
    elif message.text == 'Нет' and sort == 'Dest':  
        bot.send_message(message.chat.id, 'Продолжим.')
        markup = create_markup(('Завершить работу', ))
        msg = bot.reply_to(message, 'Напишите пост назначения: ', reply_markup=markup)
        bot.register_next_step_handler(msg, prev_step_handler)
    elif message.text == 'Нет' and sort == 'Message':
        bot.send_message(message.chat.id, 'Продолжим.')
        markup = create_markup(('Отправить', 'Завершить работу'))
        msg = bot.reply_to(message, 'Прикрепите вложения: ', reply_markup=markup)
        bot.register_next_step_handler(msg, prev_step_handler)
    elif message.text == 'Нет' and sort == 'Memo':  
        bot.send_message(message.chat.id, 'Продолжим.')
        markup = create_markup(('Ознакомился', 'Завершить работу'))
        msg = msg = print_memo(message.chat.id, markup)
        bot.register_next_step_handler(msg, prev_step_handler)


def process_attach(message, next_key, user, document_name, next_step_handler, step_hndler):
    number = user.number
    key = user.key
    if message.text == 'Завершить работу':
        #del user.letters[number]
        #markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Завершить работу'))
        markup = create_markup(('Да', 'Нет'))
        msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить?\n Все данные удалятся.', reply_markup=markup)
        bot.register_next_step_handler(msg, process_deletion_step, step_hndler, 'Attachment')
        return
    # elif message.text == 'Следующий документ':
    #     user.key = next_key
    #     markup = create_markup(('Следующий документ', 'Завершить работу'))
    #     msg = bot.reply_to(message, ('Прикрепите необходимые документы.\n'
    #                                  f'{document_name}'), reply_markup=markup)
    #     bot.register_next_step_handler(msg, next_step_handler)
    #     return
    elif message.text == 'Прикрепить еще страницу ds':
        #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'))
        markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
        if  key not in user.letters[number].attachs.keys():
            #keyboard = create_inline_keyboard({"Следующий документ":"but_next_doc", "Завершить работу":"but_quit"})
            msg = bot.reply_to(message, ('Еще нет прикрепленных документов'),
                           reply_markup=markup)
        else: 
            msg = bot.reply_to(message, ('Прикрепите еще страницу документа: \n'),
                           reply_markup=markup)
        bot.register_next_step_handler(message, step_hndler)
        return
    elif message.text == 'Следующий документ':
        user.key = next_key
        if not user.letters[number].edit:
            bot.clear_step_handler_by_chat_id(message.chat.id)
            #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'), presists=True)
            markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
            msg = bot.reply_to(message, ('Прикрепите необходимые документы.\n'
                                    f'{names[next_key]}'), reply_markup=markup)
            bot.register_next_step_handler(msg, next_step_handler)
        else:
            markup = create_markup(('Дальше', 'Изменить'))
            msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Вложения по {names[next_key]}', reply_markup=markup)
            send_all_dcouments(user.letters[number], message.chat.id, names, certain=next_key)
            bot.register_next_step_handler(msg, next_step_handler)
        return
    elif message.text == 'Дальше':
        user.key = next_key
        markup = create_markup(('Дальше', 'Изменить'))
        msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Вложения по {names[next_key]}', reply_markup=markup)
        send_all_dcouments(user.letters[number], message.chat.id, names, certain=next_key)
        bot.register_next_step_handler(msg, next_step_handler)
        return
    elif message.text == 'Изменить':
        user.letters[number].attachs[key] = []
        markup = create_markup(('Дальше', 'Завершить работу'))
        msg = bot.reply_to(message, ('Прикрепите необходимые документы.\n'
                                    '\U0000203CНеобходимо прикреплять фото документов как вложения\U0000203C\n'
                                    #f'{document_name}:'
                                    ),
                        reply_markup=markup)
        bot.register_next_step_handler(msg, step_hndler)
        return
    elif message.document or message.photo:
        letter = user.letters[number]
        letter.update_attachs(message, bot, False, key)
        if not user.letters[number].edit:
            #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'), presists=True)
            markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True) 
            if message.media_group_id is not None:
                start_timer(bot, message, markup, ('Файлы загружены. \n' 
                      'Отправьте еще или нажмите "Следующий документ".'), step_hndler)
            else:
                #bot.send_message(message.chat.id, 'Прикрепите еще вложение:', reply_markup=markup)
                bot.register_next_step_handler(message, step_hndler)
                bot.send_message(message.chat.id, 
                     ('Файлы загружены. \n' 
                      'Отправьте еще или нажмите "Следующий документ".'), reply_markup=markup)
        else:
            markup = create_markup(('Дальше', 'Завершить работу'))
            if message.media_group_id is not None:        
                start_timer(bot, message, markup, ('Файлы загружены. \n' 
                      'Отправьте еще или нажмите "Следующий документ".'), step_hndler)
            else:
                #bot.send_message(message.chat.id, 'Прикрепите еще вложение:', reply_markup=markup)
                bot.register_next_step_handler(message, step_hndler)
                bot.send_message(message.chat.id, 
                     ('Файлы загружены. \n' 
                      'Отправьте еще или нажмите "Следующий документ".'), reply_markup=markup)
        #else:
        #    answer = asyncio.create_task(setTimeout(5, func(message, step_hndler)))   
        return 
    else:
        #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'), presists=True)
        markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True) 
        bot.send_message(message.chat.id,
                          (f'Я вас не понимаю.\n' 
                           f'Выберите отпцию ниже или прикрепите документ\n {names[key]}.'),
                          reply_markup=markup)
        bot.register_next_step_handler(message, step_hndler)
        return


timer = None
def start_timer(bot, message, markup, message_body, func_step):     
    global timer
    if timer is None:
        #bot.send_message(message.chat.id, 'Подождите.')
        timer = threading.Timer(0.5, step_print,
                                 args=[bot, message, markup, message_body,func_step]
        )
        timer.start()
    else:
        print('Timer already started')


def step_print(bot, message, markup, message_body, func_step):
    global timer
    bot.register_next_step_handler(message, func_step)
    bot.send_message(message.chat.id, message_body, reply_markup=markup)
    print('Я здесь')
    timer = None


def func(message, step_hndler):
    markup = create_markup(('Следующий документ', 'Завершить работу')) 
    bot.send_message(message.chat.id, 'Прикрепите еще вложение:', reply_markup=markup)
    bot.register_next_step_handler(message, step_hndler)


"""
Обработать вложение для 1. CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ)
"""
@bot.message_handler(content_types=['document', 'photo', 'text'])
@decorator
def process_cmr_step(message, user):
    # TODO: nultiple attachments: button and multi-message
    try:
        process_attach(message, 'Invoice', user, '2. ИНВОЙС:', process_invoice_step, process_cmr_step)
    except AttributeError as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ):')
                            )
       #bot.register_next_step_handler(msg, process_cmr_step)
        

"""
Обработать вложение для 2. ИНВОЙС
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_invoice_step(message, user):
    try:
        process_attach(message, 'Specific', user, '3. СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ):',
                       process_spec_step, process_invoice_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '2. ИНВОЙС:')
                            )
         #bot.register_next_step_handler(msg, process_invoice_step, number, 'Invoice')


"""
Обработать вложение для 3. СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ)
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_spec_step(message, user):
    try:
        process_attach(message, 'Packing', user, '4. ПАКИНГ ЛИСТ:',
                       process_packing_step, process_spec_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '3. СПЕЦИФИКАЦИЮ (РАЗБИВКА С РУССКИМ ОПИСАНИЕМ):')
                            )
         #bot.register_next_step_handler(msg, process_spec_step, number, 'Specific')


"""
Обработать вложение для 4. ПАКИНГ ЛИСТ
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_packing_step(message, user):
    try:
        process_attach(message, 'Driver', user, '5.ПАСПОРТ ВОДИТЕЛЯ:',
                       process_driver_step, process_packing_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '4. ПАКИНГ ЛИСТ:')
                            )
         #bot.register_next_step_handler(msg, process_packing_step, number, 'Packing')
        

"""
Обработать вложение для 5. ПАСПОРТ ВОДИТЕЛЯ
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_driver_step(message, user):
    try:
        process_attach(message, 'Track', user, '6. ТЕХПАСПОРТ НА ТЯГАЧ:',
                       process_track_step, process_driver_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '5. ПАСПОРТ ВОДИТЕЛЯ:')
                            )
         #bot.register_next_step_handler(msg, process_driver_step, number, 'Driver')


"""
Обработать вложение для 6. ТЕХПАСПОРТ НА ТЯГАЧ
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_track_step(message, user):
    try:
        process_attach(message, 'Trailer', user, '7. ТЕХПАСПОРТ НА ПОЛУПРИЦЕП:',
                       process_trailer_step, process_track_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '6. ТЕХПАСПОРТ НА ТЯГАЧ:')
                            )
         #bot.register_next_step_handler(msg, process_track_step, number, 'Track')


"""
Обработать вложение для 7. ТЕХПАСПОРТ НА ПОЛУПРИЦЕП
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_trailer_step(message, user):
    try:
        process_attach(message, 'Permission', user, '8.СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ( СВИДЕТЕЛЬТВО ПОД ПЛОМБАМИ):',
                       process_permision_step, process_trailer_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '7. ТЕХПАСПОРТ НА ПОЛУПРИЦЕП:')
                            )
         #bot.register_next_step_handler(msg, process_trailer_step, number, 'Trailer')
        

"""
Обработать вложение для 8. СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ( СВИДЕТЕЛЬТВО ПОД ПЛОМБАМИ)
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_permision_step(message, user):
    try:
        process_attach(message, 'Carrier', user, 
                       ('9. СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА \n'
                        '( ЕСЛИ ТРАНЗИТ ПОД ТАМОЖЕННФМ ПЕРЕВОЗЧИКОМ)'),
                       process_carrier_step, process_permision_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '8. СВИДЕТЕЛЬСТВО О ДОПУЩЕНИИ( СВИДЕТЕЛЬТВО ПОД ПЛОМБАМИ):')
                            )
         #bot.register_next_step_handler(msg, process_permision_step, number, 'Permission')


"""
Обработать вложение для 9. СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА 
                           (ЕСЛИ ТРАНЗИТ ПОД ТАМОЖЕННФМ ПЕРЕВОЗЧИКОМ)
"""
@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_carrier_step(message, user):
    number  = user.number
    key = user.key
    if message.text == 'Завершить работу':
        del user.letters[number]
        markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
        bot.send_message(message.chat.id, 'Я удалил письмо.\nМожет начать заново.\nИли завершить работу.', reply_markup=markup)
        return
    elif message.text == 'Прикрепить еще страницу 2323':
        #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'))
        markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
        if  key not in user.letters[number].attachs.keys():
            #keyboard = create_inline_keyboard({"Следующий документ":"but_next_doc", "Завершить работу":"but_quit"})
            msg = bot.reply_to(message, ('Еще нет прикрепленных документов'),
                           reply_markup=markup)
        else: 
            msg = bot.reply_to(message, ('Прикрепите еще страницу документа: \n'),
                           reply_markup=markup)
        bot.register_next_step_handler(message, process_carrier_step)
        return
    elif message.text == 'Пропустить' or message.text == 'Следующий документ':
        # send all got files and its names
        # TODO: document_name

        letter = user.letters[number]
        filtered_files = dict([item for item in letter.attachs.items() if item[1] is not None])
        letter.attachs = filtered_files
        if len(letter.attachs) != 0:
            markup = create_markup(('Да', 'Нет, выбрать другие'))
            bot.send_message(message.chat.id, 'Я получил такие документы:')
            send_all_dcouments(letter, message.chat.id, names)
            msg = bot.send_message(message.chat.id, 'Список документов верный?', reply_markup=markup)
            bot.register_next_step_handler(msg, process_confirm_step, number)
        else:
            #bot.send_message(message.chat.id, 'Вы не прикрепили ни одного вложения.')
            #bot.send_message(message.chat.id, f'Заявка сформирована №{number + len(user.sent)}.')
            #bot.send_message(message.chat.id, f'Заявка сформирована.')
            #letters = user.letters
            #list_letters = [f'Заявка #{index + len(user.sent)}' for index, val in enumerate(letters)]
            #markup = create_markup(('Отправить заявку', 'Сформировать заявку', 'Текущие заявки', 'Отправленные заявки', *tuple(list_letters)))
            #markup = create_markup(('Отправить заявку', 'Заявки', 'Завершить работу'))
            #bot.send_message(message.chat.id, ('Теперь вы можете отправить заявку. \n'
            #                                   'Кнопка "Оправить заявку" - отправит созданную заявку.\n'
            #                                   'Кнопка "Зявки" - покажет все отправленные заявки.\n'),
            #                reply_markup=markup)
            send_ticket(message)
            markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
            bot.send_message(message.chat.id, (#'Вы можете сформировать еще одну заявку.\n'
                                            'Кнопка "Заявки" - покажет меню заявок.'),
                            reply_markup=markup)
        return
    
    elif message.text == 'Дальше':
        letter = user.letters[number]
        filtered_files = dict([item for item in letter.attachs.items() if item[1] is not None])
        letter.attachs = filtered_files
        if len(letter.attachs) != 0:
            markup = create_markup(('Да', 'Нет, выбрать другие'))
            bot.send_message(message.chat.id, 'Я получил такие документы:')
            send_all_dcouments(letter, message.chat.id, names)
            msg = bot.send_message(message.chat.id, 'Список документов верный?', reply_markup=markup)
            bot.register_next_step_handler(msg, process_confirm_step, number)
        else:
            bot.send_message(message.chat.id, 'Вы не прикрепили ни одного вложения.')
            #bot.send_message(message.chat.id, f'Заявка сформирована №{number + len(user.sent)}.')
            #bot.send_message(message.chat.id, f'Заявка изменена.')
            #letters = user.letters
            #list_letters = [f'Заявка #{index + len(user.sent)}' for index, val in enumerate(letters)]
            #markup = create_markup(('Отправить заявку', 'Сформировать заявку', 'Текущие заявки', 'Отправленные заявки', *tuple(list_letters)))
            send_ticket(message)
            # markup = create_markup(('Отправить заявку', 'Завершить работу'))
            # bot.send_message(message.chat.id, ('Теперь вы можете отправить заявку. \n'
            #                                    'Кнопка "Оправить заявку" - отправит созданную заявку.\n'),
            #                 reply_markup=markup)
            markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
            bot.send_message(message.chat.id, (#'Вы можете сформировать еще одну заявку.\n'
                                            'Кнопка "Заявки" - покажет меню заявок.'),
                            reply_markup=markup)
        return
    try:
        letter = user.letters[number]
        letter.update_attachs(message, bot, False, key)
        if not letter.edit: 
            markup = create_markup(('Следующий документ', 'Завершить работу')) 
            #bot.send_message(message.chat.id, 'Прикрепите еще вложение:', reply_markup=markup)
            bot.register_next_step_handler(message, process_carrier_step)
        else:
            markup = create_markup(('Дальше', 'Завершить работу')) 
            #bot.send_message(message.chat.id, 'Прикрепите еще вложение:', reply_markup=markup)
            bot.register_next_step_handler(message, process_carrier_step)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Прикрепи необходимые документы.\n'
                                     '9. СВИДЕТЕЛЬСТВО ТАМОЖЕННОГО ПЕРЕВОЗЧИКА \n'
                                     '( ЕСЛИ ТРАНЗИТ ПОД ТАМОЖЕННФМ ПЕРЕВОЗЧИКОМ)')
                            )
         #bot.register_next_step_handler(msg, process_carrier_step, number, 'Carrier')


def send_all_dcouments(letter, chat_id,  names, certain=None):
    if certain:
        if certain in letter.attachs.keys():
            for key, attach in letter.attachs.items():
                if key == certain:
                    if len(attach) != 0:
                        for index, page in enumerate(attach):
                            bot.send_document(chat_id, caption=names[key] + f' Стр. {index+1}', document=page[1])
        else:
            bot.send_message(chat_id, 'Без вложений')
    else:
        for key, attach in letter.attachs.items():
            for index, page in enumerate(attach):
                bot.send_document(chat_id, caption=names[key] + f' Стр. {index+1}', document=page[1])


def send_ticket(message):
    # сообщение: Ваше соообщение отправлено, наши специалисты скоро свяжутся с Вами.
    user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
    #markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Отправленные заявки', 'Завершить работу'))
    markup = create_markup(('Сформировать заявку',  'Заявки', 'Завершить работу'))
    # SMTP send
    list_senderrors = []
    sent_number = len(user.sent)
    for indx, letter in enumerate([letter for letter in user.letters if letter.sent == False]): # поменить номер заявки в пуле
        #bot.send_message(message.chat.id, "Формирую заявку.")  # Отправляю
        body = (f"Телефон: {user_key}\n"
                f"{letter.body}\n")
        # TODO: pythonic nested loop
        files = []
        for attach in letter.attachs.values():
            for index, page in enumerate(attach):
                page[0] = page[0] + f'_str_{index+1}'
                files.append(page)

        #files = list(page for page in attach for attach in letter.attachs.values())
        if letter.edit:
            mail_subj = f"Дополнение по {letter.sort} №{user.number} от User{message.chat.id}"
        else:
            mail_subj = f"{letter.sort} №{indx + sent_number} от User{message.chat.id}"
        senderrors = send_mail(BOT_MAIL_ADDRESS, MAIL_ADDRESS, mail_subj, body, BOT_MAIL_PASS, files=files)
        list_senderrors.append(senderrors) if senderrors is not {} else list_senderrors  
        if not senderrors:
            if letter.edit:
                index = user.number
            else:
                index = indx + sent_number
            bot.send_message(message.chat.id, f'Заявка №{index} успешно отправлена.')
            letter.sent = True
            if not letter.edit:
                user.sent.append(letter)
            else:
                letter.edit = False
                user.sent[user.number] = letter
            #letter = None                    
        else:
            bot.send_message(message.chat.id, 'Не удалось отправить заявку.')
    #user.letters = [letter for letter in user.letters if not letter.sent]
    if list_senderrors: # list of dict
        #bot.send_message(message.chat.id, 'Заявка(и) успешно отправлена(и). Скоро вернусь с ответом.',
        #                    reply_markup=markup)
        #bot.send_message(message.chat.id, ('Что будем делать дальше?\n'
        #                                    '(Выберите опцию ниже)'),
        #                    reply_markup=markup)
        pass
    else:
        print('SMTP send errors: ', list_senderrors)
        bot.send_message(message.chat.id, ('Что-то пошло не так. Давайте начнем заново.\n'
                                            #'Выберите опцию...'
                                           ),
                            reply_markup=markup)

def process_confirm_step(message, number):
    try:
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        if message.text == 'Да':
            if not user.letters[number].edit:
                #bot.send_message(message.chat.id, f'Заявка сформирована.')
                #bot.send_message(message.chat.id, f'Заявка сформирована №{number + len(user.sent)}.')
                #letters = user.letters
                #list_letters = [f'Заявка #{index + len(user.sent)}' for index, val in enumerate(letters)]
                #markup = create_markup(('Отправить заявку', 'Сформировать заявку', 'Текущие заявки', 'Отправленные заявки', *tuple(list_letters)))
                send_ticket(message)
                markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
                bot.send_message(message.chat.id, (#'Вы можете сформировать еще одну заявку.\n'
                                                'Кнопка "Заявки" - покажет меню заявок.'),
                                reply_markup=markup)
            else:
                send_ticket(message)
                #bot.send_message(message.chat.id, f'Заявка изменена.')
                markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
                bot.send_message(message.chat.id, (#'Вы можете сформировать еще одну заявку.\n'
                                                'Кнопка "Заявки" - покажет меню заявок.'),
                                reply_markup=markup)
        elif message.text == 'Нет, выбрать другие':
            if not user.letters[number].edit: 
                user.letters[number].attachs = {}
                user.key = 'CMR'
                #markup = create_markup(('Следующий документ', 'Прикрепить еще страницу', 'Завершить работу'))
                markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
                msg = bot.reply_to(message, ('Прикрепите необходимые документы.\n'
                                            '1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ):'),
                            reply_markup=markup)
                bot.register_next_step_handler(msg, process_cmr_step)
            else:
                markup = create_markup(('Дальше', 'Изменить'))
                user.key = 'CMR'
                msg = bot.send_message(message.chat.id, f'Проверьте правильность.\n Вложения по: 1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ):', reply_markup=markup)
                send_all_dcouments(user.letters[number], message.chat.id, names, certain='CMR')
                bot.register_next_step_handler(msg, process_cmr_step)
        elif message.text == 'Нет':
            user.letters[number].attachs = {}
            user.key = 'Attach'
            markup = create_markup(('Следующий документ',  'Завершить работу'))
            msg = bot.reply_to(message, ('Прикрепите необходимые документы.\n'
                                         '1.CMR (ТРАНСПОРТНАЯ НАКЛАДНАЯ):'),
                           reply_markup=markup)
            bot.register_next_step_handler(msg, process_cmr_step)
    except Exception as e:
        msg = bot.reply_to(message, 'Что-то пошло не так. Давайте начнем заново.')
        #bot.register_next_step_handler(msg, process_confirm_step)

@decorator
def process_telephone_step(message, user, prev_message=None):
    try:
        telephone = message.text
    except AttributeError as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     "Напишите еще раз телефон:\n"
                                     '(Подсказка: цифры, не менее 9 цифр, символы +, -)')
                           )
        bot.register_next_step_handler(msg, process_telephone_step, prev_message=prev_message)
    else:
        if telephone == 'Завершить работу':
            markup = create_markup(('Да', 'Нет'))
            msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить ввод телефона?\n Все данные удалятся.', reply_markup=markup)
            bot.register_next_step_handler(msg, process_deletion_step, process_telephone_step, 'Telephone')
        elif re.match('[-+]?\d{9,}', telephone) is None:
            msg = bot.reply_to(message, ('Некорректный телефон. Попробуйте еще раз. \n'
                                         'Напишите еще раз свой номер телефона: \n'
                                         '(Подсказка: только цифры, не менее 9 цифр)')
                               )
            bot.register_next_step_handler(msg, process_telephone_step, prev_message=prev_message)
        else:
            # check if message.chat.id exists in user_dict if not add a user
            try: 
                user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
                if user_key != telephone:
                    logging.info((f'User №{message.chat.id} changed telephone {user_key} '
                              f'to telephone {telephone}.'))
                    user_dict[telephone] = user_dict.pop(user_key)
                if message.chat.id != user_dict[telephone].chat_ids:
                    logging.info((f'An attempt to abuse telephone {telephone} '
                                f'registered to user №{user_dict[telephone].chat_ids} ' 
                                f'by user №{message.chat.id}.'
                                ))
                    bot.send_message(message.chat.id, ('Этот номер уже используется в другом телеграмм акаунте.\n'
                                                    'Если хотите продолжить работу в этом акаунте сообщите нам, '
                                                    'используя форму обратной связи.'))
                    markup = create_markup(('Сформировать заявку', 'Обратная связь'))
                    bot.reply_to(message, 
                                (f"Привет! Я ваш бот-помошник."
                                "Помогу быстро сформировать заявку."),
                                reply_markup=markup)
                    return
            except TypeError:
                if telephone not in user_dict.keys():
                    user = User(phone=telephone, registered=False)
                    user.chat_ids = message.chat.id
                    user_dict[telephone] = user
                    logging.info((f'Created user №{message.chat.id} '
                                f'and telephone {telephone}.'))
                else:
                    logging.info((f'An attempt to abuse telephone {telephone} '
                              f'registered to user №{user_dict[telephone].chat_ids} ' 
                              f'by user №{message.chat.id}.'
                              ))
                    bot.send_message(message.chat.id, ('Этот номер уже используется в другом телеграмм акаунте.\n'
                                                'Если хотите продолжить работу в этом акаунте сообщите нам, '
                                                'используя форму обратной связи.'))
                    markup = create_markup(('Сформировать заявку', 'Обратная связь'))
                    bot.reply_to(message, 
                            (f"Привет! Я ваш бот-помошник."
                            "Помогу быстро сформировать заявку."),
                            reply_markup=markup)
                    return
            #if telephone not in user_dict.keys():   

            if prev_message.text == 'Обратная связь':
                reply = 'Напишите то, что хотели бы передать:'
                msg = bot.reply_to(message, reply)
                bot.register_next_step_handler(msg, process_body_step)
            elif prev_message.text == 'Сформировать заявку':
                # go to DATAVASE for telephone number: verification
                db_user = conn.curs(f"SELECT * FROM users WHERE phone='{telephone}';")
                if db_user:
                    if not user_dict[telephone].registered:
                        logging.info(f'New registered user №{user_dict[telephone].chat_ids} '
                                 f'and telephone {telephone}')
                        user_dict[telephone].registered = True
                    msg = bot.reply_to(message, 'Напишите пост отправления:')
                    user.number = None
                    bot.register_next_step_handler(msg, process_src_step)
                else:
                    logging.info(f'Database not found user №{user_dict[telephone].chat_ids} '
                                 f'and telephone {telephone}')
                    reply = ("Мы не нашли вас в нашей базе. Формирование заявки недоступно.\n"
                            'Ниже можете написать нам информацию о себе и мы свяжемся с вами.')
                    msg = bot.reply_to(message, reply)
                    bot.register_next_step_handler(msg, process_body_step)
                


def get_user_by_chat_id(user_dict, chat_id):
    for key in user_dict.keys():
        if chat_id == user_dict[key].chat_ids:
            return key, user_dict[key]

@decorator
def process_body_step(message, user):
    try:
        body = message.text
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     "Напишите еще раз, то что требуется отправить:")
                           )
        #bot.register_next_step_handler(msg, process_body_step)
    else:
        if body == 'Завершить работу':
            markup = create_markup(('Да', 'Нет'))
            msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить?\n Все данные удалятся.', reply_markup=markup)
            bot.register_next_step_handler(msg, process_deletion_step, process_body_step, 'Body')
            return
        letter = Letter(body=body, sort='Сообщение')
        user.letters.insert(len(user.sent) + len(user.letters), letter)
        markup = create_markup(('Отправить', 'Завершить работу'))
        msg = bot.reply_to(message, "Прикрепите вложение:", reply_markup=markup)
        user.number = -1
        user.key = 'Attach'
        bot.register_next_step_handler(msg, process_attach_step)
        #bot.send_message(message.chat.id, 'Прикрепить вложениe?', reply_markup=markup)
    


@bot.message_handler(content_types=['document', 'photo'])
@decorator
def process_attach_step(message, user):
    try:
        letter = user.letters[user.number]
        if message.text == 'Отправить': 
        # сообщение: Ваше соообщение отправлено, наши специалисты скоро свяжутся с Вами.
        #user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
            if user.registered:
                from_user = ''
                markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Завершить работу'))
            else:
                from_user = 'Новый пользователь! '
                #markup = create_markup(('Обратная связь', 'Завершить работу'))
                markup = create_markup(('Завершить работу', ))
            # SMTP send
            list_senderrors = []
            #sent_number = len(user.sent)
            sent_number = 0
            for indx, letter in enumerate([letter for letter in user.letters if letter.sort == 'Сообщение']): # поменить номер заявки в пуле
                # process 
                bot.send_message(message.chat.id, "Отправляю Ваше сообщение.") 
                body = f'\nТелефон: {user.phone}\n' + letter.body  # body is NoneType?
                files = []
                for attach in letter.attachs.values():
                    for index, page in enumerate(attach):
                        page[0] = page[0] + f'_str_{index+1}'
                        files.append(page)
                mail_subj = f"{from_user}{letter.sort} №{sent_number+indx} от User{message.chat.id}"
                senderrors = send_mail(BOT_MAIL_ADDRESS, MAIL_ADDRESS, mail_subj, body, BOT_MAIL_PASS, files)
                list_senderrors.append(senderrors) if senderrors is not {} else list_senderrors  
                if not senderrors:
                    bot.send_message(message.chat.id, f'Сообщение №{sent_number+indx} успешно отправлено.')
                    sent_letter = user.letters.pop(indx)
                    user.sent.append(sent_letter)
                else:
                    bot.send_message(message.chat.id, 'Не удалось отправить сообщение.')
            #if list_senderrors:
                #bot.send_message(message.chat.id, 'Сообщения(е) успешно отправлены(о). Скоро вернусь с ответом.',
                #                reply_markup=markup)
                #bot.send_message(message.chat.id, ('Что будем делать дальше?\n'
                #                                   '(Выберите опцию ниже)'),
                #                 reply_markup=markup)
            #else:
            #    print('SMTP send errors: ', list_senderrors)
            #    bot.send_message(message.chat.id, ('Что-то пошло не так. Давайте начнем заново.\n'
            #                                    'Выберите опцию...'),
            #                    reply_markup=markup)
            return 
        elif  message.text == 'Завершить работу':
            markup = create_markup(('Да', 'Нет'))
            msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить?\n Все данные удалятся.', reply_markup=markup)
            bot.register_next_step_handler(msg, process_deletion_step, process_attach_step, 'Message')
            return            
        letter.update_attachs(message, bot, False, user.key)
        markup = create_markup(('Отправить', 'Завершить работу'))
        if message.media_group_id is not None:        
            start_timer(bot, message, markup, ('Файлы загружены. \n' 
                    'Прикрепите еще вложениe:'), process_attach_step)
        else:
            #bot.send_message(message.chat.id, 'Прикрепите еще вложение:', reply_markup=markup)
            bot.register_next_step_handler(message, process_attach_step)
            bot.send_message(message.chat.id, 
                    ('Файлы загружены. \n' 
                    'Прикрепите еще вложениe:'), reply_markup=markup)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     'Прикрепите вложение:')
                           )
        #bot.register_next_step_handler(msg, process_attach_step, number, key)


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
        if file_tuple[2] == ('doc'):
            attach = MIMEApplication(file_tuple[1])
            attach.add_header('content-disposition', 'attachment', filename=file_tuple[0])
            msg.attach(attach)
        elif file_tuple[2] == 'photo':
            attach = MIMEImage(file_tuple[1], name=file_tuple[0])
            msg.attach(attach)
        elif file_tuple[2] == 'image/png' or file_tuple[2] == 'image/jpeg':
            file = bot.get_file(file_tuple[1])
            downloaded_file = bot.download_file(file.file_path)
            attach = MIMEImage(downloaded_file, name=file_tuple[0])
            attach.add_header('content-disposition', 'attachment', filename=file_tuple[0])
            msg.attach(attach)
            #attach = MIMEImage(file, name=file_tuple[0])
        else:
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

#bot.infinity_polling()
bot.polling(none_stop=True)

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
