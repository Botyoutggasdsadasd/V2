"""
Thin wrapper around the Anthropic-compatible API.
Handles: plain chat, and vision (photo -> extracted text + explanation).
"""
import base64
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL, BOT_NAME

client = Anthropic(api_key=ANTHROPIC_API_KEY, base_url=ANTHROPIC_BASE_URL)

BASE_SYSTEM_PROMPT = f"""អ្នកគឺជា {{ai_name}} — មិត្តភក្តិ AI និងគ្រូបង្រៀនផ្ទាល់ខ្លួន សម្រាប់សិស្សខ្មែរនៅកម្ពុជា
ថ្នាក់ទី {{grade}} ជំនាញ {{track}}។ គោលដៅចម្បងរបស់អ្នកគឺជួយសិស្សត្រៀមប្រឡងជាតិ (Bac II / ប្រឡងសញ្ញាបត្រមធ្យមសិក្សាទុតិយភូមិ)
និងការប្រឡងប្រចាំខែ/ឆមាស តាមកម្មវិធីសិក្សារបស់ក្រសួងអប់រំ យុវជន និងកីឡា (MoEYS) កម្ពុជា។

របៀបនិយាយ៖
- និយាយភាសាខ្មែរជាចម្បង សន្ទនាដូចមិត្តភក្តិ សប្បាយ កក់ក្តៅ ជួយកាត់បន្ថយស្ត្រេស មិនធ្វើឲ្យសិស្សខ្លាចការសិក្សា។
- អាចប្រើ emoji បន្តិចបន្តួច និងកំប្លែងស្រាលៗម្តងម្កាល ជាពិសេសពេលសិស្សនិយាយថាធុញឬស្ត្រេស។
- ប៉ុន្តែពេលពន្យល់មេរៀន ត្រូវម៉ត់ចត់ ត្រឹមត្រូវ មិនលេងសើចលើខ្លឹមសារសិក្សា។

របៀបពន្យល់៖
- ពន្យល់មេរៀន គណិតវិទ្យា រូបវិទ្យា គីមីវិទ្យា ជីវវិទ្យា ភូមិវិទ្យា ប្រវត្តិវិទ្យា អក្សរសាស្ត្រខ្មែរ សីលធម៌-ពលរដ្ឋវិទ្យា
  និងមុខវិជ្ជាផ្សេងទៀត តាមកម្មវិធីសិក្សាកម្ពុជាឲ្យបានត្រឹមត្រូវបំផុត។
- សម្រាប់គណិតវិទ្យា/រូបវិទ្យា/គីមីវិទ្យា៖ បង្ហាញរូបមន្ត ជំហានគណនាលម្អិតម្តងមួយៗ រហូតដល់ចម្លើយចុងក្រោយ កុំលោត step។
- ប្រសិនបើមិនច្បាស់ថាព័ត៌មានណាមួយត្រឹមត្រូវ ឬអាចផ្លាស់ប្តូរ (ឧ. កាលបរិច្ឆេទប្រឡង ចំណុចប្រឡងចុងក្រោយ) សូមប្រាប់សិស្សឲ្យផ្ទៀងផ្ទាត់ជាមួយគ្រូ ឬគេហទំព័រផ្លូវការរបស់ក្រសួងអប់រំ ព្រោះអ្នកអាចមិនដឹងព័ត៌មានចុងក្រោយបំផុត។
- បើសិស្សសួរអ្វីក្រៅមុខវិជ្ជា អ្នកអាចជួយបានដែរ ដូចជា Claude ធម្មតា។
"""

# --- Subject keyword detection (for lightweight "what does this student study" memory) ---
SUBJECT_KEYWORDS = {
    "math": ["គណិត", "math", "អាល់សែប្រ", "ធរណីមាត្រ", "លីមីត", "អនុគមន៍"],
    "physics": ["រូបវិទ្យា", "physics", "ថាមពល", "អគ្គិសនី"],
    "chemistry": ["គីមី", "chemistry", "ប្រតិកម្ម"],
    "biology": ["ជីវវិទ្យា", "biology", "កោសិកា"],
    "khmer_lit": ["អក្សរសាស្ត្រ", "ភាសាខ្មែរ", "khmer literature", "កំណាព្យ"],
    "history": ["ប្រវត្តិវិទ្យា", "history", "អង្គរ", "សង្គ្រាម"],
    "geography": ["ភូមិវិទ្យា", "geography", "ផែនទី"],
    "moral_civics": ["សីលធម៌", "ពលរដ្ឋវិទ្យា", "civics"],
    "english": ["english", "grammar", "vocabulary"],
}

def detect_subject(text: str):
    t = text.lower()
    for key, words in SUBJECT_KEYWORDS.items():
        for w in words:
            if w.lower() in t:
                return key
    return None

# --- Stress / mood detection (keyword based, no extra API call needed) ---
STRESS_WORDS = ["ស្ត្រេស", "ខ្លាច", "ពិបាកចិត្ត", "ធុញ", "អស់សង្ឃឹម", "stress", "anxious", "worried", "give up", "លែងចង់រៀន"]

def detect_stress(text: str) -> bool:
    t = text.lower()
    return any(w.lower() in t for w in STRESS_WORDS)

CALMING_INTRO = (
    "ចាំបានៗ 🌿 ដកដង្ហើមចូលមួយសន្ធឹក បន្តិចម្តងៗ យើងជាមួយគ្នា មិនចាំបាច់ចេះអស់ថ្ងៃនេះទេ។ "
    "ចាំខ្ញុំពន្យល់ជាជំហានងាយៗ..."
)

# --- Light "joke break" for relaxing students ---
STUDY_JOKES = [
    "គ្រូសួរសិស្ស៖ '2+2 ស្មើប៉ុន្មាន?' សិស្សឆ្លើយ៖ 'ស្មើនឹងការប្រឡងជិតដល់ហើយ គ្រូអើយ! 😅' — សើចហើយ ត្រលប់មករៀនវិញណា៎!",
    "ហេតុអ្វីលេខសូន្យមិនចង់ជជែកជាមួយលេខផ្សេង? ព្រោះវាមិនមានតម្លៃអ្វីទេ 0_o ចាំបានទេ ខួរក្បាលអ្នកមានតម្លៃណាស់ ព្យាយាមទៀត!",
    "សិស្សម្នាក់ថា 'ខ្ញុំមិនចូលចិត្តគណិតទេ' គណិតឆ្លើយថា 'ចម្លែកហើយ ព្រោះខ្ញុំគិតគូរពីអ្នកគ្រប់ Bac ទាំងអស់!' 📐",
]

import random
def random_joke():
    return random.choice(STUDY_JOKES)

def _resolve_system(user):
    ai_name = (user or {}).get("ai_name") or BOT_NAME
    grade = (user or {}).get("grade") or "12"
    track = (user or {}).get("track") or ""
    return BASE_SYSTEM_PROMPT.format(ai_name=ai_name, grade=grade, track=track)

def chat(user, history, new_user_message):
    """
    history: list of {"role": "user"/"assistant", "content": str}
    """
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": new_user_message})

    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1500,
        system=_resolve_system(user),
        messages=messages,
    )
    return "".join(block.text for block in resp.content if block.type == "text")

def read_image_and_answer(user, image_bytes, media_type, instruction):
    """
    Sends a photo (math/khmer test page, etc.) plus an instruction
    (e.g. 'extract the text', 'turn this into a test', 'explain the answer').
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=2000,
        system=_resolve_system(user),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": instruction},
                ],
            }
        ],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


# --- Reusable instructions for the button menu ---

INSTR_EXTRACT = (
    "សូមអានអត្ថបទ/សំណួរទាំងអស់ក្នុងរូបភាពនេះឲ្យបានត្រឹមត្រូវ (OCR) ហើយសរសេរជាអក្សរខ្មែរ/គណិតវិទ្យាឡើងវិញ "
    "ដោយមិនកែប្រែខ្លឹមសារ។ បើជាលំហាត់គណិតវិទ្យា សរសេររូបមន្តឲ្យច្បាស់។"
)

INSTR_MAKE_TEST = (
    "ផ្អែកលើខ្លឹមសារក្នុងរូបភាព/អត្ថបទនេះ សូមបង្កើតជាកម្រងសំណួរតេស្ត (quiz) ចំនួន 5-10 សំណួរ "
    "ដែលមានទាំងសំណួរជម្រើសពហុភាព (multiple choice) និងសំណួរចម្លើយខ្លី សម្រាប់សិស្សត្រួតពិនិត្យចំណេះដឹងខ្លួនឯង។ "
    "កុំបង្ហាញចម្លើយភ្លាមៗ ដាក់ចម្លើយនៅផ្នែកចុងក្រោយ ដាក់ក្បាល 'ចម្លើយ'."
)

INSTR_MAKE_QUESTION = (
    "ផ្អែកលើខ្លឹមសារនេះ សូមបង្កើតសំណួរអនុវត្តន៍ថ្មីៗ (practice questions) ដែលស្រដៀងគ្នាតែមិនដូចគ្នាបេះបិទ "
    "ដើម្បីឲ្យសិស្សអនុវត្តន៍បន្ថែម។"
)

INSTR_SUMMARIZE = (
    "សូមសង្ខេបខ្លឹមសារសំខាន់ៗក្នុងរូបភាព/អត្ថបទនេះ ជាចំណុចៗ (bullet points) ខ្លីៗងាយចាំ សម្រាប់ត្រៀមប្រឡង។"
)

INSTR_EXPLAIN_ANSWER = (
    "រូបភាពនេះជាលំហាត់គណិតវិទ្យា ឬសំណួរដែលត្រូវការចម្លើយ។ សូម៖\n"
    "1) សរសេរឡើងវិញនូវសំណួរ/ប្រធានបទ\n"
    "2) ដោះស្រាយជាជំហានៗ ច្បាស់លាស់ (step-by-step)\n"
    "3) ផ្តល់ចម្លើយចុងក្រោយឲ្យច្បាស់\n"
    "4) ពន្យល់ថាហេតុអ្វីបានចម្លើយនោះត្រូវ (គំនិត/ច្បាប់ដែលប្រើ)"
)

# --- Bac II (national exam) style practice generator ---
BAC_SUBJECTS = {
    "math": "គណិតវិទ្យា",
    "physics": "រូបវិទ្យា",
    "chemistry": "គីមីវិទ្យា",
    "biology": "ជីវវិទ្យា",
    "khmer_lit": "អក្សរសាស្ត្រខ្មែរ",
    "history": "ប្រវត្តិវិទ្យា",
    "geography": "ភូមិវិទ្យា",
    "moral_civics": "សីលធម៌-ពលរដ្ឋវិទ្យា",
    "english": "ភាសាអង់គ្លេស",
}

def bac_practice_instruction(subject_label: str, grade: str) -> str:
    return (
        f"សូមរៀបចំសំណួរអនុវត្តន៍ម៉ូតប្រឡងជាតិ (Bac II) មុខវិជ្ជា{subject_label} សម្រាប់សិស្សថ្នាក់ទី{grade} "
        "ចំនួន 4-6 សំណួរ ដែលមានរចនាសម្ព័ន្ធនិងកម្រិតលំបាកស្រដៀងនឹងប្រឡងជាតិកម្ពុជាជាក់ស្តែង "
        "(លំហាត់គណនា/ការវិភាគ/សំណួរអភិវិវឌ្ឍន៍ តាមលក្ខណៈមុខវិជ្ជានីមួយៗ)។ "
        "ដាក់ចំណុចពិន្ទុប្រហាក់ប្រហែលនៅជាប់សំណួរនីមួយៗ ហើយដាក់ 'ចម្លើយគំរូ' ពេញលេញនៅផ្នែកចុងក្រោយ។ "
        "ប្រសិនបើមិនច្បាស់ចំណុចលម្អិតនៃទម្រង់ប្រឡងចុងក្រោយបំផុត សូមកត់សម្គាល់ថាសិស្សគួរផ្ទៀងផ្ទាត់ជាមួយគ្រូបន្ថែម។"
    )
