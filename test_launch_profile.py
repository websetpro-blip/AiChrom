import json
import traceback
from proxy.models import Proxy
from worker_chrome import launch_chrome

def main():
    try:
        with open("browser_profiles.json", encoding="utf-8") as f:
            profiles = json.load(f)
        if not profiles:
            print("No profiles found in browser_profiles.json")
            return
        p = profiles[0]
        proxy = None
        if p.get("proxy_host") and p.get("proxy_port"):
            proxy = Proxy(
                scheme=p.get("proxy_scheme") or "http",
                host=p.get("proxy_host"),
                port=int(p.get("proxy_port")),
                username=p.get("proxy_username"),
                password=p.get("proxy_password"),
            )
        print(f"Launching profile id={p.get('id')} host={p.get('proxy_host')}:{p.get('proxy_port')}")
        pid = launch_chrome(
            profile_id=p.get("id"),
            user_agent=p.get("user_agent"),
            lang=p.get("language"),
            tz=p.get("timezone"),
            proxy=proxy,
            extra_flags=None,
            allow_system_chrome=True,
            force_pac=True,  # Force PAC to ensure proxy works even if extension fails
        )
        print("Launched PID:", pid)
    except Exception:
        traceback.print_exc()

if __name__ == '__main__':
    main()


