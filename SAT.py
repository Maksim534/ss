import requests
import time
import random
from fake_useragent import UserAgent
from datetime import datetime
import platform
import socket
import datetime
from termcolor import colored
import socks
import urllib.request
import pyfiglet

# ASCII-арт приветствия
ascii_banner = pyfiglet.figlet_format("SAT-MOD LSA by AYGumHack")
colored_banner = colored(ascii_banner, color='cyan')  # Красим в цвет

print(colored_banner)
device_name = socket.gethostname()
ip_address = socket.gethostbyname(device_name)
current_time = datetime.datetime.now()

print(colored(f"Скрипт был запущен: Устройство: {device_name}", 'red'))
print(colored(f"Точное время: {current_time}", 'cyan'))
print(colored(f"IP-адрес: {ip_address}", 'blue'))

def check_data_files():
    try:
        with open('text.txt', 'r') as text_file:
            text = text_file.read().splitlines()
        with open('num.txt', 'r') as num_file:
            numbers = num_file.read().splitlines()

        if not text or not numbers:
            print("Ошибка: Файлы text.txt или num.txt пусты или отсутствуют данные.")
            return False
        return True

    except FileNotFoundError:
        print("Ошибка: Файлы text.txt или num.txt не найдены.")
        return False


# Проверка наличия данных в файлах перед запуском основного кода
if not check_data_files():
    exit()

url = 'https://telegram.org/support'
ua = UserAgent()

yukino = 0

def send_complaint(text, contact, proxy):
    headers = {
        'User-Agent': ua.random
    }
    payload = {
        'text': text,
        'contact': contact
    }

    proxy_parts = proxy.split(':')
    proxy_ip = proxy_parts[0]
    proxy_port = int(proxy_parts[1])

    # Check if the proxy has authentication details
    if len(proxy_parts) > 2:
        proxy_username = proxy_parts[2]
        proxy_password = proxy_parts[3]

        socks.set_default_proxy(socks.SOCKS5, proxy_ip, proxy_port, username=proxy_username, password=proxy_password)
        socket.socket = socks.socksocket

    else:
        socks.set_default_proxy(socks.SOCKS5, proxy_ip, proxy_port)
        socket.socket = socks.socksocket

    try:
        response = requests.post(url, data=payload, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"\33[92mЖалоба успешно отправлена\n Всего отправлено", yukino, "сообщений\33[0m")
        else:
            print(colored(f"Произошла ошибка при отправке жалобы", 'red'))
    except requests.exceptions.RequestException as e:
        print(colored(f"Ошибка соединения: {e}", 'red'))

# Чтение номеров телефонов из файла num.txt
with open('num.txt', 'r') as num_file:
    contact = num_file.read().splitlines()

# Чтение текстов жалобы из файла text.txt
with open('text.txt', 'r') as text_file:
    text = text_file.read().splitlines()

# Чтение списка прокси из файла proxy.txt
with open('proxy.txt', 'r') as proxy_file:
    proxies_list = proxy_file.read().splitlines()

# Ограничение на количество отправленных жалоб
limit = 1000

while yukino < limit:
    yukino += 1
    chosen_text = random.choice(text)
    chosen_contact = random.choice(contact)
    chosen_proxy = random.choice(proxies_list)
    print(f"Отправка жалобы №{yukino}...")
    send_complaint(chosen_text, chosen_contact, chosen_proxy)
    time.sleep(1)  # Подождать 1 секунду между отправкой жалобы
