# -*- coding: utf-8 -*-
"""
وحدة تحويل الاسكريبت المكتوب إلى تسجيل صوتي بالإلقاء المصري باستخدام Edge-TTS
"""

import os
import edge_tts
import logging

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "ar-EG-ShakirNeural"  # صوت مصري ذكوري دافئ وواضح للسرد التاريخي


async def synthesize_script_audio(
    text: str, output_file: str, voice: str = DEFAULT_VOICE
) -> str:
    """تحويل النص إلى ملف صوتي mp3 بصوت راوي مصري"""
    try:
        # التأكد من عدم تجاوز حد معقول للتسجيل
        trimmed_text = text[:3500]
        communicate = edge_tts.Communicate(
            text=trimmed_text,
            voice=voice,
            rate="+0%",
            pitch="+0Hz",
        )
        await communicate.save(output_file)
        return output_file
    except Exception as e:
        logger.error(f"خطأ أثناء توليد الصوت بواسطة Edge-TTS: {e}")
        raise
