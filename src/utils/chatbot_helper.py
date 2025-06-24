"""
チャットボット機能のヘルパー関数
"""

import re
import random
from datetime import datetime
from typing import List, Dict, Tuple


class ChatBotHelper:
    """チャットボット機能のヘルパークラス"""

    def __init__(self):
        self.greeting_patterns = [
            r"こんにちは|おはよう|こんばんは|はじめまして",
            r"hello|hi|hey|good morning|good afternoon|good evening",
        ]

        self.question_patterns = [
            r".*\?$|.*？$",
            r"^(何|なに|どう|どの|いつ|どこ|だれ|誰|なぜ|どうして).*",
            r"^(what|how|when|where|who|why|which).*",
        ]

        self.farewell_patterns = [
            r"さようなら|バイバイ|また後で|失礼します|ありがとうございました",
            r"goodbye|bye|see you|thank you|thanks",
        ]

    def detect_intent(self, message: str) -> str:
        """メッセージの意図を検出"""
        message_lower = message.lower()

        # 挨拶の検出
        for pattern in self.greeting_patterns:
            if re.search(pattern, message_lower):
                return "greeting"

        # 質問の検出
        for pattern in self.question_patterns:
            if re.search(pattern, message_lower):
                return "question"

        # 別れの挨拶の検出
        for pattern in self.farewell_patterns:
            if re.search(pattern, message_lower):
                return "farewell"

        return "general"

    def generate_response(self, message: str, intent: str = None) -> str:
        """意図に基づいて応答を生成"""
        if intent is None:
            intent = self.detect_intent(message)

        responses = {
            "greeting": [
                "こんにちは！今日はどのようなお手伝いができますか？",
                "お疲れ様です！何かご質問がございましたらお気軽にどうぞ。",
                "いらっしゃいませ！どのようなことについてお話ししましょうか？",
                "こんにちは！素晴らしい一日ですね。何かお手伝いできることはありますか？",
            ],
            "question": [
                "興味深い質問ですね。詳しく教えていただけますか？",
                "その件について詳しく調べてみますね。",
                "とても良い質問です。一緒に考えてみましょう。",
                "なるほど、それは重要なポイントですね。",
            ],
            "farewell": [
                "ありがとうございました！また何かございましたらお気軽にお声かけください。",
                "お疲れ様でした！素晴らしい一日をお過ごしください。",
                "またお会いできる日を楽しみにしております。",
                "本日はありがとうございました！",
            ],
            "general": [
                f"「{message[:30]}...」について、もう少し詳しく教えていただけますか？",
                "興味深いお話ですね。どのような点でお手伝いできるでしょうか？",
                "なるほど、そのような観点があるのですね。",
                "とても参考になります。他にも何かございますか？",
            ],
        }

        return random.choice(responses.get(intent, responses["general"]))

    def extract_keywords(self, message: str) -> List[str]:
        """メッセージからキーワードを抽出"""
        # 簡単なキーワード抽出（実際の実装では形態素解析を使用）
        stop_words = {
            "は",
            "が",
            "を",
            "に",
            "で",
            "と",
            "の",
            "から",
            "まで",
            "より",
            "も",
            "です",
            "である",
            "だ",
            "だった",
            "である",
            "ます",
            "ました",
            "でした",
            "です",
            "ですが",
            "ですか",
            "ですね",
            "ください",
            "します",
            "しました",
            "a",
            "an",
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "cannot",
            "must",
            "shall",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
        }

        # 単語に分割（簡易版）
        words = re.findall(r"\b\w+\b", message.lower())

        # ストップワードを除去
        keywords = [word for word in words if word not in stop_words and len(word) > 1]

        return keywords[:10]  # 最大10個のキーワード

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """2つのテキストの類似度を計算（簡易版）"""
        keywords1 = set(self.extract_keywords(text1))
        keywords2 = set(self.extract_keywords(text2))

        if not keywords1 and not keywords2:
            return 0.0

        intersection = keywords1.intersection(keywords2)
        union = keywords1.union(keywords2)

        return len(intersection) / len(union) if union else 0.0

    def find_similar_conversations(
        self, current_message: str, chat_history: List[Dict], threshold: float = 0.3
    ) -> List[Dict]:
        """類似した過去の会話を検索"""
        similar_conversations = []

        for session in chat_history:
            for i, message in enumerate(session.get("messages", [])):
                if message.get("role") == "user":
                    similarity = self.calculate_similarity(
                        current_message, message.get("content", "")
                    )

                    if similarity >= threshold:
                        # 次のアシスタントの返答も含める
                        context = {
                            "session_id": session.get("id"),
                            "user_message": message.get("content"),
                            "similarity": similarity,
                            "date": session.get("date"),
                        }

                        # アシスタントの返答があれば追加
                        if i + 1 < len(session.get("messages", [])):
                            next_message = session["messages"][i + 1]
                            if next_message.get("role") == "assistant":
                                context["assistant_response"] = next_message.get(
                                    "content"
                                )

                        similar_conversations.append(context)

        # 類似度順にソート
        similar_conversations.sort(key=lambda x: x["similarity"], reverse=True)

        return similar_conversations[:5]  # 最大5件

    def format_message_for_display(self, message: str, max_length: int = 100) -> str:
        """表示用にメッセージをフォーマット"""
        if len(message) <= max_length:
            return message

        return message[:max_length] + "..."

    def get_conversation_summary(self, messages: List[Dict]) -> str:
        """会話の要約を生成"""
        if not messages:
            return "会話なし"

        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        total_messages = len(messages)
        user_message_count = len(user_messages)

        if user_messages:
            first_message = user_messages[0].get("content", "")
            summary = self.format_message_for_display(first_message, 50)
        else:
            summary = "システムメッセージ"

        return f"{summary} (総メッセージ数: {total_messages}, ユーザーメッセージ数: {user_message_count})"

    def validate_message(self, message: str) -> Tuple[bool, str]:
        """メッセージの妥当性を検証"""
        if not message or not message.strip():
            return False, "メッセージが空です。"

        if len(message) > 5000:
            return False, "メッセージが長すぎます（5000文字以内）。"

        # 不適切なコンテンツのチェック（簡易版）
        inappropriate_keywords = ["スパム", "宣伝", "アダルト"]
        message_lower = message.lower()

        for keyword in inappropriate_keywords:
            if keyword in message_lower:
                return False, f"不適切なコンテンツが含まれています: {keyword}"

        return True, "OK"

    def get_chat_statistics_for_session(self, messages: List[Dict]) -> Dict:
        """セッション内のチャット統計を取得"""
        if not messages:
            return {
                "total_messages": 0,
                "user_messages": 0,
                "assistant_messages": 0,
                "average_length": 0,
            }

        user_messages = [msg for msg in messages if msg.get("role") == "user"]
        assistant_messages = [msg for msg in messages if msg.get("role") == "assistant"]

        total_length = sum(len(msg.get("content", "")) for msg in messages)
        average_length = total_length / len(messages) if messages else 0

        return {
            "total_messages": len(messages),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "average_length": round(average_length, 2),
        }

    def generate_conversation_title(self, messages: List[Dict]) -> str:
        """会話の内容からタイトルを生成"""
        if not messages:
            return "新しい会話"

        # 最初のユーザーメッセージを使用
        first_user_message = None
        for message in messages:
            if message.get("role") == "user":
                first_user_message = message.get("content", "")
                break

        if not first_user_message:
            return "新しい会話"

        # タイトル用に短縮
        title = first_user_message[:30]
        if len(first_user_message) > 30:
            title += "..."

        return title

    def get_response_suggestions(self, message: str) -> List[str]:
        """メッセージに対する応答候補を提案"""
        intent = self.detect_intent(message)
        keywords = self.extract_keywords(message)

        suggestions = []

        if intent == "question":
            suggestions.extend(
                [
                    "その件について詳しく調べてみますね。",
                    "もう少し詳細を教えていただけますか？",
                    "関連する情報をお探ししましょう。",
                ]
            )
        elif intent == "greeting":
            suggestions.extend(
                [
                    "こんにちは！今日はいかがお過ごしですか？",
                    "お疲れ様です！何かお手伝いできることはありますか？",
                ]
            )
        elif keywords:
            # キーワードに基づいた提案
            suggestions.append(
                f"「{keywords[0]}」について、どのような点をお知りになりたいですか？"
            )
            if len(keywords) > 1:
                suggestions.append(f"「{keywords[1]}」に関連する内容もお探しできます。")

        # デフォルトの提案
        suggestions.extend(
            [
                "承知いたしました。他にご質問はございますか？",
                "なるほど、そのような観点があるのですね。",
                "参考になりました。ありがとうございます。",
            ]
        )

        return suggestions[:3]  # 最大3つの提案を返す
