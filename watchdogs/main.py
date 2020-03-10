import sys
from pathlib import Path

from fire import Fire
from uvicorn import run

from .settings import Config, setup


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
                 password=None,
                 uninstall=False,
                 ignore_stdout_log=False,
                 ignore_file_log=False,
                 md5_salt=None,
                 config_dir=None,
                 use_default_cdn=False,
                 **uvicorn_kwargs):
    if config_dir:
        config_dir = Path(config_dir)
        if not config_dir.is_dir():
            config_dir.mkdir()
        Config.CONFIG_DIR = config_dir
    if uninstall:
        return clear_dir(Config.CONFIG_DIR)
    setup(
        db_url=db_url,
        password=password,
        ignore_stdout_log=ignore_stdout_log,
        ignore_file_log=ignore_file_log,
        md5_salt=md5_salt,
        use_default_cdn=use_default_cdn)
    from .app import app
    if 'port' not in uvicorn_kwargs:
        uvicorn_kwargs['port'] = 9901
    run(app, **uvicorn_kwargs)


def main():
    argv = sys.argv
    if ('-h' in argv or '--help' in argv) and '--' not in argv:
        print(
            '"-h" and "--help" should be after "--", examples:\n > python -m watchdogs -- -h\n > python run_server.py -- -h'
        )
        return
    Fire(start_server)


if __name__ == "__main__":
    main()
