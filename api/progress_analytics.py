"""Hierarchical Progress API & Learning Loop Analytics.

Returns nested tree:
Class -> Subjects -> Chapters -> Book Topics -> Cognitive Tiers
Provides encouraging status badges:
- "ভালো অবস্থানে আছো" (when mastery_pct >= 75% and weak_count == 0)
- "আরও অনুশীলন দরকার" (when weak_count > 0 or accuracy_pct < 70%)
"""

from typing import Dict, List, Any, Optional
from services.mastery_tracker import MasteryTracker


class ProgressAnalytics:
    def __init__(self, tracker: MasteryTracker, questions_catalog: Optional[List[Dict[str, Any]]] = None):
        self.tracker = tracker
        self.catalog = questions_catalog or []

    def get_hierarchical_progress(self, user_id: str, class_level: int) -> Dict[str, Any]:
        """Constructs full nested hierarchical progress tree."""
        # 1. Class level stats
        class_key = f"{user_id}_class_{class_level}"
        class_rollup = self.tracker.rollups.get(class_key, {})
        
        # Determine status label
        c_weak = class_rollup.get("weak_count", 0)
        c_acc = class_rollup.get("accuracy_pct", 0.0)
        c_mastery = class_rollup.get("mastery_pct", 0.0)
        
        status_label = "ভালো অবস্থানে আছো" if (c_mastery >= 75.0 and c_weak == 0) else "আরও অনুশীলন দরকার"

        root = {
            "class_level": class_level,
            "user_id": str(user_id),
            "mastery_pct": c_mastery,
            "accuracy_pct": c_acc,
            "weak_count": c_weak,
            "recovered_from_wrong_count": class_rollup.get("recovered_from_wrong_count", 0),
            "needs_more_practice": class_rollup.get("needs_more_practice", False),
            "status_badge": status_label,
            "subjects": {}
        }

        # 2. Group catalog questions into subjects -> chapters -> book_topics
        for q in self.catalog:
            if q.get("class_level") != class_level:
                continue
            sub = q.get("subject", "general")
            chap = q.get("chapter_title") or str(q.get("chapter_id", "General Chapter"))
            top_id = str(q.get("book_topic_id", "General Topic"))
            top_name = q.get("book_topic_name", "General Topic")
            tier = q.get("cognitive_tier", "Gyanmulok")

            if sub not in root["subjects"]:
                sub_key = f"{user_id}_sub_{sub}"
                s_r = self.tracker.rollups.get(sub_key, {})
                s_weak = s_r.get("weak_count", 0)
                s_mast = s_r.get("mastery_pct", 0.0)
                root["subjects"][sub] = {
                    "subject": sub,
                    "mastery_pct": s_mast,
                    "accuracy_pct": s_r.get("accuracy_pct", 0.0),
                    "weak_count": s_weak,
                    "status_badge": "ভালো অবস্থানে আছো" if (s_mast >= 75.0 and s_weak == 0) else "আরও অনুশীলন দরকার",
                    "chapters": {}
                }

            s_node = root["subjects"][sub]
            if chap not in s_node["chapters"]:
                c_key = f"{user_id}_chap_{q.get('chapter_id')}"
                ch_r = self.tracker.rollups.get(c_key, {})
                s_node["chapters"][chap] = {
                    "chapter_title": chap,
                    "mastery_pct": ch_r.get("mastery_pct", 0.0),
                    "weak_count": ch_r.get("weak_count", 0),
                    "book_topics": {}
                }

            ch_node = s_node["chapters"][chap]
            if top_id not in ch_node["book_topics"]:
                t_key = f"{user_id}_top_{top_id}"
                t_r = self.tracker.rollups.get(t_key, {})
                t_weak = t_r.get("weak_count", 0)
                t_mast = t_r.get("mastery_pct", 0.0)
                ch_node["book_topics"][top_id] = {
                    "book_topic_id": top_id,
                    "book_topic_name": top_name,
                    "mastery_pct": t_mast,
                    "weak_count": t_weak,
                    "status_badge": "ভালো অবস্থানে আছো" if (t_mast >= 75.0 and t_weak == 0) else "আরও অনুশীলন দরকার",
                    "cognitive_tiers": {
                        "Gyanmulok": {"attempted": 0, "correct": 0},
                        "Unudhabon": {"attempted": 0, "correct": 0},
                        "Proyog": {"attempted": 0, "correct": 0},
                        "Uchchotor_Dokkhota": {"attempted": 0, "correct": 0}
                    }
                }

            # Increment tier counter if question has state
            st = self.tracker.get_state(user_id, q["id"])
            if st["status"] != "unseen":
                t_node = ch_node["book_topics"][top_id]["cognitive_tiers"][tier]
                t_node["attempted"] += 1
                if st["status"] == "mastered":
                    t_node["correct"] += 1

        # Format subjects into list for frontend consumption
        subjects_list = []
        for s_name, s_data in root["subjects"].items():
            chap_list = []
            for c_name, c_data in s_data["chapters"].items():
                top_list = list(c_data["book_topics"].values())
                chap_list.append({
                    "chapter_title": c_name,
                    "mastery_pct": c_data["mastery_pct"],
                    "weak_count": c_data["weak_count"],
                    "book_topics": top_list
                })
            subjects_list.append({
                "subject": s_name,
                "mastery_pct": s_data["mastery_pct"],
                "accuracy_pct": s_data["accuracy_pct"],
                "weak_count": s_data["weak_count"],
                "status_badge": s_data["status_badge"],
                "chapters": chap_list
            })
        root["subjects"] = subjects_list
        return root
