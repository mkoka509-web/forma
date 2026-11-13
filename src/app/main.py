import sys
import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QComboBox, QPushButton,
    QSpinBox, QScrollArea, QFrame, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox
)
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtCore import Qt

from src.app.database import Database

# Цвета из руководства по стилю
COLOR_MAIN_BG = "#FFFFFF"      # основной фон
COLOR_ADD_BG = "#D2F6E7"       # дополнительный фон
COLOR_ACTION = "#70B2AF"       # основное действие
COLOR_LOW_STOCK = "#FF8080"    # модель с суммарным остатком не более 3

FONT_FAMILY = "Calibri"

DISCOUNT_PERCENT = 25


def resolve_image(image_path):
    """Возвращает существующий путь к изображению или None."""
    if not image_path:
        return None

    path = Path(str(image_path))
    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        path = Path.cwd() / "resources" / "Images" / Path(
            str(image_path)
        ).name

    return path if path.exists() else None


def get_previous_month_bounds(today=None):
    """Границы предыдущего календарного месяца.

    Возвращает (первый день прошлого месяца, первый день текущего).
    """
    if today is None:
        today = datetime.date.today()

    first_day_current = today.replace(day=1)
    last_day_prev = first_day_current - datetime.timedelta(days=1)
    first_day_prev = last_day_prev.replace(day=1)

    return first_day_prev, first_day_current


def discounted_price(price, discount_percent):
    """Цена со скидкой. Базовая цена не меняется."""
    return round(float(price) * (1 - discount_percent / 100), 2)


class ClickableRow(QFrame):
    """Строка товара, реагирующая на клик мышью."""

    def __init__(self, product, on_click):
        super().__init__()
        self.product = product
        self.on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click(self.product)
        super().mousePressEvent(event)


class LoginDialog(QDialog):
    """Диалог входа для гостя."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход")
        self.user = None

        layout = QFormLayout(self)

        self.login_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        layout.addRow("Логин:", self.login_input)
        layout.addRow("Пароль:", self.password_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.try_login)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def try_login(self):
        db = Database()

        if not db.connect():
            QMessageBox.critical(self, "Ошибка",
                                 "Не удалось подключиться к базе данных.")
            return

        try:
            cursor = db.connection.cursor()

            # В таблице users нет колонки password —
            # вход проверяется по логину
            cursor.execute("""
                SELECT u.user_id,
                       u.last_name || ' ' || u.first_name ||
                       COALESCE(' ' || u.middle_name, '') AS fio,
                       r.role_name
                FROM users u
                JOIN roles r ON r.role_id = u.role_id
                WHERE u.login = %s
            """, (self.login_input.text(),))

            row = cursor.fetchone()
            cursor.close()

            if row:
                self.user = {"id": row[0], "fio": row[1], "role": row[2]}
                self.accept()
            else:
                QMessageBox.warning(
                    self, "Ошибка",
                    "Пользователь с таким логином не найден. "
                    "Проверьте введённые значения и попробуйте снова."
                )

        except Exception as error:
            QMessageBox.critical(self, "Ошибка", str(error))

        finally:
            db.close()


class ProductViewWindow(QWidget):
    """Форма просмотра модели."""

    def __init__(self, product, variants, on_add_to_order):
        super().__init__()

        (
            product_id, article, name, material,
            description, price, category,
            manufacturer, total_stock, image_path,
            discount, final_price
        ) = product

        self.product = product
        self.variants = variants
        self.on_add_to_order = on_add_to_order

        self.setWindowTitle(f"ФормаДесерт — {name}")
        self.resize(560, 640)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLOR_MAIN_BG};
                color: #333333;
                font-family: {FONT_FAMILY};
            }}
            QPushButton {{
                background-color: {COLOR_ACTION};
                color: white;
                border: none;
                border-radius: 7px;
                padding: 10px 18px;
            }}
            QPushButton:hover {{
                background-color: #5d9d9a;
            }}
            QComboBox, QSpinBox {{
                padding: 8px;
                border: 1px solid #dddddd;
                border-radius: 7px;
                background: white;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(12)

        image_label = QLabel()
        image_label.setFixedSize(300, 220)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        path = resolve_image(image_path)
        if not path:
            path = resolve_image("resources/Images/picture.png")

        if path:
            pixmap = QPixmap(str(path))
            image_label.setPixmap(
                pixmap.scaled(
                    300, 220,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        else:
            image_label.setText("Нет изображения")

        layout.addWidget(image_label,
                         alignment=Qt.AlignmentFlag.AlignCenter)

        header = QLabel(f"{manufacturer} | {name}")
        header.setWordWrap(True)
        header.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(header)

        info = QLabel(
            f"Категория: {category or 'Не указана'}\n"
            f"Состав: {material or 'Не указан'}\n"
            f"Количество: {total_stock} шт."
        )
        info.setStyleSheet("font-size: 15px; color: #555555;")
        layout.addWidget(info)

        if discount > 0:
            price_text = (
                f"Скидка {discount}%: {final_price} ₽  "
                f"<s style='color:#999999'>{price} ₽</s>"
            )
        else:
            price_text = f"Цена: {price} ₽"

        price_label = QLabel(price_text)
        price_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(price_label)

        description_title = QLabel("Описание")
        description_title.setStyleSheet(
            "font-size: 16px; font-weight: bold;"
        )
        layout.addWidget(description_title)

        description_label = QLabel(
            str(description or "Описание отсутствует")
        )
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        variants_title = QLabel("Варианты исполнения")
        variants_title.setStyleSheet(
            "font-size: 16px; font-weight: bold;"
        )
        layout.addWidget(variants_title)

        self.variant_box = QComboBox()
        for variant in variants:
            self.variant_box.addItem(
                f"{variant[1]} — доступно {variant[2]} шт.",
                userData=variant
            )
        if not variants:
            self.variant_box.addItem("Варианты не указаны")
        layout.addWidget(self.variant_box)

        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("Количество:"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 999)
        qty_layout.addWidget(self.qty_spin)
        qty_layout.addStretch()
        layout.addLayout(qty_layout)

        layout.addStretch()

        buttons = QHBoxLayout()
        add_button = QPushButton("Добавить в заказ")
        add_button.clicked.connect(self.add_to_order)
        buttons.addWidget(add_button)

        back_button = QPushButton("Назад")
        back_button.clicked.connect(self.close)
        buttons.addWidget(back_button)
        layout.addLayout(buttons)

    def add_to_order(self):
        variant = self.variant_box.currentData()

        if variant is None:
            QMessageBox.warning(self, "Ошибка",
                                "Выберите вариант исполнения.")
            return

        variant_id, variant_name, available = variant
        quantity = self.qty_spin.value()

        if quantity > available:
            QMessageBox.warning(
                self, "Ошибка",
                f"Доступно только {available} шт. "
                "Уменьшите количество."
            )
            return

        self.on_add_to_order(self.product, variant, quantity)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ФормаДесерт — каталог")
        self.resize(1100, 750)

        icon_path = resolve_image("resources/Images/ФормаДесерт.ico")
        if icon_path:
            self.setWindowIcon(QIcon(str(icon_path)))

        self.products = []
        self.variants_by_product = {}
        self.current_user = None
        self.draft_order = []

        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {COLOR_MAIN_BG};
                color: #333333;
                font-family: {FONT_FAMILY};
            }}

            QLineEdit, QComboBox {{
                padding: 10px;
                border: 1px solid #dddddd;
                border-radius: 7px;
                background: white;
            }}

            QPushButton {{
                background-color: {COLOR_ACTION};
                color: white;
                border: none;
                border-radius: 7px;
                padding: 10px 18px;
            }}

            QPushButton:hover {{
                background-color: #5d9d9a;
            }}
        """)

        self.build_ui()
        self.load_products()
        self.update_user_panel()

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(15)

        top_bar = QHBoxLayout()

        logo_label = QLabel()
        logo_path = resolve_image("resources/Images/ФормаДесерт.png")
        if logo_path:
            pixmap = QPixmap(str(logo_path))
            logo_label.setPixmap(
                pixmap.scaled(
                    60, 60,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        top_bar.addWidget(logo_label)

        title = QLabel("ФормаДесерт — каталог")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        top_bar.addWidget(title)
        top_bar.addStretch()

        self.user_label = QLabel("Гость")
        top_bar.addWidget(self.user_label)

        self.user_button = QPushButton("Войти")
        self.user_button.clicked.connect(self.toggle_login)
        top_bar.addWidget(self.user_button)

        main_layout.addLayout(top_bar)

        controls = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск по наименованию...")
        self.search_input.textChanged.connect(self.filter_products)
        controls.addWidget(self.search_input, stretch=2)

        self.category_box = QComboBox()
        self.category_box.addItem("Все категории")
        self.category_box.currentIndexChanged.connect(self.filter_products)
        controls.addWidget(self.category_box)

        self.sort_box = QComboBox()
        self.sort_box.addItems([
            "Без сортировки",
            "Сначала дешёвые",
            "Сначала дорогие",
            "По названию"
        ])
        self.sort_box.currentIndexChanged.connect(self.filter_products)
        controls.addWidget(self.sort_box)

        main_layout.addLayout(controls)

        self.count_label = QLabel("Найдено моделей: 0")
        main_layout.addWidget(self.count_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.products_widget = QWidget()
        self.list_layout = QVBoxLayout(self.products_widget)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()

        self.scroll.setWidget(self.products_widget)
        main_layout.addWidget(self.scroll)

        self.set_controls_enabled(False)

    def set_controls_enabled(self, enabled):
        self.search_input.setEnabled(enabled)
        self.category_box.setEnabled(enabled)
        self.sort_box.setEnabled(enabled)

    def update_user_panel(self):
        if self.current_user:
            self.user_label.setText(self.current_user["fio"])
            self.user_button.setText("Выход")
            self.set_controls_enabled(True)
        else:
            self.user_label.setText("Гость")
            self.user_button.setText("Войти")
            self.set_controls_enabled(False)

    def toggle_login(self):
        if self.current_user:
            self.current_user = None
            self.update_user_panel()
        else:
            dialog = LoginDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.current_user = dialog.user
                self.update_user_panel()
                QMessageBox.information(
                    self, "Успех",
                    f"Добро пожаловать, {self.current_user['fio']}!"
                )

    def load_products(self):
        db = Database()

        if not db.connect():
            QMessageBox.critical(self, "Ошибка",
                                 "Не удалось подключиться к базе данных.")
            return

        try:
            cursor = db.connection.cursor()

            # Количество = сумма остатков всех вариантов модели
            # (stock_items привязан к product_id и variant_id)
            cursor.execute("""
                SELECT
                    p.product_id,
                    p.article,
                    p.name,
                    p.material,
                    p.description,
                    p.price,
                    COALESCE(c.category_name, '') AS category,
                    COALESCE(m.manufacturer_name, '') AS manufacturer,
                    COALESCE(SUM(s.quantity), 0) AS total_stock,
                    p.image_path
                FROM products p
                LEFT JOIN categories c
                    ON c.category_id = p.category_id
                LEFT JOIN manufacturers m
                    ON m.manufacturer_id = p.manufacturer_id
                LEFT JOIN stock_items s
                    ON s.product_id = p.product_id
                GROUP BY
                    p.product_id, p.article, p.name, p.material,
                    p.description, p.price,
                    c.category_name, m.manufacturer_name, p.image_path
                ORDER BY p.product_id
            """)

            products = cursor.fetchall()

            # Скидка 25%, если в предыдущем календарном месяце
            # по модели не было ни одного заказа.
            # Состав заказа ссылается на stock_item_id,
            # поэтому ведём через него к модели
            prev_start, prev_end = get_previous_month_bounds()

            cursor.execute("""
                SELECT s.product_id
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.order_id
                JOIN stock_items s ON s.stock_item_id = oi.stock_item_id
                WHERE o.order_date >= %s AND o.order_date < %s
                GROUP BY s.product_id
            """, (prev_start, prev_end))

            sold_ids = {row[0] for row in cursor.fetchall()}

            products_with_discount = []
            for row in products:
                discount = (
                    DISCOUNT_PERCENT if row[0] not in sold_ids else 0
                )
                final_price = discounted_price(row[5], discount)
                products_with_discount.append(
                    row + (discount, final_price)
                )

            self.products = products_with_discount

            # Варианты исполнения: остатки по каждой модели
            # из stock_items + variants
            self.variants_by_product = {}

            cursor.execute("""
                SELECT s.product_id,
                       v.variant_name,
                       SUM(s.quantity) AS quantity
                FROM stock_items s
                JOIN variants v ON v.variant_id = s.variant_id
                GROUP BY s.product_id, v.variant_name
                ORDER BY s.product_id, v.variant_name
            """)

            for product_id, variant_name, quantity in cursor.fetchall():
                self.variants_by_product.setdefault(
                    product_id, []
                ).append((product_id, variant_name, quantity))

            cursor.close()

            self.load_categories()
            self.filter_products()

        except Exception as error:
            QMessageBox.critical(self, "Ошибка загрузки", str(error))

        finally:
            db.close()

    def load_categories(self):
        db = Database()

        if not db.connect():
            return

        try:
            cursor = db.connection.cursor()
            cursor.execute(
                "SELECT category_name FROM categories ORDER BY category_name"
            )

            self.category_box.clear()
            self.category_box.addItem("Все категории")

            for (title,) in cursor.fetchall():
                self.category_box.addItem(str(title))

            cursor.close()

        except Exception:
            pass

        finally:
            db.close()

    def load_variants(self, product_id):
        return self.variants_by_product.get(product_id, [])

    def filter_products(self):
        if not self.current_user:
            self.show_products(self.products)
            return

        search = self.search_input.text().lower()

        filtered = [
            product for product in self.products
            if search in str(product[2]).lower()
        ]

        category = self.category_box.currentText()
        if category != "Все категории":
            filtered = [
                product for product in filtered
                if str(product[6]) == category
            ]

        sort_index = self.sort_box.currentIndex()

        if sort_index == 1:
            filtered.sort(key=lambda x: x[5])

        elif sort_index == 2:
            filtered.sort(key=lambda x: x[5], reverse=True)

        elif sort_index == 3:
            filtered.sort(key=lambda x: str(x[2]).lower())

        self.show_products(filtered)

    def show_products(self, products):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.count_label.setText(f"Найдено моделей: {len(products)}")

        if not products:
            empty = QLabel("Товары не найдены")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.insertWidget(0, empty)
            return

        for index, product in enumerate(products):
            self.list_layout.insertWidget(
                index, self.create_product_row(product)
            )

    def open_product_view(self, product):
        variants = self.load_variants(product[0])
        self.view_window = ProductViewWindow(
            product, variants, self.add_to_draft_order
        )
        self.view_window.show()

    def add_to_draft_order(self, product, variant, quantity):
        self.draft_order.append((product[0], variant[0], quantity))
        QMessageBox.information(
            self, "Успех",
            f"Позиция добавлена в заказ: {quantity} шт."
        )

    def create_product_row(self, product):
        (
            product_id, article, name, material,
            description, price, category,
            manufacturer, total_stock, image_path,
            discount, final_price
        ) = product

        low_stock = total_stock <= 3

        row = ClickableRow(product, self.open_product_view)
        row.setFrameShape(QFrame.Shape.StyledPanel)

        # Вся строка светло-красная при суммарном остатке <= 3
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {
                    COLOR_LOW_STOCK if low_stock else COLOR_ADD_BG
                };
                border-radius: 10px;
                border: 1px solid #eeeeee;
            }}
        """)
        row.setMinimumHeight(110)

        layout = QHBoxLayout(row)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        image_label = QLabel()
        image_label.setFixedSize(120, 90)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("border: none;")

        path = resolve_image(image_path)
        if not path:
            # Заглушка для пустого или неверного пути
            path = resolve_image("resources/Images/picture.png")

        if path:
            pixmap = QPixmap(str(path))
            image_label.setPixmap(
                pixmap.scaled(
                    110, 85,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        else:
            image_label.setText("Нет изображения")

        layout.addWidget(image_label)

        center = QVBoxLayout()

        header = QLabel(f"{manufacturer} | {name}")
        header.setStyleSheet(
            "font-size: 16px; font-weight: bold; border: none;"
        )
        center.addWidget(header)

        details = QLabel(
            f"Категория: {category or 'Не указана'}   "
            f"Количество: {total_stock} шт.   "
            f"Состав: {material or 'Не указан'}"
        )
        details.setStyleSheet("border: none; color: #555555;")
        center.addWidget(details)

        layout.addLayout(center, stretch=1)

        price_layout = QVBoxLayout()
        price_layout.addStretch()

        price_label = QLabel(f"{final_price} ₽")
        price_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; border: none;"
        )
        price_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        price_layout.addWidget(price_label)

        # Ложную скидку не показываем — зачёркнутая цена
        # выводится только при реальной скидке
        if discount > 0:
            old_price_label = QLabel(f"<s>{price} ₽</s>")
            old_price_label.setStyleSheet(
                "border: none; color: #999999;"
            )
            old_price_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            price_layout.addWidget(old_price_label)

        price_layout.addStretch()
        layout.addLayout(price_layout)

        return row


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
