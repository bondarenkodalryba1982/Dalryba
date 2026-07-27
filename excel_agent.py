import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime
import numpy as np

# ========== НАСТРОЙКИ ==========
YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
MAX_PREVIEW_ROWS = 5

def clean_dataframe(df):
    """Очистка DataFrame от проблемных данных для отображения"""
    # Создаем копию
    df_clean = df.copy()
    
    # Удаляем безымянные колонки
    unnamed_cols = [col for col in df_clean.columns if 'Unnamed' in str(col)]
    df_clean = df_clean.drop(columns=unnamed_cols, errors='ignore')
    
    # Очищаем каждую колонку
    for col in df_clean.columns:
        # Преобразуем смешанные типы в строки
        if df_clean[col].dtype == 'object':
            try:
                # Пробуем преобразовать в числа
                df_clean[col] = pd.to_numeric(df_clean[col], errors='ignore')
            except:
                # Если не получается - в строки
                df_clean[col] = df_clean[col].astype(str)
        
        # Заменяем проблемные значения
        df_clean[col] = df_clean[col].replace([np.inf, -np.inf], np.nan)
        df_clean[col] = df_clean[col].fillna('')
    
    return df_clean

def load_multiple_excel(files):
    """Загрузка нескольких Excel файлов с очисткой"""
    all_data = {}
    
    for file in files:
        try:
            xls = pd.ExcelFile(file)
            file_data = {}
            
            for sheet in xls.sheet_names:
                df = pd.read_excel(file, sheet_name=sheet)
                
                # Ограничиваем размер
                if len(df) > 5000:
                    df = df.head(5000)
                
                # Очищаем данные
                df = clean_dataframe(df)
                file_data[sheet] = df
            
            all_data[file.name] = {
                'sheets': file_data,
                'total_rows': sum(len(df) for df in file_data.values()),
                'total_columns': sum(len(df.columns) for df in file_data.values())
            }
            
        except Exception as e:
            st.error(f"Ошибка в файле {file.name}: {e}")
            continue
    
    return all_data

def create_analysis_context(all_data):
    """Создание контекста для анализа"""
    context = "📊 АНАЛИЗ НЕСКОЛЬКИХ EXCEL ФАЙЛОВ\n\n"
    
    context += f"Всего файлов: {len(all_data)}\n"
    context += f"Общее количество листов: {sum(len(data['sheets']) for data in all_data.values())}\n\n"
    
    for file_name, data in all_data.items():
        context += f"{'='*50}\n"
        context += f"📁 ФАЙЛ: {file_name}\n"
        context += f"{'='*50}\n"
        context += f"Листов: {len(data['sheets'])}\n"
        context += f"Всего строк: {data['total_rows']}\n\n"
        
        for sheet_name, df in data['sheets'].items():
            context += f"  📋 Лист '{sheet_name}':\n"
            context += f"    Размер: {len(df)} строк × {len(df.columns)} колонок\n"
            context += f"    Колонки: {', '.join(df.columns.tolist())}\n"
            
            # Пример данных (только первые строки и без проблемных данных)
            try:
                preview = df.head(MAX_PREVIEW_ROWS).to_string(index=False)
                context += f"    Первые {MAX_PREVIEW_ROWS} строк:\n"
                for line in preview.split('\n'):
                    context += f"    {line}\n"
            except:
                context += f"    (не удалось показать пример)\n"
            
            # Статистика только для числовых колонок
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                try:
                    stats = df[numeric_cols].describe()
                    context += f"    Статистика:\n"
                    for line in stats.to_string().split('\n'):
                        context += f"    {line}\n"
                except:
                    context += f"    (статистика недоступна)\n"
            
            context += "\n"
    
    return context

def ask_yandex_gpt(question, context, api_key, folder_id):
    """Запрос к YandexGPT"""
    
    system_prompt = (
        "Ты — senior аналитик данных. У тебя есть доступ к нескольким Excel файлам. "
        "Твоя задача — анализировать данные, находить связи, сравнивать показатели. "
        "Отвечай ТОЛЬКО на русском языке. "
        "Будь внимателен к деталям, используй конкретные цифры из данных. "
        "Если можно сравнить файлы между собой — обязательно сделай это. "
        "Структурируй ответ: выводы, цифры, рекомендации."
    )
    
    user_prompt = f"""
{context}

❓ ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

Дай точный ответ на основе данных. Сравнивай файлы, если вопрос подразумевает сравнение.
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
            "maxTokens": 3000
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
    except Exception as e:
        return f"❌ Ошибка API: {str(e)[:200]}"

def safe_display_dataframe(df, max_rows=10):
    """Безопасное отображение DataFrame в Streamlit"""
    try:
        # Очищаем данные
        df_display = clean_dataframe(df)
        
        # Показываем только первые строки
        df_display = df_display.head(max_rows)
        
        # Если всё ещё есть проблемы - преобразуем всё в строки
        try:
            st.dataframe(df_display, use_container_width=True)
        except:
            # Последний рубеж - всё в строки
            df_string = df_display.astype(str)
            st.dataframe(df_string, use_container_width=True)
            
    except Exception as e:
        st.error(f"Не удалось отобразить данные: {str(e)[:100]}")
        st.write("Первые строки в текстовом виде:")
        st.text(df.head(3).to_string())

# ========== ИНТЕРФЕЙС ==========
st.set_page_config(
    page_title="Мульти-Excel Агент",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Агент для анализа нескольких Excel файлов")
st.markdown("*YandexGPT • Загрузите до 5 файлов и сравнивайте данные*")

# Боковая панель
with st.sidebar:
    st.header("⚙️ Настройки API")
    
    folder_id = st.text_input(
        "📁 Yandex Folder ID",
        type="password",
        placeholder="b1g...",
        help="ID каталога из Yandex Cloud"
    )
    
    api_key = st.text_input(
        "🔑 Yandex API Key",
        type="password",
        placeholder="AQ...",
        help="API-ключ сервисного аккаунта"
    )
    
    if folder_id and api_key:
        st.session_state['folder_id'] = folder_id
        st.session_state['api_key'] = api_key
        st.success("✅ API настроен")
    else:
        st.warning("⚠️ Введите ключи API")
    
    st.divider()
    
    st.header("📁 Файлы")
    uploaded_files = st.file_uploader(
        "Выберите Excel файлы (до 5)",
        type=['xlsx', 'xls'],
        accept_multiple_files=True,
        help="Можно загрузить несколько файлов для сравнения"
    )
    
    if uploaded_files:
        if len(uploaded_files) > 5:
            st.warning("⚠️ Максимум 5 файлов. Будут использованы первые 5.")
            uploaded_files = uploaded_files[:5]
        
        with st.spinner("🔄 Обработка файлов..."):
            all_data = load_multiple_excel(uploaded_files)
            
            if all_data:
                st.session_state['all_data'] = all_data
                st.session_state['context'] = create_analysis_context(all_data)
                
                st.success(f"✅ Загружено файлов: {len(all_data)}")
                
                # Статистика
                st.subheader("📊 Общая статистика")
                total_rows = sum(d['total_rows'] for d in all_data.values())
                total_sheets = sum(len(d['sheets']) for d in all_data.values())
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Файлов", len(all_data))
                col2.metric("Листов", total_sheets)
                col3.metric("Строк", f"{total_rows:,}")
                
                # Предпросмотр
                st.subheader("👀 Предпросмотр")
                selected_file = st.selectbox("Файл:", list(all_data.keys()))
                
                if selected_file:
                    selected_sheet = st.selectbox(
                        "Лист:",
                        list(all_data[selected_file]['sheets'].keys())
                    )
                    # Используем безопасное отображение
                    safe_display_dataframe(
                        all_data[selected_file]['sheets'][selected_sheet]
                    )
    
    st.divider()
    st.caption(f"🤖 YandexGPT Lite (бесплатно)")
    st.caption(f"🕐 {datetime.now().strftime('%H:%M')}")

# Основная область
if 'messages' not in st.session_state:
    st.session_state.messages = []

# История чата
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Поле ввода
if prompt := st.chat_input("💬 Задайте вопрос о данных..."):
    if 'all_data' not in st.session_state:
        st.warning("⚠️ Сначала загрузите Excel файлы")
    elif not st.session_state.get('api_key') or not st.session_state.get('folder_id'):
        st.warning("⚠️ Введите API-ключи в боковой панели")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤔 Анализирую все файлы..."):
                response = ask_yandex_gpt(
                    prompt,
                    st.session_state['context'],
                    st.session_state['api_key'],
                    st.session_state['folder_id']
                )
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

# Стартовый экран
if 'all_data' not in st.session_state:
    st.info("👈 Загрузите несколько Excel файлов для сравнительного анализа")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💡 Примеры вопросов:")
        examples = [
            "Сравни общую выручку по всем файлам",
            "Найди общие позиции между файлами",
            "Где максимальные продажи?",
            "Какие данные дублируются?",
            "Сравни средние значения по месяцам"
        ]
        for ex in examples:
            st.code(ex, language=None)
    
    with col2:
        st.subheader("🔍 Что умеет агент:")
        st.markdown("""
        ✅ Сравнивать несколько файлов
        ✅ Находить общие данные
        ✅ Выявлять расхождения
        ✅ Анализировать тренды
        """)
