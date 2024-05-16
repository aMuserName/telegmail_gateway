import os
import requests
from typing import Dict, Any
from dotenv import load_dotenv
load_dotenv("..\..\.env")

API_URL = os.getenv('API_URL')
USERNAME = os.getenv("CLIENT_LOGIN")
PASSWORD = os.getenv("CLIENT_PASS")
CREDENTIALS = (USERNAME, PASSWORD)


# create a request
def create(subject: str, tp_from: str, tp_to: str, phone: str) -> Dict[Any, Any]:
    """
    type subject: str - Тема письма
    type tp_from: str - Код ТП отправления
    type tp_to: str - Код ТП назначения
    type phone: str - Номер телефона
    rtype: dict  
    """
    payload = {"subject": subject, "tp_from": tp_from, "tp_to": tp_to, "phone": phone}
    response = requests.post(url=API_URL, auth=CREDENTIALS, json=payload)
    return response.json()

# get info on the request by id
def get(request_id: int)-> Dict[Any, Any]:
    """
    type request_id: str - Номер заявки
    rtype: dict  
    """
    url = API_URL + f"{request_id}"
    response = requests.get(url=url, auth=CREDENTIALS)
    return response.json()

# send file
def send(request_id: int, file: str, file_name: str) -> int:
    """
    type request_id: int - ID заявки
    type content: str - Текст сообщения
    rtype: dict  
    """
    url = API_URL+ f"{request_id}/send_file"
    payload = {"file": (file_name, file)}
    response = requests.post(url=url, auth=CREDENTIALS, files=payload)
    return response.status_code


# get history of the request  
def retrieve():
    raise NotImplemented()


# send a message
def ask(request_id: int, content: str) -> Dict[Any, Any]:
    """
    NOT YET PROPERLY IMPLEMENTED
    type request_id: int - ID заявки
    type content: str - Текст сообщения
    rtype: dict  
    """
    url = API_URL + f"{request_id}/send_message"
    payload = {"request_id": request_id, "content": content}
    response = requests.post(url=url, auth=CREDENTIALS, json=payload)
    return response.json()