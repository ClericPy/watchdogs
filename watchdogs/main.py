from fire import Fire
from uvicorn import run

from .app import app
from .settings import setup, Config


def clear_dir(dir_path):
    if not dir_path.is_dir():
        print(f'Dir is not exist: {dir_path}.')
        return True
    print(f'Cleaning {dir_path}...')
    for f in dir_path.iterdir():
        if f.is_dir():
            return clear_dir(f)
        f.unlink()
        print(f'File removed: {f}')
    dir_path.rmdir()
    print(f'Folder removed: {dir_path}')


def start_server(db_url=None,
                 admin=None,
                 password=None,
                 uninstall=False,
                 ignore_stdout_log=False,
                 ignore_file_log=False,
                 **uvicorn_kwargs):
    if uninstall:
        return clear_dir(Config.CONFIG_DIR)
    setup(
        db_url=db_url,
        admin=admin,
        password=password,
        ignore_stdout_log=ignore_stdout_log,
        ignore_file_log=ignore_file_log)
    run(app, **uvicorn_kwargs)


def main():
    Fire(start_server)


if __name__ == "__main__":
    main()
