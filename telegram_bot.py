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

# Ініціалізація RDF графа та завантаження онтології
g = rdflib.Graph()

# Визначення просторів імен
EX = rdflib.Namespace("http://example.org/training#")
XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
RDFS = rdflib.RDFS

try:
    g.parse("SPARQL.ttl", format="n3")

    def ensure_default_workouts():
        predefined = [
            {
                "uri": "Workout_Beginner_1",
                "назва": "Ранкова зарядка",
                "exercise": "Присідання",
                "intensity": "Low",
                "duration": 15,
                "calories": 100,
            },
            {
                "uri": "Workout_Cardio_2",
                "назва": "Кардіо біг",
                "exercise": "Біг на місці",
                "intensity": "Medium",
                "duration": 20,
                "calories": 150,
            },
            {
                "uri": "Workout_Strength_3",
                "назва": "Силові віджимання",
                "exercise": "Віджимання",
                "intensity": "High",
                "duration": 10,
                "calories": 120,
            },
            {
                "uri": "Workout_Yoga_4",
                "назва": "Йога для початківців",
                "exercise": "Поза дерева",
                "intensity": "Low",
                "duration": 25,
                "calories": 80,
            },
            {
                "uri": "Workout_Boxing_5",
                "назва": "Домашній бокс",
                "exercise": "Удари в повітрі",
                "intensity": "High",
                "duration": 30,
                "calories": 200,
            },
            {
                "uri": "Workout_Pilates_6",
                "назва": "Пілатес на гнучкість",
                "exercise": "Розтяжка",
                "intensity": "Medium",
                "duration": 20,
                "calories": 110,
            },
        ]

        for w in predefined:
            workout_uri = EX[w["uri"]]
            if (workout_uri, RDF.type, EX.Workout) not in g:
                g.add((workout_uri, RDF.type, EX.Workout))
                g.add((workout_uri, EX.назва, rdflib.Literal(w["назва"], lang="uk")))
                g.add((workout_uri, EX.вправа, rdflib.Literal(w["exercise"], lang="uk")))
                g.add((workout_uri, EX.інтенсивність, EX[w["intensity"]]))
                g.add((workout_uri, EX.тривалість, rdflib.Literal(w["duration"], datatype=XSD.integer)))
                g.add((workout_uri, EX.спаленіКалорії, rdflib.Literal(w["calories"], datatype=XSD.integer)))

    ensure_default_workouts()
    g.serialize(destination="SPARQL.ttl", format="n3")
except Exception as e:
    logger.exception(f"Помилка завантаження онтології: {e}")
    raise

# Стани
NAME, AGE, HEIGHT, WEIGHT, WORKOUT_SELECTION = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Вітаємо! Використайте команду /create_user щоб додати користувача.\n"
        "Команда /recommendations <Ім’я> — покаже рекомендації."
    )

async def create_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ім’я користувача:")
    return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not re.match(r'^[\w\-]+$', name):
        await update.message.reply_text("Некоректне ім’я. Спробуйте ще раз.")
        return NAME
    if g.query(f"PREFIX ex: <http://example.org/training#> ASK {{ ex:{name} a ex:User }}").askAnswer:
        await update.message.reply_text("Користувач з таким ім’ям вже існує.")
        return NAME
    context.user_data["name"] = name
    await update.message.reply_text("Вік:")
    return AGE

async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if not (0 <= age <= 120):
            raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("Зріст (м):")
        return HEIGHT
    except:
        await update.message.reply_text("Введіть коректний вік (0–120).")
        return AGE

async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.strip())
        if not (0.5 <= height <= 2.5):
            raise ValueError
        context.user_data["height"] = height
        await update.message.reply_text("Вага (кг):")
        return WEIGHT
    except:
        await update.message.reply_text("Введіть коректний зріст у метрах.")
        return HEIGHT

async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.strip())
        if not (10 <= weight <= 300):
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
        g.serialize(destination="SPARQL.ttl", format="n3")

        await update.message.reply_text(f"Користувача {name} створено! ІМТ: {bmi}")

        context.user_data["new_user"] = name
        query = "PREFIX ex: <http://example.org/training#> SELECT ?workout WHERE { ?workout a ?type . ?type rdfs:subClassOf* ex:Workout . }"
        results = g.query(query, initNs={"rdfs": RDFS, "ex": EX})

        workouts = []
        for row in results:
            workout_uri = row.workout
            name_query = f"""
            PREFIX ex: <http://example.org/training#>
            SELECT ?title WHERE {{
                <{workout_uri}> ex:назва ?title .
            }}
            """
            title_result = g.query(name_query)
            title = next(iter(title_result))[0] if title_result else workout_uri.split('#')[-1]
            workouts.append((workout_uri.split('#')[-1], str(title)))

        if not workouts:
            await update.message.reply_text("❗ Тренувань не знайдено.")
            return ConversationHandler.END

        workout_list = "\n".join(f"{i+1}. {title}" for i, (_, title) in enumerate(workouts))
        context.user_data["available_workouts"] = [uri for uri, _ in workouts]
        await update.message.reply_text(f"Оберіть тренування для {name}:\n{workout_list}")
        return WORKOUT_SELECTION
    except:
        await update.message.reply_text("Некоректна вага.")
        return WEIGHT

async def receive_workout_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        index = int(update.message.text.strip()) - 1
        workouts = context.user_data["available_workouts"]
        if not (0 <= index < len(workouts)):
            raise ValueError
        workout_name = workouts[index]
        user_name = context.user_data["new_user"]
        g.add((EX[user_name], EX.маєРекомендацію, EX[workout_name]))
        g.serialize(destination="SPARQL.ttl", format="n3")
        await update.message.reply_text(f"✅ Тренування призначено користувачу {user_name}.")
        context.user_data.clear()
        return ConversationHandler.END
    except:
        await update.message.reply_text("Некоректний номер. Спробуйте ще раз:")
        return WORKOUT_SELECTION

async def recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Вкажіть ім’я користувача: /recommendations Ім’я")
        return
    user_name = context.args[0]
    query = f"""
    PREFIX ex: <http://example.org/training#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?workout ?exercise ?intensity ?duration ?calories ?title
    WHERE {{
        ?user a ex:User ;
              ex:маєРекомендацію ?workout .
        ?workout a ?type ;
                 ex:вправа ?exercise ;
                 ex:інтенсивність ?intensity ;
                 ex:тривалість ?duration ;
                 ex:спаленіКалорії ?calories .
        OPTIONAL {{ ?workout ex:назва ?title . }}
        ?type rdfs:subClassOf* ex:Workout .
        FILTER(STR(?user) = "http://example.org/training#{user_name}")
    }}
    """
    results = g.query(query, initNs={"rdfs": RDFS, "ex": EX})
    workouts = defaultdict(list)
    for row in results:
        title = str(row.title) if row.title else row.workout.split('#')[-1]
        intensity = row.intensity.split('#')[-1]
        workouts[title].append(
            f"• {row.exercise} — Інтенсивність: {intensity}, Тривалість: {row.duration} хв, Калорії: {row.calories}"
        )

    if not workouts:
        await update.message.reply_text(f"Рекомендацій для {user_name} не знайдено.")
        return
    reply = f"Рекомендації для {user_name}:"
    for w, details in workouts.items():
        reply += f"\n\n🏋️ {w}\n" + "\n".join(details)
    await update.message.reply_text(reply)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Операцію скасовано.")
    return ConversationHandler.END

def main():
    bot_token = "7973391875:AAHAT7xxc3TWp2ABRI-J3b5_0DhX-FPMWJ4"
    app = Application.builder().token(bot_token).build()

    conv_handler = ConversationHandler(
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

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("recommendations", recommendations))
    app.run_polling()

if __name__ == "__main__":
    main()
