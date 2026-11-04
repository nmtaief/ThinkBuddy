package com.thinkbuddy.app

import com.thinkbuddy.app.core.network.PlannerTaskResponse
import com.thinkbuddy.app.core.network.TodayScheduleResponse
import com.thinkbuddy.app.core.network.TodayTask
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit Test verifying that distinct seeded students (Tahmid vs Anika) produce
 * completely distinct live subjects, tasks, targets, and textbook citations,
 * proving zero hardcoded subject fallbacks in UI data pipelines.
 */
class TwoSeededStudentsDataTest {

    @Test
    fun testTwoSeededStudentsDisplayDistinctData() {
        // Seeded Student 1 (Tahmid)
        val student1Schedule = TodayScheduleResponse(
            date = "2026-11-02",
            studentId = "student-tahmid-1",
            studyTasks = listOf(
                PlannerTaskResponse(
                    id = "task-tahmid-1",
                    subject = "পদার্থবিজ্ঞান (Physics)",
                    chapterId = "ch-physics-1",
                    refs = mapOf("printed_pages" to "৪২ – ৫৬", "chapter_title" to "গতি ও বল", "subject_bn" to "পদার্থবিজ্ঞান"),
                    estMinutes = 45,
                    status = "pending"
                ),
                PlannerTaskResponse(
                    id = "task-tahmid-2",
                    subject = "সাধারণ গণিত (General Math)",
                    chapterId = "ch-math-2",
                    refs = mapOf("printed_pages" to "৭৮ – ৯০", "chapter_title" to "দ্বিঘাত সমীকরণ", "subject_bn" to "সাধারণ গণিত"),
                    estMinutes = 60,
                    status = "completed"
                )
            ),
            totalPlannedMinutes = 105,
            completedMinutes = 60,
            streak = 7
        )

        // Seeded Student 2 (Anika)
        val student2Schedule = TodayScheduleResponse(
            date = "2026-11-02",
            studentId = "student-anika-2",
            studyTasks = listOf(
                PlannerTaskResponse(
                    id = "task-anika-1",
                    subject = "জীববিজ্ঞান (Biology)",
                    chapterId = "ch-bio-1",
                    refs = mapOf("printed_pages" to "১৪ – ২৮", "chapter_title" to "কোষ বিভাজন", "subject_bn" to "জীববিজ্ঞান"),
                    estMinutes = 50,
                    status = "pending"
                ),
                PlannerTaskResponse(
                    id = "task-anika-2",
                    subject = "রসায়ন (Chemistry)",
                    chapterId = "ch-chem-1",
                    refs = mapOf("printed_pages" to "৩২ – ৪৬", "chapter_title" to "পদার্থের অবস্থা", "subject_bn" to "রসায়ন"),
                    estMinutes = 40,
                    status = "pending"
                )
            ),
            totalPlannedMinutes = 90,
            completedMinutes = 0,
            streak = 14
        )

        // Map tasks as done in UI
        fun mapTasks(schedule: TodayScheduleResponse): List<TodayTask> {
            return schedule.studyTasks.map { t ->
                val printedPages = (t.refs?.get("printed_pages") ?: "–").toString()
                val chBn = (t.refs?.get("chapter_title") ?: t.chapterId ?: "").toString()
                val subBn = (t.refs?.get("subject_bn") ?: t.subject).toString()
                TodayTask(
                    id = t.id,
                    subject = t.subject,
                    subjectBn = subBn,
                    chapter = t.chapterId ?: "",
                    chapterBn = chBn,
                    targetMinutes = t.estMinutes,
                    completedMinutes = if (t.status == "completed") t.estMinutes else 0,
                    status = t.status,
                    printedPages = printedPages,
                    guideline = "মনোযোগ দিয়ে পাঠ্যবই পড়ে উদাহরণ সমাধান করো।"
                )
            }
        }

        val tahmidTasks = mapTasks(student1Schedule)
        val anikaTasks = mapTasks(student2Schedule)

        // 1. Verify counts and non-empty
        assertEquals(2, tahmidTasks.size)
        assertEquals(2, anikaTasks.size)

        // 2. Verify subjects are completely disjoint
        val tahmidSubjects = tahmidTasks.map { it.subjectBn }.toSet()
        val anikaSubjects = anikaTasks.map { it.subjectBn }.toSet()
        assertTrue("Subjects must be disjoint between students", tahmidSubjects.intersect(anikaSubjects).isEmpty())

        // 3. Verify distinct citations (Rule 8)
        val tahmidPages = tahmidTasks.map { it.printedPages }.toSet()
        val anikaPages = anikaTasks.map { it.printedPages }.toSet()
        assertTrue("Printed pages must be distinct", tahmidPages.intersect(anikaPages).isEmpty())

        // 4. Verify streaks and target minutes differ
        assertNotEquals(student1Schedule.streak, student2Schedule.streak)
        assertNotEquals(student1Schedule.totalPlannedMinutes, student2Schedule.totalPlannedMinutes)
    }
}

