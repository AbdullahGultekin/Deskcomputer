import requests

windows_ip = '192.168.x.x'  # Vervang door het IP-adres van Windows
url = f'http://{windows_ip}:5000/update-notify'


def send_update_notification():
    data = {
        'message': 'Er is een nieuwe software update beschikbaar. Update nu!'
    }
    try:
        response = requests.post(url, json=data)
        if response.status_code == 200:
            print('Update melding is succesvol verzonden.')
        else:
            print(f'Fout: {response.status_code}')
    except Exception as e:
        print(f'Kon geen verbinding maken: {e}')


if __name__ == '__main__':
    send_update_notification()
