"""
╔══════════════════════════════════════════════════════════════╗
║       ANKI PHRASE MAKER - Cụm từ & Thành ngữ tiếng Anh     ║
╚══════════════════════════════════════════════════════════════╝

Cài đặt:
    pip install deep-translator gtts tqdm

Cách dùng:
    1. Thêm cụm từ vào input.txt (mỗi dòng một cụm)
    2. Chạy: python anki_phrases.py
    3. Import anki_phrases.csv vào Anki (Tab-separated)
    4. Copy thư mục collection.media/ vào Anki profile
"""

import os
import re
import csv
import time
from gtts import gTTS
from tqdm import tqdm
from deep_translator import GoogleTranslator

# ─────────────────────────────────────────────
# ⚙️  CẤU HÌNH
# ─────────────────────────────────────────────
INPUT_FILE  = "input.txt"
OUTPUT_CSV  = "anki_phrases.csv"
MEDIA_DIR   = "collection.media"
SLEEP_SEC   = 1          # nghỉ giữa các cụm từ (tránh rate-limit Google)
MAX_RETRIES = 3          # số lần thử lại khi gTTS / Translate gặp lỗi
RETRY_WAIT  = 2          # giây chờ giữa mỗi lần retry

translator = GoogleTranslator(source="en", target="vi")


# ══════════════════════════════════════════════
# 🔧  HÀM TIỆN ÍCH: TẠO SLUG TÊN FILE
# ══════════════════════════════════════════════
def to_slug(phrase: str) -> str:
    """
    Chuyển cụm từ thành tên file an toàn (slug).
    Ví dụ:
        "call it a day"      → call_it_a_day
        "it's a piece of cake" → its_a_piece_of_cake
        "25/7 hustle"        → 25_7_hustle
    Quy tắc:
        - Chuyển về chữ thường
        - Thay ký tự đặc biệt (không phải chữ/số) → dấu gạch dưới
        - Loại bỏ dấu gạch dưới thừa ở đầu/cuối và liên tiếp
    """
    slug = phrase.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)   # thay ký tự đặc biệt → _
    slug = re.sub(r"_+", "_", slug)            # loại _ trùng
    slug = slug.strip("_")                     # loại _ đầu/cuối
    return slug


# ══════════════════════════════════════════════
# 📖  HÀM 1: ĐỌC DANH SÁCH CỤM TỪ
# ══════════════════════════════════════════════
def read_phrases(filepath: str) -> list:
    """
    Đọc input.txt, trả về danh sách cụm từ đã làm sạch.
    - Bỏ qua dòng trống và dòng bắt đầu bằng #
    - Chuẩn hóa khoảng cách giữa các từ
    - Loại bỏ trùng lặp, giữ nguyên thứ tự
    """
    if not os.path.exists(filepath):
        # Tạo file mẫu nếu chưa có
        samples = [
            "# Phrasal Verbs",
            "give up",
            "break down",
            "look forward to",
            "run out of",
            "# Idioms",
            "call it a day",
            "hit the nail on the head",
            "once in a blue moon",
            "bite the bullet",
            "spill the beans",
        ]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(samples))
        print(f"⚠️  Chưa có {filepath}. Đã tạo file mẫu với {len([s for s in samples if not s.startswith('#')])} cụm từ.")

    entries, seen = [], set()
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            # Tách cụm từ và nghĩa nếu có dấu "="
            if "=" in raw:
                parts       = raw.split("=", 1)          # chỉ tách tại dấu = đầu tiên
                phrase      = " ".join(parts[0].strip().split())
                inline_mean = parts[1].strip()
            else:
                phrase      = " ".join(raw.split())
                inline_mean = ""                          # cần gọi translate

            if not phrase:
                continue

            key = phrase.lower()
            if key not in seen:
                entries.append({"phrase": phrase, "inline_meaning": inline_mean})
                seen.add(key)

    return entries


# ══════════════════════════════════════════════
# 🌐  HÀM 2: DỊCH CỤM TỪ → TIẾNG VIỆT
# ══════════════════════════════════════════════
def translate_phrase(phrase: str) -> str:
    """
    Dịch cụm từ sang tiếng Việt qua Google Translate.
    Retry tối đa MAX_RETRIES lần nếu gặp lỗi mạng.
    Trả về cụm từ gốc nếu thất bại hoàn toàn.
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

    # Fallback: giữ nguyên cụm từ gốc
    print(f"\n  ❌  Không dịch được [{phrase}]. Giữ nguyên tiếng Anh.")
    return phrase


# ══════════════════════════════════════════════
# 🔊  HÀM 3: TẠO AUDIO BẰNG gTTS
# ══════════════════════════════════════════════
def create_audio(phrase: str, media_dir: str) -> str:
    """
    Tạo file mp3 cho cụm từ bằng gTTS (giọng Mỹ).
    - Tên file theo dạng slug: "call it a day" → call_it_a_day.mp3
    - Retry tối đa MAX_RETRIES lần
    - Kiểm tra file > 0 byte sau khi tạo
    Trả về tên file mp3 nếu thành công, "" nếu thất bại.
    """
    slug     = to_slug(phrase)
    filename = f"{slug}.mp3"
    filepath = os.path.join(media_dir, filename)

    # File đã tồn tại và có nội dung → dùng lại, không tạo thêm
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return filename

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            tts = gTTS(text=phrase, lang="en", tld="co.uk")
            tts.save(filepath)

            # Xác nhận file có nội dung (tránh file 0 byte)
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                return filename

            print(f"\n  ⚠️  gTTS tạo file rỗng [{phrase}] lần {attempt}/{MAX_RETRIES}")

        except Exception as e:
            print(f"\n  ⚠️  gTTS lỗi [{phrase}] lần {attempt}/{MAX_RETRIES}: {e}")

        # Xóa file lỗi trước khi thử lại
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
    Cột: Cụm từ | Nghĩa tiếng Việt | [sound:file.mp3]

    Dùng Tab + QUOTE_MINIMAL → Anki đọc đúng từng cột,
    không bị lỗi gộp cột như khi dùng dấu phẩy.
    """
    fields = ["Cụm từ", "Nghĩa tiếng Việt", "Audio"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(
            f,
            delimiter="\t",          # Tab — chuẩn của Anki
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writerow(fields)

        for row in rows:
            audio_tag = f"[sound:{row['audio_file']}]" if row["audio_file"] else ""
            writer.writerow([
                row["phrase"],
                row["meaning_vi"],
                audio_tag,
            ])


# ══════════════════════════════════════════════
# 🚀  HÀM CHÍNH
# ══════════════════════════════════════════════
def main():
    print("=" * 60)
    print("  🎴  ANKI PHRASE MAKER")
    print("  🌐  Dịch nghĩa : Google Translate (deep-translator)")
    print("  🔊  Audio      : gTTS giọng Anh (lang=en, tld=co.uk)")
    print("  📄  Output     : Tab-separated CSV")
    print("=" * 60)

    # ── Bước 1: Đọc danh sách ────────────────
    entries = read_phrases(INPUT_FILE)
    if not entries:
        print("❌  Không có cụm từ nào trong input.txt!")
        return

    print(f"\n📋  Tìm thấy {len(entries)} cụm từ.\n")

    # ── Bước 2: Tạo thư mục media ────────────
    os.makedirs(MEDIA_DIR, exist_ok=True)

    results  = []
    failed   = []

    # ── Bước 3: Xử lý từng cụm từ ────────────
    for entry in tqdm(entries, desc="⚙️  Đang xử lý", unit="cụm", colour="green"):
        phrase        = entry["phrase"]
        inline_meaning = entry["inline_meaning"]

        row = {
            "phrase"    : phrase,
            "meaning_vi": "",
            "audio_file": "",
        }

        try:
            # 3a. Dùng nghĩa có sẵn nếu có, không thì gọi Google Translate
            if inline_meaning:
                row["meaning_vi"] = inline_meaning
            else:
                row["meaning_vi"] = translate_phrase(phrase)

            # 3b. Tạo audio mp3
            row["audio_file"] = create_audio(phrase, MEDIA_DIR)

        except Exception as e:
            print(f"\n  ❌  Lỗi không xác định [{phrase}]: {e}")
            failed.append(phrase)

        results.append(row)
        time.sleep(SLEEP_SEC)

    # ── Bước 4: Ghi CSV ──────────────────────
    write_csv(results, OUTPUT_CSV)

    # ── Tổng kết ─────────────────────────────
    ok = len(results) - len(failed)
    no_audio = [r["phrase"] for r in results if not r["audio_file"]]

    print("\n" + "=" * 60)
    print(f"  ✅  Hoàn thành! {ok}/{len(entries)} cụm từ thành công.")
    print(f"  📄  CSV   : ./{OUTPUT_CSV}")
    print(f"  🔊  Audio : ./{MEDIA_DIR}/  ({len(results) - len(no_audio)} file mp3)")
    if no_audio:
        print(f"\n  ⚠️  Không có audio: {', '.join(no_audio)}")
    if failed:
        print(f"  ❌  Lỗi hoàn toàn : {', '.join(failed)}")
    print("=" * 60)
    print("\n📌  IMPORT VÀO ANKI:")
    print("  1. Mở Anki → File → Import")
    print("  2. Chọn file anki_phrases.csv")
    print("  3. Type: Basic | Separator: Tab")
    print("  4. Map: Field 1 → Front, Field 2 → Back, Field 3 → Back")
    print("  5. Copy toàn bộ file trong collection.media/")
    print("     vào thư mục collection.media của Anki profile\n")


if __name__ == "__main__":
    main()
