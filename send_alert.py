import requests

def send2telegram(file_path):
    apiToken = '6806478220:AAElx8RrOHf7FNzRSLq_KA6Ek6tJDxYIxGQ'
    chatID = '-1001631879783'
    method = 'sendDocument'
    apiURL = f'https://api.telegram.org/bot{apiToken}/{method}'
    vid = {'document': open(file_path, 'rb')}
    data = {'chat_id': chatID}

    try:
        response = requests.post(apiURL, data=data, files=vid)
        print(response.text)
    except Exception as e:
        print(e)

#send2telegram("./explosion.mp4")