import streamlit as st
import pandas as pd
import ollama
import io
import json
from datetime import datetime

# ========== НАСТРОЙКИ ==========
MODEL_NAME = "mistral"  # Бесплатная модель в Ollama

# ========== ФУНКЦИИ ==========
def load_excel(file):
    """Загрузка Excel файла со всех листов"""
    try:
        xls = pd.ExcelFile(file)
        sheets = {}
        for sheet in xls.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet)
            # Ограничиваем для демонстрации (можно убрать)
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
        context += f"Пример данных (первые 3 строки):\n{df.head(3).to_string()}\n"
        context += f"Статистика:\n{df.describe(include='all').to_string()}\n\n"
    return context

def ask_agent(question, context):
    """Запрос к локальной модели Ollama"""
    prompt = f"""
Ты — аналитик данных. У тебя есть доступ к данным из Excel файла.
ОТВЕЧАЙ ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.

{context}

ВОПРОС ПОЛЬЗОВАТЕЛЯ: {question}

ИНСТРУКЦИИ:
1. Проанализируй данные и дай точный ответ
2. Если нужны расчеты, покажи их
3. Если данных недостаточно, скажи об этом
4. Отвечай четко и по делу
5. Если вопрос не относится к данным, вежливо откажись отвечать

ТВОЙ ОТВЕТ:
"""
    
    try:
        response = ollama.chat(model=MODEL_NAME, messages=[
            {"role": "user", "content": prompt}
        ])
        return response['message']['content']
    except Exception as e:
        return f"❌ Ошибка связи с моделью: {e}\n\nУбедитесь, что Ollama запущена локально."

# ========== ИНТЕРФЕЙС ==========
st.set_page_config(page_title="Excel AI Агент", page_icon="📊", layout="wide")

st.title("📊 Агент для анализа Excel")
st.markdown("Загрузите файл и задавайте вопросы на русском языке")

# Боковая панель
with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Загрузка файла
    uploaded_file = st.file_uploader(
        "Выберите Excel файл",
        type=['xlsx', 'xls'],
        help="Максимальный размер: 50 МБ"
    )
    
    if uploaded_file:
        st.success(f"✅ Файл загружен: {uploaded_file.name}")
        
        # Загрузка данных
        with st.spinner("Обработка файла..."):
            sheets = load_excel(uploaded_file)
            
            if sheets:
                st.session_state['sheets'] = sheets
                st.session_state['context'] = get_data_context(sheets)
                
                # Информация о файле
                st.subheader("📋 Структура файла")
                for sheet_name, df in sheets.items():
                    st.write(f"**{sheet_name}**: {len(df)} строк, {len(df.columns)} колонок")
                
                # Предпросмотр данных
                st.subheader("👀 Предпросмотр")
                selected_sheet = st.selectbox("Выберите лист", list(sheets.keys()))
                st.dataframe(sheets[selected_sheet].head(10), use_container_width=True)
    
    st.divider()
    st.caption("Модель: Mistral 7B (бесплатно)")
    st.caption(f"Время: {datetime.now().strftime('%H:%M')}")

# Основная область - чат
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Отображение истории
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Поле ввода
if prompt := st.chat_input("Спросите о данных..."):
    if 'sheets' not in st.session_state:
        st.warning("⚠️ Сначала загрузите Excel файл в боковой панели")
    else:
        # Добавляем вопрос пользователя
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Получаем ответ от агента
        with st.chat_message("assistant"):
            with st.spinner("🤔 Анализирую данные..."):
                response = ask_agent(prompt, st.session_state['context'])
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

# Инструкция для первого запуска
if 'sheets' not in st.session_state:
    st.info("👈 Загрузите Excel файл в боковой панели, чтобы начать работу")
    
    # Примеры вопросов
    st.subheader("💡 Примеры вопросов:")
    examples = [
        "Сколько всего строк в данных?",
        "Какие уникальные значения в колонке [название]?",
        "Покажи статистику по числовым колонкам",
        "Найди максимальное/минимальное значение",
        "Есть ли пропущенные данные?"
    ]
    for ex in examples:
        st.code(ex, language=None)