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
from uuid import uuid4

# Налаштування логування
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Ініціалізація RDF графа та завантаження онтології
g = rdflib.Graph()

# Визначення просторів імен
EX = rdflib.Namespace("http://example.org/training#")
XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

try:
    g.parse("SPARQL.ttl", format="n3")

    def ensure_default_workouts():
        predefined = [
            {
                "name": "Workout_Beginner_1",
                "exercise": "Присідання",
                "intensity": "Low",
                "duration": 15,
                "calories": 100,
            },
            {
                "name": "Workout_Cardio_2",
                "exercise": "Біг на місці",
                "intensity": "Medium",
                "duration": 20,
                "calories": 150,
            },
            {
                "name": "Workout_Strength_3",
                "exercise": "Віджимання",
                "intensity": "High",
                "duration": 10,
                "calories": 120,
            },
        ]

        for w in predefined:
            workout_uri = EX[w["name"]]
            if (workout_uri, RDF.type, EX.Workout) not in g:
                g.add((workout_uri, RDF.type, EX.Workout))
                g.add((workout_uri, EX.вправа, rdflib.Literal(w["exercise"])))
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

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Вітаємо у боті фітнес-онтології!\n"
        "/create_user — Створити нового користувача\n"
        "/recommendations <ім'я> — Показати тренування"
    )

# /create_user
async def create_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ім'я користувача:")
    return NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not re.match(r'^[\w\-]+$', name):
        await update.message.reply_text("Некоректне ім’я. Тільки букви, цифри, '_' або '-'.")
        return NAME
    if g.query(f"PREFIX ex: <http://example.org/training#> ASK {{ ex:{name} a ex:User }}").askAnswer:
        await update.message.reply_text("Користувач уже існує. Введіть інше ім’я.")
        return NAME
    context.user_data["name"] = name
    await update.message.reply_text("Вік:")
    return AGE

async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if not 0 <= age <= 120:
            raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("Зріст (м):")
        return HEIGHT
    except:
        await update.message.reply_text("Введіть число від 0 до 120.")
        return AGE

async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.strip())
        if not 0.5 <= height <= 2.5:
            raise ValueError
        context.user_data["height"] = height
        await update.message.reply_text("Вага (кг):")
        return WEIGHT
    except:
        await update.message.reply_text("Введіть зріст у метрах.")
        return HEIGHT

async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.strip())
        if not 10 <= weight <= 300:
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

        # Вибір тренування
        context.user_data["new_user"] = name
        query = "PREFIX ex: <http://example.org/training#> SELECT ?w WHERE { ?w a ex:Workout }"
        workouts = [row.w.split('#')[-1] for row in g.query(query)]
        if not workouts:
            await update.message.reply_text("❌ Тренування не знайдені.")
            return ConversationHandler.END

        context.user_data["available_workouts"] = workouts
        list_text = "\n".join(f"{i+1}. {w}" for i, w in enumerate(workouts))
        await update.message.reply_text(f"Оберіть тренування для {name}:\n{list_text}")
        return WORKOUT_SELECTION

    except:
        await update.message.reply_text("Некоректна вага.")
        return WEIGHT

async def receive_workout_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(update.message.text.strip()) - 1
        workouts = context.user_data["available_workouts"]
        if not (0 <= idx < len(workouts)):
            raise ValueError
        workout = workouts[idx]
        user = context.user_data["new_user"]
        g.add((EX[user], EX.маєРекомендацію, EX[workout]))
        g.serialize(destination="SPARQL.ttl", format="n3")
        await update.message.reply_text(f"✅ Тренування {workout} призначено {user}")
        context.user_data.clear()
        return ConversationHandler.END
    except:
        await update.message.reply_text("Невірний номер. Спробуйте ще раз:")
        return WORKOUT_SELECTION

# /recommendations
async def recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Вкажіть ім'я користувача: /recommendations Імя")
        return
    user_name = context.args[0]
    query = f"""
    PREFIX ex: <http://example.org/training#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?workout ?exercise ?intensity ?duration ?calories
    WHERE {{
        ?user a ex:User ;
              ex:маєРекомендацію ?workout .
        ?workout a ?type ;
                 ex:вправа ?exercise ;
                 ex:інтенсивність ?intensity ;
                 ex:тривалість ?duration ;
                 ex:спаленіКалорії ?calories .
        ?type rdfs:subClassOf* ex:Workout .
        FILTER(STR(?user) = "http://example.org/training#{user_name}")
    }}
    """
    results = g.query(query)
    workouts = defaultdict(list)
    for row in results:
        workout = row.workout.split('#')[-1]
        intensity = row.intensity.split('#')[-1]
        workouts[workout].append(
            f"• {row.exercise} — Інтенсивність: {intensity}, Тривалість: {row.duration} хв, Калорії: {row.calories}"
        )
    if not workouts:
        await update.message.reply_text(f"Рекомендацій для {user_name} не знайдено.")
        return
    reply = f"Рекомендації для {user_name}:"
    for w, details in workouts.items():
        reply += f"\n\n🏋️ Тренування: {w}\n" + "\n".join(details)
    await update.message.reply_text(reply)

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Операцію скасовано.")
    return ConversationHandler.END

# Обробка помилок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} викликав помилку {context.error}")
    await update.message.reply_text("Сталася помилка.")

# main
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
    app.add_error_handler(error_handler)

    app.run_polling()

if __name__ == '__main__':
    main()
