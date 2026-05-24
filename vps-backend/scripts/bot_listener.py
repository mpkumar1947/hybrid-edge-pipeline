#!/usr/bin/env python3
import time, requests, json, logging, re, urllib.parse, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE = Path.home() / 'torrent-hybrid'
LOG_FILE = BASE / 'logs/bot_listener.log'

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def load_config():
    return {
        "bot_token"      : os.getenv("BOT_TOKEN"),
        "chat_id"        : os.getenv("CHAT_ID"),
        "qbit_user"      : os.getenv("QBIT_USER"),
        "qbit_pass"      : os.getenv("QBIT_PASS")
    }

def add_torrent(cfg, magnet):
    url = 'http://localhost:6969/api/v2/torrents/add'
    data = {'urls': magnet}
    try:
        resp = requests.post(url, data=data, auth=(cfg['qbit_user'], cfg['qbit_pass']), timeout=10)
        return resp.status_code == 200
    except Exception as e:
        log.error(f'Failed to add torrent: {e}')
        return False

def main():
    cfg = load_config()
    token = cfg['bot_token']
    chat_id = int(cfg['chat_id'])
    offset = 0
    
    log.info('Bot listener started...')
    
    while True:
        try:
            url = f'https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=30'
            resp = requests.get(url, timeout=35).json()
            
            if not resp.get('ok'):
                time.sleep(5)
                continue
                
            for update in resp.get('result', []):
                offset = update['update_id'] + 1
                msg = update.get('message', {})
                text = msg.get('text', '')
                from_id = msg.get('from', {}).get('id')
                
                if from_id != chat_id:
                    continue
                
                # Check for magnet or torrent links
                if text.startswith('magnet:?') or text.endswith('.torrent') or 't.me/torrent' in text:
                    log.info(f'Received link: {text[:50]}...')
                    if add_torrent(cfg, text):
                        requests.post(f'https://api.telegram.org/bot{token}/sendMessage', data={
                            'chat_id': chat_id,
                            'text': '✅ *Torrent added successfully!*',
                            'parse_mode': 'Markdown'
                        })
                    else:
                        requests.post(f'https://api.telegram.org/bot{token}/sendMessage', data={
                            'chat_id': chat_id,
                            'text': '❌ *Failed to add torrent. Check logs.*',
                            'parse_mode': 'Markdown'
                        })
                elif text == '/start':
                    requests.post(f'https://api.telegram.org/bot{token}/sendMessage', data={
                        'chat_id': chat_id,
                        'text': '👋 *Torrent Hybrid Bot Active*\nSend me a magnet link to start downloading.',
                        'parse_mode': 'Markdown'
                    })
                    
        except Exception as e:
            log.error(f'Polling error: {e}')
            time.sleep(5)

if __name__ == '__main__':
    main()
