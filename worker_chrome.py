        user_agent=user_agent,
        lang=language,
        tz=timezone,
        proxy=proxy_obj,
        extra_flags=extra,
        allow_system_chrome=True,
        force_pac=False,
        browser_path=browser_path,
    )
    log.info("Chrome launched with PID %s", pid)
    # For legacy compatibility return a dummy object-like wrapper
    class _Proc:
        def __init__(self, pid_: int) -> None:
            self.pid = pid_
    return _Proc(pid)

def self_test_proxy(proxy: Proxy = DEFAULT_PROXY) -> bool:
    result = _proxy_self_test(proxy)
    return result is not None

if __name__ == "__main__":
    if self_test_proxy():
        log.info("Proxy self-test passed.")
        proc = launch_chrome(
            profile_id="test_profile",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            lang="en-US",
            tz="America/New_York",
            proxy=DEFAULT_PROXY,
            extra_flags=["--window-size=1920,1080"],
        )
        log.info("Chrome launched with PID %s", proc)
    else:
        log.error("Proxy self-test failed. Check your proxy configuration.")
