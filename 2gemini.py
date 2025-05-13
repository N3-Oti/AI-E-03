import google.generativeai as genai
import os
import re
import time
from dotenv import load_dotenv

# .env ファイルからAPIキーを読み込む
# 相対パスと絶対パスの両方で試行
try:
    # まず相対パスで試行
    load_dotenv(dotenv_path="AI-E-03/.env", verbose=True)
    # 絶対パスでも試行（必要に応じて）
    if not os.getenv("GOOGLE_API_KEY"):
        absolute_path = os.path.join(os.getcwd(), "AI-E-03", ".env")
        load_dotenv(dotenv_path=absolute_path, verbose=True)

    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
except Exception as e:
    print(f"警告: .env ファイルの読み込み中にエラーが発生しました: {e}")
    GOOGLE_API_KEY = None

# APIキーが設定されているか確認
if not GOOGLE_API_KEY:
    print("エラー: 環境変数 'GOOGLE_API_KEY' が設定されていません。")
    exit()

# Gemini API の設定
api_configured = False
try:
    genai.configure(api_key=GOOGLE_API_KEY)
    print("Gemini API configured successfully.")
    api_configured = True
except Exception as e:
    print(f"エラー: Gemini API の設定に失敗しました: {e}")
    exit()

# 使用するGeminiモデル (最新版を指定)
MODEL_NAME = "gemini-2.5-flash-preview-04-17"

# チャンク化マーカー記号の定義
CHUNK_SEPARATOR_MARKER = "[CHUNK_SEPARATOR]"


def process_file_with_gemini(file_path, output_path, model_name, marker=CHUNK_SEPARATOR_MARKER):
    """
    Gemini APIを使ってファイル内容にチャンク区切りマーカーを挿入し、保存します。
    """
    # API設定が成功しているかチェック
    if not api_configured:
        print("エラー: Gemini API 設定が完了していません。処理をスキップします。")
        return

    # ファイルの存在チェック
    if not os.path.exists(file_path):
        print(f"エラー: ファイル '{file_path}' が見つかりません。")
        return

    print(f"\n'{file_path}' を読み込み中...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
        print(f"'{file_path}' の読み込みに成功しました。")
    except Exception as e:
        print(f"エラー: ファイル '{file_path}' の読み込みに失敗しました: {e}")
        return

    # --- 必要最小限の前処理 ---
    processed_text = re.sub(r"<br\s*/?>", "\n", raw_text, flags=re.IGNORECASE)
    processed_text = re.sub(r"\n\s*\n", "\n\n", processed_text)
    if "digipanp" in file_path.lower():
        print("digiPanpファイル向けの前処理を適用中...")
        processed_text = re.sub(r"<img\s+[^>]*>", "", processed_text, flags=re.IGNORECASE)
        processed_text = re.sub(r"\n\n0\n\n", "\n\n", processed_text)

    print(f"'{file_path}' の前処理完了。Geminiで整形中...")

    # --- Geminiへのプロンプト作成 ---
    system_instruction = "You are an expert in document structure analysis. Read the provided text and identify meaningful breaks where the topic or section changes."

    user_prompt = f"""Read the following text and insert a special marker symbol {marker} at the end of each meaningful section or unit. Examples of meaningful breaks include the end of a chapter, the end of a major section, the end of a faculty profile, or a significant topic change.

Constraints:
- DO NOT change the original text content except for inserting the marker symbol `{marker}`.
- Maintain the Markdown formatting (headers, lists, tables, etc.) as much as possible.
- The marker symbol should be inserted on a new line by itself (e.g., \\n{marker}\\n).
- Do not consider the original text length when deciding where to insert markers; base your decision on the meaning and structure of the text.

Text:
---
{processed_text}
---

Please provide the text with the {marker} marker inserted at the appropriate breaks."""

    # --- Gemini API呼び出し ---
    try:
        model = genai.GenerativeModel(model_name)  # モデル名を修正
        print(f"Geminiモデル '{model_name}' をロードしました。")

        print("Gemini API呼び出し中...")
        response = model.generate_content(
            [{"role": "user", "parts": [{"text": system_instruction + "\n\n" + user_prompt}]}],  # Gemini APIの形式に合わせる
        )

        if hasattr(response, "text"):
            generated_text = response.text
            print("Gemini API 呼び出し成功。")
        else:
            print(f"エラー: Geminiからの応答にテキストが含まれていません。")
            if hasattr(response, "prompt_feedback") and hasattr(response.prompt_feedback, "block_reason"):
                print(f"Prompt was blocked due to: {response.prompt_feedback.block_reason}")
            generated_text = None

    except Exception as e:
        print(f"エラー: Gemini API 呼び出しに失敗しました: {e}")
        generated_text = None

    if generated_text is None:
        print(f"'{file_path}' のGemini処理に失敗しました。")
        return

    # --- 生成結果の後処理 ---
    if generated_text.strip().startswith("```markdown"):
        generated_text = generated_text.strip()[len("```markdown") :].strip()
        if generated_text.strip().endswith("```"):
            generated_text = generated_text.strip()[: -len("```")].strip()

    # --- 整形後のファイルを保存 ---
    print(f"Geminiによる整形結果を '{output_path}' に保存中...")
    try:
        # 出力ディレクトリが存在するか確認し、存在しない場合は作成
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"出力ディレクトリ '{output_dir}' を作成しました。")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(generated_text)
        print(f"整形結果を '{output_path}' に保存しました。")
    except Exception as e:
        print(f"エラー: 整形結果の保存に失敗しました: {e}")
        return

    print(f"'{output_path}' を開いて、'{marker}' が適切に挿入されているか確認してください。")


# --- ファイルパスの設定 ---
# 現在の作業ディレクトリを基準にした相対パスを使用
base_dir = os.getcwd()
gakusoku_file_path = os.path.join(base_dir, "AI-E-03", "RAG", "kic-gakusoku.md")
digipanp_file_path = os.path.join(base_dir, "AI-E-03", "RAG", "KIC_digiPanp.md")

# LLMで整形したファイルを保存するパス
digipanp_marked_path = os.path.join(base_dir, "AI-E-03", "RAG", "KIC_digiPanp_marked_gemini.md")
gakusoku_marked_path = os.path.join(base_dir, "AI-E-03", "RAG", "kic-gakusoku_marked_gemini.md")


# --- 処理実行 ---

# APIキーが設定されている場合のみ実行
if GOOGLE_API_KEY and api_configured:
    print("\n--- Gemini API を使用したファイル整形処理を実行 ---")

    # digiPanpファイルの処理
    process_file_with_gemini(digipanp_file_path, digipanp_marked_path, MODEL_NAME, CHUNK_SEPARATOR_MARKER)

    # 学則ファイルの処理 (必要であればコメントアウト解除)
    # process_file_with_gemini(gakusoku_file_path, gakusoku_marked_path, MODEL_NAME, CHUNK_SEPARATOR_MARKER)

    print("\n--- Geminiで整形したファイルを確認してください ---")
    print(f"- '{digipanp_marked_path}'")
    # print(f"- '{gakusoku_marked_path}'")
    print(f"これらのファイルの内容を確認し、'{CHUNK_SEPARATOR_MARKER}' が意図した場所に挿入されているか、")
    print("元の内容が失われていないかなどを手動でチェックしてください。")
    print("問題がなければ、次のステップ（Text Splitterによるチャンク化）に進めます。")
else:
    print("\nAPIキーが設定されていないか、API設定に失敗したため、Gemini API を使用したファイル処理はスキップされました。")
