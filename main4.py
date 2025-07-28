import re
from pyrogram import Client, filters
import sqlite3
from datetime import datetime

api_id = 21526018
api_hash = "030e38cd563d9f9559d218f131e684e9"

channels_to_watch = [
    -1002468383817,  # کانال اول
    -1001982472141   # کانال دوم
]

channels_to_send = [
    -1002468489028,
    -1002103351585,
    -1002268846945,
    -1001600901765,
    -1005555555555
]

def init_db():
    conn = sqlite3.connect("signals.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE,
            received_at TEXT,
            raw_signal TEXT,
            formatted_signal TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_signal(telegram_id, raw_signal, formatted_signal):
    conn = sqlite3.connect("signals.db")
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO signals (telegram_id, received_at, raw_signal, formatted_signal)
            VALUES (?, ?, ?, ?)
        ''', (telegram_id, datetime.now().isoformat(), raw_signal, formatted_signal))
        conn.commit()
    except sqlite3.IntegrityError:
        print("Signal already exists in database, skipping save.")
    conn.close()

def signal_exists(telegram_id):
    conn = sqlite3.connect("signals.db")
    c = conn.cursor()
    c.execute('SELECT 1 FROM signals WHERE telegram_id = ?', (telegram_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def clean_line(line):
    return line.strip()

# ================== کانال دوم ==================

def extract_fields_channel2(text):
    lines = [clean_line(l) for l in text.strip().splitlines() if l.strip()]
    print("LINES (CH2):", lines)
    result = {}

    try:
        # Pair و Position
        m = re.match(r'#?(\w+)\s+(Short|Long)', lines[0], re.IGNORECASE)
        result['Pair'] = m.group(1).upper() if m else '-'
        result['Position'] = m.group(2).upper() if m else '-'

        # Entry (سه مرحله)
        entry = '-'
        m = re.search(r'KATEX_INLINE_OPEN([\d\.]+)KATEX_INLINE_CLOSE', lines[1])
        if m:
            entry = m.group(1)
        if entry == '-':
            m = re.search(r'(\d+\.\d+)', lines[1])
            if m:
                entry = m.group(1)
        if entry == '-':
            for part in lines[1].split():
                if re.match(r'\d+\.\d+', part):
                    entry = part
                    break
        result['Entry'] = entry

        # TP (سه مرحله)
        tps = []
        m = re.search(r'KATEX_INLINE_OPEN([\d\.\-\s]+)KATEX_INLINE_CLOSE', lines[2])
        if m:
            tps = [tp for tp in re.split(r'[-\s]', m.group(1)) if re.match(r'^\d+\.\d+$', tp)]
        if not tps:
            tps = re.findall(r'\d+\.\d+', lines[2])
        if not tps:
            tps = [part for part in lines[2].split() if re.match(r'\d+\.\d+', part)]
        result['TPs'] = tps

        # SL (سه مرحله)
        sl = '-'
        m = re.search(r'SL.*?KATEX_INLINE_OPEN([\d\.]+)KATEX_INLINE_CLOSE', lines[3])
        if m:
            sl = m.group(1)
        if sl == '-':
            m = re.search(r'(\d+\.\d+)', lines[3])
            if m:
                sl = m.group(1)
        if sl == '-':
            for part in lines[3].split():
                if re.match(r'\d+\.\d+', part):
                    sl = part
                    break
        result['SL'] = sl

        # DCA (سه مرحله)
        dca = '-'
        m = re.search(r'DCA\s*=\s*KATEX_INLINE_OPEN([\d\.]+)KATEX_INLINE_CLOSE', lines[3])
        if m:
            dca = m.group(1)
        if dca == '-':
            nums = re.findall(r'\d+\.\d+', lines[3])
            if len(nums) > 1:
                dca = nums[1]
        if dca == '-' and len(lines[3].split()) > 1:
            nums = [part for part in lines[3].split() if re.match(r'\d+\.\d+', part)]
            if len(nums) > 1:
                dca = nums[1]
        result['DCA'] = dca

    except Exception as e:
        print("Error extracting channel2 signal:", e)
        print("LINES:", lines)
        return None

    print("DEBUG CH2: Entry:", result['Entry'], "TPs:", result['TPs'], "SL:", result['SL'], "DCA:", result['DCA'])

    if result['Entry'] == '-' or not result['TPs'] or result['SL'] == '-':
        print("❌ Signal fields not complete! Not sending.")
        return None

    return result

def format_signal_channel2(fields):
    if not fields:
        return "Error extracting signal!"
    tps = "\n".join([f"🎯 {tp}" for tp in fields['TPs']]) if fields.get('TPs') else ""
    dca = f"\n🟡 DCA: {fields['DCA']}" if fields.get('DCA') and fields['DCA'] != '-' else ""
    return f"""• Trade Setup Ready! 🪧
--------------------------
📊 Position: {fields['Position']}
🛒 Pair: {fields['Pair']}
🛫 Entry: {fields['Entry']}
{tps}
🚫 SL: {fields['SL']}{dca}
"""

def is_channel2_signal(text):
    lines = [clean_line(l) for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 4:
        return False
    if not re.match(r'#?\w+\s+(Short|Long)', lines[0], re.IGNORECASE):
        return False
    if not "Entry Market Price" in lines[1]:
        return False
    if not "TP" in lines[2]:
        return False
    if not "SL" in lines[3]:
        return False
    return True

# ================== کانال اول (همان کد قبلی) ==================

def extract_decimal(line):
    m = re.match(r'^(\d+)[KATEX_INLINE_CLOSE\.\-\s]*([0-9]+\.[0-9]+)', line)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r'([0-9]+\.[0-9]+)', line)
    if m:
        return m.group(1)
    return None

def extract_fields(text):
    lines = [clean_line(l) for l in text.strip().splitlines() if l.strip()]
    print("LINES:", lines)
    result = {}
    try:
        result['Pair'] = lines[0]
        result['Position'] = lines[1].replace("#", "")
        result['Leverage'] = lines[2].split(":")[-1].strip()
        entry_index = next(i for i, l in enumerate(lines) if "entry target" in l.lower().replace("-", "").replace("_", ""))
        entry_lines = []
        for i in range(1, 4):
            if entry_index + i < len(lines):
                line = lines[entry_index + i]
                val = extract_decimal(line)
                if val:
                    entry_lines.append(val)
                else:
                    break
        result['Entry'] = ", ".join(entry_lines)
        tp_index = next(i for i, l in enumerate(lines) if "takeprofit" in l.lower().replace("-", "").replace(" ", ""))
        try:
            sl_index = next(i for i, l in enumerate(lines) if "stoploss" in l.lower().replace("-", "").replace(" ", ""))
        except StopIteration:
            sl_index = len(lines)
        tp_lines = []
        for i in range(tp_index + 1, sl_index):
            line = lines[i]
            val = extract_decimal(line)
            if val:
                tp_lines.append(val)
        result['TPs'] = tp_lines
        sl_line = next((l for l in lines if "stoploss" in l.lower().replace("-", "").replace(" ", "")), None)
        result['SL'] = extract_decimal(sl_line) if sl_line else "-"
    except Exception as e:
        print("Error extracting signal:", e)
        print("LINES:", lines)
        return None
    return result

def format_signal(fields):
    if not fields:
        return "Error extracting signal!"
    tps = "\n".join([f"🎯 {tp}" for tp in fields['TPs']]) if fields.get('TPs') else ""
    lev = f"\n⚖️ Leverage: {fields['Leverage']}" if fields.get('Leverage') else ""
    return f"""• Trade Setup Ready! 🪧
--------------------------
📊 Position: {fields['Position']}
🛒 Pair: {fields['Pair']}{lev}
🛫 Entry: {fields['Entry']}
{tps}
🚫 SL: {fields['SL']}
"""

# ================== هندل پیام ==================

app = Client("my_account", api_id, api_hash)

@app.on_message(filters.channel & filters.chat(channels_to_watch))
def handle_signal(client, message):
    unique_id = f"{message.chat.id}_{message.id}"

    if signal_exists(unique_id):
        print("Duplicate message, skipped (already in database).")
        return

    # متن پیام یا کپشن عکس
    text = message.text or message.caption
    if text:
        if is_channel2_signal(text):
            print("Channel 2 signal detected!")
            fields = extract_fields_channel2(text)
            if not fields:
                print("❌ Signal fields not complete or extraction failed. Not sending.")
                return
            clean_output = format_signal_channel2(fields)
        else:
            print("Channel 1 signal detected!")
            fields = extract_fields(text)
            if not fields:
                print("❌ Signal fields not complete or extraction failed. Not sending.")
                return
            clean_output = format_signal(fields)

        print("Formatted signal:\n", clean_output)
        if not clean_output.strip():
            print("Extracted output was empty, not sending.")
            return
        save_signal(unique_id, text, clean_output)
        for ch in channels_to_send:
            try:
                client.send_message(ch, clean_output)
                print(f"Sent to channel: {ch}")
            except Exception as e:
                print(f"Error sending to channel {ch}: {e}")
    else:
        print("No text found.")

if __name__ == "__main__":
    print("Bot is running...")
    init_db()
    app.run()