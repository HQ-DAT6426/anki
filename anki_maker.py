"""
╔══════════════════════════════════════════════════════════════╗
║         ANKI FLASHCARD MAKER - English Vocabulary            ║
╚══════════════════════════════════════════════════════════════╝

Cài đặt:
    pip install deep-translator requests gtts tqdm

Nguồn dữ liệu:
    - Free Dictionary API : IPA, audio, loại từ, câu ví dụ EN
    - Google Translate    : Dịch CHÍNH TỪ và câu ví dụ → tiếng Việt
"""

import os
import csv
import time
import requests
from gtts import gTTS
from tqdm import tqdm
from deep_translator import GoogleTranslator

# ─────────────────────────────────────────────
# ⚙️  CẤU HÌNH
# ─────────────────────────────────────────────
INPUT_FILE      = "input.txt"
OUTPUT_CSV      = "anki_results.csv"
MEDIA_DIR       = "collection.media"
REQUEST_TIMEOUT = 10
SLEEP_SEC       = 1

translator = GoogleTranslator(source="en", target="vi")

PART_OF_SPEECH_MAP = {
    "noun": "n", "verb": "v", "adjective": "adj",
    "adverb": "adv", "preposition": "prep", "conjunction": "conj",
    "pronoun": "pron", "interjection": "interj",
    "article": "art", "numeral": "num",
}


# ══════════════════════════════════════════════
# 📖  HÀM 1: ĐỌC DANH SÁCH TỪ
# ══════════════════════════════════════════════
def read_word_list(filepath):
    if not os.path.exists(filepath):
        sample = ["apple", "beautiful", "accomplish", "perseverance", "resilience"]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("# Danh sách từ vựng - mỗi dòng một từ\n")
            f.write("\n".join(sample))
        print(f"⚠️  Chưa có {filepath}. Đã tạo file mẫu.")

    words, seen = [], set()
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w and not w.startswith("#") and w not in seen:
                words.append(w)
                seen.add(w)
    return words


# ══════════════════════════════════════════════
# 🔍  HÀM 2: FREE DICTIONARY API
# ══════════════════════════════════════════════
def fetch_dictionary_data(word):
    """
    Lấy từ Free Dictionary API:
      - ipa       : phiên âm /.../ 
      - audio_url : link mp3 giọng bản xứ
      - pos       : loại từ viết tắt (n, v, adj...)
      - example_en: câu ví dụ tiếng Anh từ từ điển
    """
    result = {"ipa": "", "audio_url": "", "pos": "", "example_en": ""}
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or not data:
            return result

        entry = data[0]

        # ── IPA + Audio ───────────────────────
        for ph in entry.get("phonetics", []):
            t = ph.get("text",  "").strip()
            a = ph.get("audio", "").strip()
            if t and not result["ipa"]:        result["ipa"]       = t
            if a and not result["audio_url"]:  result["audio_url"] = a
            if result["ipa"] and result["audio_url"]:
                break

        # ── Loại từ + Câu ví dụ ──────────────
        for meaning in entry.get("meanings", []):
            pos_raw = meaning.get("partOfSpeech", "").lower()
            pos     = PART_OF_SPEECH_MAP.get(pos_raw, pos_raw[:3])

            if not result["pos"] and pos:
                result["pos"] = pos

            for defn in meaning.get("definitions", []):
                ex = defn.get("example", "").strip()
                if ex and not result["example_en"]:
                    result["example_en"] = ex
                    result["pos"]        = pos  # lấy pos của entry có ví dụ

            if result["example_en"]:
                break

    except requests.exceptions.HTTPError as e:
        if e.response.status_code != 404:
            print(f"\n  ⚠️  Dict API lỗi [{word}]: {e}")
    except Exception as e:
        print(f"\n  ⚠️  Dict API lỗi [{word}]: {e}")

    return result


# ══════════════════════════════════════════════
# 🌐  HÀM 3: GOOGLE TRANSLATE
# ══════════════════════════════════════════════
def translate_to_vi(text):
    """Dịch text tiếng Anh → tiếng Việt. Trả về text gốc nếu lỗi."""
    if not text:
        return ""
    try:
        return translator.translate(text)
    except Exception as e:
        print(f"\n  ⚠️  Google Translate lỗi: {e}")
        return text


# ══════════════════════════════════════════════
# 🔊  HÀM 4: AUDIO
# ══════════════════════════════════════════════
def download_or_create_audio(word, audio_url, media_dir):
    filename = f"{word}.mp3"
    filepath = os.path.join(media_dir, filename)

    if os.path.exists(filepath):
        return filename

    if audio_url:
        try:
            resp = requests.get(audio_url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            return filename
        except Exception:
            pass  # fallback gTTS

    try:
        gTTS(text=word, lang="en", tld="us").save(filepath)
    except Exception as e:
        print(f"\n  ❌  gTTS thất bại [{word}]: {e}")
        return ""
    return filename


# ══════════════════════════════════════════════
# 📝  HÀM 5: GHI CSV
#     Dùng dấu PHẨY + bao ngoặc kép → mở đúng trong Excel
# ══════════════════════════════════════════════
def write_csv(rows, output_path):
    """
    Cột: Từ vựng | Phiên âm | Loại từ & Nghĩa VI | Ví dụ song ngữ | Audio

    Dùng delimiter=',' + quotechar='"' + QUOTE_ALL
    → Excel nhận đúng 5 cột, không bị gộp.
    → Anki import: chọn 'Fields separated by: Comma'
    """
    fields = ["Từ vựng", "Phiên âm", "Loại từ & Nghĩa", "Ví dụ song ngữ", "Audio"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(
            f,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_ALL,   # bao ngoặc kép toàn bộ → Excel đọc đúng
        )
        writer.writerow(fields)      # header

        for row in rows:
            # Loại từ & Nghĩa
            pos_meaning = f"({row['pos']}) {row['meaning_vi']}" if row["pos"] else row["meaning_vi"]

            # Ví dụ song ngữ: EN | VI
            if row["example_en"] and row["example_vi"]:
                example = f"{row['example_en']} | {row['example_vi']}"
            elif row["example_en"]:
                example = row["example_en"]
            else:
                example = ""

            writer.writerow([
                row["word"],
                row["ipa"],
                pos_meaning,
                example,
                f"[sound:{row['audio_file']}]" if row["audio_file"] else "",
            ])


# ══════════════════════════════════════════════
# 🚀  HÀM CHÍNH
# ══════════════════════════════════════════════
def main():
    print("=" * 62)
    print("  🎴  ANKI FLASHCARD MAKER")
    print("  🔍  Nghĩa EN  : Free Dictionary API")
    print("  🌐  Nghĩa VI  : Google Translate (dịch CHÍNH TỪ)")
    print("  🔊  Audio     : Giọng bản xứ hoặc gTTS")
    print("=" * 62)

    words = read_word_list(INPUT_FILE)
    if not words:
        print("❌  Không có từ nào trong input.txt!")
        return

    print(f"\n📋  Tìm thấy {len(words)} từ vựng.\n")
    os.makedirs(MEDIA_DIR, exist_ok=True)

    results, failed = [], []

    for word in tqdm(words, desc="⚙️  Đang xử lý", unit="từ", colour="cyan"):
        row = {
            "word": word, "ipa": "", "pos": "",
            "meaning_vi": "", "example_en": "", "example_vi": "",
            "audio_file": "",
        }

        try:
            # Bước 1: Dictionary API → IPA, audio, loại từ, ví dụ EN
            d = fetch_dictionary_data(word)
            row["ipa"]        = d["ipa"]
            row["pos"]        = d["pos"]
            row["example_en"] = d["example_en"]

            # Bước 2: Google Translate dịch CHÍNH TỪ → nghĩa VI
            row["meaning_vi"] = translate_to_vi(word)

            # Bước 3: Google Translate dịch câu ví dụ → VI
            if d["example_en"]:
                row["example_vi"] = translate_to_vi(d["example_en"])

            # Bước 4: Audio
            row["audio_file"] = download_or_create_audio(
                word, d["audio_url"], MEDIA_DIR
            )

        except Exception as e:
            print(f"\n  ❌  Lỗi [{word}]: {e}")
            failed.append(word)

        results.append(row)
        time.sleep(SLEEP_SEC)

    write_csv(results, OUTPUT_CSV)

    ok = len(results) - len(failed)
    print("\n" + "=" * 62)
    print(f"  ✅  Hoàn thành! {ok}/{len(words)} từ thành công.")
    print(f"  📄  CSV   : ./{OUTPUT_CSV}")
    print(f"  🔊  Audio : ./{MEDIA_DIR}/")
    if failed:
        print(f"\n  ⚠️  Lỗi: {', '.join(failed)}")
    print("=" * 62)
    print("\n📌  MỞ TRONG EXCEL  : double-click file CSV")
    print("📌  IMPORT VÀO ANKI :")
    print("    File → Import → anki_results.csv")
    print("    Fields separated by: Comma\n")


if __name__ == "__main__":
    main()
