"""
╔══════════════════════════════════════════════════════════════╗
║       ANKI PHRASE MAKER - Từ vựng & Cụm từ tiếng Nhật      ║
╚══════════════════════════════════════════════════════════════╝

Cài đặt:
    pip install deep-translator gtts tqdm

Cách dùng:
    1. Thêm từ/cụm từ vào input_ja.txt (mỗi dòng một từ)
       Định dạng hỗ trợ:
         - Chỉ từ:               こんにちは
         - Kèm phiên âm:         こんにちは | Konnichiwa
         - Kèm nghĩa sẵn:        こんにちは = Xin chào (ban ngày)
         - Đầy đủ:               こんにちは | Konnichiwa = Xin chào (ban ngày)
    2. Chạy: python anki_ja.py
    3. Import anki_ja.csv vào Anki (Tab-separated)
    4. Copy thư mục collection.media/ vào Anki profile
"""

import os
import re
import csv
import time
# import requests
from gtts import gTTS
from tqdm import tqdm
from deep_translator import GoogleTranslator

# ─────────────────────────────────────────────
# ⚙️  CẤU HÌNH
# ─────────────────────────────────────────────
INPUT_FILE  = "input_ja.txt"
OUTPUT_CSV  = "anki_ja.csv"
MEDIA_DIR   = "collection.media"
SLEEP_SEC   = 1          # nghỉ giữa các từ (tránh rate-limit Google)
MAX_RETRIES = 3          # số lần thử lại khi gTTS / Translate gặp lỗi
RETRY_WAIT  = 2          # giây chờ giữa mỗi lần retry

translator = GoogleTranslator(source="ja", target="vi")


# ══════════════════════════════════════════════
# 🔧  HÀM TIỆN ÍCH: TẠO SLUG TÊN FILE
# ══════════════════════════════════════════════
def to_slug(phrase: str) -> str:
    """
    Chuyển từ tiếng Nhật thành tên file an toàn (slug).
    Vì ký tự Nhật không an toàn làm tên file, dùng mã hóa hex UTF-8.
    Ví dụ:
        "こんにちは"  → e3818ae3‥ (hex của UTF-8 bytes)
        "ありがとう"  → e3818ae3‥
    """
    # Thử xem có phải toàn ASCII không (phiên âm romaji)
    try:
        phrase.encode("ascii")
        slug = phrase.lower().strip()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = re.sub(r"_+", "_", slug)
        slug = slug.strip("_")
        return slug or "unknown"
    except UnicodeEncodeError:
        pass

    # Chứa ký tự Nhật → dùng hex bytes làm tên file
    encoded = phrase.encode("utf-8").hex()
    # Giới hạn độ dài tên file (tránh path quá dài)
    return "ja_" + encoded[:60]


# ══════════════════════════════════════════════
# 📖  HÀM 1: ĐỌC DANH SÁCH TỪ
# ══════════════════════════════════════════════
def read_phrases(filepath: str) -> list:
    """
    Đọc input_ja.txt, trả về danh sách từ đã làm sạch.
    Định dạng dòng hỗ trợ:
        こんにちは
        こんにちは = Xin chào (ban ngày)
    - Bỏ qua dòng trống và dòng bắt đầu bằng #
    - Loại bỏ trùng lặp, giữ nguyên thứ tự
    """
    if not os.path.exists(filepath):
        print(f"❌  Không tìm thấy file {filepath}!")
        return []

    entries, seen = [], set()
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            # Tách nghĩa tiếng Việt nếu có dấu "="
            kanji = ""
            inline_meaning = ""
            amthanh = ""
            if "=" in raw:
                parts          = raw.split("=", 3)
                if len(parts) == 4:
                    raw            = parts[0].strip()
                    kanji          = parts[1].strip()
                    inline_meaning = parts[2].strip()
                    amthanh = parts[3].strip()
                else:
                    raw            = parts[0].strip()
                    inline_meaning = parts[1].strip()
                    amthanh = parts[2].strip()

            phrase = " ".join(raw.split())

            if not phrase:
                continue

            key = phrase
            if key not in seen:
                entries.append({
                    "phrase"        : phrase,
                    "kanji"         : kanji,
                    "inline_meaning": inline_meaning,
                    "amthanh"       : amthanh,
                })
                seen.add(key)

    return entries


# ══════════════════════════════════════════════
# 🌐  HÀM 2: DỊCH TỪ TIẾNG NHẬT → TIẾNG VIỆT
# ══════════════════════════════════════════════
def translate_phrase(phrase: str) -> str:
    """
    Dịch từ/cụm từ tiếng Nhật sang tiếng Việt qua Google Translate.
    Retry tối đa MAX_RETRIES lần nếu gặp lỗi mạng.
    Trả về từ gốc nếu thất bại hoàn toàn.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = translator.translate(phrase)
            if result and result.strip():
                return result.strip()
        except Exception as e:
            print(f"\n  ⚠️  Translate lỗi [{phrase}] lần {attempt}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)

    print(f"\n  ❌  Không dịch được [{phrase}]. Giữ nguyên tiếng Nhật.")
    return phrase


# ══════════════════════════════════════════════
# 🔊  HÀM 3: TẠO AUDIO BẰNG voicevox và gTTS (giọng Nhật)
# ══════════════════════════════════════════════
# Các hằng số cấu hình nên được đặt ở ngoài hoặc truyền qua tham số
VOICEVOX_URL = "http://127.0.0.1:50021"
SPEAKER_ID = 1
MAX_RETRIES = 3
RETRY_WAIT = 1
"""
def create_audio_voicevox(phrase: str, media_dir: str) -> str:
    
    Tạo file wav cho từ tiếng Nhật bằng Voicevox Local Engine.
    - Trả về tên file wav nếu thành công, "" nếu thất bại.
   
    slug = to_slug(phrase)
    filename = f"{slug}.wav"  # Chú ý: Đổi sang .wav
    filepath = os.path.join(media_dir, filename)

    # File đã tồn tại và có nội dung → dùng lại
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return filename

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # --- BƯỚC 1: AUDIO QUERY ---
            query_payload = {"text": phrase, "speaker": SPEAKER_ID}
            res_query = requests.post(
                f"{VOICEVOX_URL}/audio_query", 
                params=query_payload,
                timeout=5  # Ép ngắt kết nối nếu server treo quá 5s
            )
            res_query.raise_for_status()  # Ném lỗi ngay nếu HTTP Code != 200

            audio_query_data = res_query.json()

            # --- BƯỚC 2: SYNTHESIS ---
            synth_payload = {"speaker": SPEAKER_ID}
            res_synth = requests.post(
                f"{VOICEVOX_URL}/synthesis", 
                params=synth_payload, 
                json=audio_query_data,
                timeout=15  # Quá trình tổng hợp mất nhiều thời gian hơn
            )
            res_synth.raise_for_status()

            # --- LƯU FILE ---
            with open(filepath, "wb") as f:
                f.write(res_synth.content)

            # Kiểm tra hậu kiểm dung lượng file
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return filename

            print(f"\n  ⚠️  Voicevox tạo file rỗng [{phrase}] lần {attempt}/{MAX_RETRIES}")

        except requests.exceptions.RequestException as e:
            # Bắt riêng lỗi mạng (Network/HTTP Errors) để log chi tiết hơn
            print(f"\n  ⚠️  Lỗi kết nối Voicevox [{phrase}] lần {attempt}/{MAX_RETRIES}: {e}")
        except Exception as e:
            print(f"\n  ⚠️  Lỗi hệ thống [{phrase}] lần {attempt}/{MAX_RETRIES}: {e}")

        # Dọn dẹp file rỗng/lỗi trước khi retry
        if os.path.exists(filepath):
            os.remove(filepath)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_WAIT)

    print(f"\n  ❌  Không tạo được audio [{phrase}] sau {MAX_RETRIES} lần thử.")
    return ""
"""
def create_audio(phrase: str, media_dir: str) -> str:
    """
    Tạo file mp3 cho từ tiếng Nhật bằng gTTS (lang="ja").
    - Tên file theo slug an toàn từ hex UTF-8
    - Retry tối đa MAX_RETRIES lần
    - Kiểm tra file > 0 byte sau khi tạo
    Trả về tên file mp3 nếu thành công, "" nếu thất bại.
    """
    slug     = to_slug(phrase)
    filename = f"{slug}.mp3"
    filepath = os.path.join(media_dir, filename)

    # File đã tồn tại và có nội dung → dùng lại
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return filename

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tts = gTTS(text=phrase, lang="ja")
            tts.save(filepath)

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return filename

            print(f"\n  ⚠️  gTTS tạo file rỗng [{phrase}] lần {attempt}/{MAX_RETRIES}")

        except Exception as e:
            print(f"\n  ⚠️  gTTS lỗi [{phrase}] lần {attempt}/{MAX_RETRIES}: {e}")

        if os.path.exists(filepath):
            os.remove(filepath)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_WAIT)

    print(f"\n  ❌  Không tạo được audio [{phrase}] sau {MAX_RETRIES} lần thử.")
    return ""


# ══════════════════════════════════════════════
# 📝  HÀM 4: GHI FILE CSV
# ══════════════════════════════════════════════
def write_csv(rows: list, output_path: str):
    """
    Xuất file CSV định dạng Tab-separated, UTF-8.
    Cột: Từ tiếng Nhật | kanji | Nghĩa tiếng Việt | [sound:file.mp3]

    Dùng Tab + QUOTE_MINIMAL → Anki đọc đúng từng cột.
    """
    fields = ["Từ tiếng Nhật","kanji","hana", "Nghĩa tiếng Việt", "Audio"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(
            f,
            delimiter="\t",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writerow(fields)

        for row in rows:
            audio_tag = f"[sound:{row['audio_file']}]" if row["audio_file"] else ""
            writer.writerow([
                row["phrase"],
                row["kanji"],
                row["hana"],
                row["meaning_vi"],
                audio_tag,
            ])


# ══════════════════════════════════════════════
# 🚀  HÀM CHÍNH
# ══════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  🎴  ANKI PHRASE MAKER - TIẾNG NHẬT")
    print("  🌐  Dịch nghĩa : Google Translate (deep-translator)")
    print("  🔊  Audio      : gTTS giọng Nhật (lang=ja)")
    print("  📄  Output     : Tab-separated CSV")
    print("=" * 60)

    # ── Bước 1: Đọc danh sách ────────────────
    entries = read_phrases(INPUT_FILE)
    if not entries:
        print("❌  Không có từ nào trong input_ja.txt!")
        return

    print(f"\n📋  Tìm thấy {len(entries)} từ/cụm từ.\n")

    # ── Bước 2: Tạo thư mục media ────────────
    os.makedirs(MEDIA_DIR, exist_ok=True)

    results = []
    failed  = []

    # ── Bước 3: Xử lý từng từ ────────────────
    for entry in tqdm(entries, desc="⚙️  Đang xử lý", unit="từ", colour="cyan"):
        phrase         = entry["phrase"]
        kanji          = entry["kanji"]
        inline_meaning = entry["inline_meaning"]
        amthanh = entry["amthanh"]
        row = {
            "phrase"    : amthanh,
            "kanji"     : kanji,
            "hana"      : phrase,
            "meaning_vi": "",
            "audio_file": "",
        }

        try:
            # 3a. Dùng nghĩa có sẵn nếu có, không thì gọi Google Translate
            if inline_meaning:
                row["meaning_vi"] = inline_meaning
            else:
                row["meaning_vi"] = translate_phrase(phrase)

            # 3b. Tạo audio mp3 giọng Nhật
            row["audio_file"] = create_audio(amthanh, MEDIA_DIR)

        except Exception as e:
            print(f"\n  ❌  Lỗi không xác định [{phrase}]: {e}")
            failed.append(phrase)

        results.append(row)
        time.sleep(SLEEP_SEC)

    # ── Bước 4: Ghi CSV ──────────────────────
    write_csv(results, OUTPUT_CSV)

    # ── Tổng kết ─────────────────────────────
    ok       = len(results) - len(failed)
    no_audio = [r["phrase"] for r in results if not r["audio_file"]]

    print("\n" + "=" * 60)
    print(f"  ✅  Hoàn thành! {ok}/{len(entries)} từ thành công.")
    print(f"  📄  CSV   : ./{OUTPUT_CSV}")
    print(f"  🔊  Audio : ./{MEDIA_DIR}/  ({len(results) - len(no_audio)} file mp3)")
    if no_audio:
        print(f"\n  ⚠️  Không có audio: {', '.join(no_audio)}")
    if failed:
        print(f"  ❌  Lỗi hoàn toàn : {', '.join(failed)}")
    

if __name__ == "__main__":
    main()
