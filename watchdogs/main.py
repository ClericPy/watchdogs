import sys
from pathlib import Path
from traceback import format_exc

from fire import Fire
from uvicorn import run

from .settings import Config, NotSet, get_valid_value, init_logger, setup


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


def init_app(db_url=None,
             password=None,
             uninstall=False,
             mute_std_log=NotSet,
             mute_file_log=NotSet,
             md5_salt=None,
             config_dir=None,
             use_default_cdn=False,
             **uvicorn_kwargs):
    try:
        uvicorn_kwargs.setdefault('port', 9901)
        uvicorn_kwargs.setdefault('access_log', True)
        Config.access_log = uvicorn_kwargs['access_log']
        logger = init_logger()
        if config_dir:
            config_dir = Path(config_dir)
            if not config_dir.is_dir():
                config_dir.mkdir()
            Config.CONFIG_DIR = config_dir
        if uninstall:
            return clear_dir(Config.CONFIG_DIR)
        # backward compatibility
        ignore_stdout_log = uvicorn_kwargs.pop('ignore_stdout_log', NotSet)
        Config.mute_std_log = get_valid_value([ignore_stdout_log, mute_std_log],
                                              Config.mute_std_log)
        ignore_file_log = uvicorn_kwargs.pop('ignore_file_log', NotSet)
        Config.mute_file_log = get_valid_value([ignore_file_log, mute_file_log],
                                               Config.mute_file_log)
        Config.uvicorn_kwargs = uvicorn_kwargs
        setup(
            db_url=db_url,
            password=password,
            md5_salt=md5_salt,
            use_default_cdn=use_default_cdn)
        from .app import app
        return app

    except Exception:
        logger.error(f'Start server error:\n{format_exc()}')


def start_app(db_url=None,
              password=None,
              uninstall=False,
              mute_std_log=NotSet,
              mute_file_log=NotSet,
              md5_salt=None,
              config_dir=None,
              use_default_cdn=False,
              **uvicorn_kwargs):
    app = init_app(
        db_url=db_url,
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
