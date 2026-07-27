import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime

# ========== НАСТРОЙКИ ==========
YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

def load_excel(file):
    """Загрузка Excel файла со всех листов"""
    try:
        xls = pd.ExcelFile(file)
        sheets = {}
        for sheet in xls.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet)
            # Ограничиваем размер для скорости
            if len(df) > 10000:
                df = df.head(10000)
            sheets[sheet] = df
        return sheets
    except Exception as e:
        st.error(f"Ошибка загрузки: {e}")
        return None

def get_data_context(sheets):
    """Создание контекста данных для модели"""
    context = "ДАННЫЕ В ФАЙЛЕ:\n\n"
    for sheet_name, df in sheets.items():
        context += f"=== Лист '{sheet_name}' ===\n"
        context += f"Размер: {len(df)} строк × {len(df.columns)} колонок\n"
        context += f"Колонки: {', '.join(df.columns.tolist())}\n"
        context += f"Первые 3 строки:\n{df.head(3).to_string()}\n"
        
        # Добавляем базовую статистику
        context += f"Типы данных:\n{df.dtypes.to_string()}\n\n"
    return context

def ask_yandex_gpt(question, context, api_key, folder_id):
    """Запрос к YandexGPT"""
    
    system_prompt = (
        "Ты — аналитик данных. У тебя есть доступ к данным из Excel файла. "
        "Отвечай только на русском языке. "
        "Анализируй данные и давай точные ответы с конкретными цифрами. "
        "Если нужны расчеты, показывай их пошагово. "
        "Если данных недостаточно, объясняй почему. "
        "Отвечай четко и структурированно."
    )
    
    user_prompt = f"""
{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

Дай точный ответ на основе предоставленных данных.
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
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_prompt}
        ]
    }
    
    try:
        response = requests.post(YANDEX_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result['result']['alternatives'][0]['message']['text']
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return "❌ Ошибка авторизации. Проверьте API-ключ и Folder ID."
        elif response.status_code == 403:
            return "❌ Доступ запрещен. Проверьте права сервисного аккаунта (нужна роль ai.languageModels.user)."
        else:
            return f"❌ Ошибка API: {e}"
    except Exception as e:
        return f"❌ Ошибка соединения: {e}"

# ========== ИНТЕРФЕЙС ==========
st.set_page_config(
    page_title="Excel AI Агент",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Агент для анализа Excel")
st.markdown("*YandexGPT • Загрузите файл и задавайте вопросы*")

# Боковая панель с настройками
with st.sidebar:
    st.header("⚙️ Настройки API")
    
    # Сохранение ключей в сессии
    if 'api_key' not in st.session_state:
        st.session_state['api_key'] = ''
    if 'folder_id' not in st.session_state:
        st.session_state['folder_id'] = ''
    
    folder_id = st.text_input(
        "📁 Yandex Folder ID",
        value=st.session_state['folder_id'],
        type="password",
        help="ID каталога из Yandex Cloud (например b1g...)",
        placeholder="b1g..."
    )
    
    api_key = st.text_input(
        "🔑 Yandex API Key",
        value=st.session_state['api_key'],
        type="password",
        help="API-ключ сервисного аккаунта",
        placeholder="AQ..."
    )
    
    if folder_id:
        st.session_state['folder_id'] = folder_id
    if api_key:
        st.session_state['api_key'] = api_key
    
    # Индикатор статуса
    if api_key and folder_id:
        st.success("✅ API настроен")
    else:
        st.warning("⚠️ Введите ключи API")
    
    st.divider()
    
    # Загрузка файла
    st.header("📁 Файл")
    uploaded_file = st.file_uploader(
        "Выберите Excel",
        type=['xlsx', 'xls'],
        help="Максимум 50 МБ"
    )
    
    if uploaded_file:
        with st.spinner("Обработка..."):
            sheets = load_excel(uploaded_file)
            if sheets:
                st.session_state['sheets'] = sheets
                st.session_state['context'] = get_data_context(sheets)
                
                st.success(f"✅ {uploaded_file.name}")
                
                # Структура файла
                st.subheader("📋 Структура")
                for name, df in sheets.items():
                    st.write(f"**{name}**: {len(df)} стр × {len(df.columns)} кол")
                
                # Предпросмотр
                st.subheader("👀 Данные")
                selected = st.selectbox("Лист:", list(sheets.keys()))
                st.dataframe(sheets[selected].head(10), use_container_width=True)
    
    st.divider()
    st.caption("🤖 Модель: YandexGPT Lite")
    st.caption("🆓 Бесплатный тариф")
    st.caption(f"🕐 {datetime.now().strftime('%H:%M')}")

# Основная область - чат
if 'messages' not in st.session_state:
    st.session_state.messages = []

# История сообщений
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Поле ввода
if prompt := st.chat_input("💬 Задайте вопрос о данных..."):
    # Проверки
    if 'sheets' not in st.session_state:
        st.warning("⚠️ Сначала загрузите Excel файл")
    elif not st.session_state['api_key'] or not st.session_state['folder_id']:
        st.warning("⚠️ Введите API-ключ и Folder ID в боковой панели")
    else:
        # Вопрос пользователя
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Ответ агента
        with st.chat_message("assistant"):
            with st.spinner("🤔 Анализирую данные..."):
                response = ask_yandex_gpt(
                    prompt,
                    st.session_state['context'],
                    st.session_state['api_key'],
                    st.session_state['folder_id']
                )
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

# Первый запуск
if 'sheets' not in st.session_state:
    st.info("👈 Настройте API и загрузите Excel файл в боковой панели")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💡 Примеры вопросов:")
        examples = [
            "Сколько всего строк в данных?",
            "Какие уникальные значения в колонке [название]?",
            "Найди максимальное значение",
            "Есть ли пустые ячейки?",
            "Посчитай среднее по колонке [название]"
        ]
        for ex in examples:
            st.code(ex, language=None)
    
    with col2:
        st.subheader("🔑 Как получить ключи:")
        st.markdown("""
        **1. Yandex Cloud:**
        - [console.cloud.yandex.ru](https://console.cloud.yandex.ru)
        - Создать платежный аккаунт
        - Создать каталог → скопировать ID
        
        **2. Сервисный аккаунт:**
        - Роль: `ai.languageModels.user`
        - Создать API-ключ
        
        **3. Вставить ключи в боковую панель**
        """)
        
        st.info("💡 YandexGPT Lite — бесплатно до 50 000 токенов в день")
