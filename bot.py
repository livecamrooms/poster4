import os
import requests
import time
from atproto import Client, client_utils
from datetime import datetime

# === CONFIG ===
MAX_POSTS_PER_RUN = int(os.getenv('MAX_POSTS_PER_RUN', 4))
WM_CODE = os.getenv('WM_CODE', 'T2CSW')  # your affiliate code

def get_accounts():
    accounts = []
    for i in [1, 2]:
        handle = os.getenv(f'BLUESKY_HANDLE{i}')
        password = os.getenv(f'BLUESKY_PASSWORD{i}')
        if handle and password:
            accounts.append((handle, password))
    if not accounts:
        handle = os.getenv('BLUESKY_HANDLE')
        password = os.getenv('BLUESKY_PASSWORD')
        if handle and password:
            accounts.append((handle, password))
    return accounts

def get_public_ip():
    try:
        return requests.get('https://api.ipify.org?format=json', timeout=5).json()['ip']
    except Exception:
        print("⚠️ Could not fetch public IP, using fallback")
        return "0.0.0.0"

def get_niche_label(room):
    age = room.get('age')
    tags_lower = [t.lower() for t in room.get('tags', [])]
    country = (room.get('country') or '').upper()

    if age in (18, '18'):
        return "18yo"
    for kw in ['latina', 'blonde', 'petite', 'pinay', 'french']:
        if kw in tags_lower:
            return kw.capitalize()
    if country == 'FR':
        return "French"
    if country == 'PH':
        return "Pinay"
    return "Hot"

def post_to_bluesky(client, room):
    try:
        img_resp = requests.get(room['image_url_360x270'], timeout=10)
        img_resp.raise_for_status()
        img_bytes = img_resp.content

        niche = get_niche_label(room)
        subject = room.get('room_subject', '')[:70] + '...' if len(room.get('room_subject', '')) > 70 else room.get('room_subject', '')

        tb = client_utils.TextBuilder()
        tb.text(f"🔥 {niche} LIVE NOW ({room.get('num_users', 0)} watching)\n\n")
        tb.text(f"{room.get('username')} • {room.get('age') or '?'} • {room.get('country') or '??'}\n")
        tb.text(f"{subject}\n\n")
        tb.link("👉 Watch FREE", room['chat_room_url_revshare'])
        tb.text("\n\n")

        tb.tag("#nsfw", "nsfw")
        tb.text(" ")
        tb.tag(f"#{niche.lower()}", niche.lower())
        tb.text(" ")
        tb.tag("#nsfwsky", "nsfwsky")
        tb.text(" ")
        tb.tag("#LiveCams", "LiveCams")
        tb.text(" ")
        tb.tag("#Adult", "Adult")

        for tag in room.get('tags', [])[:5]:
            clean = tag.strip().replace(' ', '')
            if clean and len(clean) > 2:
                tb.text(" ")
                tb.tag(f"#{clean.title()}", clean.title())

        client.send_image(
            text=tb,
            image=img_bytes,
            image_alt=f"Live HD thumbnail of {niche} {room.get('username')} - {subject[:50]}"
        )
        print(f"✅ Posted: {niche} - {room.get('username')}")
        return True
    except Exception as e:
        print(f"❌ Error posting {room.get('username', 'unknown')}: {e}")
        return False

def main():
    accounts = get_accounts()
    if not accounts:
        print("❌ No Bluesky credentials found!")
        return

    print(f"🚀 Starting bot for {len(accounts)} Bluesky account(s)")

    # === Fetch rooms (new API + client_ip + limit) ===
    try:
        client_ip = get_public_ip()
        api_url = "https://chaturbate.com/api/public/affiliates/onlinerooms/"
        params = {
            'format': 'json',
            'wm': WM_CODE,
            'client_ip': client_ip,
            'limit': 500,          # ← important: get more rooms
            'gender': 'f'          # ← server-side filter (we only want females)
        }
        resp = requests.get(api_url, params=params, timeout=15)
        data = resp.json()

        # === NEW: Handle wrapped response format {"results": [...]} ===
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        elif isinstance(data, dict):
            print("❌ Unexpected API format (dict without 'results'):", list(data.keys()))
            return

        print(f"📡 Fetched {len(data)} rooms from Chaturbate")
    except Exception as e:
        print(f"❌ Failed to fetch Chaturbate rooms: {e}")
        return

    # === Filter ===
    filtered = [
        room for room in data
        if isinstance(room, dict) and
           room.get('gender') == 'f' and
           room.get('current_show') == 'public' and
           room.get('is_hd') is True and
           int(room.get('num_users', 0)) >= 30 and
           (room.get('age') in (18, '18') or
            any(kw in [t.lower() for t in room.get('tags', [])]
                for kw in ['latina', 'blonde', 'petite', 'pinay', 'french']) or
            room.get('country') in ['FR', 'PH'])
    ]

    filtered.sort(key=lambda x: int(x.get('num_users', 0)), reverse=True)
    print(f"✅ {len(filtered)} matching rooms found")

    # === Post to each account ===
    for handle, password in accounts:
        print(f"\n🔑 Logging into {handle}...")
        try:
            client = Client()
            client.login(handle, password)
            posted = 0
            for room in filtered[:MAX_POSTS_PER_RUN]:
                if post_to_bluesky(client, room):
                    posted += 1
                    time.sleep(12)
                else:
                    time.sleep(5)
            print(f"✅ Finished {handle} — {posted} posts")
        except Exception as e:
            print(f"❌ Login or posting failed for {handle}: {e}")

    print(f"\n🏁 Full run finished at {datetime.now().isoformat()}")

if __name__ == "__main__":
    main()
