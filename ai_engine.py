import os
import json
import time
import tempfile
import threading

import torch
import httpx
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from qwen_asr import Qwen3ASRModel

from config import (
    LANGUAGE,
    DEVICE,
    MODEL_ID,
    ALIGNER_ID,
    MAX_BATCH_SIZE,
    MAX_NEW_TOKENS,
    OUTPUT_DIR,
    NANOGPT_MODEL,
    NANOGPT_URL,
    NANOGPT_API_KEY,
    SYSTEM_PROMPT,
)
from subtitles_engine import make_subtitles


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
        chunk_path = os.path.join(tempfile.gettempdir(), f"chunk_{i}.wav")
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


def realign_timestamps(corrected_text, original_items, time_offset=0.0):
    from difflib import SequenceMatcher
    from subtitles_engine import _visual_len

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

    corrected_words = corrected_text.split()

    if not orig_words or not corrected_words:
        return []

    orig_texts = [w["text"] for w in orig_words]
    matcher = SequenceMatcher(None, orig_texts, corrected_words, autojunk=False)

    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for i, j in zip(range(i1, i2), range(j1, j2)):
                result.append({
                    "text": corrected_words[j],
                    "start_time": orig_words[i]["start_time"],
                    "end_time": orig_words[i]["end_time"],
                })

        elif tag == 'replace':
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


def transcribe(audio_path, progress_callback=None, stop_event=None):
    start_time = time.time()

    basename = os.path.splitext(os.path.basename(audio_path))[0]

    if progress_callback:
        progress_callback({"stage": "chunking"})

    chunks = chunk_audio(audio_path)

    if stop_event and stop_event.is_set():
        raise InterruptedError("Transcription stopped by user.")

    if progress_callback:
        progress_callback({"stage": "model_loading"})

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

    if progress_callback:
        progress_callback({"stage": "model_loaded"})

    all_results = []
    total_chunks = len(chunks)
    for i, chunk_info in enumerate(chunks, 1):
        if stop_event and stop_event.is_set():
            raise InterruptedError("Transcription stopped by user.")
        if progress_callback:
            progress_callback({"stage": "chunk", "current": i, "total": total_chunks})
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
        if stop_event and stop_event.is_set():
            raise InterruptedError("Transcription stopped by user.")
        if progress_callback:
            progress_callback({"stage": "llm"})
        t = r[0]
        corrected = llm_call([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": t.text},
        ])
        processed_texts.append(corrected)

        items = realign_timestamps(corrected, t.time_stamps.items, time_offset)
        realigned_timestamps.append(items)

        time_offset += chunk_info["duration_sec"]

    merged = merge_results(processed_texts, realigned_timestamps)

    if progress_callback:
        progress_callback({"stage": "srt"})

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json_path = os.path.join(OUTPUT_DIR, f"{basename}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    audio_dir = os.path.dirname(audio_path)
    srt_path = os.path.join(audio_dir, f"{basename}.srt")
    make_subtitles(merged["time_stamps"], srt_path)

    if progress_callback:
        progress_callback({"stage": "done"})

    elapsed = (time.time() - start_time) / 60
    return elapsed, merged


def log_result(minutes):
    from config import MAX_BATCH_SIZE, MAX_NEW_TOKENS
    with open("benchmark.csv", "a") as f:
        f.write(f"{MAX_BATCH_SIZE},{MAX_NEW_TOKENS},{minutes:.2f}\n")
