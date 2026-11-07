export type Language = "bn" | "en";
export type UserRole = "student" | "parent";

export interface StudentExamSettings {
  class_grade: number; // e.g. 6, 7, 8, 9, 10
  classNameBn: string; // e.g. "৮ম শ্রেণি"
  syllabus: string; // e.g. "নতুন শিক্ষাক্রম ২০২৪-২৬"
  exam_title: string; // e.g. "অর্ধবার্ষিক মূল্যায়ন পরীক্ষা"
  exam_date: string; // ISO date format YYYY-MM-DD e.g. "2026-11-20"
}

export interface UserProfile {
  uid: string;
  name: string;
  email: string;
  photoURL?: string;
  role: UserRole;
  createdAt: string;
  inviteCode?: string; // For students, e.g. "TB-7429"
  linkedChildren?: string[]; // For parents: list of student uids
  linkedParents?: string[]; // For students: list of parent uids
  class_grade?: number; // e.g. 7 or 8
  school_name?: string;
  syllabus?: string;
  exam_title?: string;
  exam_date?: string;
}

export interface RoutineSlot {
  id: string;
  timeSlot: string; // e.g. "০৭:০০ - ০৭:৫০"
  timeSlotEn: string; // e.g. "07:00 AM - 07:50 AM"
  subject: string;
  subjectEn: string;
  chapterTitle: string;
  chapterTitleEn: string;
  estimatedMinutes: number;
  printedPages: string; // e.g. "৪২ - ৪৪"
  printedPagesEn: string; // e.g. "42 - 44"
  status: "pending" | "completed" | "in_progress";
  guidelines?: string;
  bookTitle: string;
  chapterPart?: number;
  chapterTotalParts?: number;
}

export interface PageStudyBreakdown {
  page: number;
  title: string;
  summary_bn: string;
  summary_en?: string;
  key_points: string[];
}

export interface HomeworkTask {
  id: string;
  title_bn: string;
  title_en?: string;
  completed: boolean;
}

export interface TeacherReview {
  teacher_name: string;
  badge: string;
  comments: string;
  rating: number;
  reviewed_at: string;
}

export interface UploadedStudyNote {
  id: string;
  task_id: string;
  task_title: string;
  subject: string;
  student_id: string;
  student_name: string;
  pages_covered: string;
  time_spent_seconds: number;
  text_note: string;
  image_url?: string;
  created_at: string;
  is_pro?: boolean;
  teacher_review?: TeacherReview;
}

export interface StudySessionState {
  taskId: string;
  secondsElapsed: number;
  isRunning: boolean;
  lastUpdatedTimestamp: number;
  pagesProgress: Record<number, boolean>;
  homeworkProgress: Record<string, boolean>;
  noteContent?: string;
}

export interface ChildSummary {
  student_id: string;
  name: string;
  grade: string;
  avatar_url?: string;
  streak_days: number;
  completion_rate: number;
  total_study_minutes_today: number;
  overall_mastery: number;
  today_tasks_completed: number;
  today_tasks_total: number;
  weak_chapters: {
    subject: string;
    chapter: string;
    mastery_percent: number;
    status: "needs_practice" | "mastered" | "insufficient_data";
  }[];
}

export interface ClientConfig {
  min_supported_version: string;
  quiz_security_mode: string;
  features: {
    rag_chat_enabled: boolean;
    parent_dashboard_enabled: boolean;
    notifications_enabled: boolean;
    progress_mastery_enabled: boolean;
  };
  limits: {
    daily_minutes_min: number;
    daily_minutes_max: number;
    max_block_minutes: number;
  };
}

export interface QuizQuestion {
  id: string;
  question_bn: string;
  question_en: string;
  options_bn: string[];
  options_en: string[];
  correctIndex: number;
  explanation_bn: string;
  explanation_en: string;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
  citations?: { book: string; page: string }[];
  timestamp: string;
}

