print("ТЕСТ ЗАПУСКА")

import psycopg2

print("Проверяем подключение...")

try:
    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        database="my_project",
        user="postgres",
        password="123"
    )

    print("УСПЕШНО! PostgreSQL подключен!")

    connection.close()

except Exception as e:
    print("ОШИБКА:", e)