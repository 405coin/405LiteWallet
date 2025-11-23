                                            
                                                                  
                                                                    

import logging
import logging.handlers
import datetime
import sys
import pathlib
import os
import platform
from typing import Optional, TYPE_CHECKING, Set
import copy
import subprocess
import hashlib

if TYPE_CHECKING:
    from .simple_config import SimpleConfig


class LogFormatterForFiles(logging.Formatter):

    def formatTime(self, record, datefmt=None):
                                        
        date = datetime.datetime.fromtimestamp(record.created).astimezone(datetime.timezone.utc)
        if not datefmt:
            datefmt = "%Y%m%dT%H%M%S.%fZ"
        return date.strftime(datefmt)

    def format(self, record):
        record = _shorten_name_of_logrecord(record)
        return super().format(record)


file_formatter = LogFormatterForFiles(fmt="%(asctime)22s | %(levelname)8s | %(name)s | %(message)s")


class LogFormatterForConsole(logging.Formatter):

    def formatTime(self, record, datefmt=None):
        t = record.relativeCreated / 1000
        return f"{t:6.2f}"

    def format(self, record):
        record = copy.copy(record)                      
        record = _shorten_name_of_logrecord(record)
        text = super().format(record)
        return text


                                                                                      
console_formatter = LogFormatterForConsole(fmt="%(asctime)s | %(levelname).1s | %(name)s | %(message)s")


def _shorten_name_of_logrecord(record: logging.LogRecord) -> logging.LogRecord:
    record = copy.copy(record)                      
                                                     
    if record.name.startswith("electrum."):
        record.name = record.name[9:]
                                               
    record.name = record.name.replace("interface.Interface", "interface", 1)
    record.name = record.name.replace("network.Network", "network", 1)
    record.name = record.name.replace("synchronizer.Synchronizer", "synchronizer", 1)
    record.name = record.name.replace("verifier.SPV", "verifier", 1)
    record.name = record.name.replace("gui.qt.main_window.ElectrumWindow", "gui.qt.main_window", 1)
    return record


class TruncatingMemoryHandler(logging.handlers.MemoryHandler):
    """An in-memory log handler that only keeps the first N log messages
    and discards the rest.
    """
    target: Optional['logging.Handler']

    def __init__(self):
        logging.handlers.MemoryHandler.__init__(
            self,
            capacity=1,                                                       
            flushLevel=logging.DEBUG,
        )
        self.max_size = 100                               
        self.num_messages_seen = 0
        self.__never_dumped = True

                                                                                      
    def flush(self):
        self.acquire()
        try:
            if self.target:
                for record in self.buffer:
                    if record.levelno >= self.target.level:
                        self.target.handle(record)
        finally:
            self.release()

    def dump_to_target(self, target: 'logging.Handler'):
        self.acquire()
        try:
            self.setTarget(target)
            self.flush()
            self.setTarget(None)
        finally:
            self.__never_dumped = False
            self.release()

    def emit(self, record):
        self.num_messages_seen += 1
        if len(self.buffer) < self.max_size:
            super().emit(record)

    def close(self) -> None:
                                                                          
                                                                                 
        if self.__never_dumped:
            _configure_stderr_logging()
        super().close()


def _delete_old_logs(path, *, num_files_keep: int, max_total_size: int):
    """Delete old logfiles, only keeping the latest few."""
    def sortkey_oldest_first(p: pathlib.PurePath):
        fname = p.name
        basename, ext, counter = str(fname).partition(".log")
                                                                                         
                                                                                           
                                                                              
        try:
            counter = int(counter[1:]) if counter else 0                     
        except ValueError:
            _logger.warning(f"failed to parse log file name: {fname}")
            counter = 0
        return basename, -counter
    files = sorted(
        list(pathlib.Path(path).glob("electrum_log_*.log*")),
        key=sortkey_oldest_first,
    )
    total_size = sum(os.stat(f).st_size for f in files)            
    num_files_remaining = len(files)
    for f in files:
        fsize = os.stat(f).st_size
        if total_size < max_total_size and num_files_remaining <= num_files_keep:
            break
        total_size -= fsize
        num_files_remaining -= 1
        try:
            os.remove(f)
        except OSError as e:
            _logger.warning(f"cannot delete old logfile: {e}")


_logfile_path = None
def _configure_file_logging(
    log_directory: pathlib.Path,
    *,
    num_files_keep: int,
    max_total_size: int,
):
    from .util import os_chmod

    global _logfile_path
    assert _logfile_path is None, 'file logging already initialized'
    log_directory.mkdir(exist_ok=True, mode=0o700)

    _delete_old_logs(log_directory, num_files_keep=num_files_keep, max_total_size=max_total_size)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    PID = os.getpid()
    _logfile_path = log_directory / f"electrum_log_{timestamp}_{PID}.log"
                                                                                         
    with open(_logfile_path, "w+") as f:
        os_chmod(_logfile_path, 0o600)

    logfile_backupcount = 4
    file_handler = logging.handlers.RotatingFileHandler(
        _logfile_path,
        maxBytes=max_total_size // (logfile_backupcount+1),
        backupCount=logfile_backupcount,
        encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    if _inmemory_startup_logs:
        _inmemory_startup_logs.dump_to_target(file_handler)


console_stderr_handler = None
def _configure_stderr_logging(*, verbosity=None):
                                                       
    global console_stderr_handler
    if console_stderr_handler is not None:
        _logger.warning("stderr handler already exists")
        return
    console_stderr_handler = logging.StreamHandler(sys.stderr)
    console_stderr_handler.setFormatter(console_formatter)
    if not verbosity:
        console_stderr_handler.setLevel(logging.WARNING)
        root_logger.addHandler(console_stderr_handler)
    else:
        console_stderr_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(console_stderr_handler)
        _process_verbosity_log_levels(verbosity)
    if _inmemory_startup_logs:
        _inmemory_startup_logs.dump_to_target(console_stderr_handler)


def _process_verbosity_log_levels(verbosity):
    if verbosity == '*' or not isinstance(verbosity, str):
        return
                        
                                                                                                
                                                                                                
    filters = verbosity.split(',')
    for filt in filters:
        if not filt: continue
        items = filt.split('=')
        if len(items) == 1:
            level = items[0]
            electrum_logger.setLevel(level.upper())
        elif len(items) == 2:
            logger_name, level = items
            logger = get_logger(logger_name)
            logger.setLevel(level.upper())
        else:
            raise Exception(f"invalid log filter: {filt}")


class _CustomLogger(logging.getLoggerClass()):
    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)
        self.msg_hashes_seen = set()                    
                                                                                      

    def _log(self, level, msg: str, *args, only_once: bool = False, **kwargs) -> None:
        """Overridden to add 'only_once' arg to logger.debug()/logger.info()/logger.warning()/etc."""
        if only_once:                                                                                 
            msg_hash = hashlib.sha256(msg.encode("utf-8")).digest()
            if msg_hash in self.msg_hashes_seen:
                return
            self.msg_hashes_seen.add(msg_hash)
        super()._log(level, msg, *args, **kwargs)

logging.setLoggerClass(_CustomLogger)


                                                         
root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)

                                                                                  
                                                                                     
                                                                                   
                                                                                   
                                                                                          
                    
                                                                                        
                                                                          
                                                                          
                                                  
_inmemory_startup_logs = None
if getattr(sys, "_FOURZEROFIVE_RUNNING_VIA_LAUNCHER", False):
    _inmemory_startup_logs = TruncatingMemoryHandler()
    root_logger.addHandler(_inmemory_startup_logs)

                                                    
electrum_logger = logging.getLogger("electrum")
electrum_logger.setLevel(logging.DEBUG)


                  

def get_logger(name: str) -> _CustomLogger:
    prefix = "electrum."
    if name.startswith(prefix):
        name = name[len(prefix):]
    return electrum_logger.getChild(name)


_logger = get_logger(__name__)
_logger.setLevel(logging.INFO)


class Logger:

    def __init__(self):
        self.logger = self.__get_logger_for_obj()

    def __get_logger_for_obj(self) -> logging.Logger:
        cls = self.__class__
        if cls.__module__:
            name = f"{cls.__module__}.{cls.__name__}"
        else:
            name = cls.__name__
        try:
            diag_name = self.diagnostic_name()
        except Exception as e:
            raise Exception("diagnostic name not yet available?") from e
        if diag_name:
            name += f".[{diag_name}]"
        logger = get_logger(name)
        return logger

    def diagnostic_name(self):
        return ''


def configure_logging(config: 'SimpleConfig', *, log_to_file: Optional[bool] = None) -> None:
    from .util import is_android_debug_apk

    verbosity = config.get('verbosity')
    if not verbosity and config.GUI_ENABLE_DEBUG_LOGS:
        verbosity = '*'
    _configure_stderr_logging(verbosity=verbosity)

    if log_to_file is None:
        log_to_file = config.WRITE_LOGS_TO_DISK
        log_to_file |= is_android_debug_apk()
    if log_to_file:
        log_directory = pathlib.Path(config.path) / "logs"
        num_files_keep = config.LOGS_NUM_FILES_KEEP
        max_total_size = config.LOGS_MAX_TOTAL_SIZE_BYTES
        _configure_file_logging(log_directory, num_files_keep=num_files_keep, max_total_size=max_total_size)

                                        
    global _inmemory_startup_logs
    if _inmemory_startup_logs:
        num_discarded = _inmemory_startup_logs.num_messages_seen - _inmemory_startup_logs.max_size
        if num_discarded > 0:
            _logger.warning(f"Too many log messages! Some have been discarded. "
                            f"(discarded {num_discarded} messages)")
        _inmemory_startup_logs.close()
        root_logger.removeHandler(_inmemory_startup_logs)
        _inmemory_startup_logs = None

    from . import ELECTRUM_VERSION
    from .constants import GIT_REPO_URL
    _logger.info(f"Electrum version: {ELECTRUM_VERSION} - https://electrum.org - {GIT_REPO_URL}")
    _logger.info(f"Python version: {sys.version}. On platform: {describe_os_version()}")
    _logger.info(f"Logging to file: {str(_logfile_path)}")
    _logger.info(f"Log filters: verbosity {repr(verbosity)}")


def get_logfile_path() -> Optional[pathlib.Path]:
    return _logfile_path


def describe_os_version() -> str:
    if 'ANDROID_DATA' in os.environ:
        import jnius
        bv = jnius.autoclass('android.os.Build$VERSION')
        b = jnius.autoclass('android.os.Build')
        return "Android {} on {} {} ({})".format(bv.RELEASE, b.BRAND, b.DEVICE, b.DISPLAY)
    else:
        return platform.platform()


def get_git_version() -> Optional[str]:
    dir = os.path.dirname(os.path.realpath(__file__))
    try:
        version = subprocess.check_output(
            ['git', 'describe', '--always', '--dirty'], cwd=dir)
        version = str(version, "utf8").strip()
    except Exception:
        version = None
    return version
