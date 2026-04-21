import os
import re
import sys
import time
import json
import pprint
import argparse
import traceback
import unicodedata
import difflib

from dotenv import load_dotenv
import httpx
import torch
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from qwen_asr import Qwen3ASRModel

load_dotenv()

LANGUAGE = "English"
DEVICE = "cpu"
MODEL_ID = "Qwen/Qwen3-ASR-1.7B"
ALIGNER_ID = "Qwen/Qwen3-ForcedAligner-0.6B"
MAX_BATCH_SIZE = 32
MAX_NEW_TOKENS = 4096
OUTPUT_DIR = "output"

AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".opus",
    ".m4a", ".wma", ".aiff", ".alac", ".wv", ".tta",
})
VIDEO_EXTENSIONS = frozenset({
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpeg", ".mpg", ".3gp", ".ts",
})

NANOGPT_MODEL = "moonshotai/kimi-k2.5"
NANOGPT_URL = "https://nano-gpt.com/api/v1/chat/completions"
NANOGPT_API_KEY = os.getenv("NANO_GPT_KEY")

DST_LANGUAGE = "Arabic"

SYSTEM_PROMPT = """You are correcting ASR transcription output for Islamic lectures in English with interspersed Arabic.

Rules:
1. Preserve the original language of every word — do NOT translate anything.
   - Arabic words stay in Arabic script.
   - English words stay in English.
2. Convert any transliterated Arabic back to original Arabic script (e.g. "Al-Karim" → "الكريم", "Subhanahu Wa Ta'ala" → "سبحانه و تعالى", "Alhamdulillah" → "الحمد لله", "Insha'Allah" → "إن شاء الله", "SubhanAllah" → "سبحان الله", "Allahu Akbar" → "الله أكبر", "Bismillah" → "بسم الله").
3. Replace "صلى الله عليه وسلم" with "ﷺ".
4. Fix any obvious ASR misrecognitions while keeping the meaning and language intact.
5. Return ONLY the corrected text, nothing else."""


TRANSLATION_SYSTEM_PROMPT = """You are translating English text to {dst_language}.
Keeping the meaning intact.
Return ONLY the translated text, nothing else."""

TIMESTAMPS_SYSTEM_PROMPT = """Given original text with timestamps and translated text, generate new timestamps for the translated text.
Each line must follow this format exactly:
<start_time>|<end_time>|<translated_word>
Return ONLY the timestamp lines, nothing else."""


def chunk_audio(audio_path):
    audio = AudioSegment.from_file(audio_path)
    target_length = 3 * 60 * 1000
    
    chunks = []
    start = 0
    total_length = len(audio)
    
    i = 0
    while start < total_length:
        end = min(start + target_length, total_length)
        
        if end < total_length:
            search_start = max(start, end - 15000)
            audio_to_search = audio[search_start:end]
            
            non_silent_ranges = detect_nonsilent(audio_to_search, min_silence_len=500, silence_thresh=-40)
            
            if non_silent_ranges:
                end = search_start + non_silent_ranges[-1][1] + 250
        
        chunk = audio[start:end]
        chunk_path = f"/tmp/chunk_{i}.wav"
        chunk.export(chunk_path, format="wav")
        
        chunks.append({"path": chunk_path, "duration_sec": len(chunk) / 1000.0})
        
        start = end
        i += 1
        
    return chunks


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
            print(f"⚠️ LLM call failed ({exc}), retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)
    raise last_exception


def process_result(text):
    result = llm_call(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
    )
    return result


def realign_timestamps(corrected_text, original_items, time_offset=0.0):
    orig_words = []
    for item in original_items:
        text = item.text.strip().replace('\n', ' ')
        if not text:
            continue
        sub_words = text.split()
        if len(sub_words) == 1:
            orig_words.append({
                "text": text,
                "start_time": item.start_time + time_offset,
                "end_time": item.end_time + time_offset,
            })
        else:
            duration = item.end_time - item.start_time
            total_chars = sum(_visual_len(w) for w in sub_words)
            start = item.start_time + time_offset
            for i, w in enumerate(sub_words):
                w_len = _visual_len(w)
                w_duration = duration * (w_len / total_chars) if total_chars > 0 else duration / len(sub_words)
                end = start + w_duration if i < len(sub_words) - 1 else item.end_time + time_offset
                orig_words.append({
                    "text": w,
                    "start_time": start,
                    "end_time": end,
                })
                start += w_duration

    # Split corrected text into words
    corrected_words = corrected_text.split()

    if not orig_words or not corrected_words:
        return []

    # Use SequenceMatcher to align original and corrected word sequences
    orig_texts = [w["text"] for w in orig_words]
    matcher = difflib.SequenceMatcher(None, orig_texts, corrected_words, autojunk=False)

    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Direct 1:1 mapping — preserve original timestamps exactly
            for i, j in zip(range(i1, i2), range(j1, j2)):
                result.append({
                    "text": corrected_words[j],
                    "start_time": orig_words[i]["start_time"],
                    "end_time": orig_words[i]["end_time"],
                })

        elif tag == 'replace':
            # Original words were corrected — distribute time proportionally
            n_orig = i2 - i1
            n_new = j2 - j1
            total_start = orig_words[i1]["start_time"]
            total_end = orig_words[i2 - 1]["end_time"]
            total_duration = total_end - total_start

            for idx, j in enumerate(range(j1, j2)):
                frac_start = idx / n_new
                frac_end = (idx + 1) / n_new
                result.append({
                    "text": corrected_words[j],
                    "start_time": total_start + total_duration * frac_start,
                    "end_time": total_start + total_duration * frac_end,
                })

        elif tag == 'insert':
            # New words added by correction — interpolate from neighbors
            prev_end = orig_words[i1 - 1]["end_time"] if i1 > 0 else (orig_words[0]["start_time"] if orig_words else 0.0)
            next_start = orig_words[i1]["start_time"] if i1 < len(orig_words) else prev_end + 1.0
            available = next_start - prev_end
            n_inserted = j2 - j1
            word_duration = available / (n_inserted + 1)

            for idx, j in enumerate(range(j1, j2)):
                start = prev_end + word_duration * idx
                result.append({
                    "text": corrected_words[j],
                    "start_time": start,
                    "end_time": start + word_duration,
                })

        # 'delete' tag: original words removed — skip them

    return result


def merge_results(processed_texts, realigned_timestamps):
    merged_text = ""
    merged_items = []

    for idx, (text, items) in enumerate(zip(processed_texts, realigned_timestamps)):
        merged_text += text
        merged_items.extend(items)

    result = {
        "text": merged_text,
        "time_stamps": merged_items,
    }
    return result


ORPHAN_WORDS = frozenset({
    # Articles & Basic Prepositions
    "the","a","an","of","in","to","for","on","at","by","with","from","into","upon","about","above","after","against","along","among","around","before","behind","below","beneath","beside","between","beyond","down","during","except","inside","near","off","out","outside","over","through","under","until","without",
    # Conjunctions
    "and","but","not","so","or","if","as","than","then","because","since","although","though","unless","while","where","when","why","how",
    # Pronouns & Determiners
    "it","its","that","this","these","those","they","he","she","we","you","me","him","her","us","them","my","your","yours","our","ours","their","theirs","whose","which","what","some","any","every","all","both","neither","either","no",
    # Verbs (Auxiliary & To Be)
    "is","are","was","were","am","be","been","being","do","did","does","has","had","have",
    # Modals
    "can","could","shall","should","will","would","may","might","must",
    # Contractions
    "it's","i'm","don't","won't","can't","isn't","aren't","you're","he's","she's","we're","they're","i've","you've","we've","they've","i'll","you'll","he'll","she'll","we'll","they'll","i'd","you'd","he'd","she'd","we'd","they'd","that's","who's","what's","where's","there's","here's","couldn't","shouldn't","wouldn't","hasn't","haven't","hadn't","doesn't","didn't","wasn't","weren't",
    # Arabic Connectors, Prepositions, and Pronouns
    "في","من","إلى","على","عن","و","ف","ب","ل","ك","ال","هل","لم","لن","قد","ما","أن","إن","هو","هي","هم",
    "أو","ثم","حتى","لكن","بين","مع","عند","مثل","هذا","هذه","ذلك","تلك","كل","بعض","غير","إلا"
})
SENTENCE_ENDS = frozenset({".", "!", "?", "؟", "。", "！"})
MAX_TIME_GAP = 3.0
MIN_DURATION = 0.5 # Minimum seconds a subtitle must stay on screen to avoid "flashing"
MIN_GAP_BETWEEN_SUBS = 0.05 # Minimum gap between consecutive blocks to allow the eye to register a change


def _is_rtl(text):
    return bool(re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]', text))


def _visual_len(text):
    return sum(1 for c in text if unicodedata.category(c) != "Mn")


def _is_sentence_end(word):
    w = word.rstrip("\")'»】］〕〉》」』")
    return bool(w) and w[-1] in SENTENCE_ENDS


def _is_orphan(word):
    clean = word.strip('",.!?;:()\'"…').lower()
    return clean in ORPHAN_WORDS


def _block_visual_len(indices, words):
    if not indices:
        return 0
    total = words[indices[0]]["visual_len"]
    for i in indices[1:]:
        total += 1 + words[i]["visual_len"]
    return total


def _greedy_format(block, words, max_chars_per_line, max_lines):
    lines, line = [], [block[0]]
    line_len = words[block[0]]["visual_len"]

    for idx in block[1:]:
        w = words[idx]
        new_len = line_len + 1 + w["visual_len"]
        if new_len <= max_chars_per_line or not line:
            line.append(idx)
            line_len = new_len
        elif len(lines) < max_lines - 1:
            lines.append(" ".join(words[i]["text"] for i in line))
            line = [idx]
            line_len = w["visual_len"]
        else:
            line.append(idx)
            line_len = new_len

    if line:
        lines.append(" ".join(words[i]["text"] for i in line))
    return "\n".join(lines)


def _split_long_segment(indices, words, max_chars_per_line, max_lines):
    max_total = max_chars_per_line * max_lines
    blocks = []
    current = []

    for idx in indices:
        w = words[idx]
        
        is_curr_rtl = _is_rtl(w["text"])
        is_prev_rtl = _is_rtl(words[current[-1]]["text"]) if current else is_curr_rtl
        lang_switch = (is_curr_rtl != is_prev_rtl)

        added_len = w["visual_len"] + (1 if current else 0)
        current_len = _block_visual_len(current, words)
        new_len = current_len + added_len

        is_reasonably_full = current_len > (max_total * 0.6)
        good_early_split = lang_switch and is_reasonably_full

        if current and (
            (new_len > max_total and not (is_curr_rtl and is_prev_rtl)) or 
            good_early_split or
            (new_len > max_total + 25) 
        ):
            blocks.append(current)
            current = [idx]
        else:
            current.append(idx)

    if current:
        blocks.append(current)

    return blocks


def _fix_trailing_orphans(blocks, words):
    if len(blocks) <= 1:
        return blocks

    for i in range(len(blocks) - 2, -1, -1):
        while len(blocks[i]) > 1 and _is_orphan(words[blocks[i][-1]]["text"]):
            orphan = blocks[i].pop()
            blocks[i + 1].insert(0, orphan)

    return [b for b in blocks if b]


def _merge_tiny_blocks(blocks, words, max_total):
    if not blocks:
        return blocks

    min_len = max(15, max_total // 3)
    changed = True
    while changed:
        changed = False
        result = [list(blocks[0])]

        for i in range(1, len(blocks)):
            prev = result[-1]
            curr = list(blocks[i])
            
            curr_len = _block_visual_len(curr, words)
            prev_len = _block_visual_len(prev, words)
            
            time_gap = words[curr[0]]["start_time"] - words[prev[-1]]["end_time"]

            if (curr_len < min_len or prev_len < min_len) and \
               (prev_len + 1 + curr_len <= max_total) and \
               (time_gap <= MAX_TIME_GAP):
                
                result[-1] = prev + curr
                changed = True
            else:
                result.append(curr)

        blocks = result

    return blocks


def format_srt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _format_into_lines_balanced(block, words, max_chars_per_line, max_lines):
    if not block:
        return ""
        
    block_len = _block_visual_len(block, words)
    
    if block_len <= max_chars_per_line:
        return " ".join(words[i]["text"] for i in block)
        
    best_split_idx = 0
    best_score = float('inf')
    
    left_len = 0
    for i in range(len(block) - 1):
        idx = block[i]
        next_idx = block[i+1]
        
        left_len += words[idx]["visual_len"] + (1 if i > 0 else 0)
        right_len = block_len - left_len - 1 
        
        length_diff = abs(left_len - right_len)
        
        orphan_penalty = 500 if _is_orphan(words[idx]["text"]) else 0
        
        overflow_penalty = 0
        if left_len > max_chars_per_line:
            overflow_penalty += (left_len - max_chars_per_line) * 100
        if right_len > max_chars_per_line:
            overflow_penalty += (right_len - max_chars_per_line) * 100
            
        is_curr_rtl = _is_rtl(words[idx]["text"])
        is_next_rtl = _is_rtl(words[next_idx]["text"])
        
        bidi_penalty = 0
        if is_curr_rtl and is_next_rtl:
            bidi_penalty = 2000
        elif is_curr_rtl != is_next_rtl:
            bidi_penalty = -500

        score = length_diff + orphan_penalty + overflow_penalty + bidi_penalty
        
        if score < best_score:
            best_score = score
            best_split_idx = i
            
    if best_score >= 1500 and len(block) > 2:
        return _greedy_format(block, words, max_chars_per_line, max_lines)

    line1 = " ".join(words[i]["text"] for i in block[:best_split_idx + 1])
    line2 = " ".join(words[i]["text"] for i in block[best_split_idx + 1:])
    return f"{line1}\n{line2}"


def _flatten_asr_items(items):
    words = []
    for item in items:
        text = item["text"].strip().replace('\n', ' ')
        if not text:
            continue
            
        sub_words = text.split()
        
        if len(sub_words) == 1:
            words.append({
                "text": text,
                "start_time": item["start_time"],
                "end_time": item["end_time"],
                "visual_len": _visual_len(text),
            })
        else:
            duration = item["end_time"] - item["start_time"]
            total_chars = sum(_visual_len(w) for w in sub_words)
            
            start = item["start_time"]
            for i, w in enumerate(sub_words):
                w_len = _visual_len(w)
                
                if total_chars > 0:
                    w_duration = duration * (w_len / total_chars)
                else:
                    w_duration = duration / len(sub_words)
                    
                end = start + w_duration if i < len(sub_words) - 1 else item["end_time"]
                
                words.append({
                    "text": w,
                    "start_time": start,
                    "end_time": end,
                    "visual_len": w_len,
                })
                start = end
    return words


def make_subtitles(time_stamps, output_path, max_chars_per_line=50, max_lines=2):
    max_total = max_chars_per_line * max_lines
    min_content = max(20, max_total // 3)

    items = [it for it in time_stamps if it["text"].strip()]
    if not items:
        with open(output_path, "w", encoding="utf-8") as f:
            pass
        return

    words = _flatten_asr_items(items)

    segments, current = [], []
    for i in range(len(words)):
        if current:
            time_gap = words[i]["start_time"] - words[i - 1]["end_time"]
            if time_gap > MAX_TIME_GAP:
                segments.append(current)
                current = []
        current.append(i)
        if _is_sentence_end(words[i]["text"]) and _block_visual_len(current, words) >= min_content:
            segments.append(current)
            current = []
    if current:
        segments.append(current)

    blocks, current_block = [], []
    for seg in segments:
        seg_len = _block_visual_len(seg, words)

        if not current_block:
            if seg_len <= max_total:
                current_block = list(seg)
            else:
                blocks.extend(_split_long_segment(seg, words, max_chars_per_line, max_lines))
            continue

        block_len = _block_visual_len(current_block, words)
        
        if (block_len + 1 + seg_len) <= max_total:
            current_block.extend(seg)
        else:
            blocks.append(current_block)
            if seg_len <= max_total:
                current_block = list(seg)
            else:
                blocks.extend(_split_long_segment(seg, words, max_chars_per_line, max_lines))
                current_block = []

    if current_block:
        blocks.append(current_block)

    blocks = _fix_trailing_orphans(blocks, words)
    blocks = _merge_tiny_blocks(blocks, words, max_total)
    blocks = _fix_trailing_orphans(blocks, words)

    with open(output_path, "w", encoding="utf-8") as f:
        prev_end_time = -1

        for num, block in enumerate(blocks, 1):
            lines = _format_into_lines_balanced(block, words, max_chars_per_line, max_lines)
            
            start = words[block[0]]["start_time"]
            end = words[block[-1]]["end_time"]

            if start < prev_end_time + MIN_GAP_BETWEEN_SUBS:
                start = prev_end_time + MIN_GAP_BETWEEN_SUBS
            
            duration = end - start
            if duration < MIN_DURATION:
                next_start = (
                    words[blocks[num][0]]["start_time"]
                    if num < len(blocks)
                    else float("inf")
                )
                allowed_extension = min(
                    start + MIN_DURATION, next_start - MIN_GAP_BETWEEN_SUBS
                )
                end = max(end, allowed_extension)

            prev_end_time = end

            f.write(f"{num}\n")
            f.write(f"{format_srt_time(start)} --> {format_srt_time(end)}\n")
            f.write(f"{lines}\n\n")


def translate_text(merged, dst_language=DST_LANGUAGE):
    log_var("translate_text: merged", merged)
    log_var("translate_text: dst_language", dst_language)


def transcribe(audio_path):
    start_time = time.time()

    basename = os.path.splitext(os.path.basename(audio_path))[0]

    chunks = chunk_audio(audio_path)

    model = Qwen3ASRModel.from_pretrained(
        MODEL_ID,
        dtype=torch.bfloat16,
        device_map=DEVICE,
        max_inference_batch_size=MAX_BATCH_SIZE,
        max_new_tokens=MAX_NEW_TOKENS,
        forced_aligner=ALIGNER_ID,
        forced_aligner_kwargs=dict(
            dtype=torch.bfloat16,
            device_map=DEVICE,
        ),
    )

    all_results = []
    total_chunks = len(chunks)
    for i, chunk_info in enumerate(chunks, 1):
        print(f"🔉 Chunk [{i}/{total_chunks}]")
        result = model.transcribe(
            audio=chunk_info["path"],
            language=LANGUAGE,
            return_time_stamps=True,
        )
        all_results.append(result)

    time_offset = 0.0
    processed_texts = []
    realigned_timestamps = []
    for i, (r, chunk_info) in enumerate(zip(all_results, chunks)):
        t = r[0]
        corrected = process_result(t.text)
        processed_texts.append(corrected)

        items = realign_timestamps(corrected, t.time_stamps.items, time_offset)
        realigned_timestamps.append(items)

        time_offset += chunk_info["duration_sec"]

    merged = merge_results(processed_texts, realigned_timestamps)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, f"{basename}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    audio_dir = os.path.dirname(audio_path)
    srt_path = os.path.join(audio_dir, f"{basename}.srt")
    make_subtitles(merged["time_stamps"], srt_path)

    elapsed = (time.time() - start_time) / 60
    return elapsed, merged


def log_result(minutes):
    with open("benchmark.csv", "a") as f:
        f.write(f"{MAX_BATCH_SIZE},{MAX_NEW_TOKENS},{minutes:.2f}\n")


def _collect_files(path, filter_mode):
    path = os.path.abspath(path)

    if os.path.isfile(path):
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS or ext in VIDEO_EXTENSIONS:
            return [path]
        print(f"❌ Error: unsupported file format '{ext}'")
        sys.exit(1)

    if os.path.isdir(path):
        extensions = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS
        if filter_mode == "audio":
            extensions = AUDIO_EXTENSIONS
        elif filter_mode == "video":
            extensions = VIDEO_EXTENSIONS

        files = sorted(
            os.path.join(path, f)
            for f in os.listdir(path)
            if os.path.splitext(f)[1].lower() in extensions
        )
        if not files:
            label = filter_mode or "audio/video"
            print(f"❌ No {label} files found in '{path}'")
            sys.exit(1)
        return files

    print(f"❌ Error: path does not exist '{path}'")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="SUBGEN",
        description="📄 Generate subtitles from audio/video files using AI-powered ASR.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="📂 Path to an audio/video file or directory",
    )
    parser.add_argument(
        "--audio",
        "-audio",
        dest="filter",
        action="store_const",
        const="audio",
        help="⏩ Process only audio files in the directory",
    )
    parser.add_argument(
        "--video",
        "-video",
        dest="filter",
        action="store_const",
        const="video",
        help="🎦 Process only video files in the directory",
    )

    args = parser.parse_args()

    if args.path is None:
        parser.print_help()
        sys.exit(0)

    files = _collect_files(args.path, args.filter)

    total_files = len(files)
    for idx, filepath in enumerate(files, 1):
        print(f"📁 [{idx}/{total_files}] Processing: {filepath}")
        elapsed, _ = transcribe(filepath)
        print(f"✅ Done in {elapsed:.1f} min — {os.path.join(OUTPUT_DIR, os.path.splitext(os.path.basename(filepath))[0] + '.srt')}")


if __name__ == "__main__":
    main()