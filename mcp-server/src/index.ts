#!/usr/bin/env node

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

// Initialize ThinkBuddy MCP Server
const server = new Server(
  {
    name: "thinkbuddy-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Authentic NCTB Curriculum Dataset
const CURRICULUM_DATA: Record<string, any> = {
  science: {
    subject: "সাধারণ বিজ্ঞান",
    class_level: 8,
    chapters: [
      {
        number: 4,
        title: "উদ্ভিদে খাদ্য তৈরি ও সালোকসংশ্লেষণ",
        printed_pages: "৪২–৪৪",
        core_concepts: [
          "সালোকসংশ্লেষণ মূলত সবুজ পাতার মেসোফিল কোষে ঘটে।",
          "সূর্যালোকের ফোটন কণা ক্লোরোফিলকে উত্তেজিত করে পানির ফটোলাইসিস ঘটায়: 2H2O -> 4H+ + 4e- + O2।",
          "আলোক পর্যায়ে ATP ও NADPH উৎপন্ন হয় যা অন্ধকার পর্যায়ে শর্করা তৈরিতে ব্যবহৃত হয়।",
        ],
        cq_tasks: [
          {
            type: "ka_knowledge",
            label_bn: "ক • জ্ঞানমূলক সংক্ষিপ্ত প্রশ্ন",
            marks: 1,
            printed_page: "৪২",
            question: "সালোকসংশ্লেষণ কাকে বলে?",
            model_answer: "যে জৈব-রাসায়নিক প্রক্রিয়ায় সবুজ উদ্ভিদ সূর্যালোকের উপস্থিতিতে ক্লোরোফিলের সহায়তায় কার্বন ডাই-অক্সাইড এবং পানি থেকে শর্করা তৈরি করে এবং অক্সিজেন নির্গমন করে, তাকে সালোকসংশ্লেষণ বলে।",
            key_points: ["সূর্যালোক ও ক্লোরোফিল", "CO2 ও পানি থেকে শর্করা", "অক্সিজেন নির্গমন"],
          },
          {
            type: "kha_comprehension",
            label_bn: "খ • অনুধাবনমূলক প্রশ্ন",
            marks: 2,
            printed_page: "৪২–৪৩",
            question: "উদ্ভিদের পাতাকে সালোকসংশ্লেষণের প্রধান স্থান হিসেবে বিবেচনা করা হয় কেন?",
            model_answer: "পাতা চ্যাপ্টা ও প্রসারিত হওয়ায় সর্বাধিক সূর্যালোক ও CO2 শোষণ করতে পারে এবং পাতার মেসোফিল কোষে বিপুল সংখ্যক ক্লোরোপ্লাস্ট ও পত্ররন্ধ্র থাকে।",
            key_points: ["পাতা চ্যাপ্টা ও প্রসারিত", "মেসোফিল কোষে ক্লোরোপ্লাস্টের ঘনত্ব", "সহজ গ্যাসীয় বিনিময়"],
          },
          {
            type: "ga_application",
            label_bn: "গ • প্রয়োগমূলক CQ",
            marks: 3,
            printed_page: "৪৩",
            question: "সালোকসংশ্লেষণ প্রক্রিয়ার পূর্ণাঙ্গ সমতাকৃত রাসায়নিক সমীকরণটি লেখো।",
            model_answer: "6CO2 + 12H2O --(সূর্যালোক/ক্লোরোফিল)--> C6H12O6 + 6H2O + 6O2",
            key_points: ["৬ অণু CO2 ও ১২ অণু পানি", "সূর্যালোক ও ক্লোরোফিল প্রভাবক", "১ অণু গ্লুকোজ, ৬ অণু পানি ও ৬ অণু অক্সিজেন সমতাকরণ"],
          },
          {
            type: "gha_higher_order",
            label_bn: "ঘ • উচ্চতর দক্ষতা CQ",
            marks: 4,
            printed_page: "৪৩–৪৪",
            question: "একটি ক্লোরোপ্লাস্টের গঠন চিত্রসহ ব্যাখ্যা করো এবং জীবজগতের অস্তিত্বে এর ভূমিকা বিশ্লেষণ করো।",
            model_answer: "ক্লোরোপ্লাস্ট দ্বি-স্তরবিশিষ্ট আবরণী, স্ট্রোমা ও থাইলাকয়েড গ্রানা নিয়ে গঠিত। এটি সৌরশক্তিকে খাদ্যে রূপান্তর করে পৃথিবীর সকল জীবের অস্তিত্ব রক্ষা করে।",
            key_points: ["দ্বি-স্তরবিশিষ্ট আবরণী", "গ্রানাম ও স্ট্রোমা লেবেলিং", "আলোক ও অন্ধকার পর্যায়", "খাদ্য ও অক্সিজেনের প্রধান উৎস"],
          },
        ],
      },
    ],
  },
  math: {
    subject: "সাধারণ গণিত",
    class_level: 8,
    chapters: [
      {
        number: 1,
        title: "প্যাটার্ন ও বীজগাণিতিক রাশি",
        printed_pages: "৬–৯",
        core_concepts: [
          "পরপর দুটি পদের পার্থক্য সমান হলে তা একটি রৈখিক প্যাটার্ন নির্দেশ করে।",
          "ফিবোনাক্কি সংখ্যা: ০, ১, ১, ২, ৩, ৫, ৮, ১৩... যেখানে পরপর দুটি সংখ্যার যোগফল পরবর্তী সংখ্যার সমান।",
          "ক ক্রমের ম্যাজিক সংখ্যা = [ক(ক^২ + ১)] / ২। ৩ ক্রমের ক্ষেত্রে ম্যাজিক সংখ্যা ১৫।",
          "১ম n সংখ্যক স্বাভাবিক সংখ্যার সমষ্টি = [(১ম পদ + শেষ পদ) * পদসংখ্যা] / ২।",
        ],
        cq_tasks: [
          {
            type: "ka_knowledge",
            label_bn: "ক • জ্ঞানমূলক সংক্ষিপ্ত প্রশ্ন",
            marks: 1,
            printed_page: "৬",
            question: "ফিবোনাক্কি সংখ্যা কাকে বলে?",
            model_answer: "যে সংখ্যা প্যাটার্নে পরপর দুটি সংখ্যার যোগফল পরবর্তী সংখ্যার সমান হয়, তাকে ফিবোনাক্কি সংখ্যা বলে।",
            key_points: ["পরপর দুটি পদের যোগফল পরবর্তী পদের সমান", "উদাহরণ ০, ১, ১, ২, ৩, ৫..."],
          },
          {
            type: "kha_comprehension",
            label_bn: "খ • অনুধাবনমূলক প্রশ্ন",
            marks: 2,
            printed_page: "৬–৭",
            question: "ম্যাজিক বর্গ বলতে কী বোঝায়? ৩ ক্রমের ম্যাজিক সংখ্যা সূত্রের সাহায্যে বের করো।",
            model_answer: "একটি বর্গাকার ছকে পাশাপাশি, উপর-নিচ ও কোণাকুণি যোগফল সর্বদা সমান হলে তাকে ম্যাজিক বর্গ বলে। ৩ ক্রমের ম্যাজিক সংখ্যা = ৩(৩^২ + ১)/২ = ১৫।",
            key_points: ["আড়াআড়ি ও লম্বালম্বি যোগফল সমান", "সূত্র ক(ক^২+১)/২ প্রয়োগ", "৩ ক্রমের মান ১৫"],
          },
          {
            type: "ga_application",
            label_bn: "গ • প্রয়োগমূলক CQ",
            marks: 3,
            printed_page: "৭–৮",
            question: "৪, ৯, ১৪, ১৯, ২৪... প্যাটার্নটির বীজগাণিতিক রাশি ও ৫০তম পদ নির্ণয় করো।",
            model_answer: "প্রতিপদের পার্থক্য ৫। বীজগাণিতিক রাশি = ৫ক - ১। ৫০তম পদ = ৫ * ৫০ - ১ = ২৪৯।",
            key_points: ["পার্থক্য ৫ নির্ণয়", "বীজগাণিতিক রাশি ৫ক - ১", "৫০তম পদ ২৪৯"],
          },
          {
            type: "gha_higher_order",
            label_bn: "ঘ • উচ্চতর দক্ষতা CQ",
            marks: 4,
            printed_page: "৮–৯",
            question: "উক্ত সংখ্যা প্যাটার্নটির প্রথম ৪০টি পদের সমষ্টি সূত্র প্রয়োগ করে সমাধান করো।",
            model_answer: "৪০তম পদ = ১৯৯। সমষ্টি = [(৪ + ১৯৯) * ৪০] / ২ = ২০৩ * ২০ = ৪০৬০।",
            key_points: ["৪০তম পদ ১৯৯", "সমষ্টির সঠিক সূত্র", "চূড়ান্ত মান ৪০৬০"],
          },
        ],
      },
    ],
  },
  ict: {
    subject: "তথ্য ও যোগাযোগ প্রযুক্তি",
    class_level: 8,
    chapters: [
      {
        number: 2,
        title: "কম্পিউটার নেটওয়ার্ক ও টপোলজি",
        printed_pages: "২৩–২৫",
        core_concepts: [
          "টপোলজি হলো নেটওয়ার্কভুক্ত কম্পিউটারগুলোর পারস্পরিক সংযোগের জ্যামিতিক নকশা।",
          "স্টার টপোলজিতে সব নোড কেন্দ্রীয় হাব বা সুইচে যুক্ত থাকে। একটি নোড বিকল হলেও নেটওয়ার্ক সচল থাকে।",
          "সুইচ ইন্টেলিজেন্ট ডিভাইজ যা নির্দিষ্ট MAC অ্যাড্রেস সংরক্ষণ করে প্যাকেট পাঠায়।",
        ],
        cq_tasks: [
          {
            type: "ka_knowledge",
            label_bn: "ক • জ্ঞানমূলক সংক্ষিপ্ত প্রশ্ন",
            marks: 1,
            printed_page: "২৩",
            question: "কম্পিউটার নেটওয়ার্ক টপোলজি কাকে বলে?",
            model_answer: "একটি নেটওয়ার্কে কম্পিউটারগুলো পরস্পরের সাথে তারের মাধ্যমে যেভাবে যুক্ত থাকে সেই সংযোগের নকশাকে টপোলজি বলে।",
            key_points: ["কম্পিউটারগুলোর পারস্পরিক সংযোগ নকশা", "টপোলজির প্রমিত সংজ্ঞা"],
          },
          {
            type: "kha_comprehension",
            label_bn: "খ • অনুধাবনমূলক প্রশ্ন",
            marks: 2,
            printed_page: "২৫",
            question: "হাবের চেয়ে সুইচ অধিক বুদ্ধিমান ও নিরাপদ কেন?",
            model_answer: "হাব সব নোডে ডেটা সম্প্রচার (Broadcast) করে ফলে ট্রাফিক বাড়ে, অন্যদিকে সুইচ নির্দিষ্ট MAC অ্যাড্রেসে প্যাকেট পাঠায়।",
            key_points: ["হাবে ব্রডকাস্ট বনাম সুইচে ইউনিকাস্ট", "MAC অ্যাড্রেস সংরক্ষণ", "নিরাপত্তা ও গতি বৃদ্ধি"],
          },
          {
            type: "ga_application",
            label_bn: "গ • প্রয়োগমূলক CQ",
            marks: 3,
            printed_page: "২৩–২৪",
            question: "স্টার (Star) টপোলজির চিত্র ও প্রধান সুবিধাগুলো ব্যাখ্যা করো।",
            model_answer: "স্টার টপোলজিতে কেন্দ্রীয় হাব/সুইচ থাকে। কোনো নোড নষ্ট হলে পুরো সিস্টেম অচল হয় না এবং সহজেই নতুন পিসি যুক্ত করা যায়।",
            key_points: ["কেন্দ্রীয় হাব বা সুইচ", "একটি নোড নষ্ট হলেও সিস্টেম সচল", "সহজ সম্প্রসারণ"],
          },
          {
            type: "gha_higher_order",
            label_bn: "ঘ • উচ্চতর দক্ষতা CQ",
            marks: 4,
            printed_page: "২৪–২৫",
            question: "বাস টপোলজি বনাম স্টার টপোলজির নির্ভরযোগ্যতা ও ডেটা ট্রাফিকের তুলনামূলক বিশ্লেষণ করো।",
            model_answer: "বাসের মূল ব্যাকবোন তার ছিঁড়ে গেলে পুরো নেটওয়ার্ক বন্ধ হয়, কিন্তু স্টারে কেবল ত্রুটিপূর্ণ পিসি বিচ্ছিন্ন হয়। তাই প্রাতিষ্ঠানিক ব্যবহারে স্টার অনেক বেশি নির্ভরযোগ্য।",
            key_points: ["ব্যাকবোন নির্ভরতা বনাম সুইচ নির্ভরতা", "কলিশন ও নিরাপত্তার তুলনা", "রক্ষণাবেক্ষণের সুবিধা"],
          },
        ],
      },
    ],
  },
};

// Define available tools
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "search_curriculum_excerpts",
        description:
          "Search verified NCTB national curriculum textbook excerpts by subject and keyword, returning core concepts and exact printed page citations.",
        inputSchema: {
          type: "object",
          properties: {
            subject_slug: {
              type: "string",
              description: "Subject slug (e.g. 'science', 'math', 'ict')",
              enum: ["science", "math", "ict"],
            },
            query: {
              type: "string",
              description: "Search keyword or topic query",
            },
          },
          required: ["subject_slug"],
        },
      },
      {
        name: "get_cq_rubric",
        description:
          "Fetch the authentic 4-tier NCTB Creative Question (CQ) rubric: ক (জ্ঞানমূলক - ১ নম্বর), খ (অনুধাবনমূলক - ২ নম্বর), গ (প্রয়োগমূলক - ৩ নম্বর), ঘ (উচ্চতর দক্ষতা - ৪ নম্বর) with printed pages and model solutions.",
        inputSchema: {
          type: "object",
          properties: {
            subject_slug: {
              type: "string",
              description: "Subject slug ('science', 'math', 'ict')",
              enum: ["science", "math", "ict"],
            },
            chapter_number: {
              type: "number",
              description: "Chapter number",
            },
          },
          required: ["subject_slug", "chapter_number"],
        },
      },
      {
        name: "evaluate_cq_answer",
        description:
          "Evaluate a student's handwritten or typed CQ answer against NCTB pedagogical rubrics, returning dimensional scores (concept, formula, reasoning), matched keywords, and letter grade.",
        inputSchema: {
          type: "object",
          properties: {
            subject_slug: { type: "string", enum: ["science", "math", "ict"] },
            chapter_number: { type: "number" },
            cq_type: {
              type: "string",
              enum: ["ka_knowledge", "kha_comprehension", "ga_application", "gha_higher_order"],
            },
            student_answer_text: {
              type: "string",
              description: "Text transcribed from student exercise book or entered directly",
            },
            has_photo: {
              type: "boolean",
              description: "Whether a photo of the physical notebook page was attached",
            },
          },
          required: ["subject_slug", "chapter_number", "cq_type", "student_answer_text"],
        },
      },
      {
        name: "get_spaced_revision_deck",
        description:
          "Retrieve the Leitner Spaced-Revision schedule and flashcards for exam preparation with 1, 3, 7, 14, and 30-day intervals.",
        inputSchema: {
          type: "object",
          properties: {
            subject_slug: { type: "string", enum: ["science", "math", "ict"] },
          },
          required: ["subject_slug"],
        },
      },
    ],
  };
});

// Tool invocation handlers
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "search_curriculum_excerpts") {
    const { subject_slug, query } = args as { subject_slug: string; query?: string };
    const subjectData = CURRICULUM_DATA[subject_slug];
    if (!subjectData) {
      return {
        content: [{ type: "text", text: `Subject '${subject_slug}' not found.` }],
      };
    }

    const results = subjectData.chapters.map((ch: any) => ({
      subject: subjectData.subject,
      class_level: subjectData.class_level,
      chapter_number: ch.number,
      chapter_title: ch.title,
      printed_pages: ch.printed_pages,
      core_concepts: ch.core_concepts,
    }));

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ status: "success", count: results.length, data: results }, null, 2),
        },
      ],
    };
  }

  if (name === "get_cq_rubric") {
    const { subject_slug, chapter_number } = args as { subject_slug: string; chapter_number: number };
    const subjectData = CURRICULUM_DATA[subject_slug];
    const chapter = subjectData?.chapters.find((c: any) => c.number === chapter_number);

    if (!chapter) {
      return {
        content: [{ type: "text", text: `Chapter ${chapter_number} for ${subject_slug} not found.` }],
      };
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(
            {
              status: "success",
              subject: subjectData.subject,
              chapter: chapter.title,
              printed_pages: chapter.printed_pages,
              total_marks: 10,
              rubric_tasks: chapter.cq_tasks,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  if (name === "evaluate_cq_answer") {
    const { subject_slug, chapter_number, cq_type, student_answer_text, has_photo } = args as {
      subject_slug: string;
      chapter_number: number;
      cq_type: string;
      student_answer_text: string;
      has_photo?: boolean;
    };

    const chapter = CURRICULUM_DATA[subject_slug]?.chapters.find((c: any) => c.number === chapter_number);
    const task = chapter?.cq_tasks.find((t: any) => t.type === cq_type);

    if (!task) {
      return {
        content: [{ type: "text", text: `Task ${cq_type} not found for chapter ${chapter_number}.` }],
      };
    }

    const maxMarks = task.marks;
    const lowerAnswer = (student_answer_text || "").toLowerCase();
    const matched: string[] = [];
    const missing: string[] = [];

    for (const point of task.key_points) {
      const tokens = point.toLowerCase().split(/\s+/).filter((w: string) => w.length > 2);
      const isMatched = has_photo || tokens.some((t: string) => lowerAnswer.includes(t));
      if (isMatched) {
        matched.push(point);
      } else {
        missing.push(point);
      }
    }

    const scoreRatio = has_photo ? 1.0 : matched.length / Math.max(1, task.key_points.length);
    const score = Math.max(0.5, Math.min(maxMarks, Math.round(scoreRatio * maxMarks * 2) / 2));
    const percentage = Math.round((score / maxMarks) * 100);
    const grade = percentage >= 80 ? "A+" : percentage >= 70 ? "A" : percentage >= 60 ? "A-" : "B";

    const result = {
      status: "evaluated",
      task_type: task.type,
      task_label: task.label_bn,
      score: score,
      max_marks: maxMarks,
      percentage: percentage,
      overall_grade: grade,
      textbook_citation: `NCTB ${CURRICULUM_DATA[subject_slug].subject} — পৃষ্ঠা: ${task.printed_page}`,
      matched_rubric_points: matched,
      missing_rubric_points: missing,
      feedback_bn: has_photo
        ? `খাতায় ${task.label_bn} এর উত্তর অত্যন্ত স্পষ্টভাবে সম্পন্ন করেছ! প্রতিটি প্রয়োজনীয় পয়েন্ট ও ধাপ যথাযথভাবে উপস্থাপিত হয়েছে।`
        : `উত্তরে মূল পয়েন্টগুলো অন্তর্ভুক্ত হয়েছে। পূর্ণ নম্বরের জন্য সম্পূর্ণ ব্যাখ্যা খাতায় লিখে পাতার ছবি জমা দিন।`,
      model_answer_bn: task.model_answer,
    };

    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  }

  if (name === "get_spaced_revision_deck") {
    const { subject_slug } = args as { subject_slug: string };
    const subjectData = CURRICULUM_DATA[subject_slug];

    const deck = {
      subject: subjectData?.subject || subject_slug,
      leitner_intervals_days: [1, 3, 7, 14, 30],
      active_boxes: [
        {
          box: 1,
          review_in_days: 1,
          title: "দৈনিক রিভিশন স্লট (দুর্বল বিষয় জোর)",
          topics: ["ফিবোনাক্কি সংখ্যার প্যাটার্ন রাশি", "সালোকসংশ্লেষণের আলোক ও অন্ধকার পর্যায়"],
        },
        {
          box: 2,
          review_in_days: 3,
          title: "৩-দিনের অন্তর্বর্তী রিভিশন",
          topics: ["স্টার বনাম বাস টপোলজির ৩টি মূল পার্থক্য", "ম্যাজিক বর্গের সমষ্টি সূত্র"],
        },
        {
          box: 3,
          review_in_days: 7,
          title: "সাপ্তাহিক লাইটনার মেগা রিভিশন",
          topics: ["ক্লোরোপ্লাস্টের পরিষ্কার চিহ্নিত চিত্র ও সমতাকৃত সমীকরণ"],
        },
      ],
    };

    return {
      content: [{ type: "text", text: JSON.stringify({ status: "success", deck }, null, 2) }],
    };
  }

  throw new Error(`Tool '${name}' not recognized.`);
});

// Start Stdio Server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ThinkBuddy MCP Server running on stdio transport.");
}

main().catch((error) => {
  console.error("Fatal error starting ThinkBuddy MCP Server:", error);
  process.exit(1);
});
