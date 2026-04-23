import os
from dotenv import load_dotenv

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
MIN_DURATION = 0.5  # Minimum seconds a subtitle must stay on screen to avoid "flashing"
MIN_GAP_BETWEEN_SUBS = 0.05  # Minimum gap between consecutive blocks to allow the eye to register a change
