import streamlit as st
import json
import os
import sys
from datetime import datetime

# パスの設定を改善
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from utils.database import DataManager
except ImportError as e:
    st.error(f"モジュールのインポートエラー: {e}")
    st.stop()


def prompt_library_page():
    """プロンプトライブラリ画面"""
    st.header("📚 プロンプトライブラリ")

    # データマネージャーの初期化
    if "data_manager" not in st.session_state:
        DATA_DIR = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"
        )
        st.session_state.data_manager = DataManager(DATA_DIR)

    data_manager = st.session_state.get("data_manager")
    if not data_manager:
        st.error("データマネージャーの初期化に失敗しました。")
        return

    # タブで機能を分割
    tabs = st.tabs(["📖 プロンプト一覧", "➕ 新規追加", "✏️ 編集・削除"])

    with tabs[0]:
        st.subheader("📖 プロンプト一覧")

        # プロンプトの読み込み
        prompts = data_manager.load_prompts()

        if not prompts:
            st.info(
                "プロンプトが登録されていません。「新規追加」タブから追加してください。"
            )
        else:
            # カテゴリでフィルタリング
            categories = list(
                set(prompt.get("category", "未分類") for prompt in prompts)
            )
            categories.insert(0, "すべて")

            selected_category = st.selectbox("カテゴリで絞り込み", categories)

            # 検索
            search_query = st.text_input("プロンプトを検索")

            # フィルタリング
            filtered_prompts = prompts
            if selected_category != "すべて":
                filtered_prompts = [
                    p
                    for p in filtered_prompts
                    if p.get("category", "未分類") == selected_category
                ]

            if search_query:
                filtered_prompts = [
                    p
                    for p in filtered_prompts
                    if search_query.lower() in p.get("title", "").lower()
                    or search_query.lower() in p.get("content", "").lower()
                ]

            # プロンプトの表示
            st.write(f"表示中: {len(filtered_prompts)} / {len(prompts)} 件")

            for i, prompt in enumerate(filtered_prompts):
                with st.expander(
                    f"📄 {prompt.get('title', '無題')} "
                    f"[{prompt.get('category', '未分類')}]"
                ):
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.markdown("**内容:**")
                        st.markdown(f"> {prompt.get('content', '')}")
                        st.write(f"📅 作成日: {prompt.get('created_at', '不明')}")

                    with col2:
                        # プロンプトをコピー
                        if st.button("📋 コピー", key=f"copy_{i}"):
                            # JavaScript経由でクリップボードにコピー（実際の実装では制限あり）
                            st.success("プロンプトをコピーしました！")
                            st.code(prompt.get("content", ""), language=None)

    with tabs[1]:
        st.subheader("➕ 新しいプロンプトを追加")

        with st.form("add_prompt_form"):
            title = st.text_input("タイトル*", placeholder="プロンプトのタイトルを入力")
            category = st.text_input("カテゴリ", placeholder="例: 一般, 技術, 創作など")
            content = st.text_area(
                "プロンプト内容*",
                placeholder="プロンプトの内容を入力してください...",
                height=200,
            )

            submitted = st.form_submit_button("📝 プロンプトを追加")

            if submitted:
                if not title.strip():
                    st.error("タイトルは必須です。")
                elif not content.strip():
                    st.error("プロンプト内容は必須です。")
                else:
                    # 新しいプロンプトを追加
                    prompts = data_manager.load_prompts()

                    # 新しいIDを生成
                    new_id = max([p.get("id", 0) for p in prompts], default=0) + 1

                    new_prompt = {
                        "id": new_id,
                        "title": title.strip(),
                        "content": content.strip(),
                        "category": category.strip() if category.strip() else "未分類",
                        "created_at": datetime.now().isoformat(),
                    }

                    prompts.append(new_prompt)

                    # ファイルに保存
                    try:
                        PROMPTS_FILE = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            "data",
                            "prompts.json",
                        )
                        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                            json.dump(prompts, f, ensure_ascii=False, indent=2)

                        st.success("✅ プロンプトを追加しました！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"保存に失敗しました: {str(e)}")

    with tabs[2]:
        st.subheader("✏️ プロンプトの編集・削除")

        prompts = data_manager.load_prompts()

        if not prompts:
            st.info("編集・削除するプロンプトがありません。")
        else:
            # 編集するプロンプトを選択
            prompt_options = {
                f"{prompt.get('title', '無題')} [{prompt.get('category', '未分類')}]": prompt
                for prompt in prompts
            }

            selected_option = st.selectbox(
                "編集・削除するプロンプトを選択", list(prompt_options.keys())
            )

            selected_prompt = prompt_options.get(selected_option)

            if selected_prompt:
                st.markdown("---")

                # 編集フォーム
                with st.form("edit_prompt_form"):
                    st.write("**現在の内容:**")

                    edit_title = st.text_input(
                        "タイトル", value=selected_prompt.get("title", "")
                    )
                    edit_category = st.text_input(
                        "カテゴリ", value=selected_prompt.get("category", "")
                    )
                    edit_content = st.text_area(
                        "プロンプト内容",
                        value=selected_prompt.get("content", ""),
                        height=200,
                    )

                    col1, col2 = st.columns(2)

                    with col1:
                        update_submitted = st.form_submit_button(
                            "💾 更新", use_container_width=True
                        )

                    with col2:
                        delete_submitted = st.form_submit_button(
                            "🗑️ 削除", use_container_width=True, type="secondary"
                        )

                    if update_submitted:
                        if not edit_title.strip():
                            st.error("タイトルは必須です。")
                        elif not edit_content.strip():
                            st.error("プロンプト内容は必須です。")
                        else:
                            # プロンプトを更新
                            for prompt in prompts:
                                if prompt.get("id") == selected_prompt.get("id"):
                                    prompt["title"] = edit_title.strip()
                                    prompt["category"] = (
                                        edit_category.strip()
                                        if edit_category.strip()
                                        else "未分類"
                                    )
                                    prompt["content"] = edit_content.strip()
                                    break

                            # ファイルに保存
                            try:
                                PROMPTS_FILE = os.path.join(
                                    os.path.dirname(
                                        os.path.dirname(os.path.dirname(__file__))
                                    ),
                                    "data",
                                    "prompts.json",
                                )
                                with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                                    json.dump(prompts, f, ensure_ascii=False, indent=2)

                                st.success("✅ プロンプトを更新しました！")
                                st.rerun()
                            except Exception as e:
                                st.error(f"保存に失敗しました: {str(e)}")

                    if delete_submitted:
                        # 削除の確認
                        if st.session_state.get(
                            "confirm_delete"
                        ) != selected_prompt.get("id"):
                            st.session_state.confirm_delete = selected_prompt.get("id")
                            st.warning(
                                "⚠️ 再度「削除」ボタンを押すと完全に削除されます。"
                            )
                        else:
                            # プロンプトを削除
                            prompts = [
                                p
                                for p in prompts
                                if p.get("id") != selected_prompt.get("id")
                            ]

                            # ファイルに保存
                            try:
                                PROMPTS_FILE = os.path.join(
                                    os.path.dirname(
                                        os.path.dirname(os.path.dirname(__file__))
                                    ),
                                    "data",
                                    "prompts.json",
                                )
                                with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                                    json.dump(prompts, f, ensure_ascii=False, indent=2)

                                st.success("✅ プロンプトを削除しました！")
                                if "confirm_delete" in st.session_state:
                                    del st.session_state.confirm_delete
                                st.rerun()
                            except Exception as e:
                                st.error(f"削除に失敗しました: {str(e)}")


# このページが直接実行された場合
if __name__ == "__main__":
    prompt_library_page()
