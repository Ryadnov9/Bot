import logging
import re
from collections import defaultdict
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import rdflib
import matplotlib.pyplot as plt
import os
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# RDF граф
g = rdflib.Graph()
EX = rdflib.Namespace("http://example.org/training#")
XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = rdflib.RDFS

# Стани розмови
NAME, AGE, HEIGHT, WEIGHT, WORKOUT_SELECTION, ADD_WORKOUT_NAME, ADD_WORKOUT_SELECTION, RECOMMENDATION_NAME, STAT_NAME, MYWORKOUTS_NAME, AI_MODE = range(
    11)

# Завантаження онтології і додавання базових тренувань
try:
    g.parse("SPARQL.ttl", format="n3")


    def ensure_default_workouts():
        predefined = [
            {"uri": "Workout_Beginner_1", "назва": "Ранкова зарядка", "exercise": "Присідання", "intensity": "Low",
             "duration": None, "calories": 100, "sets": 3},
            {"uri": "Workout_Cardio_2", "назва": "Кардіо біг", "exercise": "Біг на місці", "intensity": "Medium",
             "duration": 20, "calories": 150, "sets": None},
            {"uri": "Workout_Strength_3", "назва": "Силові віджимання", "exercise": "Віджимання", "intensity": "Висока",
             "duration": None, "calories": 120, "sets": 5},
            {"uri": "Workout_Yoga_4", "назва": "Йога для початківців", "exercise": "Поза дерева", "intensity": "Low",
             "duration": 25, "calories": 80, "sets": None},
            {"uri": "Workout_Boxing_5", "назва": "Домашній бокс", "exercise": "Удари в повітрі", "intensity": "Висока",
             "duration": None, "calories": 200, "sets": 6},
            {"uri": "Workout_Pilates_6", "назва": "Пілатес на гнучкість", "exercise": "Розтяжка", "intensity": "Medium",
             "duration": None, "calories": 110, "sets": 3},
            {"uri": "Workout_Squats", "назва": "Присідання з вагою тіла", "exercise": "Присідання з вагою тіла",
             "intensity": "Moderate", "duration": None, "calories": 250.0, "sets": 6},
            {"uri": "Workout_Swimming", "назва": "Плавання", "exercise": "Плавання", "intensity": "Moderate",
             "duration": 45, "calories": 450.0, "sets": None},
            {"uri": "Workout_Yoga", "назва": "Йога-флоу", "exercise": "Йога-флоу", "intensity": "Low", "duration": 30,
             "calories": 200.0, "sets": None},
            {"uri": "Workout_Cardio", "назва": "Біг", "exercise": "Біг", "intensity": "Moderate", "duration": 45,
             "calories": 400.0, "sets": None},
            {"uri": "Workout_Strength", "назва": "Підняття ваги", "exercise": "Підняття ваги", "intensity": "High",
             "duration": None, "calories": 350.0, "sets": 5},
        ]

        for w in predefined:
            workout_uri = EX[w["uri"]]
            if (workout_uri, RDF.type, EX.Workout) not in g:
                g.add((workout_uri, RDF.type, EX.Workout))
                g.add((workout_uri, EX.назва, rdflib.Literal(w["назва"], lang="uk")))
                g.add((workout_uri, EX.вправа, rdflib.Literal(w["exercise"], lang="uk")))
                g.add((workout_uri, EX.інтенсивність, EX[w["intensity"]]))
                if w["sets"] is not None:
                    g.add((workout_uri, EX.кількістьПідходів, rdflib.Literal(w["sets"], datatype=XSD.integer)))
                if w["duration"] is not None:
                    g.add((workout_uri, EX.тривалість, rdflib.Literal(w["duration"], datatype=XSD.integer)))
                g.add((workout_uri, EX.спаленіКалорії, rdflib.Literal(w["calories"], datatype=XSD.float)))

        for uri, label in [("Low", "Низька"), ("Medium", "Середня"), ("High", "Висока"), ("Moderate", "Середня"),
                           ("Висока", "Висока")]:
            intensity_uri = EX[uri]
            if (intensity_uri, RDF.type, EX.Intensity) not in g:
                g.add((intensity_uri, RDF.type, EX.Intensity))
            g.set((intensity_uri, RDFS.label, rdflib.Literal(label, lang="uk")))

        g.serialize("SPARQL.ttl", format="n3")

except Exception as e:
    logger.error(f"🚨 Помилка завантаження онтології: {e}")
    raise


# Команди
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🏋️‍♂️ Вітаємо в боті фітнес-тренувань! 💪\n\n"
        "Скористайтеся командами:\n"
        "🏃 /create_user — Створити нового користувача\n"
        "👥 /users — Переглянути всіх користувачів\n"
        "🏋️ /add_workout — Додати тренування\n"
        "📋 /recommendations — Показати рекомендації\n"
        "💪 /myworkouts — Показати всі тренування користувача\n"
        "📊 /stats — Показати статистику тренувань\n"
        "❌ /cancel — Скасувати операцію\n"
        "ℹ️ /help — Допомога / список команд"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Список доступних команд:\n\n"
        "🏋️‍♂️ /start — Привітальне повідомлення\n"
        "🏃 /create_user — Створити нового користувача\n"
        "👥 /users — Переглянути всіх користувачів\n"
        "🏋️ /add_workout — Додати тренування\n"
        "📋 /recommendations — Показати рекомендації тренувань\n"
        "💪 /myworkouts — Показати всі тренування користувача\n"
        "📊 /stats — Показати статистику тренувань\n"
        "❌ /cancel — Скасувати поточну операцію\n"
        "ℹ️ /help — Показати це повідомлення"
    )


async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = """
    PREFIX ex: <http://example.org/training#>
    SELECT ?user ?age ?height ?weight ?fitnessLevel ?bmi
    WHERE {
        ?user a ex:User ;
              ex:вік ?age ;
              ex:зріст ?height ;
              ex:вага ?weight ;
              ex:рівеньФітнесу ?fitnessLevel ;
              ex:індексМасиТіла ?bmi .
    }"""
    results = g.query(q)
    text = "📋 Користувачі:\n"
    for r in results:
        name = r.user.split('#')[-1]
        text += f"👤 {name} — Вік: {r.age}, Зріст: {r.height}, Вага: {r.weight}, ІМТ: {r.bmi}, Рівень: {r.fitnessLevel.split('#')[-1]}\n"
    await update.message.reply_text(text or "👥 Немає користувачів.")


async def create_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏃 Введіть ім’я користувача:")
    return NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", name):
        await update.message.reply_text("❌ Некоректне ім’я. Спробуйте ще раз:")
        return NAME
    if g.query(f"PREFIX ex: <http://example.org/training#> ASK {{ ex:{name} a ex:User }}").askAnswer:
        await update.message.reply_text("⚠️ Користувач вже існує.")
        return NAME
    context.user_data["name"] = name
    await update.message.reply_text("📅 Вік:")
    return AGE


async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if not (0 < age < 120):
            raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("📏 Зріст (м):")
        return HEIGHT
    except:
        await update.message.reply_text("❌ Некоректно. Спробуйте ще раз:")
        return AGE


async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text)
        if not (0.5 < height < 3):
            raise ValueError
        context.user_data["height"] = height
        await update.message.reply_text("⚖️ Вага (кг):")
        return WEIGHT
    except:
        await update.message.reply_text("❌ Некоректно. Спробуйте ще раз:")
        return HEIGHT


async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text)
        if not (10 < weight < 300):
            raise ValueError
        name = context.user_data["name"]
        age = context.user_data["age"]
        height = context.user_data["height"]
        bmi = round(weight / (height * height), 1)
        uri = EX[name]
        g.add((uri, RDF.type, EX.User))
        g.add((uri, EX.вік, rdflib.Literal(age, datatype=XSD.integer)))
        g.add((uri, EX.зріст, rdflib.Literal(height, datatype=XSD.float)))
        g.add((uri, EX.вага, rdflib.Literal(weight, datatype=XSD.float)))
        g.add((uri, EX.індексМасиТіла, rdflib.Literal(bmi, datatype=XSD.float)))
        g.add((uri, EX.рівеньФітнесу, EX.Beginner))
        g.add((uri, EX.досвід, EX.Beginner))
        g.serialize("SPARQL.ttl", format="n3")
        await update.message.reply_text(f"✅ Користувача {name} створено! ІМТ: {bmi}")
        context.user_data["new_user"] = name
        return await list_workouts(update, context, select_state=WORKOUT_SELECTION)
    except:
        await update.message.reply_text("❌ Некоректно. Спробуйте ще раз:")
        return WEIGHT


async def list_workouts(update, context, select_state):
    q = "PREFIX ex: <http://example.org/training#> SELECT ?w WHERE { ?w a ?t . ?t rdfs:subClassOf* ex:Workout . }"
    res = g.query(q, initNs={"ex": EX, "rdfs": RDFS})
    workouts = []
    for row in res:
        wid = row.w
        label_query = f"""
        PREFIX ex: <http://example.org/training#>
        SELECT ?назва WHERE {{
            <{wid}> ex:назва ?назва .
        }}
        """
        label_result = g.query(label_query)
        title = next(iter(label_result))[0] if label_result else wid.split('#')[-1]
        wid = wid.split('#')[-1]
        workouts.append((wid, str(title)))
    context.user_data["available_workouts"] = [w[0] for w in workouts]
    context.user_data["workout_names"] = workouts
    txt = "\n".join([f"{i + 1}. {w[1]}" for i, w in enumerate(workouts)])
    await update.message.reply_text(f"🏋️ Оберіть тренування (введіть номери через кому, наприклад, 1,3,5):\n{txt}")
    return select_state


async def receive_workout_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_input = update.message.text.strip()
        selected_indices = [int(i.strip()) - 1 for i in user_input.split(',') if i.strip().isdigit()]
        workouts = context.user_data["available_workouts"]
        if not selected_indices or any(i < 0 or i >= len(workouts) for i in selected_indices):
            raise ValueError

        workout_names = context.user_data["workout_names"]
        user_name = context.user_data["new_user"]
        selected_workouts = [workouts[i] for i in selected_indices]

        for workout_name in selected_workouts:
            g.add((EX[user_name], EX.маєРекомендацію, EX[workout_name]))
            label_query = f"""
            PREFIX ex: <http://example.org/training#>
            SELECT ?назва WHERE {{
                ex:{workout_name} ex:назва ?назва .
            }}
            """
            label_result = g.query(label_query)
            workout_label = next(iter(label_result))[0] if label_result else workout_name
            await update.message.reply_text(f"✅ Додано тренування {workout_label} для {user_name}.")

        g.serialize("SPARQL.ttl", format="n3")
        await update.message.reply_text(
            f"💡 Користувач {user_name} створений! Тепер задавайте мені будь-які питання (або введіть /cancel, щоб вийти).")
        return AI_MODE

    except:
        await update.message.reply_text(
            "❌ Некоректний ввід. Введіть номери через кому (наприклад, 1,3,5) у межах доступного списку:")
        return WORKOUT_SELECTION


async def ai_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_question = update.message.text.strip()
    user_name = context.user_data.get("new_user")

    if user_question.lower() in ["/cancel", "/end"]:
        await update.message.reply_text("❌ Ви вийшли з режиму AI. Для продовження використовуйте команди.")
        context.user_data.clear()
        return ConversationHandler.END

    # Логіка відповіді AI (проста реалізація на основі доступних даних)
    reply = f"🤖 Привіт, {user_name}! Ти запитав: {user_question}\n"

    # Перевірка запитів, пов’язаних із тренуваннями
    if "тренування" in user_question.lower() or "workout" in user_question.lower():
        query = f"""
        PREFIX ex: <http://example.org/training#>
        SELECT ?назва ?вправа ?калорії
        WHERE {{
            ex:{user_name} ex:маєРекомендацію ?workout .
            OPTIONAL {{ ?workout ex:назва ?назва . }}
            OPTIONAL {{ ?workout ex:вправа ?вправа . }}
            OPTIONAL {{ ?workout ex:спаленіКалорії ?калорії . }}
        }}
        """
        results = g.query(query, initNs={"ex": EX})
        if results:
            reply += "Твої тренування:\n"
            for row in results:
                title = row.назва if row.назва else "Невідоме тренування"
                exercise = row.вправа if row.вправа else "—"
                calories = row.калорії if row.калорії else "?"
                reply += f"• {title} ({exercise}, {calories} ккал)\n"
        else:
            reply += "У тебе ще немає тренувань. Додай їх через /add_workout.\n"

    # Загальна відповідь, якщо запит не пов’язаний із тренуваннями
    else:
        reply += "Я можу допомогти з питаннями про твої тренування! Спробуй запитати щось на кшталт 'Які у мене тренування?' або додай нові тренування через /add_workout. 😊"

    await update.message.reply_text(reply)
    return AI_MODE


async def add_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏋️ Введіть ім’я користувача:")
    return ADD_WORKOUT_NAME


async def receive_add_workout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", name):
        await update.message.reply_text("❌ Некоректне ім’я. Спробуйте ще раз:")
        return ADD_WORKOUT_NAME
    if (EX[name], RDF.type, EX.User) not in g:
        await update.message.reply_text("⚠️ Користувача не знайдено. Спробуйте ще раз:")
        return ADD_WORKOUT_NAME
    context.user_data["new_user"] = name
    return await list_workouts(update, context, select_state=ADD_WORKOUT_SELECTION)


async def receive_additional_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_input = update.message.text.strip()
        selected_indices = [int(i.strip()) - 1 for i in user_input.split(',') if i.strip().isdigit()]
        workouts = context.user_data["available_workouts"]
        if not selected_indices or any(i < 0 or i >= len(workouts) for i in selected_indices):
            raise ValueError

        workout_names = context.user_data["workout_names"]
        user = context.user_data["new_user"]
        selected_workouts = [workouts[i] for i in selected_indices]

        for workout_name in selected_workouts:
            g.add((EX[user], EX.маєРекомендацію, EX[workout_name]))
            label_query = f"""
            PREFIX ex: <http://example.org/training#>
            SELECT ?назва WHERE {{
                ex:{workout_name} ex:назва ?назва .
            }}
            """
            label_result = g.query(label_query)
            workout_label = next(iter(label_result))[0] if label_result else workout_name
            await update.message.reply_text(f"✅ Додано тренування {workout_label} для {user}.")

        g.serialize("SPARQL.ttl", format="n3")
        context.user_data.clear()
        return ConversationHandler.END

    except:
        await update.message.reply_text("❌ Спробуйте ще раз: введіть номери через кому (наприклад, 1,3,5):")
        return ADD_WORKOUT_SELECTION


async def recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Введіть ім’я користувача:")
    return RECOMMENDATION_NAME


async def receive_recommendation_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", user_name):
        await update.message.reply_text("❌ Некоректне ім’я. Спробуйте ще раз:")
        return RECOMMENDATION_NAME
    if (EX[user_name], RDF.type, EX.User) not in g:
        await update.message.reply_text("⚠️ Користувача не знайдено. Спробуйте ще раз:")
        return RECOMMENDATION_NAME

    query = f"""
    PREFIX ex: <http://example.org/training#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?workout ?назва ?вправа ?інтенсивність ?кількістьПідходів ?тривалість ?калорії
    WHERE {{
        ex:{user_name} ex:маєРекомендацію ?workout .
        OPTIONAL {{ ?workout ex:назва ?назва . }}
        OPTIONAL {{ ?workout ex:вправа ?вправа . }}
        OPTIONAL {{ ?workout ex:інтенсивність ?інтенсивність . }}
        OPTIONAL {{ ?workout ex:кількістьПідходів ?кількістьПідходів . }}
        OPTIONAL {{ ?workout ex:тривалість ?тривалість . }}
        OPTIONAL {{ ?workout ex:спаленіКалорії ?калорії . }}
    }}
    """

    results = g.query(query, initNs={"ex": EX, "rdfs": RDFS})

    if not results:
        await update.message.reply_text(f"📋 Рекомендацій для {user_name} не знайдено.")
        return ConversationHandler.END

    reply = f"🏋️ Рекомендації для {user_name}:\n"
    for row in results:
        title = str(row.назва) if row.назва else row.workout.split('#')[-1]
        exercise = str(row.вправа) if row.вправа else "—"
        calories = str(row.калорії) if row.калорії else "?"

        if row.тривалість:
            duration_or_sets = f"{row.тривалість} хв"
        elif row.кількістьПідходів:
            duration_or_sets = f"{row.кількістьПідходів} підходів"
        else:
            duration_or_sets = "невідомо"

        intensity_label = None
        if row.інтенсивність:
            labels = list(g.objects(row.інтенсивність, RDFS.label))
            intensity_label = next((str(l) for l in labels if getattr(l, 'language', None) == 'uk'), None)
        if not intensity_label and row.інтенсивність:
            intensity_label = row.інтенсивність.split('#')[-1]
        if not intensity_label:
            intensity_label = "Невідомо"

        reply += f"\n🏋️ {title} — {exercise}, Інтенсивність: {intensity_label}, {duration_or_sets}, {calories} ккал"

    await update.message.reply_text(reply)
    return ConversationHandler.END


async def myworkouts_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💪 Введіть ім’я користувача:")
    return MYWORKOUTS_NAME


async def myworkouts_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", user_name):
        await update.message.reply_text("❌ Некоректне ім’я. Спробуйте ще раз:")
        return MYWORKOUTS_NAME
    if (EX[user_name], RDF.type, EX.User) not in g:
        await update.message.reply_text("⚠️ Користувача не знайдено. Спробуйте ще раз:")
        return MYWORKOUTS_NAME

    query = f"""
    PREFIX ex: <http://example.org/training#>
    SELECT ?workout ?назва
    WHERE {{
        ex:{user_name} ex:маєРекомендацію ?workout .
        OPTIONAL {{ ?workout ex:назва ?назва }}
    }}
    """

    results = g.query(query, initNs={"ex": EX})

    if not results:
        await update.message.reply_text(f"💪 Для користувача {user_name} не знайдено тренувань.")
        return ConversationHandler.END

    reply = f"🏋️‍♂️ Тренування користувача {user_name}:\n"
    for row in results:
        label = row.назва if row.назва else row.workout.split('#')[-1]
        reply += f"• {label}\n"

    await update.message.reply_text(reply)
    return ConversationHandler.END


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Введіть ім’я користувача для перегляду статистики:")
    return STAT_NAME


async def receive_stat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", user_name):
        await update.message.reply_text("❌ Некоректне ім’я. Спробуйте ще раз:")
        return STAT_NAME
    if (EX[user_name], RDF.type, EX.User) not in g:
        await update.message.reply_text("⚠️ Користувача не знайдено. Спробуйте ще раз:")
        return STAT_NAME

    # Запит для отримання спалених калорій за тренуваннями
    query_workouts = f"""
    PREFIX ex: <http://example.org/training#>
    SELECT ?назва ?калорії
    WHERE {{
        ex:{user_name} ex:маєРекомендацію ?workout .
        OPTIONAL {{ ?workout ex:назва ?назва . }}
        OPTIONAL {{ ?workout ex:спаленіКалорії ?калорії . }}
    }}
    """
    results_workouts = g.query(query_workouts, initNs={"ex": EX})

    if not results_workouts:
        await update.message.reply_text(f"📊 Статистики для {user_name} не знайдено.")
        return ConversationHandler.END

    # Запит для отримання ваги користувача
    query_weight = f"""
    PREFIX ex: <http://example.org/training#>
    SELECT ?вага
    WHERE {{
        ex:{user_name} ex:вага ?вага .
    }}
    """
    result_weight = g.query(query_weight, initNs={"ex": EX})
    weight = float(next(iter(result_weight)).вага) if result_weight else 0.0

    # Підготовка даних для графіка
    labels = []
    calories_data = []
    for row in results_workouts:
        label = str(row.назва) if row.назва else "Невідоме тренування"
        calories = float(row.калорії) if row.калорії else 0.0
        labels.append(label)
        calories_data.append(calories)

    # Генерація графіка з двома осями Y
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Перша вісь Y: калорії
    ax1.bar(labels, calories_data,
            color=['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#4BC0C0', '#FF6384', '#36A2EB',
                   '#FFCE56', '#9966FF'])
    ax1.set_xlabel('Тренування')
    ax1.set_ylabel('Калорії', color='#FF6384')
    ax1.tick_params(axis='y', labelcolor='#FF6384')
    ax1.set_xticks(range(len(labels)))
    ax1.set_xticklabels(labels, rotation=45, ha='right')

    # Друга вісь Y: вага
    ax2 = ax1.twinx()
    ax2.axhline(y=weight, color='#36A2EB', linestyle='--', label=f'Вага ({weight} кг)')
    ax2.set_ylabel('Вага (кг)', color='#36A2EB')
    ax2.tick_params(axis='y', labelcolor='#36A2EB')
    ax2.legend(loc='upper right')

    # Додавання логотипу (зображення)
    logo_path = "logo.png"  # Шлях до вашої картинки (потрібно завантажити її)
    logo_img = mpimg.imread(logo_path)
    imagebox = OffsetImage(logo_img, zoom=0.1)
    ab = AnnotationBbox(imagebox, (1, 1), xycoords='axes fraction', frameon=False, box_alignment=(1, 1))
    ax1.add_artist(ab)

    # Заголовок і налаштування
    plt.title(f'📊 Порівняння спалених калорій та ваги для {user_name}')
    plt.tight_layout()

    # Збереження графіка у тимчасовий файл
    chart_path = 'chart.png'
    plt.savefig(chart_path)
    plt.close()

    # Надсилання графіка
    with open(chart_path, 'rb') as chart_file:
        await update.message.reply_photo(photo=chart_file,
                                         caption=f"📊 Порівняння спалених калорій та ваги для {user_name}")

    # Видалення тимчасового файлу
    os.remove(chart_path)

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Скасовано.")
    return ConversationHandler.END


def main():
    app = Application.builder().token("7973391875:AAHAT7xxc3TWp2ABRI-J3b5_0DhX-FPMWJ4").build()

    # Встановлюємо список команд для бота
    commands = [
        ("start", "Привітальне повідомлення"),
        ("help", "Допомога / список команд"),
        ("create_user", "Створити нового користувача"),
        ("users", "Переглянути всіх користувачів"),
        ("add_workout", "Додати тренування"),
        ("recommendations", "Показати рекомендації тренувань"),
        ("myworkouts", "Показати всі тренування користувача"),
        ("stats", "Показати статистику тренувань"),
        ("cancel", "Скасувати операцію"),
    ]
    app.bot.set_my_commands(commands)

    # Обробник для створення користувача
    conv = ConversationHandler(
        entry_points=[CommandHandler("create_user", create_user)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_weight)],
            WORKOUT_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_workout_choice)],
            AI_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_mode)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Обробник для додавання тренувань
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add_workout", add_workout)],
        states={
            ADD_WORKOUT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_add_workout_name)],
            ADD_WORKOUT_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_additional_workout)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Обробник для рекомендацій
    recommendation_conv = ConversationHandler(
        entry_points=[CommandHandler("recommendations", recommendations)],
        states={
            RECOMMENDATION_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_recommendation_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Обробник для статистики
    stats_conv = ConversationHandler(
        entry_points=[CommandHandler("stats", show_stats)],
        states={
            STAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stat_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Обробник для myworkouts
    myworkouts_conv = ConversationHandler(
        entry_points=[CommandHandler("myworkouts", myworkouts_start)],
        states={
            MYWORKOUTS_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, myworkouts_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Додавання обробників до програми
    app.add_handler(conv)
    app.add_handler(add_conv)
    app.add_handler(recommendation_conv)
    app.add_handler(stats_conv)
    app.add_handler(myworkouts_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("users", users))
    app.run_polling()


if __name__ == "__main__":
    main()