import logging
import re
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
NAME, AGE, HEIGHT, WEIGHT = range(4)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ласкаво просимо до бота онтології фітнесу! Доступні команди:\n"
        "/users - Переглянути список усіх користувачів\n"
        "/recommendations <користувач> - Отримати рекомендації тренувань для користувача\n"
        "/progress <користувач> - Переглянути прогрес користувача\n"
        "/create_user - Створити нового користувача з віком, зростом, вагою та ІМТ\n"
        "Приклад: /recommendations User_John або /recommendations Користувач_Іван"
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
        await update.message.reply_text("Будь ласка, вкажіть ім'я користувача, наприклад, /recommendations User_John або /recommendations Користувач_Іван")
        return
    user_name = context.args[0]
    query = """
    PREFIX ex: <http://example.org/training#>
    SELECT ?workout ?exercise ?intensity ?duration ?calories
    WHERE {
        ?user a ex:User ;
              ex:маєРекомендацію ?workout .
        ?workout ex:вправа ?exercise ;
                 ex:інтенсивність ?intensity ;
                 ex:тривалість ?duration ;
                 ex:спаленіКалорії ?calories .
        FILTER (STR(?user) = "http://example.org/training#%s")
    }
    """
    query = query % user_name
    results = g.query(query)
    response = f"Рекомендації для {user_name}:\n"
    for row in results:
        workout_uri = row.workout.split('#')[-1]
        intensity = row.intensity.split('#')[-1]
        response += f"Тренування: {workout_uri}, Вправа: {row.exercise}, Інтенсивність: {intensity}, Тривалість: {row.duration} хв, Калорії: {row.calories}\n"
    await update.message.reply_text(response or f"Рекомендацій для {user_name} не знайдено.")

# Перегляд прогресу користувача
async def progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Будь ласка, вкажіть ім'я користувача, наприклад, /progress User_John або /progress Користувач_Іван")
        return
    user_name = context.args[0]
    query = """
    PREFIX ex: <http://example.org/training#>
    SELECT ?progress ?date ?calories ?workout ?exercise
    WHERE {
        ?progress a ex:Progress ;
                  ex:датаПрогресу ?date ;
                  ex:досягнутіКалорії ?calories ;
                  ex:виконанеТренування ?workout ;
                  ex:належитьКористувачу ?user .
        ?workout ex:вправа ?exercise .
        FILTER (STR(?user) = "http://example.org/training#%s")
    }
    """
    query = query % user_name
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
        "Будь ласка, введіть ім'я користувача (наприклад, Користувач_Іван або Ivan_2025). "
        "Ім'я може бути українською мовою, але не повинно містити пробілів чи спеціальних символів, крім '_' або '-'."
    )
    return NAME

# Обробка імені
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()
    # Перевірка валідності імені для URI (лише літери, цифри, '_', '-')
    if not re.match(r'^[\w\-]+$', user_name):
        await update.message.reply_text(
            "Ім'я містить некоректні символи. Використовуйте лише літери, цифри, '_' або '-'. "
            "Наприклад: Користувач_Іван, Ivan_2025. Спробуйте ще раз:"
        )
        return NAME
    # Перевірка, чи існує користувач
    query = """
    PREFIX ex: <http://example.org/training#>
    ASK WHERE { ex:%s a ex:User }
    """
    if g.query(query % user_name).askAnswer:
        await update.message.reply_text("Користувач з таким ім'ям уже існує. Виберіть інше ім'я:")
        return NAME
    context.user_data["name"] = user_name
    await update.message.reply_text("Введіть вік користувача (наприклад, 25):")
    return AGE

# Обробка віку
async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        age = int(update.message.text.strip())
        if age < 0 or age > 120:
            await update.message.reply_text("Будь ласка, введіть коректний вік (0-120):")
            return AGE
        context.user_data["age"] = age
        await update.message.reply_text("Введіть зріст користувача в метрах (наприклад, 1.75):")
        return HEIGHT
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть коректне ціле число для віку:")
        return AGE

# Обробка зросту
async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        height = float(update.message.text.strip())
        if height <= 0 or height > 3:
            await update.message.reply_text("Будь ласка, введіть коректний зріст у метрах (0-3):")
            return HEIGHT
        context.user_data["height"] = height
        await update.message.reply_text("Введіть вагу користувача в кілограмах (наприклад, 70.0):")
        return WEIGHT
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть коректне число для зросту:")
        return HEIGHT

# Обробка ваги та створення користувача
async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        weight = float(update.message.text.strip())
        if weight <= 0 or weight > 300:
            await update.message.reply_text("Будь ласка, введіть коректну вагу в кілограмах (0-300):")
            return WEIGHT
        user_name = context.user_data["name"]
        age = context.user_data["age"]
        height = context.user_data["height"]

        # Обчислення ІМТ
        bmi = round(weight / (height * height), 1)

        # Створення користувача в онтології
        user_uri = EX[user_name]
        g.add((user_uri, RDF.type, EX.User))
        g.add((user_uri, EX.вік, rdflib.Literal(age, datatype=XSD.integer)))
        g.add((user_uri, EX.зріст, rdflib.Literal(height, datatype=XSD.float)))
        g.add((user_uri, EX.вага, rdflib.Literal(weight, datatype=XSD.float)))
        g.add((user_uri, EX.індексМасиТіла, rdflib.Literal(bmi, datatype=XSD.float)))
        g.add((user_uri, EX.рівеньФітнесу, EX.Beginner))  # За замовчуванням
        g.add((user_uri, EX.досвід, EX.Beginner))  # За замовчуванням

        # Збереження оновленої онтології
        try:
            g.serialize(destination="SPARQL.ttl", format="n3")
            await update.message.reply_text(
                f"Користувача {user_name} успішно створено!\n"
                f"Вік: {age}, Зріст: {height} м, Вага: {weight} кг, ІМТ: {bmi}"
            )
        except Exception as e:
            logger.error(f"Помилка збереження онтології: {e}")
            await update.message.reply_text("Помилка при збереженні користувача в онтологію. Спробуйте ще раз.")
            return ConversationHandler.END

        # Очищення даних користувача
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Будь ласка, введіть коректне число для ваги:")
        return WEIGHT

# Скасування створення користувача
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Створення користувача скасовано.")
    return ConversationHandler.END

# Обробка помилок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Оновлення {update} викликало помилку {context.error}")
    await update.message.reply_text("Сталася помилка. Спробуйте ще раз.")

def main():
    # Замініть 'YOUR_BOT_TOKEN' на ваш токен бота від BotFather
    bot_token = "7973391875:AAHAT7xxc3TWp2ABRI-J3b5_0DhX-FPMWJ4"
    application = Application.builder().token(bot_token).build()

    # Обробник діалогу для створення користувача
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

    # Додавання обробниківвв
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("users", users))
    application.add_handler(CommandHandler("recommendations", recommendations))
    application.add_handler(CommandHandler("progress", progress))
    application.add_error_handler(error_handler)

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()