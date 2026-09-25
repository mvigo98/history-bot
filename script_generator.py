# -*- coding: utf-8 -*-
"""
وحدة توليد السكريبتات التاريخية والإجابة عن أي سؤال في التاريخ بالعامية المصرية
- سكريبتات كلامية صرفة بدون أي توجيهات مونتاج أو موسيقى
- شات مفتوح للإجابة عن أي تساؤل تاريخي
- نظام REST فائق السرعة لمنع أي بطء أو أخطاء
"""

import os
import re
import random
import logging
import asyncio
import requests
from typing import Tuple, Optional, List
from dotenv import load_dotenv
import database

load_dotenv()

logger = logging.getLogger(__name__)

# الموديلات المرشحة للتبديل التلقائي
CANDIDATE_MODELS = [
    os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
]

# تصنيفات تاريخية للتناوب في زر 'جديد'
HISTORICAL_ERAS = [
    "أسرار الفراعنة ومصر القديمة (مومياوات، مقابر، ألغاز، بردية غامضة)",
    "أغرب المعارك والحروب في التاريخ والخطط العسكرية الماكرة",
    "ملوك وحكام مجانين وقرارات غريبة قلبت التاريخ",
    "العصر الذهبي الإسلامي والعلماء والاختراعات العبقرية",
    "تاريخ مصر المملوكي والعثماني وقصص شوارع القاهرة المنسية",
    "صدف تاريخية تافهة وبسيطة غيرت مجرى كوكب الأرض",
    "أخطر عمليات الجواسيس والمخابرات والاغتيالات التاريخية",
    "ألغاز وحضارات مفقودة وأحداث غامضة لم تفسر",
    "تاريخ الطب والعلوم والأوبئة والغرائب الإنسانية",
    "بطولات وملاحم تاريخية مصرية وعربية ملهمة",
    "الحربين العالميتين وأسرار الغرف المغلقة ومعارك الظل",
]

# برومبت توليد الاسكريبت (كلام صرف لصانع المحتوى فقط بدون أي توجيهات مونتاج أو موسيقى)
SCRIPT_SYSTEM_PROMPT = """أنت كاتب ومعد سكريبتات محتوى تاريخي أسطوري بالعامية المصرية الصريحة والممتعة (أسلوب حكواتي مشوق وسلس زي الدحيح وأحمد الغندور).

⚠️ تعليمات وقواعد حاسمة لا تخالفها أبداً:
1. اكتب فقط الكلام والنص الذي سينطقه صانع المحتوى بلسانه كلمة بكلمة.
2. ممنوع منعاً باتاً ومرفوض نهائياً كتابة أي توجيهات للمونتاج أو الكاميرا أو الموسيقى أو المؤثرات الصوتية (ممنوع كتابة: "صوت كذا"، "موسيقى كذا"، "زووم"، "B-Roll"، "لقطة أرشيفية"، أو أي جمل بين أقواس تشير للمونتاج والإخراج).
3. ابدأ بهوك قوي جداً في أول سطرين يجبر المشاهد يكمل الفيديو وما يقلبش.
4. اسرد القصة بالعامية المصرية السلسة الغنية بالتشويق والمعلومات الحقيقية الموثقة.
5. اختم بسؤال ذكي للمشاهدين يفتح نقاش في التعليقات لزيادة التفاعل.

هيكل الاسكريبت المطلوب:
📌 عنوان الفيديو: [عنوان جذاب جداً]

🪝 الهوك:
(الكلام المشوق الصادم اللي هيقوله في أول 5-10 ثواني)

📖 القصة:
(نص الحكاية الكامل بالعامية المصرية المتدفقة، سرد كلامي ممتع ومسلسل بدون أي توجيهات مونتاج)

🤯 الصدمة أو المفاجأة:
(المعلومة أو الزاوية غير المتوقعة في القصة)

🎯 الخاتمة:
(القفلة وسؤال صانع المحتوى للمتابعين في الكومنتات)
"""

# برومبت الإجابة عن أي سؤال في التاريخ (شات تاريخي مفتوح)
CHAT_SYSTEM_PROMPT = """أنت مؤرخ وباحث تاريخي مصري موسوعي ورفيق لصانع المحتوى.
تتحدث بالعامية المصرية الذكية والممتعة والودودة.
مهمتك الإجابة عن أي سؤال تاريخي بدقة وتفصيل وسلاسة بدون تعقيد وبأسلوب سردي ممتع يفتح النفس.
"""

# برومبت السكريبت المنسق بنمط التلقين للشاشة (Teleprompter)
TELEPROMPTER_SYSTEM_PROMPT = """أنت كاتب ومعد سكريبتات محتوى تاريخي أسطوري بالعامية المصرية الصريحة والممتعة (أسلوب حكواتي مشوق وسلس زي الدحيح وأحمد الغندور)، وخبير في إعداد نصوص التلقين (Teleprompter) المصممة للقراءة المباشرة من الشاشة أثناء التصوير.

⚠️ قواعد التلقين الحاسمة (التزم بها بحزم):
1. اكتب كلام وسرد القصة فقط الذي سينطقه صانع المحتوى بلسانه كلمة بكلمة.
2. ممنوع نهائياً كتابة أي توجيهات للمونتاج أو الكاميرا أو الموسيقى أو المؤثرات الصوتية.
3. قسّم النص بحيث يحتوي كل سطر على جملتين اثنتين فقط مترابطتين (جملتين في السطر الواحد)، لتسهيل القراءة المتدفقة والسلسة من الشاشة بدون حركة ملحوظة للرأس أو العين.
4. ضع علامة الوقف ⏸️ في نهاية كل سطر لإتاحة أخذ نفس هادئ بين كل جملتين متتاليتين.
5. استخدم نقاط الوقف (...) لتهدئة الإيقاع ومد النبرة قبل الكلمات المفتاحية والمفاجآت.
6. اسرد القصة كاملة ومفصلة بكل أحداثها وحواراتها ومواقفها المشوقة بدون أي اختصار أو حذف مخل.
7. اختم بسؤال ذكي للمتابعين يفتح نقاش في الكومنتات.

هيكل الاسكريبت المطلوب:
📌 عنوان الفيديو: [عنوان جذاب]

(نص الاسكريبت كاملاً مقسماً بحيث يحتوي كل سطر على جملتين اثنتين مع علامة ⏸️ بنهاية السطر)

🎯 الخاتمة:
(سؤال القفلة للمتابعين)
"""


def _call_gemini_rest_sync(prompt: str) -> str:
    """استدعاء Gemini REST API مع تجربة الموديلات المتاحة تلقائياً"""
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or "ضع_مفتاح" in api_key:
        raise ValueError("مفتاح GEMINI_API_KEY غير محدد في ملف .env!")

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.9,
            "topP": 0.95,
            "topK": 64,
            "maxOutputTokens": 6000,
        },
    }

    last_error = None
    seen_models = set()
    for model in CANDIDATE_MODELS:
        if model in seen_models:
            continue
        seen_models.add(model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=25)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            else:
                last_error = f"Model {model} returned status {res.status_code}: {res.text}"
                logger.warning(last_error)
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Error calling {model}: {e}")

    raise RuntimeError(f"تعذر الاتصال بـ Gemini: {last_error}")


async def call_gemini_api(prompt: str) -> str:
    """استدعاء Gemini في خيط منفصل لتفادي تجميد البوت"""
    return await asyncio.to_thread(_call_gemini_rest_sync, prompt)


def extract_title(script_text: str) -> str:
    """استخراج عنوان الفيديو"""
    title = "قصة تاريخية مشوقة"
    title_match = re.search(r"📌[^\n:]*[:\s]+(.+)", script_text)
    if title_match:
        raw_title = title_match.group(1).strip().replace("*", "").replace("#", "").strip()
        if raw_title:
            title = raw_title
    return title


def clean_script_output(text: str) -> str:
    """إزالة أي بقايا توجيهات موسيقية أو مونتاج إن وجدت لضمان كلام صرف فقط"""
    # إزالة سطور الصوت والموسيقى والمونتاج
    cleaned_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        # تجاهل سطور التوجيهات الفنية
        if re.match(r"^(?:صوت|موسيقى|توجيه|كاميرا|زووم|مؤثرات|لقطات|B-Roll)\s*[:\-]", stripped, re.IGNORECASE):
            continue
        # حذف التوجيهات بين الأقواس المربعة أو المعكوفة داخل السطور
        line_clean = re.sub(r"\[(?:صوت|موسيقى|زووم|B-Roll|صورة|لقطة|مؤثر).*?\]", "", line, flags=re.IGNORECASE)
        line_clean = re.sub(r"\((?:صوت|موسيقى|زووم|B-Roll|صورة|لقطة|مؤثر).*?\)", "", line_clean, flags=re.IGNORECASE)
        cleaned_lines.append(line_clean)
    return "\n".join(cleaned_lines)


async def generate_new_history_script(user_id: int, era_preference: Optional[str] = None) -> Tuple[str, str, int]:
    """توليد اسكريبت تاريخي جديد كلياً بدون تكرار وخالٍ تماماً من توجيهات المونتاج"""
    past_topics = database.get_user_recent_topics(user_id, limit=60)
    
    avoid_instruction = ""
    if past_topics:
        avoid_list_str = "\n".join([f"- {t}" for t in past_topics])
        avoid_instruction = (
            f"\n🚨 تنبيه منع التكرار: سبق وأن كتبنا للمستخدم سكريبتات عن هذه المواضيع:\n"
            f"{avoid_list_str}\n"
            f"ممنوع تكرار أي فكرة أو شخصية أو حدث مذكور أعلاه! اختر موضوعاً تاريخياً مختلفاً 100%."
        )

    chosen_era = era_preference or random.choice(HISTORICAL_ERAS)

    prompt = f"""{SCRIPT_SYSTEM_PROMPT}

المطلوب:
اكتب اسكريبت فيديو جديد ومميز بالعامية المصرية في التصنيف التالي:
🏛️ التصنيف: {chosen_era}
{avoid_instruction}

تنبيه هام جداً: اكتب كلام وسرد القصة فقط، بدون أي كلام عن الموسيقى أو لقطات الفيديو أو مؤثرات الصوت نهائياً."""

    raw_script = await call_gemini_api(prompt)
    script_text = clean_script_output(raw_script)
    title = extract_title(script_text)

    script_id = database.save_script(
        user_id=user_id,
        topic_title=title,
        era_category=chosen_era[:20],
        script_text=script_text,
        format_type="standard",
    )
    return script_text, title, script_id


async def generate_custom_topic_script(user_id: int, custom_topic: str) -> Tuple[str, str, int]:
    """توليد اسكريبت مخصص عن موضوع أو فكرة محددة طلبها المستخدم"""
    prompt = f"""{SCRIPT_SYSTEM_PROMPT}

المطلوب:
اكتب اسكريبت فيديو تاريخي كامل بالعامية المصرية عن الموضوع التالي:
🎯 الموضوع: {custom_topic}

تنبيه هام جداً: اكتب كلام وسرد القصة فقط اللي صانع المحتوى هيقوله للمشاهدين، بدون أي كلام عن الموسيقى أو لقطات الفيديو أو مؤثرات الصوت نهائياً."""

    raw_script = await call_gemini_api(prompt)
    script_text = clean_script_output(raw_script)
    title = extract_title(script_text)
    if title == "قصة تاريخية مشوقة":
        title = custom_topic

    script_id = database.save_script(
        user_id=user_id,
        topic_title=title,
        era_category="مخصص",
        script_text=script_text,
        format_type="custom",
    )
    return script_text, title, script_id


async def generate_teleprompter_script(user_id: int, topic: Optional[str] = None) -> Tuple[str, str, int]:
    """توليد سكريبت بنمط التلقين للشاشة (Teleprompter) جاهز للقراءة والتسجيل الفوري"""
    if topic:
        prompt = f"""{TELEPROMPTER_SYSTEM_PROMPT}

المطلوب:
اكتب سكريبت تاريخي بنمط التلقين للشاشة (جملتين في كل سطر مع علامة ⏸️ بنهاية السطر) عن الموضوع التالي:
🎯 الموضوع: {topic}

تنبيه: كلام وسرد خالص بالعامية المصرية فقط، بدون أي كلام عن الموسيقى أو المونتاج."""
        chosen_category = "مخصص تلقين"
    else:
        past_topics = database.get_user_recent_topics(user_id, limit=60)
        avoid_instruction = ""
        if past_topics:
            avoid_list_str = "\n".join([f"- {t}" for t in past_topics])
            avoid_instruction = (
                f"\n🚨 تنبيه منع التكرار: سبق وأن كتبنا للمستخدم سكريبتات عن هذه المواضيع:\n"
                f"{avoid_list_str}\n"
                f"ممنوع تكرار أي فكرة مذكورة أعلاه! اختر موضوعاً تاريخياً مختلفاً 100%."
            )
        chosen_era = random.choice(HISTORICAL_ERAS)
        prompt = f"""{TELEPROMPTER_SYSTEM_PROMPT}

المطلوب:
اكتب سكريبت تاريخي بنمط التلقين للشاشة (جملتين في كل سطر مع علامة ⏸️ بنهاية السطر) في التصنيف التالي:
🏛️ التصنيف: {chosen_era}
{avoid_instruction}

تنبيه: كلام وسرد خالص بالعامية المصرية فقط، بدون أي كلام عن الموسيقى أو المونتاج."""
        chosen_category = chosen_era[:20]

    raw_script = await call_gemini_api(prompt)
    script_text = clean_script_output(raw_script)
    script_text = format_script_to_teleprompter(script_text)
    title = extract_title(script_text)
    if topic and title == "قصة تاريخية مشوقة":
        title = topic

    script_id = database.save_script(
        user_id=user_id,
        topic_title=title,
        era_category=chosen_category,
        script_text=script_text,
        format_type="teleprompter",
    )
    return script_text, title, script_id


async def answer_history_question(user_id: int, question: str) -> str:
    """الإجابة عن أي سؤال أو استفسار أو نقاش في التاريخ بحرية تامة وبدون قيود"""
    prompt = f"""{CHAT_SYSTEM_PROMPT}

سؤال المستخدم:
"{question}"

جاوب عليه بالعامية المصرية بأسلوب شيق وممتع وموثق، خليه يحس إنه بيكلم صاحبه المؤرخ الشاطر."""

    return await call_gemini_api(prompt)


def format_script_to_teleprompter(text: str) -> str:
    """تحويل أي اسكريبت بالكامل لنمط التلقين للشاشة (جملتين في كل سطر مع وقفة ⏸️) مع الحفاظ على كل كلمة 100%"""
    lines = text.split("\n")
    result = []
    header_pattern = re.compile(r"^(?:📌|🪝|📖|🤯|🎯|🏷️|✨|#|===).*")

    for line in lines:
        line_str = line.strip()
        if not line_str:
            result.append("")
            continue

        # العناوين والأقسام والرموز تبقى كما هي في سطر مستقل بدون علامة وقف
        if header_pattern.match(line_str) or (line_str.startswith("(") and line_str.endswith(")")):
            result.append(line_str)
            continue

        # تفكيك السطر أو الفقرة إلى جمل وعبارات بناءً على علامات الترقيم
        tokens = re.split(r"([،,؛;.!?؟:\n]+)", line_str)
        clauses = []
        i = 0
        while i < len(tokens):
            c = tokens[i].strip()
            p = tokens[i + 1].strip() if i + 1 < len(tokens) else ""
            if c:
                # إذا كانت العبارة فقط علامات تنصيص أو أقواس أو ترقيم يتيم، نضمها للعبارة السابقة
                if re.match(r"^[\"\'»«\)\]\.\s]+$", c) and clauses:
                    clauses[-1] = clauses[-1] + c + p
                    i += 2
                    continue

                words = c.split()
                # إذا كانت العبارة طويلة جداً (أكثر من 14 كلمة) بدون فواصل، نقسمها لنصفين متوازنين
                if len(words) > 14:
                    mid = len(words) // 2
                    split_pos = None
                    for offset in [0, -1, 1, -2, 2, -3, 3]:
                        idx = mid + offset
                        if 0 < idx < len(words):
                            w = words[idx]
                            if w.startswith("و") or w.startswith("ف") or w in ["اللي", "عشان", "علشان", "إن", "إنه", "إنها", "حيث", "لما", "بعد"]:
                                split_pos = idx
                                break
                    if split_pos is None:
                        split_pos = mid
                    clauses.append(" ".join(words[:split_pos]))
                    clauses.append(" ".join(words[split_pos:]) + p)
                else:
                    clauses.append(c + p)
            i += 2

        if not clauses:
            clauses = [line_str]

        # تجميع كل جملتين في سطر واحد (جملتين في السطر) مع وقفة تنفس ⏸️ بنهاية السطر
        k = 0
        while k < len(clauses):
            if k + 1 < len(clauses):
                c1 = clauses[k].strip()
                c2 = clauses[k + 1].strip()
                # تنظيف الفواصل في نهاية السطر واستبدالها بنقطتين إن لزم
                c2_clean = re.sub(r"[،,؛;:]+$", "..", c2)
                line_content = f"{c1} {c2_clean}"
                if not line_content.endswith(("..", ".", "!", "؟", "?")):
                    line_content += ".."
                result.append(f"{line_content} ⏸️")
                k += 2
            else:
                c1 = clauses[k].strip()
                c1_clean = re.sub(r"[،,؛;:]+$", "..", c1)
                if not c1_clean.endswith(("..", ".", "!", "؟", "?")):
                    c1_clean += ".."
                result.append(f"{c1_clean} ⏸️")
                k += 1

    formatted = "\n".join(result)
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)
    return formatted.strip()


async def adapt_script_format(script_id: int, target_format: str) -> Tuple[str, int]:
    """تحويل الاسكريبت لريلز قصير 60 ثانية أو يوتيوب طويل أو تلقين وحفظه في قاعدة البيانات"""
    script_data = database.get_script_by_id(script_id)
    if not script_data:
        raise ValueError("السكريبت غير موجود في قاعدة البيانات!")

    original_text = script_data["script_text"]

    # نمط التلقين للشاشة: يعتمد على التنسيق المباشر للنص كاملاً دون استدعاء تلخيص لمنع حذف أي تفاصيل إطلاقاً
    if target_format == "teleprompter":
        adapted_text = format_script_to_teleprompter(original_text)
        format_label = "تلقين"
        adapted_script_id = database.save_script(
            user_id=script_data["user_id"],
            topic_title=f"{script_data['topic_title']} ({format_label})",
            era_category=script_data["era_category"],
            script_text=adapted_text,
            format_type=target_format,
        )
        return adapted_text, adapted_script_id

    if target_format == "reels_60s":
        instruction = """قم بإعادة كتابة هذا الاسكريبت ليكون ريلز / تيك توك مدته 60 ثانية بالضبط (حوالي 130 - 150 كلمة فقط).
سرد كلامي سريع ومكثف بالعامية المصرية بدون أي توجيهات مونتاج أو مؤثرات صوتية أو موسيقى نهائياً."""
    else:
        instruction = """قم بتوسيع هذا الاسكريبت ليكون حلقة يوتيوب مفصلة ومدتها 5 إلى 8 دقائق (سرد كلامي دسم وممتع بالعامية المصرية، تفاصيل وشخصيات وأحداث شيقة).
اكتب فقط الكلام الذي سيقوله صانع المحتوى بدون أي توجيهات للمونتاج أو الموسيقى نهائياً."""

    prompt = f"""{SCRIPT_SYSTEM_PROMPT}

الاسكريبت السابق:
{original_text}

المطلوب:
{instruction}"""

    raw_script = await call_gemini_api(prompt)
    adapted_text = clean_script_output(raw_script)

    format_label = "ريلز" if target_format == "reels_60s" else "يوتيوب"
    adapted_script_id = database.save_script(
        user_id=script_data["user_id"],
        topic_title=f"{script_data['topic_title']} ({format_label})",
        era_category=script_data["era_category"],
        script_text=adapted_text,
        format_type=target_format,
    )
    return adapted_text, adapted_script_id


def clean_text_for_speech(script_text: str) -> str:
    """تنظيف نص السكريبت ليكون جاهزاً للإلقاء الصوتي المباشر بدون عناوين أو رموز"""
    text = script_text
    # تحويل إيموجي الوقفات لوقفة صوتية طبيعية
    text = text.replace("⏸️", " . ")
    # إزالة العناوين والرموز
    text = re.sub(r"^.*?📌.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^.*?🏛️.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[🪝📖🤯🎯]\s*.*?:", "", text)
    text = text.replace("*", "").replace("#", "").replace("~", "")
    lines = []
    for line in text.split("\n"):
        cleaned = line.strip(" -:•.،")
        if cleaned and len(cleaned) > 2:
            lines.append(cleaned)
    return " . ".join(lines)
