import re
import unicodedata

from config import (
    ORPHAN_WORDS,
    SENTENCE_ENDS,
    MAX_TIME_GAP,
    MIN_DURATION,
    MIN_GAP_BETWEEN_SUBS,
)


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
