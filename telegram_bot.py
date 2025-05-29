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
try:
    g.parse("SPARQL.ttl", format="n3")
except Exception as e:
    logger.error(f"Помилка завантаження онтології: {e}")
    raise

# Визначення просторів імен
EX = rdflib.Namespace("http://example.org/training#")
XSD = rdflib.Namespace("http://www.w3.org/2001/XMLSchema#")
RDF = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")

# Стани для ConversationHandler
NAME, AGE, HEIGHT, WEIGHT, ASSIGN_USER, ASSIGN_WORKOUT = range(6)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ласкаво просимо до бота онтології фітнесу! Доступні команди:\n"
        "/users - Переглянути список усіх користувачів\n"
        "/recommendations <користувач> - Отримати рекомендації тренувань для користувача\n"
        "/progress <користувач> - Переглянути прогрес користувача\n"
        "/create_user - Створити нового користувача з віком, зростом, вагою та ІМТ\n"
        "/assign_workout - Призначити тренування користувачу"
    )

# Перегляд усіх користувачів
async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = """
    PREFIX ex: <http://example.org/training#>
    SELECT ?user ?age ?height ?weight ?fitnessLevel ?bmi
    WHERE {
        ?user a ex:User ;
              ex:вік ?age ;
              ex:зріст ?height ;
              ex:вага ?weight ;
              ex:рівеньФітнесу ?fitnessLevel ;
              ex:індексМасиТіла ?bmi .
    }
    """
    results = g.query(query)
    response = "Користувачі в онтології:\n"
    for row in results:
        user_uri = row.user.split('#')[-1]
        fitness_level = row.fitnessLevel.split('#')[-1]
        response += f"Користувач: {user_uri}, Вік: {row.age}, Зріст: {row.height} м, Вага: {row.weight} кг, Рівень фітнесу: {fitness_level}, ІМТ: {row.bmi}\n"
    await update.message.reply_text(response or "Користувачів не знайдено.")

# Отримання рекомендацій для користувача
async def recommendations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Будь ласка, вкажіть ім'я користувача, наприклад, /recommendations User_John")
        return
    user_name = context.args[0]
    query = f"""
    PREFIX ex: <http://example.org/training#>
    SELECT ?workout ?exercise ?intensity ?duration ?calories
    WHERE {{
        ?user a ex:User ;
              ex:маєРекомендацію ?workout .
        ?workout ex:вправа ?exercise ;
                 ex:інтенсивність ?intensity ;
                 ex:тривалість ?duration ;
                 ex:спаленіКалорії ?calories .
        FILTER (STR(?user) = "http://example.org/training#{user_name}")
    }}
    """
    results = g.query(query)
    workouts = defaultdict(list)
    for row in results:
        workout_uri = row.workout.split('#')[-1]
        intensity = row.intensity.split('#')[-1]
        workouts[workout_uri].append(
            f"• Вправа: {row.exercise}\n  Інтенсивність: {intensity}, Тривалість: {row.duration} хв, Калорії: {row.calories}"
        )

    if workouts:
        response = f"Рекомендації для {user_name}:\n"
        for workout, details in workouts.items():
            response += f"\nТренування: {workout}\n" + "\n".join(details) + "\n"
    else:
        response = f"Рекомендацій для {user_name} не знайдено."
    await update.message.reply_text(response)

# Перегляд прогресу користувача
async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Будь ласка, вкажіть ім'я користувача, наприклад, /progress User_John")
        return
    user_name = context.args[0]
    query = f"""
    PREFIX ex: <http://example.org/training#>
    SELECT ?progress ?date ?calories ?workout ?exercise
    WHERE {{
        ?progress a ex:Progress ;
                  ex:датаПрогресу ?date ;
                  ex:досягнутіКалорії ?calories ;
                  ex:виконанеТренування ?workout ;
                  ex:належитьКористувачу ?user .
        ?workout ex:вправа ?exercise .
        FILTER (STR(?user) = "http://example.org/training#{user_name}")
    }}
    """
    results = g.query(query)
    response = f"Прогрес для {user_name}:\n"
    for row in results:
        progress_uri = row.progress.split('#')[-1]
        workout_uri = row.workout.split('#')[-1]
        response += f"Прогрес: {progress_uri}, Дата: {row.date}, Калорії: {row.calories}, Тренування: {workout_uri}, Вправа: {row.exercise}\n"
    await update.message.reply_text(response or f"Прогресу для {user_name} не знайдено.")

# Створення користувача: Початок
async def create_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введіть ім'я користувача (наприклад, Ivan_2025):"
    )
    return NAME

# Обробка імені
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    if not re.match(r'^[\w\-]+$', user_name):
        await update.message.reply_text("Ім'я містить некоректні символи. Спробуйте ще раз:")
        return NAME
    query = f"""
    PREFIX ex: <http://example.org/training#>
    ASK WHERE {{ ex:{user_name} a ex:User }}
    """
    if g.query(query).askAnswer:
        await update.message.reply_text("Користувач вже існує. Виберіть інше ім'я:")
        return NAME
    context.user_data["name"] = user_name
    await update.message.reply_text("Введіть вік користувача:")
    return AGE

# Вік
async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if age < 0 or age > 120:
            raise ValueError
        context.user_data["age"] = age
        await update.message.reply_text("Введіть зріст у метрах:")
        return HEIGHT
    except ValueError:
        await update.message.reply_text("Некоректний вік. Спробуйте ще раз:")
        return AGE

# Зріст
async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.strip())
        if height <= 0 or height > 3:
            raise ValueError
        context.user_data["height"] = height
        await update.message.reply_text("Введіть вагу в кг:")
        return WEIGHT
    except ValueError:
        await update.message.reply_text("Некоректний зріст. Спробуйте ще раз:")
        return HEIGHT

# Вага
async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.strip())
        if weight <= 0 or weight > 300:
            raise ValueError
        user_name = context.user_data["name"]
        age = context.user_data["age"]
        height = context.user_data["height"]
        bmi = round(weight / (height * height), 1)

        user_uri = EX[user_name]
        g.add((user_uri, RDF.type, EX.User))
        g.add((user_uri, EX.вік, rdflib.Literal(age, datatype=XSD.integer)))
        g.add((user_uri, EX.зріст, rdflib.Literal(height, datatype=XSD.float)))
        g.add((user_uri, EX.вага, rdflib.Literal(weight, datatype=XSD.float)))
        g.add((user_uri, EX.індексМасиТіла, rdflib.Literal(bmi, datatype=XSD.float)))
        g.add((user_uri, EX.рівеньФітнесу, EX.Beginner))
        g.add((user_uri, EX.досвід, EX.Beginner))

        g.serialize(destination="SPARQL.ttl", format="n3")
        await update.message.reply_text(f"Користувача {user_name} створено! ІМТ: {bmi}")
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Некоректна вага. Спробуйте ще раз:")
        return WEIGHT

# Скасування
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Операцію скасовано.")
    return ConversationHandler.END

# Призначення тренування
async def assign_workout_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введіть ім'я користувача:")
    return ASSIGN_USER

async def assign_workout_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    query = f"""
    PREFIX ex: <http://example.org/training#>
    ASK WHERE {{ ex:{user_name} a ex:User }}
    """
    if not g.query(query).askAnswer:
        await update.message.reply_text("Користувача не знайдено. Спробуйте ще раз.")
        return ASSIGN_USER

    context.user_data["assign_user"] = user_name
    query = """
    PREFIX ex: <http://example.org/training#>
    SELECT ?workout WHERE { ?workout a ex:Workout. }
    """
    results = g.query(query)
    workouts = [row.workout.split('#')[-1] for row in results]
    if not workouts:
        await update.message.reply_text("Тренувань не знайдено.")
        return ConversationHandler.END
    context.user_data["available_workouts"] = workouts
    workout_list = "\n".join(f"{i+1}. {w}" for i, w in enumerate(workouts))
    await update.message.reply_text(f"Виберіть номер тренування:\n{workout_list}")
    return ASSIGN_WORKOUT

async def assign_workout_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        index = int(update.message.text.strip()) - 1
        workouts = context.user_data["available_workouts"]
        if not (0 <= index < len(workouts)):
            raise ValueError
        user_name = context.user_data["assign_user"]
        workout_name = workouts[index]
        g.add((EX[user_name], EX.маєРекомендацію, EX[workout_name]))
        g.serialize(destination="SPARQL.ttl", format="n3")
        await update.message.reply_text(f"Тренування '{workout_name}' призначено {user_name} ✅")
        context.user_data.clear()
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text("Некоректний вибір. Введіть номер ще раз:")
        return ASSIGN_WORKOUT

# Обробка помилок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Оновлення {update} викликало помилку {context.error}")
    await update.message.reply_text("Сталася помилка. Спробуйте ще раз.")

# Головна функція
def main():
    bot_token = "7973391875:AAHAT7xxc3TWp2ABRI-J3b5_0DhX-FPMWJ4"
    application = Application.builder().token(bot_token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create_user", create_user)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_height)],
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_weight)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    assign_handler = ConversationHandler(
        entry_points=[CommandHandler("assign_workout", assign_workout_start)],
        states={
            ASSIGN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, assign_workout_user)],
            ASSIGN_WORKOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, assign_workout_choose)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(assign_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("users", users))
    application.add_handler(CommandHandler("recommendations", recommendations))
    application.add_handler(CommandHandler("progress", progress))
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
