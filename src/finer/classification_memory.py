"""
Classification Memory Module
分类记忆模块 - 用于存储和查询历史分类规则
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime


class ClassificationMemory:
    """分类记忆管理器"""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent.parent.parent / "data" / "classification_memory"
        self.rules_file = self.data_dir / "rules_learned.json"
        self.patterns_file = self.data_dir / "creator_patterns.json"
        self.feedback_file = self.data_dir / "feedback_log.json"

    def _load_json(self, file_path: Path) -> dict:
        """加载JSON文件"""
        if not file_path.exists():
            return {"rules": [], "patterns": [], "feedbacks": [], "metadata": {}}
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, file_path: Path, data: dict) -> None:
        """保存JSON文件"""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_creator_by_filename(self, filename: str) -> Optional[str]:
        """根据文件名匹配创作者"""
        patterns = self._load_json(self.patterns_file)
        for pattern in patterns.get("patterns", []):
            import fnmatch
            for fp in pattern.get("file_patterns", []):
                if fnmatch.fnmatch(filename, fp):
                    return pattern["creator_name"]
        return None

    def get_creator_by_content(self, content: str) -> Optional[str]:
        """根据内容关键词匹配创作者"""
        patterns = self._load_json(self.patterns_file)
        best_match = None
        best_confidence = 0

        for pattern in patterns.get("patterns", []):
            for keyword in pattern.get("content_keywords", []):
                if keyword in content:
                    if pattern["confidence"] > best_confidence:
                        best_match = pattern["creator_name"]
                        best_confidence = pattern["confidence"]

        return best_match

    def record_feedback(
        self,
        file_path: str,
        original_creator: str,
        corrected_creator: str,
        reason: str = ""
    ) -> str:
        """记录人工纠正反馈"""
        feedbacks = self._load_json(self.feedback_file)
        feedback_id = f"fb_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        feedbacks.setdefault("feedbacks", []).append({
            "id": feedback_id,
            "timestamp": datetime.now().isoformat(),
            "file_path": file_path,
            "original_creator": original_creator,
            "corrected_creator": corrected_creator,
            "reason": reason
        })
        feedbacks["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        feedbacks["metadata"]["total_feedbacks"] = len(feedbacks["feedbacks"])

        self._save_json(self.feedback_file, feedbacks)
        return feedback_id

    def learn_rule_from_feedback(self, feedback_id: str) -> Optional[str]:
        """从反馈中学习新规则"""
        feedbacks = self._load_json(self.feedback_file)
        rules = self._load_json(self.rules_file)

        for fb in feedbacks.get("feedbacks", []):
            if fb["id"] == feedback_id:
                rule_id = f"rule_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                rules.setdefault("rules", []).append({
                    "id": rule_id,
                    "pattern": fb["file_path"],
                    "creator": fb["corrected_creator"],
                    "category": "自动学习",
                    "confidence": 0.8,
                    "learned_from": feedback_id,
                    "created_at": datetime.now().strftime("%Y-%m-%d")
                })
                rules["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                rules["metadata"]["total_rules"] = len(rules["rules"])
                self._save_json(self.rules_file, rules)
                return rule_id
        return None


# 单例实例
_memory_instance: Optional[ClassificationMemory] = None


def get_memory() -> ClassificationMemory:
    """获取分类记忆单例"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = ClassificationMemory()
    return _memory_instance
