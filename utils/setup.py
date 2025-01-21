import os
import json

def ensure_directories_and_files_exist():
    # Create basic settings.json and other jsons
    directories = ["data", "logs"]
    files = {
        "data/settings.json": {
            "telegram_token": "",
            "allowed_users": [],
            "solana_rpc_url": "https://api.mainnet-beta.solana.com"
        },
        "data/balances.json": {},
        "data/transactions.json": {},
        "data/users.json": {}
    }

    # Create directory
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Directory '{directory}' created.")  # Сообщение только при создании

    # Создаем файлы, если их нет
    for file_path, default_content in files.items():
        if not os.path.exists(file_path):
            with open(file_path, "w") as f:
                json.dump(default_content, f, indent=4)
            print(f"File '{file_path}' created.")  # Сообщение только при создании
