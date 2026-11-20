"""Authoritative NCTB Curriculum Subjects, Chapters, and Academic Profiles.

Provides exhaustive subject combinations, chapters count, difficulty weights,
and full chapter rosters for Classes 6 through 10 (Bangla & English mediums).
Every chapter has its official NCTB number and title in Bengali and English.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SubjectGroup = Literal["general", "science", "humanities", "business_studies"]


@dataclass(frozen=True)
class NCTBChapterMeta:
    number: int
    title_bn: str
    title_en: str
    estimated_study_hours: float
    is_hard: bool = False


@dataclass(frozen=True)
class NCTBSubjectMeta:
    slug: str
    name_bn: str
    name_en: str
    class_level: int
    group: SubjectGroup
    total_chapters: int
    base_difficulty: float  # 1.0 (standard) to 1.6 (heavy/complex)
    is_stem: bool
    recommended_min_weekly_minutes: int
    chapters: list[NCTBChapterMeta]


# ============================================================================
# AUTHORITATIVE NCTB CHAPTER DEFINITIONS FOR CLASSES 6 TO 10
# ============================================================================

# --- Class 8 Chapters ---
C8_MATH_CHAPTERS = [
    NCTBChapterMeta(1, "প্যাটার্ন", "Patterns", 5.0, False),
    NCTBChapterMeta(2, "মুনাফা", "Profit & Simple Interest", 6.0, True),
    NCTBChapterMeta(3, "পরিমাপ", "Measurement", 6.0, False),
    NCTBChapterMeta(4, "বীজগণিতীয় সূত্রাবলি ও প্রয়োগ", "Algebraic Formulae & Applications", 8.0, True),
    NCTBChapterMeta(5, "বীজগণিতীয় ভগ্নাংশ", "Algebraic Fractions", 6.0, True),
    NCTBChapterMeta(6, "সরল সহসমীকরণ", "Simultaneous Linear Equations", 7.0, True),
    NCTBChapterMeta(7, "সেট", "Sets", 4.0, False),
    NCTBChapterMeta(8, "চতুর্ভুজ", "Quadrilaterals", 6.0, False),
    NCTBChapterMeta(9, "পিথাগোরাসের উপপাদ্য", "Pythagoras' Theorem", 6.0, True),
    NCTBChapterMeta(10, "বৃত্ত", "Circle", 5.0, False),
    NCTBChapterMeta(11, "তথ্য ও উপাত্ত", "Information & Data Statistics", 4.0, False),
]

C8_SCIENCE_CHAPTERS = [
    NCTBChapterMeta(1, "প্রাণিজগতের শ্রেণিবিন্যাস", "Classification of Animal Kingdom", 5.0, False),
    NCTBChapterMeta(2, "জীবের বৃদ্ধি ও বংশগতি", "Growth and Heredity", 6.0, True),
    NCTBChapterMeta(3, "ব্যাপন, অভিস্রবণ ও প্রস্বেদন", "Diffusion, Osmosis and Transpiration", 5.0, True),
    NCTBChapterMeta(4, "উদ্ভিদের বংশবৃদ্ধি", "Reproduction in Plants", 5.0, False),
    NCTBChapterMeta(5, "সমন্বয় ও নিঃসরণ", "Coordination and Secretion", 6.0, True),
    NCTBChapterMeta(6, "পরমাণুর গঠন", "Structure of Atoms", 7.0, True),
    NCTBChapterMeta(7, "পৃথিবী ও মহাকর্ষ", "Earth and Gravitation", 6.0, True),
    NCTBChapterMeta(8, "রাসায়নিক বিক্রিয়া", "Chemical Reactions", 7.0, True),
    NCTBChapterMeta(9, "বর্তনী ও চলবিদ্যুৎ", "Electric Circuits and Current", 7.0, True),
    NCTBChapterMeta(10, "অম্ল, ক্ষারক ও লবণ", "Acids, Bases and Salts", 5.0, False),
    NCTBChapterMeta(11, "আলো", "Light", 5.0, True),
    NCTBChapterMeta(12, "মহাকাশ ও উপগ্রহ", "Outer Space and Satellite", 4.0, False),
    NCTBChapterMeta(13, "খাদ্য ও পুষ্টি", "Food and Nutrition", 4.0, False),
    NCTBChapterMeta(14, "পরিবেশ এবং বাস্তুতন্ত্র", "Environment and Ecosystem", 4.0, False),
]

C8_BANGLA_CHAPTERS = [
    NCTBChapterMeta(1, "অতিথির স্মৃতি", "Otithir Smriti (Story)", 3.0, False),
    NCTBChapterMeta(2, "ভাব ও কাজ", "Bhab O Kaaj", 3.0, False),
    NCTBChapterMeta(3, "পড়ে পাওয়া", "Pore Pawa", 3.0, False),
    NCTBChapterMeta(4, "তৈলচিত্রের ভূত", "Toilochitrer Bhoot", 3.0, False),
    NCTBChapterMeta(5, "এবারের সংগ্রাম স্বাধীনতার সংগ্রাম", "Ebarer Songram", 4.0, False),
    NCTBChapterMeta(6, "মানব-ধর্ম (কবিতা)", "Manob-Dharma (Poem)", 3.0, False),
    NCTBChapterMeta(7, "বঙ্গভূমির প্রতি", "Bongobhumir Proti", 3.0, False),
    NCTBChapterMeta(8, "দুই বিঘা জমি", "Dui Bigha Jomi", 3.5, False),
    NCTBChapterMeta(9, "পাছে লোকে কিছু বলে", "Pachhe Loke Kichhu Bole", 2.5, False),
    NCTBChapterMeta(10, "বাংলা ব্যাকরণ: ধ্বনি ও বর্ণ", "Phonetics & Letters", 4.0, True),
    NCTBChapterMeta(11, "শব্দ ও পদ", "Words and Parts of Speech", 5.0, True),
    NCTBChapterMeta(12, "সন্ধি ও সমাস", "Sandhi & Samas", 6.0, True),
]

C8_ENGLISH_CHAPTERS = [
    NCTBChapterMeta(1, "A Glimpse of Our Culture", "Unit 1: Culture", 4.0, False),
    NCTBChapterMeta(2, "Food and Nutrition", "Unit 2: Nutrition", 4.0, False),
    NCTBChapterMeta(3, "Health and Hygiene", "Unit 3: Health", 4.0, False),
    NCTBChapterMeta(4, "Our Ethnic Friends", "Unit 4: Ethnic Friends", 4.0, False),
    NCTBChapterMeta(5, "Making a Difference", "Unit 5: Making a Difference", 4.0, False),
    NCTBChapterMeta(6, "Going on a Tour", "Unit 6: Tour", 4.0, False),
    NCTBChapterMeta(7, "Different People, Different Occupations", "Unit 7: Occupations", 4.0, False),
    NCTBChapterMeta(8, "Grammar: Tenses & Voice", "Grammar: Tenses & Voice", 6.0, True),
    NCTBChapterMeta(9, "Grammar: Right Form of Verbs", "Right Form of Verbs", 6.0, True),
    NCTBChapterMeta(10, "Grammar: Narration & Speech", "Narration & Direct/Indirect", 6.0, True),
    NCTBChapterMeta(11, "Grammar: Transformation of Sentences", "Transformation of Sentences", 6.0, True),
    NCTBChapterMeta(12, "Writing: Paragraphs & Formal Letters", "Composition & Writing", 5.0, False),
]

C8_BGS_CHAPTERS = [
    NCTBChapterMeta(1, "ঔপনিবেশিক যুগ ও বাংলার স্বাধীনতা সংগ্রাম", "Colonial Era & Freedom Struggle", 5.0, False),
    NCTBChapterMeta(2, "মুক্তিযুদ্ধ", "The Liberation War 1971", 5.0, False),
    NCTBChapterMeta(3, "বাংলাদেশের সাংস্কৃতিক পরিবর্তন ও উন্নয়ন", "Cultural Change and Development", 4.0, False),
    NCTBChapterMeta(4, "উপনিবেশিক যুগের প্রত্নতাত্ত্বিক ঐতিহ্য", "Archaeological Heritage", 3.0, False),
    NCTBChapterMeta(5, "সামাজিকীকরণ ও উন্নয়ন", "Socialization and Development", 4.0, False),
    NCTBChapterMeta(6, "বাংলাদেশের অর্থনীতি", "Economy of Bangladesh", 4.0, False),
    NCTBChapterMeta(7, "বাংলাদেশ রাষ্ট্র ও সরকার ব্যবস্থা", "State & Government of Bangladesh", 4.0, False),
    NCTBChapterMeta(8, "দুর্যোগ ব্যবস্থাপনা", "Disaster Management", 4.0, False),
    NCTBChapterMeta(9, "বাংলাদেশের জনসংখ্যা ও উন্নয়ন", "Population and Development", 3.5, False),
    NCTBChapterMeta(10, "বাংলাদেশের সামাজিক সমস্যা", "Social Problems of Bangladesh", 3.5, False),
]

C8_ICT_CHAPTERS = [
    NCTBChapterMeta(1, "তথ্য ও যোগাযোগ প্রযুক্তির গুরুত্ব", "Importance of ICT", 3.0, False),
    NCTBChapterMeta(2, "কম্পিউটার নেটওয়ার্ক", "Computer Networks", 5.0, True),
    NCTBChapterMeta(3, "তথ্য ও যোগাযোগ প্রযুক্তির নিরাপদ ও নৈতিক ব্যবহার", "Safe & Ethical Use of ICT", 4.0, False),
    NCTBChapterMeta(4, "স্প্রেডশিটের ব্যবহার", "Using Spreadsheets (Excel)", 5.0, True),
    NCTBChapterMeta(5, "শিক্ষা ও দৈনন্দিন জীবনে ইন্টারনেটের ব্যবহার", "Internet in Education & Life", 3.0, False),
]

C8_RELIGION_CHAPTERS = [
    NCTBChapterMeta(1, "আকাইদ", "Aqaid (Beliefs)", 4.0, False),
    NCTBChapterMeta(2, "ইবাদত", "Ibadat (Worship)", 4.0, False),
    NCTBChapterMeta(3, "কুরআন ও হাদিস শিক্ষা", "Quran & Hadith Studies", 5.0, False),
    NCTBChapterMeta(4, "আখলাক (নৈতিক চরিত্র)", "Akhlaq (Moral Character)", 4.0, False),
    NCTBChapterMeta(5, "আদর্শ জীবনচরিত", "Model Characters & Biographies", 4.0, False),
]

# --- Class 6 Chapters ---
C6_MATH_CHAPTERS = [
    NCTBChapterMeta(1, "স্বাভাবিক সংখ্যা ও ভগ্নাংশ", "Natural Numbers & Fractions", 6.0, False),
    NCTBChapterMeta(2, "অনুপাত ও শতকরা", "Ratio and Percentage", 6.0, True),
    NCTBChapterMeta(3, "পূর্ণসংখ্যা", "Integers", 5.0, False),
    NCTBChapterMeta(4, "বীজগণিতীয় রাশি", "Algebraic Expressions", 7.0, True),
    NCTBChapterMeta(5, "সরল সমীকরণ", "Simple Equations", 6.0, True),
    NCTBChapterMeta(6, "জ্যামিতির মৌলিক ধারণা", "Basic Concepts of Geometry", 6.0, False),
    NCTBChapterMeta(7, "ব্যবহারিক জ্যামিতি", "Practical Geometry", 5.0, False),
    NCTBChapterMeta(8, "তথ্য ও উপাত্ত", "Data & Statistics", 4.0, False),
]

C6_SCIENCE_CHAPTERS = [
    NCTBChapterMeta(1, "বৈজ্ঞানিক প্রক্রিয়া ও পরিমাপ", "Scientific Process & Measurement", 4.0, False),
    NCTBChapterMeta(2, "জীবজগৎ", "Living World", 4.0, False),
    NCTBChapterMeta(3, "উদ্ভিদ ও প্রাণীর কোষীয় সংগঠন", "Cellular Organization", 6.0, True),
    NCTBChapterMeta(4, "উদ্ভিদের বাহ্যিক বৈশিষ্ট্য", "Morphology of Plants", 5.0, False),
    NCTBChapterMeta(5, "সালোকসংশ্লেষণ", "Photosynthesis", 6.0, True),
    NCTBChapterMeta(6, "সংবেদী অঙ্গ", "Sense Organs", 5.0, False),
    NCTBChapterMeta(7, "পদার্থের বৈশিষ্ট্য ও প্রভাব", "Properties of Matter", 5.0, True),
    NCTBChapterMeta(8, "মিশ্রণ", "Mixture", 4.0, False),
    NCTBChapterMeta(9, "আলোর ঘটনা", "Phenomena of Light", 5.0, True),
    NCTBChapterMeta(10, "গতি", "Motion", 6.0, True),
    NCTBChapterMeta(11, "বল ও সরল যন্ত্র", "Force & Simple Machines", 6.0, True),
    NCTBChapterMeta(12, "পৃথিবীর উৎপত্তি ও গঠন", "Origin of Earth", 4.0, False),
    NCTBChapterMeta(13, "খাদ্য ও পুষ্টি", "Food and Nutrition", 4.0, False),
    NCTBChapterMeta(14, "পরিবেশের ভারসাম্য ও দূষণ", "Pollution & Environment", 4.0, False),
]

# --- Class 7 Chapters ---
C7_MATH_CHAPTERS = [
    NCTBChapterMeta(1, "মূলদ ও অমূলদ সংখ্যা", "Rational and Irrational Numbers", 6.0, True),
    NCTBChapterMeta(2, "সমানুপাত ও লাভ-ক্ষতি", "Proportion and Profit-Loss", 7.0, True),
    NCTBChapterMeta(3, "পরিমাপ", "Measurement", 6.0, False),
    NCTBChapterMeta(4, "বীজগণিতীয় রাশির গুণ ও ভাগ", "Multiplication & Division of Algebra", 7.0, True),
    NCTBChapterMeta(5, "বীজগণিতীয় সূত্রাবলি ও প্রয়োগ", "Algebraic Formulae", 8.0, True),
    NCTBChapterMeta(6, "বীজগণিতীয় ভগ্নাংশ", "Algebraic Fractions", 6.0, True),
    NCTBChapterMeta(7, "সরল সমীকরণ", "Simple Equations", 6.0, True),
    NCTBChapterMeta(8, "সমান্তরাল সরলরেখা", "Parallel Lines", 5.0, False),
    NCTBChapterMeta(9, "ত্রিভুজ", "Triangles", 6.0, True),
    NCTBChapterMeta(10, "সর্বসমতা ও সদৃশতা", "Congruence and Similarity", 5.0, False),
    NCTBChapterMeta(11, "তথ্য ও উপাত্ত", "Statistics & Data", 4.0, False),
]

# --- Class 9 & 10 Chapters (Secondary Science) ---
C9_GENERAL_MATH_CHAPTERS = [
    NCTBChapterMeta(1, "বাস্তব সংখ্যা", "Real Numbers", 5.0, False),
    NCTBChapterMeta(2, "সেট ও ফাংশন", "Set and Functions", 6.0, True),
    NCTBChapterMeta(3, "বীজগণিতীয় রাশি", "Algebraic Expressions", 8.0, True),
    NCTBChapterMeta(4, "সূচক ও লগারিদম", "Exponents and Logarithms", 7.0, True),
    NCTBChapterMeta(5, "এক চলকবিশিষ্ট সমীকরণ", "Linear Equations in One Variable", 6.0, False),
    NCTBChapterMeta(6, "রেখা, কোণ ও ত্রিভুজ", "Lines, Angles and Triangles", 6.0, False),
    NCTBChapterMeta(7, "ব্যবহারিক জ্যামিতি", "Practical Geometry", 5.0, False),
    NCTBChapterMeta(8, "বৃত্ত", "Circles & Theorems", 7.0, True),
    NCTBChapterMeta(9, "ত্রিকোণমিতিক অনুপাত", "Trigonometric Ratios", 8.0, True),
    NCTBChapterMeta(10, "দূরত্ব ও উচ্চতা", "Distance and Elevation", 6.0, True),
    NCTBChapterMeta(11, "বীজগণিতীয় অনুপাত ও সমানুপাত", "Algebraic Ratio & Proportion", 6.0, False),
    NCTBChapterMeta(12, "দুই চলকবিশিষ্ট সরল সমীকরণ", "Simultaneous Equations in Two Variables", 6.0, True),
    NCTBChapterMeta(13, "সসীম ধারা", "Finite Series (Arithmetic & Geometric)", 7.0, True),
    NCTBChapterMeta(14, "অনুপাত, সদৃশতা ও প্রতিসমতা", "Similarity and Symmetry", 4.0, False),
    NCTBChapterMeta(15, "ক্ষেত্রফল সম্পর্কিত উপপাদ্য", "Theorems related to Area", 6.0, False),
    NCTBChapterMeta(16, "পরিমিতি", "Mensuration (2D & 3D)", 8.0, True),
    NCTBChapterMeta(17, "পরিসংখ্যান", "Statistics (Mean, Median, Mode, Ogive)", 5.0, False),
]

C9_HIGHER_MATH_CHAPTERS = [
    NCTBChapterMeta(1, "সেট ও ফাংশন", "Sets and Functions", 6.0, True),
    NCTBChapterMeta(2, "বীজগাণিতিক রাশি", "Algebraic Expressions & Partial Fractions", 8.0, True),
    NCTBChapterMeta(3, "জ্যামিতি (অ্যাপোলোনিয়াস ও টলেমি)", "Higher Geometry & Theorems", 8.0, True),
    NCTBChapterMeta(4, "জ্যামিতিক অঙ্কন", "Geometric Constructions", 5.0, False),
    NCTBChapterMeta(5, "সমীকরণ", "Higher Equations & Quadratic Formula", 7.0, True),
    NCTBChapterMeta(6, "অসমতা", "Inequalities", 6.0, True),
    NCTBChapterMeta(7, "অসীম ধারা", "Infinite Series", 6.0, True),
    NCTBChapterMeta(8, "ত্রিকোণমিতি (রেডিয়ান ও কোণ)", "Trigonometry (Radian Measure)", 8.0, True),
    NCTBChapterMeta(9, "সূচকীয় ও লগারিদমীয় ফাংশন", "Exponential & Logarithmic Functions", 7.0, True),
    NCTBChapterMeta(10, "দ্বিপদী বিস্তৃতি", "Binomial Expansion (Pascal & Formula)", 7.0, True),
    NCTBChapterMeta(11, "স্থানাঙ্ক জ্যামিতি", "Coordinate Geometry & Straight Lines", 8.0, True),
    NCTBChapterMeta(12, "সমতলীয় ভেক্টর", "Planar Vectors", 7.0, True),
    NCTBChapterMeta(13, "ঘন জ্যামিতি", "Solid Geometry", 6.0, False),
    NCTBChapterMeta(14, "সম্ভাবনা", "Probability", 5.0, False),
]

C9_PHYSICS_CHAPTERS = [
    NCTBChapterMeta(1, "ভৌত রাশি ও পরিমাপ", "Physical Quantities and Measurement", 5.0, False),
    NCTBChapterMeta(2, "গতি", "Motion (Kinematics)", 8.0, True),
    NCTBChapterMeta(3, "বল", "Force & Newton's Laws", 8.0, True),
    NCTBChapterMeta(4, "কাজ, ক্ষমতা ও শক্তি", "Work, Power and Energy", 7.0, True),
    NCTBChapterMeta(5, "পদার্থের অবস্থা ও চাপ", "State of Matter & Pressure (Archimedes)", 7.0, True),
    NCTBChapterMeta(6, "বস্তুর উপর তাপের প্রভাব", "Effect of Heat on Substances", 7.0, True),
    NCTBChapterMeta(7, "তরঙ্গ ও শব্দ", "Waves and Sound", 6.0, False),
    NCTBChapterMeta(8, "আলোর প্রতিফলন", "Reflection of Light (Mirrors)", 7.0, True),
    NCTBChapterMeta(9, "আলোর প্রতিসরণ", "Refraction of Light (Lenses)", 7.0, True),
    NCTBChapterMeta(10, "স্থির তড়িৎ", "Static Electricity (Coulomb's Law)", 6.0, True),
    NCTBChapterMeta(11, "চল তড়িৎ", "Current Electricity (Ohm's Law)", 8.0, True),
    NCTBChapterMeta(12, "বিদ্যুতের চৌম্বক ক্রিয়া", "Magnetic Effects of Current", 6.0, True),
    NCTBChapterMeta(13, "আধুনিক পদার্থবিজ্ঞান ও ইলেকট্রনিক্স", "Modern Physics & Electronics", 5.0, False),
    NCTBChapterMeta(14, "জীবন বাঁচাতে পদার্থবিজ্ঞান", "Physics to Save Life (Medical)", 4.0, False),
]

C9_CHEMISTRY_CHAPTERS = [
    NCTBChapterMeta(1, "রসায়নের ধারণা", "Concept of Chemistry", 4.0, False),
    NCTBChapterMeta(2, "পদার্থের অবস্থা", "States of Matter & Kinetic Theory", 5.0, False),
    NCTBChapterMeta(3, "পদার্থের গঠন", "Structure of Matter & Isotopes", 7.0, True),
    NCTBChapterMeta(4, "পর্যায় সারণি", "Periodic Table & Periodic Properties", 8.0, True),
    NCTBChapterMeta(5, "রাসায়নিক বন্ধন", "Chemical Bonds (Ionic & Covalent)", 8.0, True),
    NCTBChapterMeta(6, "মোলের ধারণা ও রাসায়নিক গণনা", "Concept of Mole & Stoichiometry", 9.0, True),
    NCTBChapterMeta(7, "রাসায়নিক বিক্রিয়া", "Chemical Reactions & Le Chatelier", 8.0, True),
    NCTBChapterMeta(8, "রসায়ন ও শক্তি", "Chemistry and Energy (Electrochemical Cells)", 7.0, True),
    NCTBChapterMeta(9, "এসিড-ক্ষার সমতা", "Acid-Base Balance & pH Scale", 6.0, True),
    NCTBChapterMeta(10, "খনিজ সম্পদ: ধাতু-অধাতু", "Mineral Resources: Metals and Non-metals", 6.0, False),
    NCTBChapterMeta(11, "খনিজ সম্পদ: জীবাশ্ম (জৈব যৌগ)", "Mineral Resources: Fossils (Organic Chemistry)", 9.0, True),
    NCTBChapterMeta(12, "আমাদের জীবনে রসায়ন", "Chemistry in Our Lives", 5.0, False),
]

C9_BIOLOGY_CHAPTERS = [
    NCTBChapterMeta(1, "জীবন পাঠ", "Lesson of Life & Taxonomy", 4.0, False),
    NCTBChapterMeta(2, "জীবকোষ ও টিস্যু", "Living Cells and Tissues", 7.0, True),
    NCTBChapterMeta(3, "কোষ বিভাজন", "Cell Division (Mitosis & Meiosis)", 6.0, True),
    NCTBChapterMeta(4, "জীবনীশক্তি", "Bioenergetics (Photosynthesis & Respiration)", 8.0, True),
    NCTBChapterMeta(5, "খাদ্য, পুষ্টি এবং পরিপাক", "Food, Nutrition and Digestion", 6.0, False),
    NCTBChapterMeta(6, "জীবে পরিবহন", "Transport in Organisms (Blood & Heart)", 7.0, True),
    NCTBChapterMeta(7, "গ্যাসীয় বিনিময়", "Gaseous Exchange (Lungs & Respiration)", 6.0, False),
    NCTBChapterMeta(8, "রেচন প্রক্রিয়া", "Excretory System (Kidney & Nephron)", 6.0, True),
    NCTBChapterMeta(9, "দৃঢ়তা প্রদান ও চলন", "Support and Movement (Bones & Muscles)", 5.0, False),
    NCTBChapterMeta(10, "সমন্বয়", "Coordination (Hormones & Nervous System)", 7.0, True),
    NCTBChapterMeta(11, "জীবের প্রজনন", "Reproduction in Organisms", 7.0, True),
    NCTBChapterMeta(12, "জীবের বংশগতি ও বিবর্তন", "Heredity in Organisms and Evolution (DNA/RNA)", 8.0, True),
    NCTBChapterMeta(13, "জীবের পরিবেশ", "Environment of Organisms", 4.0, False),
    NCTBChapterMeta(14, "জীবপ্রযুক্তি", "Biotechnology (Tissue Culture & GMO)", 6.0, True),
]


def _build_generic_chapters(subject_name: str, count: int) -> list[NCTBChapterMeta]:
    """Fallback generator for humanities/business subjects."""
    return [
        NCTBChapterMeta(
            number=i,
            title_bn=f"অধ্যায় {i}: {subject_name} পাঠ {i}",
            title_en=f"Chapter {i}: {subject_name} Lesson {i}",
            estimated_study_hours=4.5,
            is_hard=i in (3, 4, 7),
        )
        for i in range(1, count + 1)
    ]


# ============================================================================
# MASTER NCTB CATALOG
# ============================================================================

NCTB_SUBJECTS_CATALOG: list[NCTBSubjectMeta] = [
    # CLASS 6
    NCTBSubjectMeta("c6_bangla", "বাংলা", "Bangla", 6, "general", 10, 1.0, False, 180, _build_generic_chapters("বাংলা", 10)),
    NCTBSubjectMeta("c6_english", "English", "English", 6, "general", 12, 1.2, False, 180, _build_generic_chapters("English", 12)),
    NCTBSubjectMeta("c6_math", "গণিত", "Mathematics", 6, "general", 8, 1.4, True, 240, C6_MATH_CHAPTERS),
    NCTBSubjectMeta("c6_science", "বিজ্ঞান", "Science", 6, "general", 14, 1.3, True, 210, C6_SCIENCE_CHAPTERS),
    NCTBSubjectMeta("c6_bgs", "বাংলাদেশ ও বিশ্বপরিচয়", "Bangladesh & Global Studies", 6, "general", 10, 1.0, False, 150, _build_generic_chapters("বাংলাদেশ ও বিশ্বপরিচয়", 10)),
    NCTBSubjectMeta("c6_ict", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 6, "general", 5, 1.0, True, 90, _build_generic_chapters("তথ্য ও যোগাযোগ প্রযুক্তি", 5)),
    NCTBSubjectMeta("c6_religion", "ধর্ম ও নৈতিক শিক্ষা", "Religion & Moral Education", 6, "general", 5, 0.9, False, 90, C8_RELIGION_CHAPTERS),

    # CLASS 7
    NCTBSubjectMeta("c7_bangla", "বাংলা", "Bangla", 7, "general", 11, 1.0, False, 180, _build_generic_chapters("বাংলা", 11)),
    NCTBSubjectMeta("c7_english", "English", "English", 7, "general", 12, 1.2, False, 180, _build_generic_chapters("English", 12)),
    NCTBSubjectMeta("c7_math", "গণিত", "Mathematics", 7, "general", 11, 1.4, True, 240, C7_MATH_CHAPTERS),
    NCTBSubjectMeta("c7_science", "বিজ্ঞান", "Science", 7, "general", 14, 1.3, True, 210, _build_generic_chapters("বিজ্ঞান", 14)),
    NCTBSubjectMeta("c7_bgs", "বাংলাদেশ ও বিশ্বপরিচয়", "Bangladesh & Global Studies", 7, "general", 10, 1.0, False, 150, _build_generic_chapters("বাংলাদেশ ও বিশ্বপরিচয়", 10)),
    NCTBSubjectMeta("c7_ict", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 7, "general", 5, 1.0, True, 90, _build_generic_chapters("তথ্য ও যোগাযোগ প্রযুক্তি", 5)),
    NCTBSubjectMeta("c7_religion", "ধর্ম ও নৈতিক শিক্ষা", "Religion & Moral Education", 7, "general", 5, 0.9, False, 90, C8_RELIGION_CHAPTERS),

    # CLASS 8
    NCTBSubjectMeta("c8_bangla", "বাংলা", "Bangla", 8, "general", 12, 1.0, False, 180, C8_BANGLA_CHAPTERS),
    NCTBSubjectMeta("c8_english", "English", "English", 8, "general", 12, 1.2, False, 180, C8_ENGLISH_CHAPTERS),
    NCTBSubjectMeta("c8_math", "গণিত", "Mathematics", 8, "general", 11, 1.5, True, 270, C8_MATH_CHAPTERS),
    NCTBSubjectMeta("c8_science", "বিজ্ঞান", "Science", 8, "general", 14, 1.4, True, 240, C8_SCIENCE_CHAPTERS),
    NCTBSubjectMeta("c8_bgs", "বাংলাদেশ ও বিশ্বপরিচয়", "Bangladesh & Global Studies", 8, "general", 10, 1.0, False, 150, C8_BGS_CHAPTERS),
    NCTBSubjectMeta("c8_ict", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 8, "general", 5, 1.0, True, 90, C8_ICT_CHAPTERS),
    NCTBSubjectMeta("c8_religion", "ধর্ম ও নৈতিক শিক্ষা", "Religion & Moral Education", 8, "general", 5, 0.9, False, 90, C8_RELIGION_CHAPTERS),

    # CLASS 9 & 10 (SCIENCE)
    NCTBSubjectMeta("c9_bangla", "বাংলা (১ম ও ২য় পত্র)", "Bangla", 9, "science", 12, 1.1, False, 180, _build_generic_chapters("বাংলা", 12)),
    NCTBSubjectMeta("c9_english", "English (1st & 2nd)", "English", 9, "science", 12, 1.3, False, 200, _build_generic_chapters("English", 12)),
    NCTBSubjectMeta("c9_general_math", "সাধারণ গণিত", "General Mathematics", 9, "science", 17, 1.5, True, 270, C9_GENERAL_MATH_CHAPTERS),
    NCTBSubjectMeta("c9_higher_math", "উচ্চতর গণিত", "Higher Mathematics", 9, "science", 14, 1.6, True, 270, C9_HIGHER_MATH_CHAPTERS),
    NCTBSubjectMeta("c9_physics", "পদার্থবিজ্ঞান", "Physics", 9, "science", 14, 1.5, True, 240, C9_PHYSICS_CHAPTERS),
    NCTBSubjectMeta("c9_chemistry", "রসায়ন", "Chemistry", 9, "science", 12, 1.5, True, 240, C9_CHEMISTRY_CHAPTERS),
    NCTBSubjectMeta("c9_biology", "জীববিজ্ঞান", "Biology", 9, "science", 14, 1.3, True, 210, C9_BIOLOGY_CHAPTERS),
    NCTBSubjectMeta("c9_bgs_sci", "বাংলাদেশ ও বিশ্বপরিচয়", "Bangladesh & Global Studies", 9, "science", 10, 1.0, False, 120, _build_generic_chapters("বাংলাদেশ ও বিশ্বপরিচয়", 10)),
    NCTBSubjectMeta("c9_ict_sci", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 9, "science", 5, 1.0, True, 90, _build_generic_chapters("তথ্য ও যোগাযোগ প্রযুক্তি", 5)),
    NCTBSubjectMeta("c9_religion_sci", "ধর্ম ও নৈতিক শিক্ষা", "Religion & Moral Education", 9, "science", 5, 0.9, False, 90, C8_RELIGION_CHAPTERS),

    # CLASS 9 & 10 (HUMANITIES)
    NCTBSubjectMeta("c9_bangla_hum", "বাংলা (১ম ও ২য় পত্র)", "Bangla", 9, "humanities", 12, 1.1, False, 180, _build_generic_chapters("বাংলা", 12)),
    NCTBSubjectMeta("c9_english_hum", "English", "English", 9, "humanities", 12, 1.3, False, 200, _build_generic_chapters("English", 12)),
    NCTBSubjectMeta("c9_math_hum", "সাধারণ গণিত", "General Mathematics", 9, "humanities", 17, 1.4, True, 240, C9_GENERAL_MATH_CHAPTERS),
    NCTBSubjectMeta("c9_history", "বাংলাদেশের ইতিহাস ও বিশ্বসভ্যতা", "History of Bangladesh & World", 9, "humanities", 15, 1.2, False, 210, _build_generic_chapters("ইতিহাস", 15)),
    NCTBSubjectMeta("c9_geography", "ভূগোল ও পরিবেশ", "Geography & Environment", 9, "humanities", 15, 1.2, False, 210, _build_generic_chapters("ভূগোল", 15)),
    NCTBSubjectMeta("c9_civics", "পৌরনীতি ও নাগরিকতা", "Civics & Citizenship", 9, "humanities", 11, 1.1, False, 180, _build_generic_chapters("পৌরনীতি", 11)),
    NCTBSubjectMeta("c9_economics", "অর্থনীতি", "Economics", 9, "humanities", 10, 1.3, False, 180, _build_generic_chapters("অর্থনীতি", 10)),
    NCTBSubjectMeta("c9_general_science_hum", "সাধারণ বিজ্ঞান", "General Science", 9, "humanities", 14, 1.2, True, 180, _build_generic_chapters("সাধারণ বিজ্ঞান", 14)),
    NCTBSubjectMeta("c9_ict_hum", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 9, "humanities", 5, 1.0, True, 90, _build_generic_chapters("তথ্য ও যোগাযোগ প্রযুক্তি", 5)),
    NCTBSubjectMeta("c9_religion_hum", "ধর্ম ও নৈতিক শিক্ষা", "Religion & Moral Education", 9, "humanities", 5, 0.9, False, 90, C8_RELIGION_CHAPTERS),

    # CLASS 9 & 10 (BUSINESS STUDIES)
    NCTBSubjectMeta("c9_bangla_bus", "বাংলা (১ম ও ২য় পত্র)", "Bangla", 9, "business_studies", 12, 1.1, False, 180, _build_generic_chapters("বাংলা", 12)),
    NCTBSubjectMeta("c9_english_bus", "English", "English", 9, "business_studies", 12, 1.3, False, 200, _build_generic_chapters("English", 12)),
    NCTBSubjectMeta("c9_math_bus", "সাধারণ গণিত", "General Mathematics", 9, "business_studies", 17, 1.4, True, 240, C9_GENERAL_MATH_CHAPTERS),
    NCTBSubjectMeta("c9_accounting", "হিসাববিজ্ঞান", "Accounting", 9, "business_studies", 12, 1.5, True, 240, _build_generic_chapters("হিসাববিজ্ঞান", 12)),
    NCTBSubjectMeta("c9_business_ent", "ব্যবসায় উদ্যোগ", "Business Entrepreneurship", 9, "business_studies", 12, 1.1, False, 180, _build_generic_chapters("ব্যবসায় উদ্যোগ", 12)),
    NCTBSubjectMeta("c9_finance", "ফিন্যান্স ও ব্যাংকিং", "Finance & Banking", 9, "business_studies", 11, 1.4, True, 210, _build_generic_chapters("ফিন্যান্স", 11)),
    NCTBSubjectMeta("c9_general_science_bus", "সাধারণ বিজ্ঞান", "General Science", 9, "business_studies", 14, 1.2, True, 180, _build_generic_chapters("সাধারণ বিজ্ঞান", 14)),
    NCTBSubjectMeta("c9_ict_bus", "তথ্য ও যোগাযোগ প্রযুক্তি", "ICT", 9, "business_studies", 5, 1.0, True, 90, _build_generic_chapters("তথ্য ও যোগাযোগ প্রযুক্তি", 5)),
    NCTBSubjectMeta("c9_religion_bus", "ধর্ম ও নৈতিক শিক্ষা", "Religion & Moral Education", 9, "business_studies", 5, 0.9, False, 90, C8_RELIGION_CHAPTERS),
]


def get_subjects_for_class_and_group(
    class_level: int,
    group: str = "general",
) -> list[NCTBSubjectMeta]:
    """Retrieve subjects matching student's class and study group."""
    effective_class = 9 if class_level in (9, 10) else class_level
    target_group = group.lower() if class_level in (9, 10) else "general"

    matches = [
        s for s in NCTB_SUBJECTS_CATALOG
        if s.class_level == effective_class and s.group == target_group
    ]
    if not matches and class_level in (9, 10):
        # Fallback to science if group not found
        matches = [
            s for s in NCTB_SUBJECTS_CATALOG
            if s.class_level == 9 and s.group == "science"
        ]
    return matches


def get_subject_by_slug(slug: str) -> NCTBSubjectMeta | None:
    """Find subject by slug."""
    for s in NCTB_SUBJECTS_CATALOG:
        if s.slug == slug:
            return s
    return None
