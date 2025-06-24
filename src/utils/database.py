"""
データベース操作用のユーティリティ関数
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional


class DataManager:
    """データ管理クラス"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.prompts_file = os.path.join(data_dir, "prompts.json")
        self.chat_history_file = os.path.join(data_dir, "chat_history.json")
        self.users_file = os.path.join(data_dir, "users.json")

        # データディレクトリが存在しない場合は作成
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def load_prompts(self) -> List[Dict]:
        """プロンプトデータを読み込み"""
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_prompts(self, prompts: List[Dict]) -> bool:
        """プロンプトデータを保存"""
        try:
            with open(self.prompts_file, "w", encoding="utf-8") as f:
                json.dump(prompts, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"プロンプト保存エラー: {e}")
            return False

    def add_prompt(self, title: str, content: str, category: str = "一般") -> Dict:
        """新しいプロンプトを追加"""
        prompts = self.load_prompts()
        new_id = max([p.get("id", 0) for p in prompts]) + 1 if prompts else 1

        new_prompt = {
            "id": new_id,
            "title": title,
            "content": content,
            "category": category,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "usage_count": 0,
        }

        prompts.append(new_prompt)
        self.save_prompts(prompts)
        return new_prompt

    def update_prompt(
        self,
        prompt_id: int,
        title: str = None,
        content: str = None,
        category: str = None,
    ) -> bool:
        """プロンプトを更新"""
        prompts = self.load_prompts()

        for i, prompt in enumerate(prompts):
            if prompt.get("id") == prompt_id:
                if title:
                    prompts[i]["title"] = title
                if content:
                    prompts[i]["content"] = content
                if category:
                    prompts[i]["category"] = category
                prompts[i]["updated_at"] = datetime.now().isoformat()

                self.save_prompts(prompts)
                return True
        return False

    def delete_prompt(self, prompt_id: int) -> bool:
        """プロンプトを削除"""
        prompts = self.load_prompts()
        original_length = len(prompts)

        prompts = [p for p in prompts if p.get("id") != prompt_id]

        if len(prompts) < original_length:
            self.save_prompts(prompts)
            return True
        return False

    def get_prompt_by_id(self, prompt_id: int) -> Optional[Dict]:
        """IDでプロンプトを取得"""
        prompts = self.load_prompts()
        return next((p for p in prompts if p.get("id") == prompt_id), None)

    def load_chat_history(self) -> List[Dict]:
        """チャット履歴を読み込み"""
        try:
            if os.path.exists(self.chat_history_file):
                with open(self.chat_history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_chat_history(self, history: List[Dict]) -> bool:
        """チャット履歴を保存"""
        try:
            with open(self.chat_history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"チャット履歴保存エラー: {e}")
            return False

    def add_chat_session(self, title: str, messages: List[Dict]) -> Dict:
        """新しいチャットセッションを追加"""
        history = self.load_chat_history()

        # プレビューを作成
        preview = ""
        if messages:
            first_message = messages[0].get("content", "")
            preview = (
                first_message[:50] + "..." if len(first_message) > 50 else first_message
            )

        new_session = {
            "id": datetime.now().timestamp(),
            "title": title,
            "preview": preview,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": messages,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        history.append(new_session)
        self.save_chat_history(history)
        return new_session

    def update_chat_session(
        self, session_id: float, title: str = None, messages: List[Dict] = None
    ) -> bool:
        """チャットセッションを更新"""
        history = self.load_chat_history()

        for i, session in enumerate(history):
            if session.get("id") == session_id:
                if title:
                    history[i]["title"] = title
                if messages:
                    history[i]["messages"] = messages
                    # プレビューを更新
                    if messages:
                        first_message = messages[0].get("content", "")
                        history[i]["preview"] = (
                            first_message[:50] + "..."
                            if len(first_message) > 50
                            else first_message
                        )

                history[i]["updated_at"] = datetime.now().isoformat()
                self.save_chat_history(history)
                return True
        return False

    def delete_chat_session(self, session_id: float) -> bool:
        """チャットセッションを削除"""
        history = self.load_chat_history()
        original_length = len(history)

        history = [s for s in history if s.get("id") != session_id]

        if len(history) < original_length:
            self.save_chat_history(history)
            return True
        return False

    def search_chat_history(self, query: str) -> List[Dict]:
        """チャット履歴を検索"""
        history = self.load_chat_history()
        query_lower = query.lower()

        filtered_history = []
        for session in history:
            # タイトルまたはプレビューに検索クエリが含まれているかチェック
            if (
                query_lower in session.get("title", "").lower()
                or query_lower in session.get("preview", "").lower()
            ):
                filtered_history.append(session)
            else:
                # メッセージ内容も検索
                for message in session.get("messages", []):
                    if query_lower in message.get("content", "").lower():
                        filtered_history.append(session)
                        break

        return filtered_history

    def get_chat_statistics(self) -> Dict:
        """チャット統計情報を取得"""
        history = self.load_chat_history()
        prompts = self.load_prompts()

        total_chats = len(history)
        total_messages = sum(len(session.get("messages", [])) for session in history)
        total_prompts = len(prompts)

        # 最新のチャット日時
        latest_chat = None
        if history:
            latest_session = max(history, key=lambda x: x.get("date", ""))
            latest_chat = latest_session.get("date", "")

        return {
            "total_chats": total_chats,
            "total_messages": total_messages,
            "total_prompts": total_prompts,
            "latest_chat": latest_chat,
        }

    def export_data(self, export_type: str = "all") -> Dict:
        """データをエクスポート"""
        result = {}

        if export_type in ["all", "prompts"]:
            result["prompts"] = self.load_prompts()

        if export_type in ["all", "chat_history"]:
            result["chat_history"] = self.load_chat_history()

        result["exported_at"] = datetime.now().isoformat()
        return result

    def import_data(self, data: Dict) -> bool:
        """データをインポート"""
        try:
            if "prompts" in data:
                self.save_prompts(data["prompts"])

            if "chat_history" in data:
                self.save_chat_history(data["chat_history"])

            return True
        except Exception as e:
            print(f"データインポートエラー: {e}")
            return False
