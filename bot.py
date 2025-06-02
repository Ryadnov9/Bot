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
NAME, AGE, HEIGHT, WEIGHT, WORKOUT_SELECTION, ADD_WORKOUT_SELECTION, RECOMMENDATION_NAME, ADD_WORKOUT_NAME = range(8)

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

        # Додаткові налаштування інтенсивності
        for uri, label in [("Low", "Низька"), ("Medium", "Середня"), ("High", "Висока"), ("Moderate", "Середня"),
                           ("Висока", "Висока")]:
            intensity_uri = EX[uri]
            if (intensity_uri, RDF.type, EX.Intensity) not in g:
                g.add((intensity_uri, RDF.type, EX.Intensity))
            g.set((intensity_uri, RDFS.label, rdflib.Literal(label, lang="uk")))

        g.serialize("SPARQL.ttl", format="n3")

except Exception as e:
    logger.error(f"Помилка завантаження онтології: {e}")
    raise


# Команди
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Вітаємо в боті фітнес-тренувань!\n\n"
        "Скористайтеся командами:\n"
        "/create_user — Створити нового користувача\n"
        "/users — Переглянути всіх користувачів\n"
        "/add_workout — Додати тренування\n"
        "/recommendations — Показати рекомендації\n"
        "/myworkouts <Ім’я> — Показати всі тренування\n"
        "/stats — Показати статистику тренувань\n"
        "/cancel — Скасувати операцію\n"
        "/help — Допомога / список команд"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 Список доступних команд:\n\n"
        "/start — Привітальне повідомлення\n"
        "/create_user — Створити нового користувача\n"
        "/users — Переглянути всіх користувачів\n"
        "/add_workout — Додати тренування\n"
        "/recommendations — Показати рекомендації тренувань\n"
        "/myworkouts <Ім’я> — Показати всі тренування користувача\n"
        "/stats — Показати статистику тренувань\n"
        "/cancel — Скасувати поточну операцію\n"
        "/help — Показати це повідомлення"
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
    await update.message.reply_text(text or "Немає користувачів.")


async def create_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ім’я користувача:")
    return NAME


async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", name):
        await update.message.reply_text("Некоректне ім’я. Спробуйте ще раз:")
        return NAME
    if g.query(f"PREFIX ex: <http://example.org/training#> ASK {{ ex:{name} a ex:User }}").askAnswer:
        await update.message.reply_text("Користувач вже існує.")
        return NAME
    context.user_data["name"] = name
    await update.message.reply_text("Вік:")
    return AGE


async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text)
        if not (0 < age < 120):
            raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("Зріст (м):")
        return HEIGHT
    except:
        await update.message.reply_text("Некоректно. Спробуйте ще раз:")
        return AGE


async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text)
        if not (0.5 < height < 3):
            raise ValueError
        context.user_data["height"] = height
        await update.message.reply_text("Вага (кг):")
        return WEIGHT
    except:
        await update.message.reply_text("Некоректно. Спробуйте ще раз:")
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
        await update.message.reply_text(f"Користувача {name} створено! ІМТ: {bmi}")
        context.user_data["new_user"] = name
        return await list_workouts(update, context, select_state=WORKOUT_SELECTION)
    except:
        await update.message.reply_text("Некоректно. Спробуйте ще раз:")
        return WEIGHT


async def list_workouts(update, context, select_state):
    q = "PREFIX ex: <http://example.org/training#> SELECT ?w WHERE { ?w a ?t . ?t rdfs:subClassOf* ex:Workout . }"
    res = g.query(q, initNs={"ex": EX, "rdfs": RDFS})
    workouts = []
    for row in res:
        wid = row.w

        # Отримуємо українську назву тренування
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
    await update.message.reply_text(f"Оберіть тренування:\n{txt}")
    return select_state


async def receive_workout_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        index = int(update.message.text.strip()) - 1
        workouts = context.user_data["available_workouts"]
        if not (0 <= index < len(workouts)):
            raise ValueError

        workout_name = workouts[index]
        user_name = context.user_data["new_user"]

        # Додаємо зв’язок користувач -> тренування
        g.add((EX[user_name], EX.маєРекомендацію, EX[workout_name]))
        g.serialize(destination="SPARQL.ttl", format="n3")

        # Отримуємо назву тренування (ex:назва), якщо вона є
        label_query = f"""
        PREFIX ex: <http://example.org/training#>
        SELECT ?назва WHERE {{
            ex:{workout_name} ex:назва ?назва .
        }}
        """
        label_result = g.query(label_query)
        workout_label = next(iter(label_result))[0] if label_result else workout_name

        await update.message.reply_text(f"✅ Додано тренування {workout_label} для {user_name}.")
        context.user_data.clear()
        return ConversationHandler.END

    except:
        await update.message.reply_text("Некоректний номер. Спробуйте ще раз:")
        return WORKOUT_SELECTION


async def add_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ім’я користувача:")
    return ADD_WORKOUT_NAME


async def receive_add_workout_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", name):
        await update.message.reply_text("Некоректне ім’я. Спробуйте ще раз:")
        return ADD_WORKOUT_NAME
    if (EX[name], RDF.type, EX.User) not in g:
        await update.message.reply_text("Користувача не знайдено. Спробуйте ще раз:")
        return ADD_WORKOUT_NAME
    context.user_data["new_user"] = name
    return await list_workouts(update, context, select_state=ADD_WORKOUT_SELECTION)


async def receive_additional_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        i = int(update.message.text) - 1
        workout = context.user_data["available_workouts"][i]
        user = context.user_data["new_user"]
        g.add((EX[user], EX.маєРекомендацію, EX[workout]))
        g.serialize("SPARQL.ttl", format="n3")

        # Отримуємо назву тренування українською мовою
        label_query = f"""
        PREFIX ex: <http://example.org/training#>
        SELECT ?назва WHERE {{
            ex:{workout} ex:назва ?назва .
        }}
        """
        label_result = g.query(label_query)
        workout_label = next(iter(label_result))[0] if label_result else workout

        await update.message.reply_text(f"✅ Додано тренування {workout_label} для {user}.")
        context.user_data.clear()
        return ConversationHandler.END
    except:
        await update.message.reply_text("Спробуйте ще раз:")
        return ADD_WORKOUT_SELECTION


async def recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ім’я користувача:")
    return RECOMMENDATION_NAME


async def receive_recommendation_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", user_name):
        await update.message.reply_text("Некоректне ім’я. Спробуйте ще раз:")
        return RECOMMENDATION_NAME
    if (EX[user_name], RDF.type, EX.User) not in g:
        await update.message.reply_text("Користувача не знайдено. Спробуйте ще раз:")
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
        await update.message.reply_text(f"Рекомендацій для {user_name} не знайдено.")
        return ConversationHandler.END

    reply = f"🏋️ Рекомендації для {user_name}:\n"
    for row in results:
        title = str(row.назва) if row.назва else row.workout.split('#')[-1]
        exercise = str(row.вправа) if row.вправа else "—"
        calories = str(row.калорії) if row.калорії else "?"

        # Визначаємо, що відображати: тривалість чи кількість підходів
        if row.тривалість:
            duration_or_sets = f"{row.тривалість} хв"
        elif row.кількістьПідходів:
            duration_or_sets = f"{row.кількістьПідходів} підходів"
        else:
            duration_or_sets = "невідомо"

        # Отримуємо український label інтенсивності
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


async def myworkouts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Вкажіть ім’я користувача: /myworkouts Ім’я")
        return
    user_name = context.args[0]

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
        await update.message.reply_text(f"❌ Для користувача {user_name} не знайдено тренувань.")
        return

    reply = f"🏋️‍♂️ Тренування користувача {user_name}:\n"
    for row in results:
        label = row.назва if row.назва else row.workout.split('#')[-1]
        reply += f"• {label}\n"

    await update.message.reply_text(reply)


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ім’я користувача для перегляду статистики:")
    return "STAT_NAME"


async def receive_stat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    if not re.match(r"^[\w\-]+$", user_name):
        await update.message.reply_text("Некоректне ім’я. Спробуйте ще раз:")
        return "STAT_NAME"
    if (EX[user_name], RDF.type, EX.User) not in g:
        await update.message.reply_text("Користувача не знайдено. Спробуйте ще раз:")
        return "STAT_NAME"

    # Запит для отримання спалених калорій за тренуваннями
    query = f"""
    PREFIX ex: <http://example.org/training#>
    SELECT ?назва ?калорії
    WHERE {{
        ex:{user_name} ex:маєРекомендацію ?workout .
        ?workout ex:назва ?назва .
        ?workout ex:спаленіКалорії ?калорії .
    }}
    """
    results = g.query(query, initNs={"ex": EX})

    if not results:
        await update.message.reply_text(f"Статистики для {user_name} не знайдено.")
        return ConversationHandler.END

    # Підготовка даних для графіка
    labels = []
    data = []
    for row in results:
        labels.append(str(row.назва))
        data.append(float(row.калорії))

    # Генерація JSON для бар-чарту
    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Спалені калорії",
                "data": data,
                "backgroundColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#4BC0C0",
                                    "#FF6384", "#36A2EB", "#FFCE56", "#9966FF"],
                "borderColor": ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#4BC0C0", "#FF6384",
                                "#36A2EB", "#FFCE56", "#9966FF"],
                "borderWidth": 1
            }]
        },
        "options": {
            "scales": {
                "y": {
                    "beginAtZero": True,
                    "title": {"display": True, "text": "Калорії"}
                },
                "x": {
                    "title": {"display": True, "text": "Тренування"}
                }
            },
            "plugins": {
                "legend": {"position": "top"}
            }
        }
    }

    # Відправка графіка
    await update.message.reply_text(f"📊 Статистика спалених калорій для {user_name}:")
    chart_block = f"```chartjs\n{chart_config}\n```"
    await update.message.reply_text(chart_block)

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
            "STAT_NAME": [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stat_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Додавання обробників до програми
    app.add_handler(conv)
    app.add_handler(add_conv)
    app.add_handler(recommendation_conv)
    app.add_handler(stats_conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("myworkouts", myworkouts))
    app.run_polling()


if __name__ == "__main__":
    main()