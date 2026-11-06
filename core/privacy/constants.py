"""Parental consent legal text constants and cryptographic hash definitions."""

from __future__ import annotations

import hashlib

# Canonical legal consent disclosure presented to parents in Bengali
PARENTAL_CONSENT_TEXT_BN = (
    "আমি নিশ্চিত করছি যে আমি শিক্ষার্থীর আইনগত অভিভাবক এবং থিংকবাডি প্ল্যাটফর্মে শিক্ষার্থীর পড়াশোনা সংক্রান্ত তথ্য "
    "প্রক্রিয়াকরণে সম্মতি দিচ্ছি। শিক্ষার্থীর প্রোফাইল, দৈনিক পড়ার সময়, কুইজের ফলাফল এবং পড়াশোনার অগ্রগতির উপর ভিত্তি করে "
    "ব্যক্তিগতকৃত পাঠ পরিকল্পনা তৈরি করা হবে। কাঁচা চ্যাট বার্তা কোনো তৃতীয় পক্ষের সাথে ভাগ করা হবে না এবং যেকোনো সময় "
    "সম্মতি প্রত্যাহার অথবা ডেটা মুছে ফেলার অনুরোধ করা যাবে।"
)

# Canonical legal consent disclosure presented to parents in English
PARENTAL_CONSENT_TEXT_EN = (
    "I confirm that I am the legal guardian and consent to ThinkBuddy processing study data for the minor student under "
    "applicable child privacy protections. Personalized study schedules will be generated based on curriculum progress, "
    "quiz responses, and study duration. Raw chat transcripts are never shared with third parties, and parental consent "
    "may be withdrawn or data deletion requested at any time."
)

# Full composite legal text
PARENTAL_CONSENT_TERMS_TEXT = f"{PARENTAL_CONSENT_TEXT_BN} ({PARENTAL_CONSENT_TEXT_EN})"

CURRENT_CONSENT_VERSION = "v1.0"

# Cryptographic SHA-256 fingerprint of the active legal disclosure text
CURRENT_CONSENT_TEXT_HASH: str = hashlib.sha256(
    PARENTAL_CONSENT_TERMS_TEXT.strip().encode("utf-8")
).hexdigest()


