
import psycopg2


class Database:
    def __init__(self):
        self.connection = None

    def connect(self):
        try:
            self.connection = psycopg2.connect(
                host="localhost",
                port=5432,
                database="my_project",
                user="postgres",
                password="123",
                client_encoding="UTF8"
            )

            print("Подключение к базе данных успешно!")
            return True

        except Exception as error:
            print("Ошибка подключения к базе данных.")
            print("Тип ошибки:", type(error).__name__)
            print("Подробности:", repr(error))
            return False

    def close(self):
        if self.connection:
            self.connection.close()
            print("Соединение закрыто.")
