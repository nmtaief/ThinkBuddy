import { NextRequest, NextResponse } from "next/server";
import { getQuizQuestionsForSubjectAndChapter } from "@/lib/curriculum-study-engine";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      subject = "সাধারণ বিজ্ঞান",
      chapterNumber = 1,
      chapterTitle = "",
      classLevel = 8,
      part = 1,
      startPage = 1,
      endPage = 3,
      count = 15,
      seed,
    } = body;

    const questions = getQuizQuestionsForSubjectAndChapter({
      subject,
      chapterNumber: Number(chapterNumber) || 1,
      chapterTitle,
      classLevel: Number(classLevel) || 8,
      part: Number(part) || 1,
      startPage: Number(startPage) || 1,
      endPage: Number(endPage) || 3,
      count: Number(count) || 15,
      seed: seed ?? Date.now(),
    });

    return NextResponse.json({
      success: true,
      data: {
        subject,
        chapter_title: chapterTitle,
        class_level: classLevel,
        pages_covered: `${startPage}–${endPage}`,
        count: questions.length,
        questions,
      },
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message || "Failed to generate AI quiz" },
      { status: 500 }
    );
  }
}
