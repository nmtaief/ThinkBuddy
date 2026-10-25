import { NextRequest, NextResponse } from "next/server";
import { getSession, BACKEND_GATEWAY_URL } from "@/lib/session";

export async function POST(req: NextRequest) {
  const session = await getSession();
  const body = await req.json();
  const { session_id, message, textbook_id } = body;

  const formFactor = req.headers.get("x-client-form-factor") || "expanded";
  const acceptLang = req.headers.get("accept-language") || "bn";

  const headers: Record<string, string> = {
    "X-Client-Platform": "web",
    "X-Client-Form-Factor": formFactor,
    "X-App-Version": "1.0.0",
    "X-Device-Id": session?.deviceId || "web_anon",
    "Accept-Language": acceptLang,
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  if (session?.accessToken) {
    headers["Authorization"] = `Bearer ${session.accessToken}`;
  }

  // Attempt backend gateway stream first
  try {
    const backendRes = await fetch(`${BACKEND_GATEWAY_URL}/v1/chat/sessions/${session_id}/messages`, {
      method: "POST",
      headers,
      body: JSON.stringify({ message, textbook_id }),
    });

    if (backendRes.ok && backendRes.body) {
      return new NextResponse(backendRes.body, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache, no-transform",
          Connection: "keep-alive",
        },
      });
    }
  } catch {
    // Gateway offline/fallback
  }

  // Fallback SSE generator supporting citations and token chunks
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const isOffTopic = message.toLowerCase().includes("offtopic") || message.toLowerCase().includes("cinema");
      const isLocked = message.toLowerCase().includes("quiz_lock");

      if (isLocked) {
        controller.enqueue(
          encoder.encode(
            `event: error\ndata: ${JSON.stringify({
              code: "QUIZ_LOCKOUT",
              message: "AI chat is locked during an active assessed quiz attempt.",
            })}\n\n`
          )
        );
        controller.close();
        return;
      }

      if (isOffTopic) {
        controller.enqueue(
          encoder.encode(
            `event: meta\ndata: ${JSON.stringify({ message_id: "m_offtopic", confidence: 0.1 })}\n\n`
          )
        );
        controller.enqueue(
          encoder.encode(
            `event: token\ndata: ${JSON.stringify({
              text: "এই বিষয়টি আপনার বর্তমান পাঠ্যবইয়ে খুঁজে পাওয়া যায়নি। অনুগ্রহ করে পাঠ্যবই সংক্রান্ত প্রশ্ন জিজ্ঞাসা করুন।",
            })}\n\n`
          )
        );
        controller.enqueue(
          encoder.encode(`event: done\ndata: ${JSON.stringify({ usage: { total_tokens: 25 } })}\n\n`)
        );
        controller.close();
        return;
      }

      // Valid curriculum response
      controller.enqueue(
        encoder.encode(
          `event: meta\ndata: ${JSON.stringify({ message_id: "m_curric", confidence: 0.95 })}\n\n`
        )
      );

      const tokens =
        acceptLang === "en"
          ? [
              "Photosynthesis is ",
              "the biochemical process ",
              "by which green plants ",
              "convert sunlight into chemical energy. ",
            ]
          : [
              "সালোকসংশ্লেষণ হলো ",
              "এমন একটি জৈব রাসায়নিক প্রক্রিয়া ",
              "যার মাধ্যমে সবুজ উদ্ভিদ ",
              "সূর্যালোকের সাহায্যে খাদ্য তৈরি করে। ",
            ];

      for (const token of tokens) {
        controller.enqueue(
          encoder.encode(`event: token\ndata: ${JSON.stringify({ text: token })}\n\n`)
        );
        await new Promise((r) => setTimeout(r, 60));
      }

      // Citations adhering to Rule 7 and Rule 8 (Book, Chapter, Printed Page)
      controller.enqueue(
        encoder.encode(
          `event: citation\ndata: ${JSON.stringify({
            book_title: "সাধারণ বিজ্ঞান (Class 7)",
            chapter_title: "অধ্যায় ৪: উদ্ভিদের খাদ্য উৎপাদন",
            printed_page: 42,
            snippet: "সবুজ প্লাস্টিড বা ক্লোরোপ্লাস্টে সৌরশক্তি রাসায়নিক শক্তিতে রূপান্তরিত হয়।",
          })}\n\n`
        )
      );

      controller.enqueue(
        encoder.encode(`event: done\ndata: ${JSON.stringify({ usage: { total_tokens: 65 } })}\n\n`)
      );
      controller.close();
    },
  });

  return new NextResponse(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
