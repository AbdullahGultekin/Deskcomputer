from flask import Flask, request
from plyer import notification

app = Flask(__name__)


@app.route('/update-notify', methods=['POST'])
def update_notify():
    data = request.json
    message = data.get('message', 'Er is een update beschikbaar.')

    # Toon desktop notificatie op Windows
    notification.notify(
        title='Software Update',
        message=message,
        timeout=10
    )
    return {'status': 'notificatie verzonden'}


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
