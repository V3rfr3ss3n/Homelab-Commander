"""Fixed remote argv runner; no shell, bootstrap or unbounded output retention."""

COMMAND_SCRIPT = r"""
import json, os, selectors, subprocess, sys, time
request = json.loads(sys.argv[1])
process = None
try:
    environment = dict(os.environ, LC_ALL='C', LANG='C')
    deadline = time.monotonic() + request['timeout']
    process = subprocess.Popen(request['argv'], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               env=environment)
    data = bytearray()
    overflow = False
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            for key, _ in selector.select(min(remaining, 0.5)):
                chunk = key.fileobj.read1(65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                elif len(data) + len(chunk) <= 2097152:
                    data.extend(chunk)
                else:
                    overflow = True
    code = process.wait(timeout=max(0.001, deadline - time.monotonic()))
    text = '' if overflow else data.decode('utf-8', errors='strict')
    print(json.dumps({'rc': -2 if overflow else code, 'stdout': text}))
except (OSError, TimeoutError, subprocess.TimeoutExpired, UnicodeError):
    print(json.dumps({'rc': -1, 'stdout': ''}))
finally:
    if process is not None:
        if process.poll() is None:
            process.kill()
            process.wait()
        if process.stdout is not None:
            process.stdout.close()
"""
