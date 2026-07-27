import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# ========== НАСТРОЙКИ ==========
# YandexGPT API (работает из РФ, есть бесплатный тариф)
YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MODEL_NAME = "yandexgpt-lite"  # Бесплатная модель

def load_excel(file):
    """Загрузка Excel файла"""
    try:
        xls = pd.ExcelFile(file)
        sheets = {}
        for sheet in xls.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet)
            if len(df) > 10000:
                df = df.head(10000)
            sheets[sheet] = df
        return sheets
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return None

def get_data_context(sheets):
    """Контекст данных"""
    context = "ДАННЫЕ В ФАЙЛЕ:\n\n"
    for sheet_name, df in sheets.items():
        context += f"=== Лист '{sheet_name}' ===\n"
        context += f"Размер: {len(df)} строк × {len(df.columns)} колонок\n"
        context += f"Колонки: {', '.join(df.columns.tolist())}\n"
        context += f"Первые 3 строки:\n{df.head(3).to_string()}\n\n"
    return context

def ask_agent_yandex(question, context, api_key, folder_id):
    """Запрос к YandexGPT"""
    prompt = f"""
Ты — аналитик данных. У тебя есть доступ к данным из Excel файла.
ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.

{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

Дай точный ответ на основе данных. Если нужны расчеты, покажи их.
Если данных недостаточно, скажи об этом.
"""
    
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "modelUri": f"gpt://{folder_id}/yandexgpt-lite",
        "completionOptions": {
            "stream": False,
            "temperature": 0.1,
            "maxTokens": 2000
        },
        "messages": [
            {"role": "user", "text": prompt}
        ]
    }
    
    try:
        response = requests.post(YANDEX_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result['result']['alternatives'][0]['message']['text']
    except Exception as e:
        return f"❌ Ошибка API: {e}"

# ========== ИНТЕРФЕЙС ==========
st.set_page_config(page_title="Excel AI Агент", page_icon="📊", layout="wide")

st.title("📊 Агент для анализа Excel")
st.markdown("*Загрузите файл и задавайте вопросы на русском языке*")

with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Выбор API
    api_choice = st.radio(
        "API сервис:",
        ["Groq (зарубежный)", "YandexGPT (российский)"],
        help="Выберите API для работы модели"
    )
    
    st.divider()
    
    if api_choice == "Groq (зарубежный)":
        api_key = st.text_input(
            "🔑 Groq API Key",
            type="password",
            help="Ключ с console.groq.com"
        )
        folder_id = None
    else:
        folder_id = st.text_input(
            "📁 Yandex Folder ID",
            help="ID каталога в Yandex Cloud"
        )
        api_key = st.text_input(
            "🔑 Yandex API Key",
            type="password",
            help="Ключ с console.cloud.yandex.ru"
        )
    
    if api_key:
        st.session_state['api_key'] = api_key
        st.session_state['folder_id'] = folder_id
    
    st.divider()
    
    uploaded_file = st.file_uploader(
        "📁 Выберите Excel файл",
        type=['xlsx', 'xls']
    )
    
    if uploaded_file:
        st.success(f"✅ {uploaded_file.name}")
        with st.spinner("Обработка..."):
            sheets = load_excel(uploaded_file)
            if sheets:
                st.session_state['sheets'] = sheets
                st.session_state['context'] = get_data_context(sheets)
                
                st.subheader("📋 Структура")
                for name, df in sheets.items():
                    st.write(f"**{name}**: {len(df)} стр. × {len(df.columns)} кол.")
                
                st.subheader("👀 Превью")
                sheet = st.selectbox("Лист:", list(sheets.keys()))
                st.dataframe(sheets[sheet].head(10), use_container_width=True)

if 'messages' not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("💬 Спросите о данных..."):
    if 'sheets' not in st.session_state:
        st.warning("⚠️ Загрузите файл")
    elif not api_key:
        st.warning("⚠️ Введите API-ключ")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤔 Анализирую..."):
                if api_choice == "Groq (зарубежный)":
                    # Здесь используем Groq код
                    response = "Используйте код для Groq из предыдущего ответа"
                else:
                    response = ask_agent_yandex(
                        prompt, 
                        st.session_state['context'],
                        api_key,
                        st.session_state.get('folder_id')
                    )
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

if 'sheets' not in st.session_state:
    st.info("👈 Загрузите Excel файл и настройте API")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("💡 Примеры вопросов:")
        for ex in ["Сколько строк в данных?",
                    "Найди максимум в колонке...",
                    "Есть ли пустые ячейки?"]:
            st.code(ex)
    
    with col2:
        st.subheader("🔑 Получить ключ:")
        st.markdown("""
        **Groq:** [console.groq.com](https://console.groq.com)
        **Yandex:** [console.cloud.yandex.ru](https://console.cloud.yandex.ru)
        """)
