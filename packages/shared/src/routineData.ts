import { RoutineSlot, PageStudyBreakdown, HomeworkTask, UploadedStudyNote, StudentExamSettings } from "./types";

export const DEFAULT_PAGE_BREAKDOWNS: Record<string, PageStudyBreakdown[]> = {
  science_ch4: [
    {
      page: 42,
      title: "সালোকসংশ্লেষণের মৌলিক ধারণা ও কাঁচামাল",
      summary_bn:
        "সালোকসংশ্লেষণ হলো সবুজ উদ্ভিদের শর্করা তৈরির জৈব-রাসায়নিক প্রক্রিয়া। প্রধান কাঁচামাল: কার্বন ডাই-অক্সাইড (CO₂) ও পানি (H₂O); শক্তি যোগায় সূর্যালোক এবং ক্লোরোফিল সৌরশক্তি শোষণ করে।",
      summary_en:
        "Photosynthesis is the biochemical process by which green plants manufacture carbohydrates. Key raw materials: CO₂ and H₂O using solar energy absorbed by chlorophyll.",
      key_points: [
        "উদ্ভিদের পাতায় মেসোফিল কোষে অবস্থিত ক্লোরোপ্লাস্টে প্রক্রিয়াটি সম্পন্ন হয়।",
        "বায়ুমণ্ডল থেকে পত্ররন্ধ্রের মাধ্যমে CO₂ গৃহীত হয় এবং মূলরোম দিয়ে মাটি থেকে পানি শোষিত হয়।",
        "সবুজ পাতার ক্লোরোফিল কণা সৌরশক্তি শোষণ করে রাসায়নিক শক্তিতে রূপান্তরিত করে।",
      ],
    },
    {
      page: 43,
      title: "সালোকসংশ্লেষণের বিক্রিয়া ও পর্যায়সমূহ",
      summary_bn:
        "পূর্ণাঙ্গ সমীকরণ: 6CO₂ + 12H₂O ⟶ C₆H₁₂O₆ + 6H₂O + 6O₂ (সূর্যালোক ও ক্লোরোফিলের উপস্থিতিতে)। প্রক্রিয়াটি আলোক এবং অন্ধকার (কার্বন বিজারণ) পর্যায়ে সম্পন্ন হয়।",
      summary_en:
        "Balanced equation: 6CO₂ + 12H₂O ⟶ C₆H₁₂O₆ + 6H₂O + 6O₂ (in sunlight and chlorophyll). Operates in light and dark reactions.",
      key_points: [
        "আলোক পর্যায়ে পানির ফটোলাইসিস ঘটে এবং উচ্চ শক্তি সম্পন্ন ATP ও NADPH তৈরি হয়।",
        "অন্ধকার পর্যায়ে কেলভিন চক্রের মাধ্যমে CO₂ বিজারিত হয়ে গ্লুকোজ উৎপন্ন হয়।",
        "উপজাত হিসেবে বায়ুমণ্ডলে জীবনধারণের জন্য অক্সিজেন (O₂) নির্গত হয়।",
      ],
    },
    {
      page: 44,
      title: "সালোকসংশ্লেষণের পরিবেশগত তাৎপর্য ও গ্যাসীয় ভারসাম্য",
      summary_bn:
        "সালোকসংশ্লেষণ সমগ্র জীবজগতের খাদ্যের একমাত্র প্রাথমিক উৎস এবং বায়ুমণ্ডলে অক্সিজেন ও কার্বন ডাই-অক্সাইডের অনুপাত ভারসাম্যপূর্ণ রাখে।",
      summary_en:
        "Photosynthesis is the sole primary food provider on Earth and balances oxygen and carbon dioxide levels in the atmosphere.",
      key_points: [
        "সমগ্র প্রাণী ও মানবকুলের শ্বাসকার্যের জন্য অক্সিজেন নিশ্চিত করে।",
        "গ্রিনহাউস গ্যাস কার্বন ডাই-অক্সাইড শোষণ করে পরিবেশ ও জলবায়ু রক্ষা করে।",
        "জীবাশ্ম জ্বালানি (কয়লা, তেল, গ্যাস) মূলত উদ্ভিদের সঞ্চিত প্রাচীন সৌরশক্তি।",
      ],
    },
  ],
  math_ch5: [
    {
      page: 72,
      title: "বীজগণিতীয় সূত্রাবলী ও বর্গ নির্ণয়",
      summary_bn:
        "(a + b)² = a² + 2ab + b² এবং (a - b)² = a² - 2ab + b² সূত্রের জ্যামিতিক ও বীজগাণিতিক প্রমাণ।",
      summary_en:
        "Geometric and algebraic proofs of square expansion formulas: (a + b)² and (a - b)².",
      key_points: [
        "দুইটি পদের যোগফল ও বিয়োগফলের বর্গের অনুসিদ্ধান্ত প্রয়োগ।",
        "a² + b² = (a + b)² - 2ab = (a - b)² + 2ab অনুসিদ্ধান্তের ব্যবহার।",
      ],
    },
    {
      page: 73,
      title: "বর্গের সম্প্রসারণ ও মান নির্ণয়ের গাণিতিক সমস্যা",
      summary_bn: "সূত্র প্রয়োগ করে বিভিন্ন রাশিমালার মান নির্ণয় ও জটিল সমাধান।",
      key_points: [
        "যদি x + 1/x = 4 হয়, তবে x² + 1/x² = 14 প্রমাণ করা।",
        "প্রাত্যহিক গাণিতিক সমস্যায় সূত্রের বাস্তব প্রয়োগ।",
      ],
    },
  ],
};

export const DEFAULT_HOMEWORK: Record<string, HomeworkTask[]> = {
  science_ch4: [
    {
      id: "hw_sci_1",
      title_bn: "সালোকসংশ্লেষণ প্রক্রিয়ার পূর্ণাঙ্গ রাসায়নিক সমীকরণটি খাতায় না দেখে লিখো ও সমতাকরণ করো।",
      title_en: "Write the balanced chemical equation for photosynthesis in your notebook without looking.",
      completed: false,
    },
    {
      id: "hw_sci_2",
      title_bn: "একটি ক্লোরোপ্লাস্টের চিত্র এঁকে গ্রানা ও স্ট্রোমা চিহ্নিত করো।",
      title_en: "Draw a chloroplast diagram and label grana and stroma clearly.",
      completed: false,
    },
    {
      id: "hw_sci_3",
      title_bn: "বায়ুমণ্ডলে অক্সিজেন ও কার্বন ডাই-অক্সাইডের ভারসাম্য রক্ষায় উদ্ভিদের ৩টি অবদান খাতায় লেখো।",
      title_en: "Write 3 key environmental contributions of photosynthesis in maintaining atmospheric balance.",
      completed: false,
    },
  ],
  math_ch5: [
    {
      id: "hw_math_1",
      title_bn: "অনুশীলনী ৫.১ এর ১ থেকে ৫ নম্বর প্রশ্নের বর্গ নির্ণয় খাতায় সমাধান করো।",
      title_en: "Solve square calculations for problems 1 to 5 from Exercise 5.1.",
      completed: false,
    },
  ],
};

export const INITIAL_ROUTINE_SLOTS: RoutineSlot[] = [
  {
    id: "slot_sci_morning",
    timeSlot: "০৭:০০ - ০৭:৫০",
    timeSlotEn: "07:00 AM - 07:50 AM",
    subject: "বিজ্ঞান",
    subjectEn: "Science",
    chapterTitle: "সালোকসংশ্লেষণ ও ক্লোরোপ্লাস্টের ভূমিকা",
    chapterTitleEn: "Photosynthesis & Role of Chloroplast",
    estimatedMinutes: 50,
    printedPages: "৪২ - ৪৪",
    printedPagesEn: "42 - 44",
    status: "pending",
    guidelines: "পাঠ্যবইয়ের ৪২-৪৪ পৃষ্ঠা মনোযোগ সহকারে পড়ুন এবং গুরুত্বপূর্ণ রাসায়নিক সমীকরণ ও ক্লোরোপ্লাস্টের চিত্র খাতায় অনুশীলন করুন।",
    bookTitle: "সাধারণ বিজ্ঞান (NCTB Class 7)",
    chapterPart: 2,
    chapterTotalParts: 3,
  },
  {
    id: "slot_math_afternoon",
    timeSlot: "১৬:০০ - ১৬:৪৫",
    timeSlotEn: "04:00 PM - 04:45 PM",
    subject: "গণিত",
    subjectEn: "Mathematics",
    chapterTitle: "বীজগণিতীয় সূত্রাবলী ও প্রয়োগ",
    chapterTitleEn: "Algebraic Formulas & Applications",
    estimatedMinutes: 45,
    printedPages: "৭২ - ৭৩",
    printedPagesEn: "72 - 73",
    status: "pending",
    guidelines: "বর্গের সূত্রসমূহ মুখস্থ করে অনুশীলনী ৫.১ এর উদাহরণগুলো খাতায় সমাধান করো।",
    bookTitle: "গণিত (NCTB Class 7)",
    chapterPart: 1,
    chapterTotalParts: 3,
  },
  {
    id: "slot_eng_evening",
    timeSlot: "১৯:৩০ - ২০:১৫",
    timeSlotEn: "07:30 PM - 08:15 PM",
    subject: "ইংরেজি",
    subjectEn: "English",
    chapterTitle: "Unit 3: Health and Hygiene - Reading Comprehension",
    chapterTitleEn: "Unit 3: Health and Hygiene - Reading Comprehension",
    estimatedMinutes: 45,
    printedPages: "২৮ - ৩০",
    printedPagesEn: "28 - 30",
    status: "pending",
    guidelines: "Read the passage carefully, underline difficult words and write vocabulary with synonyms.",
    bookTitle: "English For Today (NCTB Class 7)",
    chapterPart: 1,
    chapterTotalParts: 2,
  },
];

const ROUTINE_STORAGE_KEY = "tb_student_routine_slots";

export function getStoredRoutineSlots(): RoutineSlot[] {
  if (typeof window === "undefined") return INITIAL_ROUTINE_SLOTS;
  try {
    const raw = localStorage.getItem(ROUTINE_STORAGE_KEY);
    return raw ? JSON.parse(raw) : INITIAL_ROUTINE_SLOTS;
  } catch {
    return INITIAL_ROUTINE_SLOTS;
  }
}

export function saveStoredRoutineSlots(slots: RoutineSlot[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(ROUTINE_STORAGE_KEY, JSON.stringify(slots));
  } catch {}
}

export const DEFAULT_EXAM_SETTINGS: StudentExamSettings = {
  class_grade: 8,
  classNameBn: "৮ম শ্রেণি",
  syllabus: "নতুন শিক্ষাক্রম ২০২৪-২৬ (বাংলা মাধ্যম)",
  exam_title: "অর্ধবার্ষিক মূল্যায়ন পরীক্ষা",
  exam_date: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().split("T")[0],
};

const EXAM_SETTINGS_STORAGE_KEY = "tb_student_exam_settings";

export function getStoredExamSettings(): StudentExamSettings {
  if (typeof window === "undefined") return DEFAULT_EXAM_SETTINGS;
  try {
    const raw = localStorage.getItem(EXAM_SETTINGS_STORAGE_KEY);
    return raw ? { ...DEFAULT_EXAM_SETTINGS, ...JSON.parse(raw) } : DEFAULT_EXAM_SETTINGS;
  } catch {
    return DEFAULT_EXAM_SETTINGS;
  }
}

export function saveStoredExamSettings(settings: StudentExamSettings): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(EXAM_SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  } catch {}
}

export function calculateDaysRemaining(examDateStr: string): number {
  if (!examDateStr) return 0;
  try {
    const target = new Date(examDateStr + "T00:00:00");
    const now = new Date();
    const targetDate = new Date(target.getFullYear(), target.getMonth(), target.getDate());
    const nowDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const diffTime = targetDate.getTime() - nowDate.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch {
    return 14;
  }
}

