import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from datetime import datetime
import json
import os
import pandas as pd
import sys

# 現在のディレクトリをパスに追加
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from utils.database import DataManager
from utils.chatbot_helper import ChatBotHelper
from utils.styles import get_custom_css
from utils.tools import timer

# データディレクトリのパス
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
USERS_FILE = os.path.join(DATA_DIR, "users.yaml")
PROMPTS_FILE = os.path.join(DATA_DIR, "prompts.json")
CHAT_HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")


def init_auth_config():
    """認証設定ファイルの初期化"""
    # データディレクトリが存在しない場合は作成
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if not os.path.exists(USERS_FILE):
        # パスワードをハッシュ化
        passwords = ["123456", "abc123"]
        hasher = stauth.Hasher()
        hashed_passwords = [hasher.hash(password) for password in passwords]

        config = {
            "credentials": {
                "usernames": {
                    "admin": {
                        "email": "admin@example.com",
                        "name": "管理者",
                        "password": hashed_passwords[0],
                    },
                    "user": {
                        "email": "user@example.com",
                        "name": "ユーザー",
                        "password": hashed_passwords[1],
                    },
                }
            },
            "cookie": {
                "expiry_days": 30,
                "key": "some_signature_key",
                "name": "some_cookie_name",
            },
            "preauthorized": {"emails": ["admin@example.com"]},
        }

        with open(USERS_FILE, "w", encoding="utf-8") as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)


def init_prompts():
    """プロンプトライブラリの初期化"""
    if not os.path.exists(PROMPTS_FILE):
        default_prompts = [
            {
                "id": 1,
                "title": "一般的な質問回答",
                "content": "あなたは親切で知識豊富なアシスタントです。ユーザーの質問に対して正確で分かりやすい回答を提供してください。",
                "category": "一般",
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": 2,
                "title": "技術サポート",
                "content": "あなたは技術サポートの専門家です。技術的な問題について段階的な解決方法を提供してください。",
                "category": "技術",
                "created_at": datetime.now().isoformat(),
            },
        ]
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_prompts, f, ensure_ascii=False, indent=2)


def init_chat_history():
    """チャット履歴の初期化"""
    if not os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def init_session_state():
    """セッション状態の初期化"""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "current_chat_id" not in st.session_state:
        st.session_state.current_chat_id = None


@st.cache_data
def calculate_statistics_data(chat_history_file: str, prompts_file: str):
    """統計情報を計算する関数（キャッシュ対象）"""
    try:
        # チャット履歴の統計
        if os.path.exists(chat_history_file):
            with open(chat_history_file, "r", encoding="utf-8") as f:
                chat_history = json.load(f)
        else:
            chat_history = []

        total_chats = len(chat_history)
        total_messages = sum(len(chat.get("messages", [])) for chat in chat_history)

        # プロンプト数
        if os.path.exists(prompts_file):
            with open(prompts_file, "r", encoding="utf-8") as f:
                prompts = json.load(f)
        else:
            prompts = []

        return {
            "total_chats": total_chats,
            "total_messages": total_messages,
            "total_prompts": len(prompts),
        }
    except Exception as e:
        return {
            "total_chats": 0,
            "total_messages": 0,
            "total_prompts": 0,
            "error": str(e),
        }


def display_statistics():
    """統計情報の表示"""
    data_manager = st.session_state.get("data_manager")
    if not data_manager:
        return

    # サイドバーに統計情報を表示
    with st.sidebar:
        st.markdown("---")
        st.subheader("📊 統計情報")

        # キャッシュされた統計データを取得
        stats = calculate_statistics_data(CHAT_HISTORY_FILE, PROMPTS_FILE)

        if "error" in stats:
            st.error(f"統計情報の取得に失敗: {stats['error']}")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("チャット数", stats["total_chats"])
            with col2:
                st.metric("メッセージ数", stats["total_messages"])

            st.metric("プロンプト数", stats["total_prompts"])


def setup_authentication():
    """認証の設定と実行"""
    # 初期化
    init_auth_config()
    init_prompts()
    init_chat_history()
    init_session_state()

    # 認証設定の読み込み
    with open(USERS_FILE, encoding="utf-8") as file:
        config = yaml.load(file, Loader=SafeLoader)

    # 認証器の作成
    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )
    return authenticator


@timer
def initialize_managers():
    """データマネージャーとチャットボットヘルパーの初期化"""
    if "data_manager" not in st.session_state:
        st.session_state.data_manager = DataManager(DATA_DIR)
    if "chatbot_helper" not in st.session_state:
        st.session_state.chatbot_helper = ChatBotHelper()


@timer
def apply_custom_styles():
    """カスタムCSSの適用"""
    st.markdown(get_custom_css(), unsafe_allow_html=True)
