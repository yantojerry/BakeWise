import threading


def run_in_thread(widget, worker, on_success=None, on_error=None, is_current=None):
    def should_deliver():
        if not getattr(widget, "winfo_exists", lambda: False)():
            return False
        return is_current() if callable(is_current) else True

    def deliver(callback, *args):
        if callback is None or not should_deliver():
            return

        def runner():
            if not should_deliver():
                return
            callback(*args)

        try:
            widget.after(0, runner)
        except Exception:
            return

    def background_runner():
        try:
            result = worker()
        except Exception as exc:
            deliver(on_error, exc)
        else:
            deliver(on_success, result)

    threading.Thread(target=background_runner, daemon=True).start()
