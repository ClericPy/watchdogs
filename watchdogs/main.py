import sys

from fire import Fire
from uvicorn import run

from .config import NotSet, ensure_dir
from .settings import Config, get_valid_value, setup


def clear_dir(dir_path):
    if not dir_path.is_dir():
        print(f'Dir is not exist: {dir_path}.')
        return True
    print(f'Cleaning {dir_path}...')
    for f in dir_path.iterdir():
        if f.is_dir():
            clear_dir(f)
        else:
            f.unlink()
            print(f'File removed: {f}')
    dir_path.rmdir()
    print(f'Folder removed: {dir_path}')


def init_app(db_url=None,
             password=None,
             uninstall=False,
             mute_std_log=NotSet,
             mute_file_log=NotSet,
             md5_salt=None,
             config_dir=None,
             use_default_cdn=False,
             **uvicorn_kwargs):
    if config_dir:
        Config.CONFIG_DIR = ensure_dir(config_dir)
    if uninstall:
        clear_dir(Config.CONFIG_DIR)
        sys.exit('Config dir cleared.')
    # backward compatibility for ignore_stdout_log & ignore_file_log
    Config.mute_std_log = get_valid_value(
        [uvicorn_kwargs.pop('ignore_stdout_log', NotSet), mute_std_log],
        Config.mute_std_log)
    Config.mute_file_log = get_valid_value(
        [uvicorn_kwargs.pop('ignore_file_log', NotSet), mute_file_log],
        Config.mute_file_log)
    # update by given uvicorn_kwargs
    Config.uvicorn_kwargs.update(uvicorn_kwargs)
    if db_url:
        # update by given db_url
        Config.db_url = db_url
    Config.password = password
    Config.md5_salt = md5_salt or ''
    setup(use_default_cdn=use_default_cdn)
    from .app import app
    return app


def start_app(db_url=None,
              password=None,
              uninstall=False,
              mute_std_log=NotSet,
              mute_file_log=NotSet,
              md5_salt=None,
              config_dir=None,
              use_default_cdn=False,
              **uvicorn_kwargs):
    app = init_app(db_url=db_url,
                   password=password,
                   uninstall=uninstall,
                   mute_std_log=mute_std_log,
                   mute_file_log=mute_file_log,
                   md5_salt=md5_salt,
                   config_dir=config_dir,
                   use_default_cdn=use_default_cdn,
                   **uvicorn_kwargs)
    run(app, **Config.uvicorn_kwargs)


def main():
    argv = sys.argv
    if ('-h' in argv or '--help' in argv) and '--' not in argv:
        print(
            '"-h" and "--help" should be after "--", examples:\n > python -m watchdogs -- -h\n > python run_server.py -- -h'
        )
        return
    Fire(start_app)


if __name__ == "__main__":
    main()
