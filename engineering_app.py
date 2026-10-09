"""Opt-in additive launcher: preserve legacy Flask/bot features and its single poller.
Do not run alongside main.py or engineering_telegram.py polling the same token.
"""
import os
import threading
import time
import engineering_telegram as engineering


def start_engineering(bot, owner):
    before = len(bot.message_handlers)
    engineering.install_handlers(bot, owner)
    # Put explicit new commands before any legacy catch-all; keep all existing handlers.
    bot.message_handlers[:] = bot.message_handlers[before:] + bot.message_handlers[:before]

    def cycle():
        while True:
            try:
                with engineering.LOCK:
                    engineering.refresh()
                    engineering.dispatch(bot, owner)
            except Exception as exc:
                # Deliberate external SDK/source boundary: retain the scheduler
                # after a recorded failure; never treat it as successful delivery.
                print(f'Engineering scan/delivery failed: {type(exc).__name__}', flush=True)
            time.sleep(max(900, int(os.environ.get('ENGINEERING_INTERVAL_SECONDS', '3600'))))
    threading.Thread(target=cycle, name='EngineeringSearch', daemon=True).start()


def main():
    # Import existing application only at launch, never during offline helper tests.
    from dotenv import load_dotenv
    load_dotenv(override=False)
    owner = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not owner or not owner.isdigit():
        raise SystemExit('Set a positive private TELEGRAM_CHAT_ID before launch')
    import main as legacy
    start_engineering(legacy.bot, owner)
    # Exactly the existing supervisor/poller path, not a second infinity_polling call.
    threading.Thread(target=legacy.thread_supervisor, name='ThreadSupervisor', daemon=True).start()
    # Deliberate container ingress binding, not a claim this Flask server is hardened.
    # Hugging Face's proxy must reach port 7860; loopback would break that deployment.
    # Deploy only behind the platform proxy with existing access controls reviewed;
    # do not expose this development server directly on an untrusted network.
    legacy.app.run(host='0.0.0.0', port=7860, use_reloader=False)


if __name__ == '__main__':
    main()
