import os
import re
import sys
import smtplib
import threading
import logging
import time

import telebot
import pandas as pd
from telebot import types
from classes import User, Connection, Letter
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from email.utils import formatdate
from dotenv import load_dotenv
from functools import wraps
from funcs import read_photo


logging.basicConfig(format='%(asctime)s %(message)s',datefmt='%d-%m-%Y %H:%M:%S',level=logging.INFO)
telebot.logger.setLevel(logging.DEBUG)

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

MAIL_ADDRESS = os.getenv('MAIL_ADDRESS')
BOT_MAIL_ADDRESS = os.getenv('BOT_MAIL_ADDRESS')
BOT_MAIL_PASS = os.getenv('BOT_MAIL_PASS')
MAIL_SUBJECT = os.getenv('MAIL_SUBJECT')
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT'))

PATH_TO_CSV = os.getenv('PATH_TO_CSV')

PATH_TO_IMG_1 = os.getenv('PATH_TO_IMG_1')
PATH_TO_IMG_2 = os.getenv('PATH_TO_IMG_2')

CHAT_ID = int(os.getenv('CHAT_ID'))
NAME = int(os.getenv('NAME'))
SURNAME = int(os.getenv('SURNAME'))
EMAIL = int(os.getenv('EMAIL'))
DB_PATH = os.getenv('DB_PATH')


bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
bot.enable_save_next_step_handlers(delay=2)
conn = Connection(DB_PATH)
user_dict = {}
user_timers = {}
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
dataset = pd.read_csv(PATH_TO_CSV, sep='\t')

def decorator(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        global user_timers
        #try:
        user_key, user = get_user_by_chat_id(user_dict, args[0].chat.id)
        #except TypeError:
        #    logging.warning(f'Unregistered user with chat id {args[0].chat.id}. Function call: {func.__name__}')
        #    user = None 
        return func(*args, user, **kwargs)
    return wrap

def inline_decorator(func):
    @wraps(func)
    def wrap(*args, **kwargs):
        user_key, user = get_user_by_chat_id(user_dict, args[0].from_user.id)
        return func(*args, user, **kwargs)
    return wrap





def get_user_by_chat_id(user_dict, chat_id):
    for key in user_dict.keys():
        if chat_id == user_dict[key].chat_ids:
            return key, user_dict[key]
    return (None, None)


def meets(dataset, query, column, amount = 10, strict=False):
    # TODO: correct serach depending on name and code
    if not strict:
        dataset['found'] = dataset[column].apply(lambda cell: str(cell).startswith(query))
    else:
        dataset['found'] = dataset[column].apply(lambda value: True if query == value else False)
    return dataset[dataset['found']].sort_values(by=['code']).head(amount)  


def find_adress(query: str, limit: int = 10, strict: bool = False) -> pd.DataFrame:
    if not strict:
        dataset['found'] = dataset['namt'].apply(lambda cell: True if str(cell).lower().find((query).lower()) != -1 else False)
    else:
        dataset['found'] = dataset['namt'].apply(lambda value: True if query == value else False)
    return dataset[dataset['found']].sort_values(by=['namt']).head(limit)  
 

def get_string(stroka, beg_str):
    beg = stroka.index(beg_str)
    end = stroka.find('\n', beg)
    return stroka[beg+6:end].strip()


@bot.inline_handler(lambda query: len(query.query) == 0)
@inline_decorator
def query_text(inline_query, user):
    try:
        column_name = user.filter_name
    except AttributeError as e:
        column_name = 'namt'

    if column_name == 'namt':
        r = types.InlineQueryResultArticle(id='1', title='Введите название пункта',
                                            description='Дальше выберите нужный',
                                            input_message_content=types.InputTextMessageContent(message_text='Не смог найти'))
    elif column_name == 'code':
        r = types.InlineQueryResultArticle(id='1', title='Введите номер пункта',
                                            description='Дальше выберите нужный',
                                              input_message_content=types.InputTextMessageContent(message_text='Не смог найти'))
    try:
        bot.answer_inline_query(inline_query.id, [r])
    except Exception as e:
        print(e)


@bot.inline_handler(lambda query: query.query)
@inline_decorator
def query_text(inline_query, user):
    try:
        column_name = user.filter_name
    except AttributeError as e:
        column_name = 'namt'

    if column_name == 'code':
        result = meets(dataset, inline_query.query, column_name)
    elif column_name == 'namt':
        result = find_adress(inline_query.query)
    output = []
    if result.empty:
        r = types.InlineQueryResultArticle(id='1', title='Что-то не так',
                                            description='Не было найдено',
                                              input_message_content=types.InputTextMessageContent(message_text='Не смог найти'))
        output.append(r)
    else:
        if column_name == 'namt':
            for row in result.itertuples(index=True):
                r = types.InlineQueryResultArticle(row.index, str(row.namt),
                                                    description=row.code,
                                                      input_message_content=types.InputTextMessageContent(row.namt))
                output.append(r)
        else:
            for row in result.itertuples(index=True):
                r = types.InlineQueryResultArticle(row.index, str(row.code),
                                                    description=row.namt,
                                                      input_message_content=types.InputTextMessageContent(row.code))
                output.append(r)
    try:
        bot.answer_inline_query(inline_query.id, output)
    except TypeError as e:
        print(e)


@bot.callback_query_handler(func=lambda call: call.data)
@inline_decorator
def callback_query(call, user):
    if call.data == "namt_src":
        user.filter_name = "namt"
        bot.answer_callback_query(call.id, "Поиск по адресу")
        markup = create_markup({"back_src": "Назад"}, inline=True, request=True)
        bot.edit_message_text(chat_id=call.message.chat.id, 
                              message_id=call.message.message_id,
                              text="Нажмите далее и начните вводить адрес.",
        reply_markup=markup)
    elif call.data == "code_src":
        user.filter_name = "code"
        bot.answer_callback_query(call.id, "Поиск по номеру")
        markup = create_markup({"back_src": "Назад"}, inline=True, request=True)
        bot.edit_message_text(chat_id=call.message.chat.id, 
                              message_id=call.message.message_id,
                              text="Нажмите далее и начните вводить номер.",
        reply_markup=markup)
    if call.data == "namt_dest":
        user.filter_name = "namt"
        bot.answer_callback_query(call.id, "Поиск по адресу")
        markup = create_markup({"back_src": "Назад"}, inline=True, request=True)
        bot.edit_message_text(chat_id=call.message.chat.id, 
                              message_id=call.message.message_id,
                              text="Нажмите далее и начните вводить адрес.",
        reply_markup=markup)
    elif call.data == "code_dest":
        user.filter_name = "code"
        bot.answer_callback_query(call.id, "Поиск по номеру")
        markup = create_markup({"back_dest": "Назад"}, inline=True, request=True)
        bot.edit_message_text(chat_id=call.message.chat.id, 
                              message_id=call.message.message_id,
                              text="Начинайте вводить номер:",
        reply_markup=markup)
    elif call.data == "back_src":
        markup = create_markup({"namt_src": "Адрес", "code_src": "Номер"}, inline=True)
        bot.edit_message_text(chat_id=call.message.chat.id, 
                              message_id=call.message.message_id,
                              text="Укажите по какому параметру будем искать пост отправления?",
        reply_markup=markup)
    elif call.data == "back_dest":
        markup = create_markup({"namt_dest": "Адрес", "code_dest": "Номер"}, inline=True)
        bot.edit_message_text(chat_id=call.message.chat.id, 
                              message_id=call.message.message_id,
                              text="Укажите по какому параметру будем искать пост назначения?",
        reply_markup=markup)
    elif call.data == 'cancel':
        bot.clear_step_handler_by_chat_id(chat_id=call.message.chat.id)
        user.letters = []
        bot.answer_callback_query(call.id, "Заявка удалена.")
        markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Заявки'))
        bot.send_message(call.message.chat.id,
                          f"Привет! Я ваш бот-помошник. Помогу быстро сформировать заявку.",
                            reply_markup=markup)


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


# Handle sent text messages.
@bot.message_handler(content_types=['text'])
@decorator
def get_text_message(message, user):
    if message.text == 'Обратная связь':
        markup = create_markup(('Завершить работу', ), contact=True)
        try:
            if not user.registered:
                msg = bot.reply_to(message, 
                                ("Требуется ваш телефон.\nЧтобы его отправить нажмите кнопку."), reply_markup=markup)
                bot.register_next_step_handler(msg, process_telephone_step, prev_message=message)
            elif user.registered:
                markup = create_markup(('Завершить работу', ))
                msg = bot.reply_to(message, 
                                ("Напишите то, что хотели бы передать:"), reply_markup=markup)
                bot.register_next_step_handler(msg, process_body_step)
        except AttributeError:
            msg = bot.reply_to(message, 
                                ("Для продолжение работы поделитесь своим номером телефона."), reply_markup=markup)
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
        markup = create_markup(('Завершить работу', ), contact=True)
        try:
            if not user.registered:
                msg = bot.reply_to(message, (f"Для продолжение работы поделитесь своим номером телефона.\n"),
                                reply_markup=markup)
                bot.register_next_step_handler(msg, process_telephone_step, prev_message=message)
            elif user.registered:
                markup = create_markup({"namt_src": "Адрес", "code_src": "Номер"}, inline=True)
                msg = bot.reply_to(message, ("Приступим к формированию заявки!\n"
                                            "Укажите по какому параметру будем искать " 
                                            "пост отправления.\n"), reply_markup=markup)
                user.number = None
                bot.register_next_step_handler(msg, process_src_step)
        except AttributeError:
            msg = bot.reply_to(message, (f"Прежде чем начать, напишите свой номер телефона.\n"),
                            reply_markup=markup)
            bot.register_next_step_handler(msg, process_telephone_step, prev_message=message)
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
    #elif message.text == 'Нет':
    #    msg = bot.reply_to(message, "Давайте начнем сначала.\nYНапишите пост отправления: ")
    #    bot.register_next_step_handler(msg, process_content_step)
    else:
        bot.reply_to(message, " Я вас не понимаю. Попробуйте /start")


def create_markup(button_texts, presists=False, contact=False, inline=False, request=False):
    if not inline:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, is_persistent=presists)
        if contact:
            but = types.KeyboardButton('Поделиться номером', request_contact=True)
            markup.add(but)
        for text in button_texts:
            but = types.KeyboardButton(text)
            markup.add(but)
    else:
        markup = types.InlineKeyboardMarkup()
        buts = []
        if request: 
            markup.row_width = 1
            but = types.InlineKeyboardButton('Далее', switch_inline_query_current_chat="", data='yes')
            buts.append(but)
        for data, text in button_texts.items():
            but = types.InlineKeyboardButton(text, callback_data=f"{data}")
            buts.append(but)
        markup.row(*buts)
    return markup


@decorator
def process_src_step(message, user, value = ''):
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
            markup = create_markup({"namt_src": "Адрес", "code_src": "Номер"}, inline=True)
            msg = bot.reply_to(message, ("Давайте найдем пост отправления.\n"), reply_markup=markup)
            bot.register_next_step_handler(msg, process_src_step)
            return
        else:
            # TODO: check name is in scv file
            if user.filter_name == 'code':
                result = meets(dataset, src, user.filter_name, 1, strict=True)
            elif user.filter_name == 'namt':
                result = find_adress(src, limit=1, strict=True)
                #result = meets(dataset, src, user.filter_name, 1,  strict=True)
            if result.empty:
                markup = create_markup({'back_src': 'Назад'}, inline=True, request=True)
                msg = bot.reply_to(message, ('Пост не был найден в базе данных.\n'
                                             "Попробуйте написать пост отправления заново:"), reply_markup=markup)
                bot.register_next_step_handler(msg, process_src_step)
                return
        code = result['code'].values[0]
        src =  f"Пост отправления: {code}\n"
        if user.number is None:
            letter = Letter(body=src, sort='Заявка')
            user.letters.insert(len(user.sent) + len(user.letters), letter)
            user.number = len(user.letters) - 1 
        else:
            letter = user.letters[user.number]
            letter.body = src
        if not letter.edit:
            markup = create_markup(('Завершить работу', ))
            # markup = create_markup({'code_dest': 'Номер', 'namt_dest':'Адрес'}, inline=True)
            msg = bot.reply_to(message, (#"Укажите по какому параметру будем искать "
                                         #"пост назначения.\n"
                                         "Введите пост назначения:"), reply_markup=markup)
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

@decorator
def process_select_step(message, user, type, selected=False):
    # TODO: get list of elements
        if message.text and type == 'address':
            condition = message.text
            spisok = ['ааа', 'ааааа', 'бббб', 'ббб', 'пистолет']
            hits = [row for row in spisok if condition in row]
            if len(hits) > 1:
                markup = create_markup(tuple(hits))
                msg = bot.reply_to(message, ("Выберите пост назначения."), reply_markup=markup)
                bot.register_next_step_handler(msg, process_select_step, value=condition)
            else:
                markup = create_markup(('Да', 'Нет'))
                msg = bot.reply_to(message, (f"Этот пост {condition}?"), reply_markup=markup)
                bot.register_next_step_handler(msg, process_src_step, value=condition)
        if message.text and type == 'num':
            condition = message.text
            spisok = ['ггггааа', 'гггггааааа', 'зззззбббб', 'ззббб', 'автомат']
            hits = [row for row in spisok if condition in row]
            if len(hits) > 1:
                markup = create_markup(tuple(hits))
                msg = bot.reply_to(message, ("Выберите пост назначения."), reply_markup=markup)
                bot.register_next_step_handler(msg, process_select_step, value=condition)
            else:
                markup = create_markup(('Да', 'Нет'))
                msg = bot.reply_to(message, (f"Этот пост {condition}?"), reply_markup=markup)
            bot.register_next_step_handler(msg, process_src_step, value=condition)
        else:
             msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Начните вводить пост назначения: ')
                           )


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
    memos = [PATH_TO_IMG_1, PATH_TO_IMG_2]
    for memo in memos:
       bot.send_photo(chat_id, read_photo(memo))
    return msg


BOT_NAME = '@salt_pepper_cheese_bot'
@decorator
def process_choose_step(message, user):
    try:
        choose = message.text
    except Exception as e:
        markup = create_markup(('Номер', 'Адрес', 'Завершить работу'))
        msg = bot.reply_to(message, ('Что-то пошло не так. Давай начнем заново.\n'
                                     'Выберите отпцию: '),
                           reply_markup=markup)
    else:
        if choose == 'Номер':
            user.filter_name = 'code'
            markup = create_markup(('Завершить работу', ))
            # TODO: добавить inline_button для ввода имени бота
            # TODO: поиск нормлаьный сделать
            msg = bot.send_message(message.chat.id, f'Начните вводить номер.\n(Подсказка: введите {BOT_NAME})', reply_markup=markup)
            bot.register_next_step_handler(msg, process_src_step)
        elif choose == 'Адрес':
            user.filter_name = 'namt'
            markup = create_markup(('Завершить работу', ))
            msg = bot.send_message(message.chat.id, f'Начните вводить адрес.\n(Подсказка: введите {BOT_NAME})', reply_markup=markup)
            bot.register_next_step_handler(msg, process_src_step)
        elif choose == 'Завершить работу':
            markup = create_markup(('Да', 'Нет'))
            msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить?\n Все данные удалятся.', reply_markup=markup)
            bot.register_next_step_handler(msg, process_deletion_step, process_choose_step, 'Choose')
        else:
            markup = create_markup(('Номер', 'Адрес', 'Завершить работу'))
            msg = bot.reply_to(message, 'Я вас не понимаю. Найти пост отправления по номеру или адресу?', reply_markup=markup)
            bot.register_next_step_handler(msg, process_choose_step)


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
            return # go to attach step
        elif dest == 'Изменить':
            msg = bot.reply_to(message, ("Напишите пост назначения:"))
            bot.register_next_step_handler(msg, process_dest_step)
            return
        else:
            # if user.filter_name == 'code':
            #     result = meets(dataset, dest, user.filter_name, 1, strict=True)
            # elif user.filter_name == 'namt':
            #     result = find_adress(dest, limit=1, strict=True)
            # if result.empty:
            #     markup = create_markup({'code_dest': 'Номер', 'namt_dest':'Адрес'}, inline=True)
            #     msg = bot.reply_to(message, ('Пост не был найден в базе данных.\n'
            #                                  "Попробуйте написать пост назначения завново:"), reply_markup=markup)
            #     bot.register_next_step_handler(msg, process_dest_step)
            #     return
            dest = f"Пост назначения:: {dest}\n"
            letter.body = letter.body + dest
            if not letter.edit: 
                user.key = 'CMR'
                markup = create_markup(('Ознакомился', 'Завершить работу'))
                msg = print_memo(message.chat.id, markup)
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


def process_memo_step(message):
    try:
        if message.text == 'Ознакомился':
            markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
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
    if message.text == 'Да' and sort in ('Telephone', 'Choose', 'Body', 'Src', 'Dest', 'Message', 'Memo'):
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
        bot.send_message(message.chat.id, 'Я удалил заявку.', reply_markup=markup)
    elif message.text == 'Нет' and sort == 'Attachment': 
        bot.send_message(message.chat.id, 'Продолжим.')
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
        msg = print_memo(message.chat.id, markup)
        bot.register_next_step_handler(msg, prev_step_handler)
    elif message.text == 'Нет' and sort == 'Choose': 
        bot.send_message(message.chat.id, 'Продолжим.')
        markup = create_markup(('Номер', 'Адрес', 'Завершить работу'))
        msg = print_memo(message.chat.id, markup)
        bot.register_next_step_handler(msg, prev_step_handler)


def process_attach(message, next_key, user, document_name, next_step_handler, step_hndler):
    number = user.number
    key = user.key
    if message.text == 'Завершить работу':
        markup = create_markup(('Да', 'Нет'))
        msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить?\n Все данные удалятся.', reply_markup=markup)
        bot.register_next_step_handler(msg, process_deletion_step, step_hndler, 'Attachment')
        return
    elif message.text == 'Следующий документ':
        user.key = next_key
        if not user.letters[number].edit:
            bot.clear_step_handler_by_chat_id(message.chat.id)
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
                                    ),
                        reply_markup=markup)
        bot.register_next_step_handler(msg, step_hndler)
        return
    elif message.document or message.photo:
        letter = user.letters[number]
        letter.update_attachs(message, bot, False, key)
        if not user.letters[number].edit:
            markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True) 
            if message.media_group_id is not None:
                start_timer(bot, message, markup, ('Файлы загружены. \n' 
                      'Отправьте еще или нажмите "Следующий документ".'), step_hndler)
            else:
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
                bot.register_next_step_handler(message, step_hndler)
                bot.send_message(message.chat.id, 
                     ('Файлы загружены. \n' 
                      'Отправьте еще или нажмите "Следующий документ".'), reply_markup=markup)  
        return 
    else:
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
        markup = create_markup(('Следующий документ', 'Завершить работу'), presists=True)
        if  key not in user.letters[number].attachs.keys():
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
            send_ticket(message)
            markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
            bot.send_message(message.chat.id, ('Кнопка "Заявки" - покажет меню заявок.'),
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
            send_ticket(message)
            markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
            bot.send_message(message.chat.id, ('Кнопка "Заявки" - покажет меню заявок.'),
                            reply_markup=markup)
        return
    try:
        letter = user.letters[number]
        letter.update_attachs(message, bot, False, key)
        if not letter.edit: 
            markup = create_markup(('Следующий документ', 'Завершить работу')) 
            bot.register_next_step_handler(message, process_carrier_step)
        else:
            markup = create_markup(('Дальше', 'Завершить работу')) 
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
    user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
    markup = create_markup(('Сформировать заявку',  'Заявки', 'Завершить работу'))
    # SMTP send
    list_senderrors = []
    sent_number = len(user.sent)
    for indx, letter in enumerate([letter for letter in user.letters if letter.sent == False]): # поменить номер заявки в пуле
        body = (f"Телефон: {user_key}\n"
                f"{letter.body}\n")
        # TODO: pythonic nested loop
        files = []
        for attach in letter.attachs.values():
            for index, page in enumerate(attach):
                page[0] = page[0] + f'_str_{index+1}'
                files.append(page)

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
        else:
            bot.send_message(message.chat.id, 'Не удалось отправить заявку.')
    if list_senderrors != [{}]:
        logging.error(f'SMTP send errors: {list_senderrors}')
        bot.send_message(message.chat.id, ('Что-то пошло не так. Давайте начнем заново.\n'),
                            reply_markup=markup)


def process_confirm_step(message, number):
    try:
        user_key, user = get_user_by_chat_id(user_dict, message.chat.id)
        if message.text == 'Да':
            if not user.letters[number].edit:
                send_ticket(message)
                markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
                bot.send_message(message.chat.id, ('Кнопка "Заявки" - покажет меню заявок.'),
                                reply_markup=markup)
            else:
                send_ticket(message)
                markup = create_markup(('Сформировать заявку', 'Заявки', 'Завершить работу'))
                bot.send_message(message.chat.id, (#'Вы можете сформировать еще одну заявку.\n'
                                                'Кнопка "Заявки" - покажет меню заявок.'),
                                reply_markup=markup)
        elif message.text == 'Нет, выбрать другие':
            if not user.letters[number].edit: 
                user.letters[number].attachs = {}
                user.key = 'CMR'
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
    if message.text:
        telephone = message.text
    elif message.contact:
        telephone = message.contact.phone_number
    else:
        markup = create_markup(('Завершить работу',), contact=True)
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                    'Поделитесь своим номером телефона еще раз.\n'
                                    ), reply_markup=markup)
        bot.register_next_step_handler(msg, process_telephone_step, prev_message=prev_message)
        return
    telephone = telephone.replace('(', '').replace(')', '').replace('+', '').replace('-', '')
    if telephone == 'Завершить работу':
        markup = create_markup(('Да', 'Нет'))
        msg = bot.send_message(message.chat.id, 'Вы точно хотите прeкратить ввод телефона?\n Все данные удалятся.', reply_markup=markup)
        bot.register_next_step_handler(msg, process_deletion_step, process_telephone_step, 'Telephone')
    elif re.match('^\d{9,}', telephone) is None:
        markup = create_markup(('Завершить работу',), contact=True)
        msg = bot.reply_to(message, ('Некорректный телефон. Попробуйте еще раз. \n'
                                        'Поделитесь своим номером телефона еще раз. \n'
                                        '(Подсказка: только цифры, не менее 9 цифр)')
                            )
        bot.register_next_step_handler(msg, process_telephone_step, prev_message=prev_message)
    else:
        if user is None:
            if telephone not in user_dict.keys():
                user = User(phone=telephone, registered=False)
                user.chat_ids = message.chat.id
                user_dict[telephone] = user
                logging.info((f'Created user №{message.chat.id} with phone {telephone}.'))
            else:
                markup = create_markup(('Сформировать заявку', 'Обратная связь'))
                bot.send_message(message.chat.id, ('Этот номер уже используется в другом телеграмм акаунте.\n'
                                            'Если хотите продолжить работу в этом акаунте сообщите нам, '
                                            'используя форму обратной связи.'))
                bot.reply_to(message, (f"Привет! Я ваш бот-помошник. Помогу быстро сформировать заявку."),
                             reply_markup=markup)
                logging.info((f'An abuse user`s №{user_dict[telephone].chat_ids} telephone {telephone} '
                              f'by user №{message.chat.id}.'))
                return
        else:
            if user.phone != telephone:
                logging.info((f'User №{message.chat.id} changed phone {user.phone} '
                            f'to phone {telephone}.'))
                user_dict[telephone] = user_dict.pop(user.phone)
            if message.chat.id != user.chat_ids:
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
            
        if prev_message.text == 'Обратная связь':
            reply = 'Напишите то, что хотели бы передать:'
            msg = bot.reply_to(message, reply)
            bot.register_next_step_handler(msg, process_body_step)
        elif prev_message.text == 'Сформировать заявку':
            # go to DATABASE for telephone number: verification
            db_user = conn.curs(f"SELECT * FROM users WHERE phone='{telephone}';")
            if db_user:
                if not user.registered:
                    logging.info(f'New registered user №{user.chat_ids} with telephone {telephone}')
                    user_dict[telephone].registered = True
                markup = create_markup({"namt_src": "Адрес", "code_src": "Номер"},
                                        inline=True)
                msg = bot.reply_to(message, ("Приступим к формированию заявки!\n"
                                        "Укажите по какому параметру будем искать " 
                                        "пост отправления.\n"), reply_markup=markup)
                user.number = None
                bot.register_next_step_handler(msg, process_src_step)
            elif db_user is None:
                logging.info(f'Database not found user №{user.chat_ids} '
                                f'and telephone {telephone}')
                reply = ("Мы не нашли вас в нашей базе. Формирование заявки недоступно.\n"
                        "Ниже можете написать нам информацию о себе и мы свяжемся с вами.")
                msg = bot.reply_to(message, reply, reply_markup=create_markup(('Завершить работу', )))
                bot.register_next_step_handler(msg, process_body_step)


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
            if user.registered:
                from_user = ''
                markup = create_markup(('Сформировать заявку', 'Обратная связь', 'Завершить работу'))
            else:
                from_user = 'Новый пользователь! '
                markup = create_markup(('Завершить работу', ))
            # SMTP send
            list_senderrors = []
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
                    bot.send_message(message.chat.id, f'Сообщение №{sent_number+indx} успешно отправлено.', reply_markup=markup)
                    sent_letter = user.letters.pop(indx)
                    user.sent.append(sent_letter)
                else:
                    bot.send_message(message.chat.id, 'Не удалось отправить сообщение.')
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
            bot.register_next_step_handler(message, process_attach_step)
            bot.send_message(message.chat.id, 
                    ('Файлы загружены. \n' 
                    'Прикрепите еще вложениe:'), reply_markup=markup)
    except Exception as e:
        msg = bot.reply_to(message, ('Что-то пошло не так. Давайте начнем заново.\n'
                                     'Прикрепите вложение:')
                           )
        #bot.register_next_step_handler(msg, process_attach_step, number, key)


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


def main_loop():
    bot.infinity_polling()
    while 1:
        time.sleep(3)


if __name__ == '__main__':
    try:
        main_loop()
    except KeyboardInterrupt:
        print('\nExiting by user request.\n')
        sys.exit(0)

bot.load_next_step_handlers()