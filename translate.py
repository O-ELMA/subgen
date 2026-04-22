import os
import re
import sys
import time
import argparse

from dotenv import load_dotenv
import httpx

load_dotenv()

NANOGPT_MODEL = "moonshotai/kimi-k2.5"
NANOGPT_URL = "https://nano-gpt.com/api/v1/chat/completions"
NANOGPT_API_KEY = os.getenv("NANO_GPT_KEY")

LANGUAGES = {
    "ar": "Arabic",
    "nl": "Dutch",
    "es": "Spanish",
    "fr": "French",
}

BATCH_SIZE = 125

TRANSLATION_PROMPT = """You are a professional translator specializing in Islamic content.
Translate the following subtitle text from English (with interspersed Arabic) to {language}.

Rules:
1. Translate ALL English text into natural, fluent {language}.
2. Translate ALL Arabic text into natural, fluent {language}.
3. Preserve the exact meaning — this is Islamic content and accuracy is critical.
4. Keep the same number of subtitle entries and their numbering.
5. Keep multi-line subtitles as multi-line (preserve line breaks within entries).
6. Separate each subtitle entry with "---" on its own line, matching the input format.
7. Return ONLY the translated subtitles with their numbers, nothing else."""


def parse_srt(srt_path):
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())
    subtitles = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue

        try:
            index = int(lines[0].strip())
        except ValueError:
            continue

        timestamp_match = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            lines[1].strip(),
        )
        if not timestamp_match:
            continue

        start_time = timestamp_match.group(1)
        end_time = timestamp_match.group(2)
        text = "\n".join(lines[2:])

        subtitles.append({
            "index": index,
            "start": start_time,
            "end": end_time,
            "text": text,
        })

    return subtitles


def write_srt(subtitles, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, sub in enumerate(subtitles, 1):
            f.write(f"{i}\n")
            f.write(f"{sub['start']} --> {sub['end']}\n")
            f.write(f"{sub['text']}\n\n")


def llm_call(messages, model=None, max_retries=5):
    model = model or NANOGPT_MODEL
    headers = {
        "Authorization": f"Bearer {NANOGPT_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    last_exception = None
    for attempt in range(max_retries):
        try:
            resp = httpx.post(NANOGPT_URL, json=payload, headers=headers, timeout=600)
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"]
            return result
        except (httpx.RemoteProtocolError, httpx.NetworkError, httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exception = exc
            wait = 2 ** attempt
            print(f"  LLM call failed ({exc}), retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
    raise last_exception


def format_batch_for_translation(subtitles, start_idx):
    lines = []
    for sub in subtitles:
        lines.append(f"[{sub['index']}] {sub['text']}")
        lines.append("---")
    return "\n".join(lines)


def parse_translated_batch(translated_text, original_subtitles):
    pattern = re.compile(r"\[(\d+)\]\s*(.*)")
    translated_map = {}
    blocks = translated_text.strip().split("---")

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        block_lines = block.split("\n")
        header = block_lines[0].strip()
        m = pattern.match(header)
        if not m:
            continue
        idx = int(m.group(1))
        first_line = m.group(2).strip()
        rest = [l.strip() for l in block_lines[1:] if l.strip()]
        text = "\n".join([first_line] + rest)
        translated_map[idx] = text

    result = []
    for sub in original_subtitles:
        new_sub = dict(sub)
        if sub["index"] in translated_map:
            new_sub["text"] = translated_map[sub["index"]]
        else:
            new_sub["text"] = sub["text"]
        result.append(new_sub)

    return result


def translate_batch(subtitles, lang_code):
    system_prompt = TRANSLATION_PROMPT.format(language=LANGUAGES[lang_code])
    batch_text = format_batch_for_translation(subtitles, subtitles[0]["index"])

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": batch_text},
    ]

    translated = llm_call(messages)
    return parse_translated_batch(translated, subtitles)


def translate_srt(srt_path, lang_code, output_path=None):
    if output_path is None:
        base, ext = os.path.splitext(srt_path)
        output_path = f"{base}.{lang_code}{ext}"

    subtitles = parse_srt(srt_path)
    if not subtitles:
        print(f"  No subtitles found in {srt_path}")
        return output_path

    total = len(subtitles)
    all_translated = []

    for i in range(0, total, BATCH_SIZE):
        batch = subtitles[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Translating batch {batch_num}/{total_batches} ({len(batch)} subtitles)")

        translated_batch = translate_batch(batch, lang_code)
        all_translated.extend(translated_batch)

    write_srt(all_translated, output_path)
    print(f"  Saved: {output_path}")
    return output_path


def collect_srt_files(path):
    path = os.path.abspath(path)
    srt_ext = ".srt"

    if os.path.isfile(path):
        if path.lower().endswith(srt_ext):
            return [path]
        print(f"❌ Error: unsupported file format '{os.path.splitext(path)[1]}'")
        sys.exit(1)

    if os.path.isdir(path):
        files = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if f.lower().endswith(srt_ext) and os.path.isfile(os.path.join(path, f))
        )
        if not files:
            print(f"❌ No .srt files found in '{path}'")
            sys.exit(1)
        return files

    print(f"❌ Error: path does not exist '{path}'")
    sys.exit(1)


def main():
    lang_list = ", ".join(f"{k}={v}" for k, v in LANGUAGES.items())
    parser = argparse.ArgumentParser(
        prog="TRANSLATE",
        description="Translate .srt subtitle files from English (with Arabic) to a target language.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to an .srt file or directory containing .srt files",
    )
    parser.add_argument(
        "--lang", "-l",
        required=True,
        choices=LANGUAGES.keys(),
        help=f"Target language ({lang_list})",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output path (only valid for single file input)",
    )

    args = parser.parse_args()

    if args.path is None:
        parser.print_help()
        sys.exit(0)

    srt_files = collect_srt_files(args.path)

    if args.output and len(srt_files) > 1:
        print("❌ Error: --output can only be used with a single file input")
        sys.exit(1)

    lang_name = LANGUAGES[args.lang]
    total_files = len(srt_files)

    for idx, srt_path in enumerate(srt_files, 1):
        print(f"[{idx}/{total_files}] Translating: {srt_path} -> {lang_name}")
        output = args.output if args.output and len(srt_files) == 1 else None
        translate_srt(srt_path, args.lang, output)

    print(f"Done! Translated {total_files} file(s) to {lang_name}.")


if __name__ == "__main__":
    main()