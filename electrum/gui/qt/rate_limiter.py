



from functools import wraps
import threading
import time
import weakref

from PyQt6.QtCore import QObject, QTimer

from electrum.logging import Logger, get_logger


_logger = get_logger(__name__)


class RateLimiter(Logger):


    last_ts = 0.0
    timer = None
    saved_args = (tuple(),dict())
    ctr = 0

    def __init__(self, rate, ts_after, obj, func):
        self.n = func.__name__
        self.qn = func.__qualname__
        self.rate = rate
        self.ts_after = ts_after
        self.obj = weakref.ref(obj)
        self.func = func
        Logger.__init__(self)


    def diagnostic_name(self):
        return "{}:{}".format("rate_limited",self.qn)

    def kill_timer(self):
        if self.timer:

            try:
                self.timer.stop()
                self.timer.deleteLater()
            except RuntimeError as e:
                if 'c++ object' in str(e).lower():




                    self.logger.debug("advisory: QTimer was already deleted by Qt, ignoring...")
                else:
                    raise
            finally:
                self.timer = None

    @classmethod
    def attr_name(cls, func): return "__{}__{}".format(func.__name__, cls.__name__)

    @classmethod
    def invoke(cls, rate, ts_after, func, args, kwargs):

        assert args and isinstance(args[0], object), "@rate_limited decorator may only be used with object instance methods"
        assert threading.current_thread() is threading.main_thread(), "@rate_limited decorator may only be used with functions called in the main thread"
        obj = args[0]
        a_name = cls.attr_name(func)

        rl = getattr(obj, a_name, None)
        if rl is None:

            rl = cls(rate, ts_after, obj, func)
            setattr(obj, a_name, rl)
        return rl._invoke(args, kwargs)

    def _invoke(self, args, kwargs):
        self._push_args(args, kwargs)
        self.ctr += 1

        if not self.timer:
            now = time.time()
            diff = float(self.rate) - (now - self.last_ts)
            if diff <= 0:


                return self._doIt()
            else:

                self.timer = QTimer(self.obj() if isinstance(self.obj(), QObject) else None)
                self.timer.timeout.connect(self._doIt)

                self.timer.setSingleShot(True)
                self.timer.start(int(diff*1e3))

        else:


            pass


    def _pop_args(self):
        args, kwargs = self.saved_args
        self.saved_args = (tuple(),dict())
        return args, kwargs

    def _push_args(self, args, kwargs):
        self.saved_args = (args, kwargs)

    def _doIt(self):

        t0 = time.time()
        args, kwargs = self._pop_args()

        ctr0 = self.ctr
        retval = self.func(*args, **kwargs)
        was_reentrant = self.ctr != ctr0
        del args, kwargs
        tf = time.time()
        time_taken = tf-t0
        if self.ts_after:
            self.last_ts = tf
        else:
            if time_taken > float(self.rate):
                self.logger.debug(f"method took too long: {time_taken} > {self.rate}. Fudging timestamps to compensate.")
                self.last_ts = tf
            else:
                self.last_ts = t0

        if self.timer:
            if was_reentrant:

                self.logger.debug("*** detected a re-entrant call, re-starting timer")
                time_left = float(self.rate) - (tf - self.last_ts)
                self.timer.start(time_left*1e3)
            else:

                self.kill_timer()
        elif was_reentrant:
            self.logger.debug("*** detected a re-entrant call")

        return retval


class RateLimiterClassLvl(RateLimiter):


    @classmethod
    def invoke(cls, rate, ts_after, func, args, kwargs):
        assert args and not isinstance(args[0], type), "@rate_limited decorator may not be used with static or class methods"
        obj = args[0]
        objcls = obj.__class__
        args = list(args)
        args.insert(0, objcls)
        return super(RateLimiterClassLvl, cls).invoke(rate, ts_after, func, args, kwargs)

    def _push_args(self, args, kwargs):
        objcls, obj = args[0:2]
        args = args[2:]
        self.saved_args[obj] = (args, kwargs)

    def _pop_args(self):
        weak_dict = self.saved_args
        self.saved_args = weakref.WeakKeyDictionary()
        return (weak_dict,),dict()

    def _call_func_for_all(self, weak_dict):
        for ref in weak_dict.keyrefs():
            obj = ref()
            if obj:
                args,kwargs = weak_dict[obj]
                obj_name = obj.diagnostic_name() if hasattr(obj, "diagnostic_name") else obj

                self.func_target(obj, *args, **kwargs)

    def __init__(self, rate, ts_after, obj, func):

        super().__init__(rate, ts_after, obj, func)
        self.func_target = func
        self.func = self._call_func_for_all
        self.saved_args = weakref.WeakKeyDictionary()


def rate_limited(rate, *, classlevel=False, ts_after=False):

    def wrapper0(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if classlevel:
                return RateLimiterClassLvl.invoke(rate, ts_after, func, args, kwargs)
            return RateLimiter.invoke(rate, ts_after, func, args, kwargs)
        return wrapper
    return wrapper0

