from watchdogs.main import start_server

if __name__ == "__main__":
    # 1. pip install watchdogs
    # 2. python -m watchdogs
    # start_server()
    # start_server(mute_std_log=True)
    start_server(mute_file_log=True)
