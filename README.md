[![works on my machine badge](https://cdn.jsdelivr.net/gh/nikku/works-on-my-machine@v0.4.0/badge.svg)](https://github.com/nikku/works-on-my-machine)

**To run code:**

```
cd SolanaMemeTradeTGbot
```
```
python3.12 -m venv venv
```
```
source venv/bin/activate
```
```
pip3 install -r requirements.txt
```
```
python main.py
```

To run:
1) Run "python main.py"  to create directory /data with necessary files for next steps
2) Fill in settings your TelegramToken (get from BotFather)
3) Again Run "python main.py" and find your bot in TG and send with hands "/start" and than click any button
4) Add allowed users if you don't know your tg_id start bot without id and use /start and then check logs and find:
"WARNING - Unauthorized access attempt by user ..." {HERE is your telegram_id} and add it in setting
5) Take care and save your private keys if you want use your old keys, just press "Create private Keys"
and thank replace private key to yours and click again "Сreate private key" and u must see correct address
6) Enjoy bots
