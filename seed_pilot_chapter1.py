import uuid
import psycopg2
import json

def seed_pilot():
    conn = psycopg2.connect("postgresql://thinkbuddy:thinkbuddy_dev_password@127.0.0.1:5432/thinkbuddy")
    cur = conn.cursor()
    
    # 1. math_books
    book_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO math_books (id, class_level, medium, title, version_year)
        VALUES (%s, 8, 'bangla', 'গণিত - অষ্টম শ্রেণি', 2026)
        ON CONFLICT (class_level, medium, title) DO UPDATE 
        SET updated_at = NOW()
        RETURNING id;
    """, (book_id,))
    book_id = cur.fetchone()[0]

    # 2. math_chapters
    chap_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO math_chapters (id, book_id, class_level, medium, chapter_number, title, title_ascii, printed_page_start, printed_page_end)
        VALUES (%s, %s, 8, 'bangla', 1, 'প্যাটার্ন', 'Pattern', 1, 11)
        ON CONFLICT (book_id, chapter_number) DO UPDATE
        SET title = EXCLUDED.title
        RETURNING id;
    """, (chap_id, book_id))
    chap_id = cur.fetchone()[0]

    # 3. math_theory
    theories = [
        ("formula", "ক্রমিক স্বাভাবিক বিজোড় সংখ্যার যোগফল", "প্রথম ক সংখ্যক ক্রমিক স্বাভাবিক বিজোড় সংখ্যার যোগফল = ক^২। সূত্র: ১ + ৩ + ৫ + ... + (২ক - ১) = ক^২।", 4),
        ("formula", "ক্রমিক স্বাভাবিক সংখ্যার সমষ্টি", "ক্রমিক স্বাভাবিক সংখ্যার সমষ্টি = [ (১ম সংখ্যা + শেষ সংখ্যা) / ২ ] × পদসংখ্যা।", 4),
        ("definition", "ফিবোনাচ্চি সংখ্যা", "পরপর দুইটি সংখ্যার যোগফল পরবর্তী সংখ্যার সমান হলে তাকে ফিবোনাচ্চি সংখ্যা বলে। যেমন: ০, ১, ১, ২, ৩, ৫, ৮, ১৩, ২১, ...।", 3),
        ("rule", "দুইটি বর্গের সমষ্টিরূপে প্রকাশ", "যেকোনো স্বাভাবিক সংখ্যাকে দুইটি স্বাভাবিক সংখ্যার বর্গের সমষ্টিরূপে প্রকাশ করা যায়। যেমন: ২৯ = ৪ + ২৫ = ২^২ + ৫^২ এবং ৩৭ = ১ + ৩৬ = ১^২ + ৬^২।", 7),
        ("rule", "অঙ্ক স্থান বিনিময়ে ৯ দ্বারা বিভাজ্যতা", "যেকোনো দুই অঙ্কের সংখ্যার অঙ্কদ্বয় স্থান বিনিময় করে যে সংখ্যা পাওয়া যায়, বৃহত্তর সংখ্যা থেকে ক্ষুদ্রতর সংখ্যা বিয়োগ করলে বিয়োগফল সর্বদা ৯ দ্বারা বিভাজ্য।", 7)
    ]
    for t_type, t_title, t_content, t_page in theories:
        cur.execute("""
            INSERT INTO math_theory (id, chapter_id, theory_type, title, content, printed_page)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (str(uuid.uuid4()), chap_id, t_type, t_title, t_content, t_page))

    # 4. math_exercises
    ex_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO math_exercises (id, chapter_id, exercise_label, exercise_label_ascii, printed_page_start, printed_page_end)
        VALUES (%s, %s, 'অনুশীলনী ১', '1', 9, 10)
        ON CONFLICT (chapter_id, exercise_label) DO UPDATE
        SET printed_page_start = 9
        RETURNING id;
    """, (ex_id, chap_id))
    ex_id = cur.fetchone()[0]

    # 5. math_items_v2 & math_solutions & math_hints
    items_data = [
        {
            "qno": 1,
            "qno_disp": "১",
            "type": "mcq",
            "subpart": None,
            "stimulus": None,
            "text": "নিচের কোন ফলাফলটি ৯ দ্বারা বিভাজ্য সংখ্যা?",
            "text_ascii": "Which of the following result is divisible by 9? 52+25, 527+725, 412+234, 75-57",
            "options": ["৫২+২৫", "৫২৭+৭২৫", "৪১২+২৩৪", "৭৫-৫৭"],
            "page": 9,
            "pdf_p": 13,
            "needs_figure": False,
            "steps": [
                "প্রত্যেকটি অপশনের ফলাফল হিসাব করে দেখি:",
                "ক) $৫২ + ২৫ = ৭৭$, যা ৯ দ্বারা বিভাজ্য নয় ($৭৭ = ৯ \\times ৮ + ৫$)।",
                "খ) $৫২৭ + ৭২৫ = ১২৫২$, অঙ্কগুলোর যোগফল $১+২+৫+২ = ১০$, যা ৯ দ্বারা বিভাজ্য নয়।",
                "গ) $৪১২ + ২৩৪ = ৬৪৬$, অঙ্কগুলোর যোগফল $৬+৪+৬ = ১৬$, যা ৯ দ্বারা বিভাজ্য নয়।",
                "ঘ) $৭৫ - ৫৭ = ১৮$। ১৮ সংখ্যাটি ৯ দ্বারা নিঃশেষে বিভাজ্য ($১৮ = ৯ \\times ২$)।",
                "তাছাড়া পাঠ্যবইয়ের নিয়ম অনুযায়ী: দুই অঙ্কের কোনো সংখ্যার অঙ্কদ্বয় স্থান বিনিময় করলে প্রাপ্ত সংখ্যার বিয়োগফল সর্বদা ৯ দ্বারা বিভাজ্য। এখানে ৭৫ এর অঙ্ক স্থান বিনিময় করলে ৫৭ হয় এবং বিয়োগফল ১৮, যা ৯ দ্বারা বিভাজ্য।"
            ],
            "ans": "ঘ) ৭৫-৫৭",
            "ans_ascii": "gh) 75-57",
            "method": "অঙ্ক স্থান বিনিময় বিয়োগের নিয়ম ও বিভাজ্যতা পরীক্ষা",
            "theory_page": 7,
            "verifier": {"sympy_eval": "(75 - 57) % 9 == 0", "is_correct": True, "method": "exact_arithmetic"},
            "hints": [
                "দুই অঙ্কের একটি সংখ্যার অঙ্ক স্থান বিনিময় করে বিয়োগ করলে কী ঘটে মনে করো।",
                "বিয়োগফল সর্বদা ৯ দ্বারা বিভাজ্য হয়। ৭৫ এবং ৫৭ এর মধ্যে সম্পর্কটি দেখো।",
                "৭৫ - ৫৭ = ১৮ হিসাব করো এবং ১৮ কে ৯ দিয়ে ভাগ করে নিশ্চিত হও।"
            ]
        },
        {
            "qno": 2,
            "qno_disp": "২",
            "type": "mcq",
            "subpart": None,
            "stimulus": None,
            "text": "'ক' সংখ্যক ক্রমিক স্বাভাবিক বিজোড় সংখ্যার যোগফল কত?",
            "text_ascii": "What is the sum of first k consecutive odd natural numbers?",
            "options": ["ক", "২ক - ১", "ক^২", "২ক + ১"],
            "page": 9,
            "pdf_p": 13,
            "needs_figure": False,
            "steps": [
                "ক্রমিক স্বাভাবিক বিজোড় সংখ্যাগুলো হলো: ১, ৩, ৫, ৭, ৯, ...",
                "প্রথম ১টি বিজোড় সংখ্যার যোগফল = $১ = ১^২$",
                "প্রথম ২টি বিজোড় সংখ্যার যোগফল = $১ + ৩ = ৪ = ২^২$",
                "প্রথম ৩টি বিজোড় সংখ্যার যোগফল = $১ + ৩ + ৫ = ৯ = ৩^২$",
                "প্রথম ৪টি বিজোড় সংখ্যার যোগফল = $১ + ৩ + ৫ + ৭ = ১৬ = ৪^২$",
                "সুতরাং দেখা যাচ্ছে, প্রথম যতটি ক্রমিক বিজোড় সংখ্যার যোগফল নেওয়া হয়, যোগফল সেই সংখ্যার বর্গের সমান হয়।",
                "অতএব, প্রথম 'ক' সংখ্যক ক্রমিক স্বাভাবিক বিজোড় সংখ্যার যোগফল হবে $ক^২$।"
            ],
            "ans": "গ) ক^২",
            "ans_ascii": "g) k^2",
            "method": "ক্রমিক স্বাভাবিক বিজোড় সংখ্যার প্যাটার্ন সূত্র",
            "theory_page": 4,
            "verifier": {"sympy_eval": "sympy.summation(2*i - 1, (i, 1, k)) == k**2", "is_correct": True, "method": "symbolic_algebra"},
            "hints": [
                "প্রথম ১টি, ২টি ও ৩টি বিজোড় সংখ্যা যোগ করে দেখো কোনো বিশেষ প্যাটার্ন পাও কি না।",
                "১+৩=৪ (২ এর বর্গ), ১+৩+৫=৯ (৩ এর বর্গ)।",
                "সুতরাং ক-সংখ্যক বিজোড় সংখ্যার সমষ্টি ক এর বর্গ অর্থাৎ ক^২ হবে।"
            ]
        },
        {
            "qno": 3,
            "qno_disp": "৩",
            "type": "mcq",
            "subpart": None,
            "stimulus": "প্রথম তিনটি বিজোড় স্বাভাবিক সংখ্যার যোগফল একটি–\ni. পূর্ণবর্গ সংখ্যা\nii. বিজোড় সংখ্যা\niii. মৌলিক সংখ্যা\nনিচের কোনটি সঠিক?",
            "text": "প্রথম তিনটি বিজোড় স্বাভাবিক সংখ্যার যোগফল একটি– i. পূর্ণবর্গ সংখ্যা ii. বিজোড় সংখ্যা iii. মৌলিক সংখ্যা, নিচের কোনটি সঠিক?",
            "text_ascii": "The sum of the first three odd natural numbers is: i. a perfect square, ii. an odd number, iii. a prime number. Which one is correct?",
            "options": ["i ও ii", "i ও iii", "ii ও iii", "i, ii ও iii"],
            "page": 9,
            "pdf_p": 13,
            "needs_figure": False,
            "steps": [
                "প্রথম তিনটি বিজোড় স্বাভাবিক সংখ্যা হলো: ১, ৩, এবং ৫।",
                "এদের যোগফল = $১ + ৩ + ৫ = ৯$।",
                "এখন প্রদত্ত উক্তিগুলো যাচাই করি:",
                "i. পূর্ণবর্গ সংখ্যা: $৯ = ৩^২$, সুতরাং ৯ একটি পূর্ণবর্গ সংখ্যা (উক্তিটি সঠিক)।",
                "ii. বিজোড় সংখ্যা: ৯ কে ২ দ্বারা ভাগ করলে ১ অবশিষ্ট থাকে, তাই ৯ একটি বিজোড় সংখ্যা (উক্তিটি সঠিক)।",
                "iii. মৌলিক সংখ্যা: ৯ এর গুণনীয়ক হলো ১, ৩, ৯। একের অধিক গুণনীয়ক থাকায় ৯ মৌলিক সংখ্যা নয়, এটি যৌগিক সংখ্যা (উক্তিটি মিথ্যা)।",
                "সুতরাং সঠিক উক্তি হলো i ও ii।"
            ],
            "ans": "ক) i ও ii",
            "ans_ascii": "k) i and ii",
            "method": "সংখ্যার বৈশিষ্ট্য ও মৌলিক/যৌগিক যাচাই",
            "theory_page": 4,
            "verifier": {"sympy_eval": "1+3+5 == 9 and 9 == 3**2 and 9%2 == 1 and not sympy.isprime(9)", "is_correct": True, "method": "number_theory_check"},
            "hints": [
                "প্রথম তিনটি বিজোড় সংখ্যা ১, ৩ ও ৫ যোগ করো।",
                "যোগফল ৯। ৯ কি পূর্ণবর্গ সংখ্যা? বিজোড় সংখ্যা? মৌলিক সংখ্যা?",
                "৯ = ৩ × ৩, তাই ৯ মৌলিক নয় কিন্তু পূর্ণবর্গ ও বিজোড়। ফলে উত্তর i ও ii।"
            ]
        },
        {
            "qno": 4,
            "qno_disp": "৪",
            "type": "short",
            "subpart": "ক",
            "stimulus": "তালিকার পাশাপাশি দুইটি পদের পার্থক্য বের করো এবং পরবর্তী দুইটি সংখ্যা নির্ণয় করো।",
            "text": "৭, ১২, ১৭, ২২, ২৭, ...",
            "text_ascii": "7, 12, 17, 22, 27, ... Find the difference between adjacent terms and the next two numbers.",
            "options": None,
            "page": 9,
            "pdf_p": 13,
            "needs_figure": False,
            "steps": [
                "প্রদত্ত তালিকা: ৭, ১২, ১৭, ২২, ২৭, ...",
                "পাশাপাশি দুইটি পদের পার্থক্য বের করি:",
                "$১২ - ৭ = ৫$",
                "$১৭ - ১২ = ৫$",
                "$২২ - ১৭ = ৫$",
                "$২৭ - ২২ = ৫$",
                "দেখা যাচ্ছে, প্রতিবার পার্থক্য ৫ করে বাড়ছে।",
                "সুতরাং তালিকার পরবর্তী ১ম সংখ্যাটি হবে: $২৭ + ৫ = ৩২$",
                "এবং পরবর্তী ২য় সংখ্যাটি হবে: $৩২ + ৫ = ৩৭$"
            ],
            "ans": "পার্থক্য ৫; পরবর্তী দুইটি সংখ্যা ৩২ এবং ৩৭।",
            "ans_ascii": "Difference 5; next two numbers are 32 and 37.",
            "method": "সমান্তর পদের পার্থক্য ও প্যাটার্ন বৃদ্ধি",
            "theory_page": 2,
            "verifier": {"sympy_eval": "[7 + 5*i for i in range(7)] == [7, 12, 17, 22, 27, 32, 37]", "is_correct": True, "method": "exact_sequence"},
            "hints": [
                "১২ থেকে ৭ এবং ১৭ থেকে ১২ বিয়োগ করে পার্থক্য লক্ষ্য করো।",
                "প্রতিটি পদের সাথে ৫ যোগ করে পরবর্তী পদ পাওয়া যাচ্ছে।",
                "২৭ এর সাথে ৫ যোগ করে ১ম পরবর্তী পদ এবং তার সাথে আবার ৫ যোগ করে ২য় পদ বের করো।"
            ]
        },
        {
            "qno": 4,
            "qno_disp": "৪",
            "type": "short",
            "subpart": "খ",
            "stimulus": "তালিকার পাশাপাশি দুইটি পদের পার্থক্য বের করো এবং পরবর্তী দুইটি সংখ্যা নির্ণয় করো।",
            "text": "৬, ১৭, ২৮, ৩৯, ৫০, ...",
            "text_ascii": "6, 17, 28, 39, 50, ... Find the difference between adjacent terms and the next two numbers.",
            "options": None,
            "page": 9,
            "pdf_p": 13,
            "needs_figure": False,
            "steps": [
                "প্রদত্ত তালিকা: ৬, ১৭, ২৮, ৩৯, ৫০, ...",
                "পাশাপাশি দুইটি পদের পার্থক্য বের করি:",
                "$১৭ - ৬ = ১১$",
                "$২৮ - ১৭ = ১১$",
                "$৩৯ - ২৮ = ১১$",
                "$৫০ - ৩৯ = ১১$",
                "দেখা যাচ্ছে, প্রতিবার পার্থক্য ১১ করে বাড়ছে।",
                "সুতরাং তালিকার পরবর্তী ১ম সংখ্যাটি হবে: $৫০ + ১১ = ৬১$",
                "এবং পরবর্তী ২য় সংখ্যাটি হবে: $৬১ + ১১ = ৭২$"
            ],
            "ans": "পার্থক্য ১১; পরবর্তী দুইটি সংখ্যা ৬১ এবং ৭২।",
            "ans_ascii": "Difference 11; next two numbers are 61 and 72.",
            "method": "সমান্তর পদের পার্থক্য ও প্যাটার্ন বৃদ্ধি",
            "theory_page": 2,
            "verifier": {"sympy_eval": "[6 + 11*i for i in range(7)] == [6, 17, 28, 39, 50, 61, 72]", "is_correct": True, "method": "exact_sequence"},
            "hints": [
                "১৭ থেকে ৬ বিয়োগ করে পাশাপাশি পদের পার্থক্য নির্ণয় করো।",
                "পার্থক্য সর্বদা ১১।",
                "৫০ এর সাথে ১১ যোগ করে ৬১ এবং ৬১ এর সাথে ১১ যোগ করে ৭২ নির্ণয় করো।"
            ]
        },
        {
            "qno": 5,
            "qno_disp": "৫",
            "type": "short",
            "subpart": "ক",
            "stimulus": "নিচের সংখ্যা প্যাটার্নগুলোর মধ্যে কোনো মিল রয়েছে কি? প্রতিটি তালিকার পরবর্তী সংখ্যা নির্ণয় করো।",
            "text": "১, ১, ২, ৩, ৫, ৮, ১৩, ...",
            "text_ascii": "1, 1, 2, 3, 5, 8, 13, ... Is there any similarity? Find the next number in the list.",
            "options": None,
            "page": 10,
            "pdf_p": 14,
            "needs_figure": False,
            "steps": [
                "প্রদত্ত তালিকা: ১, ১, ২, ৩, ৫, ৮, ১৩, ...",
                "পদগুলোর পারস্পরিক সম্পর্ক লক্ষ্য করি:",
                "$১ + ১ = ২$",
                "$১ + ২ = ৩$",
                "$২ + ৩ = ৫$",
                "$৩ + ৫ = ৮$",
                "$৫ + ৮ = ১৩$",
                "দেখা যাচ্ছে, পরপর দুইটি পদের যোগফল তার পরবর্তী পদের সমান। এটি একটি ফিবোনাচ্চি (Fibonacci) সংখ্যা প্যাটার্ন।",
                "সুতরাং তালিকার পরবর্তী সংখ্যাটি হবে: $৮ + ১৩ = ২১$।"
            ],
            "ans": "এটি একটি ফিবোনাচ্চি প্যাটার্ন এবং তালিকার পরবর্তী সংখ্যা ২১।",
            "ans_ascii": "Fibonacci pattern, next number is 21.",
            "method": "ফিবোনাচ্চি ধারা বিশ্লেষণ",
            "theory_page": 3,
            "verifier": {"sympy_eval": "8 + 13 == 21", "is_correct": True, "method": "fibonacci_property"},
            "hints": [
                "১+১=২, ১+২=৩ লক্ষ্য করো। পরপর দুইটি পদের যোগফল কী হচ্ছে?",
                "এটি ফিবোনাচ্চি ধারা।",
                "শেষ দুইটি পদ ৮ ও ১৩ যোগ করে পরবর্তী সংখ্যা বের করো।"
            ]
        },
        {
            "qno": 5,
            "qno_disp": "৫",
            "type": "short",
            "subpart": "খ",
            "stimulus": "নিচের সংখ্যা প্যাটার্নগুলোর মধ্যে কোনো মিল রয়েছে কি? প্রতিটি তালিকার পরবর্তী সংখ্যা নির্ণয় করো।",
            "text": "৪, ৪, ৫, ৬, ৮, ১১, ...",
            "text_ascii": "4, 4, 5, 6, 8, 11, ... Is there any similarity? Find the next number in the list.",
            "options": None,
            "page": 10,
            "pdf_p": 14,
            "needs_figure": False,
            "steps": [
                "প্রদত্ত তালিকা: ৪, ৪, ৫, ৬, ৮, ১১, ...",
                "পাশাপাশি দুইটি পদের পার্থক্য লক্ষ্য করি:",
                "$৪ - ৪ = ০$",
                "$৫ - ৪ = ১$",
                "$৬ - ৫ = ১$",
                "$৮ - ৬ = ২$",
                "$১১ - ৮ = ৩$",
                "পার্থক্যগুলো লক্ষ্য করলে দেখা যায়: ০, ১, ১, ২, ৩, ... যা একটি ফিবোনাচ্চি ধারা গঠন করেছে (যেখানে $০+১=১, ১+১=২, ১+২=৩$)।",
                "সুতরাং পার্থক্যের পরবর্তী পদটি হবে: $২ + ৩ = ৫$।",
                "অতএব তালিকার পরবর্তী সংখ্যাটি হবে: $১১ + ৫ = ১৬$।",
                "উভয় প্যাটার্নের মধ্যে মিল: (ক) ও (খ) উভয় প্যাটার্নেই ফিবোনাচ্চি নিয়ম জড়িত। (ক)-তে সংখ্যাগুলো সরাসরি ফিবোনাচ্চি সংখ্যা, আর (খ)-তে পাশাপাশি দুইটি পদের পার্থক্যগুলো ফিবোনাচ্চি সংখ্যা তৈরি করে।"
            ],
            "ans": "মিল: উভয় প্যাটার্নে ফিবোনাচ্চি নিয়ম অনুসরণ করা হয়েছে; পরবর্তী সংখ্যা ১৬।",
            "ans_ascii": "Similarity: Fibonacci property in term differences; next number is 16.",
            "method": "পার্থক্যভিত্তিক ফিবোনাচ্চি ধারা",
            "theory_page": 3,
            "verifier": {"sympy_eval": "11 + (2 + 3) == 16", "is_correct": True, "method": "fibonacci_difference"},
            "hints": [
                "পাশাপাশি পদগুলোর বিয়োগফল বের করো: ৪-৪, ৫-৪, ৬-৫, ৮-৬, ১১-৮।",
                "বিয়োগফলগুলো হলো: ০, ১, ১, ২, ৩। এটি কি ফিবোনাচ্চি ধারার মতো?",
                "পরবর্তী পার্থক্য হবে ২+৩=৫। সুতরাং ১১ এর সাথে ৫ যোগ করো।"
            ]
        },
        {
            "qno": 6,
            "qno_disp": "৬",
            "type": "creative",
            "subpart": "ক",
            "stimulus": "৫, ১৩, ২১, ২৯, ৩৭, ...",
            "text": "২৯ ও ৩৭কে দুইটি স্বাভাবিক সংখ্যার বর্গের সমষ্টিরূপে প্রকাশ করো।",
            "text_ascii": "Express 29 and 37 as the sum of squares of two natural numbers.",
            "options": None,
            "page": 10,
            "pdf_p": 14,
            "needs_figure": False,
            "steps": [
                "২৯ সংখ্যাটিকে বিশ্লেষণ করে পাই:",
                "$২৯ = ৪ + ২৫ = ২^২ + ৫^২$",
                "৩৭ সংখ্যাটিকে বিশ্লেষণ করে পাই:",
                "$৩৭ = ১ + ৩৬ = ১^২ + ৬^২$",
                "সুতরাং, ২৯ ও ৩৭ উভয়কেই দুইটি স্বাভাবিক সংখ্যার বর্গের সমষ্টিরূপে প্রকাশ করা হলো।"
            ],
            "ans": "২৯ = ২^২ + ৫^২ এবং ৩৭ = ১^২ + ৬^২",
            "ans_ascii": "29 = 2^2 + 5^2 and 37 = 1^2 + 6^2",
            "method": "স্বাভাবিক সংখ্যার বর্গের সমষ্টি নির্ণয়",
            "theory_page": 7,
            "verifier": {"sympy_eval": "2**2 + 5**2 == 29 and 1**2 + 6**2 == 37", "is_correct": True, "method": "exact_squares"},
            "hints": [
                "স্বাভাবিক সংখ্যার বর্গগুলো ভাবো: ১, ৪, ৯, ১৬, ২৫, ৩৬।",
                "কোন দুইটি বর্গ যোগ করলে ২৯ হয়? ৪ + ২৫ = ২৯।",
                "কোন দুইটি বর্গ যোগ করলে ৩৭ হয়? ১ + ৩৬ = ৩৭।"
            ]
        },
        {
            "qno": 6,
            "qno_disp": "৬",
            "type": "creative",
            "subpart": "খ",
            "stimulus": "৫, ১৩, ২১, ২৯, ৩৭, ...",
            "text": "তালিকার পরবর্তী ৪টি সংখ্যা নির্ণয় করো।",
            "text_ascii": "Find the next 4 numbers of the list 5, 13, 21, 29, 37, ...",
            "options": None,
            "page": 10,
            "pdf_p": 14,
            "needs_figure": False,
            "steps": [
                "প্রদত্ত তালিকা: ৫, ১৩, ২১, ২৯, ৩৭, ...",
                "পাশাপাশি দুইটি পদের পার্থক্য বের করি:",
                "$১৩ - ৫ = ৮$",
                "$২১ - ১৩ = ৮$",
                "$২৯ - ২১ = ৮$",
                "$৩৭ - ২৯ = ৮$",
                "দেখা যাচ্ছে, প্রতিবার পার্থক্য ৮ করে বৃদ্ধি পাচ্ছে।",
                "সুতরাং পরবর্তী ৪টি সংখ্যা ক্রমান্বয়ে হবে:",
                "১ম সংখ্যা: $৩৭ + ৮ = ৪৫$",
                "২য় সংখ্যা: $৪৫ + ৮ = ৫৩$",
                "৩য় সংখ্যা: $৫৩ + ৮ = ৬১$",
                "৪র্থ সংখ্যা: $৬১ + ৮ = ৬৯$",
                "অতএব পরবর্তী ৪টি সংখ্যা হলো: ৪৫, ৫৩, ৬১ ও ৬৯।"
            ],
            "ans": "৪৫, ৫৩, ৬১, ৬৯",
            "ans_ascii": "45, 53, 61, 69",
            "method": "সমান্তর সাধারণ অন্তর যোগ",
            "theory_page": 2,
            "verifier": {"sympy_eval": "[37 + 8*i for i in range(1, 5)] == [45, 53, 61, 69]", "is_correct": True, "method": "arithmetic_progression"},
            "hints": [
                "পাশাপাশি দুইটি পদের বিয়োগফল লক্ষ্য করো। প্রতিবার কত করে বাড়ছে?",
                "পার্থক্য ৮। শেষ পদ ৩৭ এর সাথে ৮ যোগ করতে থাকো।",
                "৩৭+৮=৪৫, ৪৫+৮=৫৩, ৫৩+৮=৬১, ৬১+৮=৬৯।"
            ]
        },
        {
            "qno": 6,
            "qno_disp": "৬",
            "type": "creative",
            "subpart": "গ",
            "stimulus": "৫, ১৩, ২১, ২৯, ৩৭, ...",
            "text": "তালিকার প্রথম ৫০টি সংখ্যার সমষ্টি নির্ণয় করো।",
            "text_ascii": "Find the sum of the first 50 numbers of the list 5, 13, 21, 29, 37, ...",
            "options": None,
            "page": 10,
            "pdf_p": 14,
            "needs_figure": False,
            "steps": [
                "প্রদত্ত সংখ্যা তালিকা: ৫, ১৩, ২১, ২৯, ৩৭, ...",
                "তালিকাটির সাধারণ বীজগাণিতীয় রাশি নির্ণয় করি:",
                "১ম পদ = $৫ = ৮ \\times ১ - ৩$",
                "২য় পদ = $১৩ = ৮ \\times ২ - ৩$",
                "৩য় পদ = $২১ = ৮ \\times ৩ - ৩$",
                "সুতরাং 'ক' তম পদ = $৮ক - ৩$",
                "৫০তম পদ = $৮ \\times ৫০ - ৩ = ৪০০ - ৩ = ৩৯৭$",
                "সমষ্টি নির্ণয়ের সূত্র:",
                "$$\\text{সমষ্টি} = \\frac{\\text{১ম পদ} + \\text{শেষ পদ}}{২} \\times \\text{পদসংখ্যা}$$",
                "এখানে, ১ম পদ = ৫, শেষ পদ (৫০তম পদ) = ৩৯৭, এবং পদসংখ্যা = ৫০",
                "$$\\text{সমষ্টি} = \\frac{৫ + ৩৯৭}{২} \\times ৫০ = \\frac{৪০২}{২} \\times ৫০ = ২০১ \\times ৫০ = ১০০৫০$$",
                "অতএব, তালিকার প্রথম ৫০টি পদের সমষ্টি ১০,০৫০।"
            ],
            "ans": "১০,০৫০",
            "ans_ascii": "10050",
            "method": "বীজগাণিতীয় রাশি ও সমান্তর ধারার সমষ্টি সূত্র",
            "theory_page": 4,
            "verifier": {"sympy_eval": "sympy.summation(8*k - 3, (k, 1, 50)) == 10050", "is_correct": True, "method": "exact_summation"},
            "hints": [
                "প্রথমে তালিকাটির ক-তম পদ বের করো: ৮ক - ৩।",
                "ক = ৫০ বসিয়ে ৫০তম পদের মান বের করো: ৩৯৭।",
                "সমষ্টি সূত্র [(১ম পদ + শেষ পদ)/২] × পদসংখ্যা ব্যবহার করো: [(৫ + ৩৯৭)/২] × ৫০ = ১০০৫০।"
            ]
        }
    ]

    for item in items_data:
        item_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO math_items_v2 (
                id, book_id, chapter_id, exercise_id, class_level, chapter_number,
                exercise_label, item_type, question_no, question_no_display, subpart,
                stimulus_text, question_text, question_text_ascii, mcq_options,
                printed_page, pdf_page_index, needs_figure, internal_answer_key,
                read_1_text, read_2_text, diff_disagreement
            ) VALUES (
                %s, %s, %s, %s, 8, 1, 'অনুশীলনী ১', %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE
            )
            ON CONFLICT (chapter_id, exercise_label, question_no, subpart) DO UPDATE
            SET question_text = EXCLUDED.question_text,
                question_text_ascii = EXCLUDED.question_text_ascii,
                updated_at = NOW()
            RETURNING id;
        """, (
            item_id, book_id, chap_id, ex_id,
            item["type"], item["qno"], item["qno_disp"], item["subpart"],
            item["stimulus"], item["text"], item["text_ascii"],
            json.dumps(item["options"]) if item["options"] else None,
            item["page"], item["pdf_p"], item["needs_figure"], item["ans"],
            item["text"], item["text"]
        ))
        item_id = cur.fetchone()[0]

        # math_solutions
        cur.execute("""
            INSERT INTO math_solutions (
                id, item_id, steps, final_answer, final_answer_ascii, method, theory_page,
                model_version, prompt_version, verification_status, verifier_details
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, 'gemini-agent-v1', 'p15-tutor-v1', 'verified_symbolic', %s
            )
            ON CONFLICT (item_id) DO UPDATE
            SET steps = EXCLUDED.steps,
                final_answer = EXCLUDED.final_answer,
                verification_status = EXCLUDED.verification_status,
                verifier_details = EXCLUDED.verifier_details,
                updated_at = NOW();
        """, (
            str(uuid.uuid4()), item_id,
            json.dumps(item["steps"]), item["ans"], item["ans_ascii"],
            item["method"], item["theory_page"], json.dumps(item["verifier"])
        ))

        # math_hints (levels 1, 2, 3)
        for lvl, h_text in enumerate(item["hints"], start=1):
            cur.execute("""
                INSERT INTO math_hints (id, item_id, level, hint_text)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (item_id, level) DO UPDATE
                SET hint_text = EXCLUDED.hint_text;
            """, (str(uuid.uuid4()), item_id, lvl, h_text))

    conn.commit()
    print(f"Successfully seeded pilot Chapter 1 with {len(items_data)} verified items!")
    conn.close()

if __name__ == "__main__":
    seed_pilot()
