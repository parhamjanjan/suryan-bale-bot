import os
import re
import uuid

from dataclasses import dataclass, field
from typing import Optional, List

from dotenv import load_dotenv

from bale import (
    Bot,
    Message,
    InputFile,
    MenuKeyboardMarkup,
    MenuKeyboardButton,
)


# =========================================================
# ENV
# =========================================================

load_dotenv()

BALE_BOT_TOKEN = os.getenv("BALE_BOT_TOKEN")

CARD_NUMBER = os.getenv(
    "CARD_NUMBER",
    "شماره کارت در تنظیمات ربات وارد نشده است"
)

if not BALE_BOT_TOKEN:
    raise RuntimeError(
        "BALE_BOT_TOKEN در فایل .env تنظیم نشده است"
    )


# =========================================================
# CONFIG
# =========================================================

ADMIN_ID = 602834325

SHIPPING_POST = "پست"
SHIPPING_PICKUP = "دریافت توسط مشتری"

# هزینه‌های ثابت دریافت سفارش
POST_FEE = 200_000
PICKUP_PACKAGING_FEE = 45_000

bot = Bot(token=BALE_BOT_TOKEN)


# =========================================================
# STATES
# =========================================================

START = "start"
NAME = "name"
PHONE = "phone"
PRODUCT = "product"
PRODUCT_DETAILS = "product_details"
CART = "cart"
ADDRESS = "address"
SHIPPING = "shipping"
CUSTOMER_DESCRIPTION = "customer_description"
PRICE_STATUS = "price_status"
WAITING_ADMIN_PRICE = "waiting_admin_price"
PAYMENT = "payment"
RECEIPT = "receipt"
CONFIRM = "confirm"


# =========================================================
# DATA
# =========================================================

@dataclass
class CartItem:
    product_type: str = "text"
    product_text: str = ""
    product_file_id: Optional[str] = None
    details: str = ""


@dataclass
class OrderData:

    order_id: str = field(
        default_factory=lambda:
        f"S-{uuid.uuid4().hex[:8].upper()}"
    )

    state: str = START

    first_name: str = ""
    last_name: str = ""
    phone: str = ""

    cart: List[CartItem] = field(
        default_factory=list
    )

    full_address: str = ""

    shipping_method: str = ""

    customer_description: str = ""

    price_known: bool = False

    price: str = ""

    receipt_file_id: Optional[str] = None

    receipt_type: str = ""

    waiting_for_admin_price: bool = False

    admin_price_message_id: Optional[int] = None


# =========================================================
# STORAGE
# =========================================================

orders = {}

# message_id پیام درخواست قیمت ادمین
#
# {
#     admin_message_id: {
#         "user_id": ...,
#         "order_id": ...
#     }
# }

admin_price_requests = {}


# =========================================================
# TEXT HELPERS
# =========================================================

def normalize_text(value: str) -> str:

    if not value:
        return ""

    return (
        str(value)
        .strip()
        .replace("ي", "ی")
        .replace("ى", "ی")
        .replace("ك", "ک")
    )


def normalize_digits(value: str) -> str:

    if not value:
        return ""

    translation = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return str(value).translate(translation)


def normalize_price(value: str) -> Optional[str]:

    if not value:
        return None

    value = normalize_digits(value)

    value = (
        value
        .replace(",", "")
        .replace("٬", "")
        .replace(" ", "")
        .replace("تومان", "")
        .replace("تومن", "")
        .replace("ریال", "")
    )

    if not value.isdigit():
        return None

    number = int(value)

    if number <= 0:
        return None

    return f"{number:,} تومان"


def get_shipping_fee(order: OrderData) -> int:
    """هزینه اضافه‌شونده بر اساس روش دریافت سفارش."""
    if order.shipping_method == SHIPPING_POST:
        return POST_FEE

    if order.shipping_method == SHIPPING_PICKUP:
        return PICKUP_PACKAGING_FEE

    return 0


def add_shipping_fee(order: OrderData, base_price: str) -> str:
    """قیمت پایه را با هزینه ارسال/بسته‌بندی جمع می‌کند."""
    normalized = normalize_price(base_price)

    if not normalized:
        raise ValueError("قیمت پایه معتبر نیست.")

    base_number = int(
        normalized.replace(",", "").replace(" تومان", "")
    )

    total = base_number + get_shipping_fee(order)

    return f"{total:,} تومان"


# =========================================================
# MESSAGE HELPERS
# =========================================================

def get_message_id(message) -> Optional[int]:

    if message is None:
        return None

    if isinstance(message, dict):

        for key in (
            "message_id",
            "id"
        ):

            value = message.get(key)

            if value is not None:

                try:
                    return int(value)

                except Exception:
                    pass

    for attr in (
        "message_id",
        "id"
    ):

        value = getattr(
            message,
            attr,
            None
        )

        if value is not None:

            try:
                return int(value)

            except Exception:
                pass

    return None


def get_replied_message(message):

    if message is None:
        return None

    if isinstance(message, dict):

        for key in (
            "reply_to_message",
            "reply_to",
            "reply_message",
            "reply_to_msg"
        ):

            replied = message.get(key)

            if replied is not None:
                return replied

    for attr in (
        "reply_to_message",
        "reply_to",
        "reply_message",
        "reply_to_msg"
    ):

        replied = getattr(
            message,
            attr,
            None
        )

        if replied is not None:
            return replied

    return None


def get_replied_message_id(message) -> Optional[int]:

    if message is None:
        return None

    replied = get_replied_message(
        message
    )

    if replied is not None:

        if isinstance(
            replied,
            int
        ):
            return replied

        if isinstance(
            replied,
            str
        ):

            if replied.isdigit():
                return int(replied)

        replied_id = get_message_id(
            replied
        )

        if replied_id is not None:
            return replied_id

    if isinstance(message, dict):

        for key in (
            "reply_to_message_id",
            "reply_to_id"
        ):

            value = message.get(key)

            if value is not None:

                try:
                    return int(value)

                except Exception:
                    pass

    for attr in (
        "reply_to_message_id",
        "reply_to_id"
    ):

        value = getattr(
            message,
            attr,
            None
        )

        if value is not None:

            try:
                return int(value)

            except Exception:
                pass

    return None


def get_message_text(message) -> str:

    if message is None:
        return ""

    if isinstance(message, dict):

        return (
            message.get("text")
            or message.get("content")
            or message.get("caption")
            or ""
        )

    return (
        getattr(
            message,
            "text",
            None
        )
        or getattr(
            message,
            "content",
            None
        )
        or getattr(
            message,
            "caption",
            None
        )
        or ""
    )


def extract_order_id(text: str) -> Optional[str]:

    if not text:
        return None

    pattern = (
        r"شماره\s*سفارش\s*[:：]\s*"
        r"([A-Z0-9\-]+)"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1).upper()

    return None


# =========================================================
# FILE HELPERS
# =========================================================

def get_photo_file_id(message) -> Optional[str]:

    photo = getattr(
        message,
        "photo",
        None
    )

    if not photo:
        return None

    try:

        if isinstance(
            photo,
            list
        ):

            photo_item = photo[-1]

        else:

            photo_item = photo

        return (
            getattr(
                photo_item,
                "file_id",
                None
            )
            or
            getattr(
                photo_item,
                "id",
                None
            )
        )

    except Exception:

        return None


def get_document_file_id(message) -> Optional[str]:

    document = getattr(
        message,
        "document",
        None
    )

    if not document:
        return None

    try:

        return (
            getattr(
                document,
                "file_id",
                None
            )
            or
            getattr(
                document,
                "id",
                None
            )
        )

    except Exception:

        return None


# =========================================================
# PRICE REQUEST HELPERS
# =========================================================

def cleanup_price_request(
    user_id: int,
    order_id: Optional[str] = None
):

    keys_to_delete = []

    for message_id, data in list(
        admin_price_requests.items()
    ):

        if data.get("user_id") != user_id:
            continue

        if order_id is not None:

            if data.get("order_id") != order_id:
                continue

        keys_to_delete.append(
            message_id
        )

    for key in keys_to_delete:

        admin_price_requests.pop(
            key,
            None
        )


def find_order_by_order_id(
    order_id: str
):

    if not order_id:
        return None, None

    order_id = order_id.upper()

    for user_id, order in orders.items():

        if (
            order.order_id.upper()
            == order_id
        ):

            return user_id, order

    return None, None


# =========================================================
# ORDER MANAGEMENT
# =========================================================

def get_order(
    user_id: int
) -> OrderData:

    if user_id not in orders:

        orders[user_id] = OrderData()

    return orders[user_id]


def reset_order(
    user_id: int
):

    old_order = orders.get(
        user_id
    )

    if old_order:

        cleanup_price_request(
            user_id,
            old_order.order_id
        )

    orders[user_id] = OrderData()


# =========================================================
# KEYBOARDS
# =========================================================

def main_start_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="🛍 شروع خرید"
        ),
        row=1
    )

    return keyboard


def cancel_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=1
    )

    return keyboard


def product_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="➕ افزودن محصول"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="🛒 مشاهده سبد خرید"
        ),
        row=2
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=3
    )

    return keyboard


def cart_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="➕ افزودن محصول"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="✅ ادامه ثبت سفارش"
        ),
        row=2
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=3
    )

    return keyboard


def product_details_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="⏭ بدون توضیح"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=2
    )

    return keyboard


def shipping_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="📦 پست"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="🏪 تحویل حضوری در محل فروشگاه توسط مشتری"
        ),
        row=2
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=3
    )

    return keyboard


def customer_description_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="⏭ بدون توضیح"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=2
    )

    return keyboard


def price_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="💰 قیمت را می‌دانم"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❓ قیمت را نمی‌دانم"
        ),
        row=2
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=3
    )

    return keyboard


def payment_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="📸 ارسال رسید پرداخت"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=2
    )

    return keyboard


def confirm_keyboard():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton(
            text="✅ تأیید نهایی سفارش"
        ),
        row=1
    )

    keyboard.add(
        MenuKeyboardButton(
            text="✏️ ویرایش سفارش"
        ),
        row=2
    )

    keyboard.add(
        MenuKeyboardButton(
            text="❌ لغو سفارش"
        ),
        row=3
    )

    return keyboard


# =========================================================
# WELCOME
# =========================================================

async def send_welcome(
    message: Message
):

    user_id = message.author.id

    reset_order(
        user_id
    )

    await message.reply(
        "🛍 به فروشگاه سورین خوش آمدید!\n\n"
        "برای ثبت سفارش، روی دکمه «🛍 شروع خرید» بزنید.",
        components=main_start_keyboard()
    )


async def start_purchase(
    message: Message
):

    user_id = message.author.id

    reset_order(
        user_id
    )

    order = get_order(
        user_id
    )

    order.state = NAME

    await message.reply(
        "عالیه 🌱\n\n"
        "برای شروع ثبت سفارش، لطفاً نام و نام خانوادگی "
        "خود را وارد کنید.",
        components=cancel_keyboard()
    )


# =========================================================
# ASK FUNCTIONS
# =========================================================

async def ask_phone(
    message: Message
):

    await message.reply(
        "📱 لطفاً شماره تماس خود را به‌صورت متنی ارسال کنید.",
        components=cancel_keyboard()
    )


async def ask_product(
    message: Message
):

    await message.reply(
        "🛍 حالا محصول موردنظر را ارسال کنید.\n\n"
        "می‌توانید یکی از این موارد را بفرستید:\n"
        "• عکس محصول\n"
        "• کد محصول\n"
        "• نام محصول\n"
        "• لینک محصول\n\n"
        "بعد از ارسال محصول، اطلاعات تکمیلی آن را "
        "از شما می‌پرسم.",
        components=product_keyboard()
    )


async def ask_product_details(
    message: Message
):

    await message.reply(
        "📝 اگر برای این محصول توضیحی دارید، همینجا بنویسید.\n\n"
        "مثلاً:\n"
        "سایز L، رنگ مشکی\n\n"
        "اگر توضیحی ندارید، روی «⏭ بدون توضیح» بزنید.",
        components=product_details_keyboard()
    )


async def ask_address(
    message: Message
):

    await message.reply(
        "📍 لطفاً آدرس کامل را در یک پیام ارسال کنید.\n\n"

        "ساختار پیشنهادی:\n\n"

        "استان: ...\n"
        "شهر: ...\n"
        "آدرس دقیق: ...\n"
        "کدپستی: ...\n\n"

        "مثال:\n"

        "استان: البرز\n"
        "شهر: کرج\n"
        "آدرس دقیق: مهرشهر، بلوار ارم، خیابان ...، "
        "پلاک ۱۲، واحد ۳\n"
        "کدپستی: ۳۱۸۷۶۴۵۱۲۳\n\n"

        "⚠️ اگر کدپستی را دارید، آن را در آخر آدرس بنویسید.\n"
        "اگر کدپستی ندارید، فقط آدرس کامل را ارسال کنید.",

        components=cancel_keyboard()
    )


async def ask_shipping(
    message: Message
):

    await message.reply(
        "🚚 روش دریافت سفارش را انتخاب کنید:",
        components=shipping_keyboard()
    )


async def ask_customer_description(
    message: Message
):

    await message.reply(
        "📝 اگر توضیح یا درخواست خاصی برای سفارش دارید، بنویسید.\n\n"

        "مثلاً:\n"
        "لطفاً قبل از ارسال با من تماس بگیرید.\n\n"

        "اگر توضیحی ندارید، روی «⏭ بدون توضیح» بزنید.",

        components=customer_description_keyboard()
    )


async def ask_price_status(
    message: Message
):

    await message.reply(
        "💰 آیا قیمت محصول و هزینه ارسال و موجودی را می‌دانید؟ و با ادمین هماهنگ کردید؟",
        components=price_keyboard()
    )


async def ask_payment(
    message: Message
):

    order = get_order(
        message.author.id
    )

    await message.reply(
        "💳 مبلغ نهایی سفارش شما (با احتساب هزینه دریافت):\n\n"

        f"💰 {order.price}\n\n"

        "لطفاً مبلغ بالا را به شماره کارت زیر واریز کنید:\n\n"

        f"💳 {CARD_NUMBER}\n\n"

        "بعد از پرداخت، تصویر رسید پرداخت را ارسال کنید.",

        components=payment_keyboard()
    )


# =========================================================
# CART
# =========================================================

def cart_text(
    order: OrderData
) -> str:

    if not order.cart:
        return "🛒 سبد خرید شما خالی است."

    lines = [
        "🛒 سبد خرید شما:",
        ""
    ]

    for index, item in enumerate(
        order.cart,
        start=1
    ):

        if item.product_type == "photo":

            product_name = "📷 محصول تصویری"

        elif item.product_type == "document":

            product_name = "📄 محصول ارسالی"

        else:

            product_name = (
                item.product_text
                or "محصول"
            )

        lines.append(
            f"{index}. {product_name}"
        )

        if item.details:

            lines.append(
                f"   📝 {item.details}"
            )

        lines.append("")

    return "\n".join(lines)


async def show_cart(
    message: Message
):

    order = get_order(
        message.author.id
    )

    await message.reply(
        cart_text(order),
        components=cart_keyboard()
    )


# =========================================================
# CUSTOMER ORDER SUMMARY
# =========================================================

def customer_order_summary(
    order: OrderData
) -> str:

    customer_name = (
        f"{order.first_name} "
        f"{order.last_name}"
    ).strip()

    return (
        "🧾 اطلاعات کامل سفارش شما\n\n"

        "━━━━━━━━━━━━━━━━━━\n"

        f"🆔 شماره سفارش:\n"
        f"{order.order_id}\n\n"

        "👤 اطلاعات مشتری\n"
        f"نام: {customer_name}\n"
        f"📱 شماره تماس: {order.phone}\n\n"

        "🛒 محصولات\n"
        f"{cart_text(order)}\n"

        "📍 آدرس\n"
        f"{order.full_address}\n\n"

        "🚚 روش دریافت\n"
        f"{order.shipping_method}\n"
        f"💸 هزینه ارسال/بسته‌بندی: {get_shipping_fee(order):,} تومان\n\n"

        "💰 مبلغ نهایی سفارش\n"
        f"{order.price}\n\n"

        "📝 توضیحات\n"
        f"{order.customer_description or 'ندارد'}\n\n"

        "💳 وضعیت پرداخت\n"
        "رسید پرداخت دریافت شد\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        "⚠️ لطفاً تمام اطلاعات بالا را بررسی کنید.\n"
        "اگر همه اطلاعات صحیح است، روی «✅ تأیید نهایی سفارش» بزنید.\n\n"
        "در صورت وجود اشتباه، «✏️ ویرایش سفارش» را انتخاب کنید."
    )


# =========================================================
# SEND PRICE REQUEST TO ADMIN
# =========================================================

async def send_price_request_to_admin(
    user_id: int,
    order: OrderData
):

    customer_name = (
        f"{order.first_name} "
        f"{order.last_name}"
    ).strip()

    text = (
        "💰 درخواست تعیین قیمت جدید\n\n"

        f"🆔 شماره سفارش: {order.order_id}\n"
        f"👤 مشتری: {customer_name}\n"
        f"📱 شماره تماس: {order.phone}\n\n"

        f"🛒 تعداد محصولات: {len(order.cart)}\n\n"

        "📦 سبد خرید:\n"
        f"{cart_text(order)}\n\n"

        "📍 آدرس:\n"
        f"{order.full_address}\n\n"

        f"🚚 روش ارسال: {order.shipping_method}\n"
        f"💸 هزینه دریافت: {get_shipping_fee(order):,} تومان\n\n"

        "📝 توضیحات مشتری:\n"
        f"{order.customer_description or 'ندارد'}\n\n"

        "━━━━━━━━━━━━━━\n"

        "⚠️ برای تعیین قیمت، روی همین پیام Reply کنید.\n\n"

        "فقط قیمت خودِ محصولات را ارسال کنید؛ هزینه دریافت خودکار اضافه می‌شود:\n"
        "850000\n\n"

        "یا:\n"
        "/price 850000\n"

        "━━━━━━━━━━━━━━"
    )

    admin_message = await bot.send_message(
        ADMIN_ID,
        text
    )

    admin_message_id = get_message_id(
        admin_message
    )

    print(
        "PRICE REQUEST SENT:",
        admin_message_id,
        order.order_id,
        user_id
    )

    for item in order.cart:

        if (
            item.product_type == "photo"
            and item.product_file_id
        ):

            try:

                await bot.send_photo(
                    ADMIN_ID,
                    InputFile(
                        item.product_file_id
                    ),
                    caption=(
                        f"📷 محصول سفارش\n"
                        f"🆔 {order.order_id}"
                    )
                )

            except Exception as e:

                print(
                    "SEND PRODUCT PHOTO ERROR:",
                    repr(e)
                )

        elif (
            item.product_type == "document"
            and item.product_file_id
        ):

            try:

                await bot.send_document(
                    ADMIN_ID,
                    InputFile(
                        item.product_file_id
                    ),
                    caption=(
                        f"📄 محصول سفارش\n"
                        f"🆔 {order.order_id}"
                    )
                )

            except Exception as e:

                print(
                    "SEND PRODUCT DOCUMENT ERROR:",
                    repr(e)
                )

    if admin_message_id is not None:

        order.admin_price_message_id = (
            admin_message_id
        )

        admin_price_requests[
            admin_message_id
        ] = {
            "user_id": user_id,
            "order_id": order.order_id
        }

    order.waiting_for_admin_price = True

    order.state = WAITING_ADMIN_PRICE


# =========================================================
# ADMIN PRICE PROCESSOR
# =========================================================

async def process_admin_price(
    message: Message
):

    try:

        author = getattr(
            message,
            "author",
            None
        )

        if author is None:
            return

        author_id = getattr(
            author,
            "id",
            None
        )

        if author_id != ADMIN_ID:
            return

        text = normalize_text(
            get_message_text(message)
        )

        if not text:
            return

        print(
            "ADMIN MESSAGE:",
            repr(text)
        )

        customer_id = None
        order = None
        order_id = None

        # =================================================
        # پیدا کردن Reply
        # =================================================

        replied_message_id = (
            get_replied_message_id(
                message
            )
        )

        print(
            "REPLIED MESSAGE ID:",
            replied_message_id
        )

        if replied_message_id is not None:

            request = admin_price_requests.get(
                replied_message_id
            )

            if request:

                customer_id = request.get(
                    "user_id"
                )

                order_id = request.get(
                    "order_id"
                )

                current_order = orders.get(
                    customer_id
                )

                if (
                    current_order
                    and
                    current_order.order_id
                    == order_id
                ):

                    order = current_order

            # -------------------------------------------------
            # fallback با شماره سفارش
            # -------------------------------------------------

            if order is None:

                replied_message = (
                    get_replied_message(
                        message
                    )
                )

                replied_text = (
                    get_message_text(
                        replied_message
                    )
                )

                extracted_order_id = (
                    extract_order_id(
                        replied_text
                    )
                )

                if extracted_order_id:

                    (
                        customer_id,
                        order
                    ) = find_order_by_order_id(
                        extracted_order_id
                    )

                    order_id = (
                        extracted_order_id
                    )

        # =================================================
        # حالت /price USER_ID PRICE
        # =================================================

        if order is None:

            parts = text.split()

            if (
                len(parts) >= 3
                and
                parts[0].lower() == "/price"
            ):

                try:

                    legacy_user_id = int(
                        parts[1]
                    )

                except Exception:

                    await message.reply(
                        "❌ شناسه کاربر معتبر نیست."
                    )

                    return

                legacy_order = orders.get(
                    legacy_user_id
                )

                if legacy_order is None:

                    await message.reply(
                        "❌ سفارش فعالی برای این کاربر پیدا نشد."
                    )

                    return

                customer_id = legacy_user_id

                order = legacy_order

                order_id = legacy_order.order_id

        # =================================================
        # سفارش پیدا نشد
        # =================================================

        if (
            order is None
            or customer_id is None
        ):

            await message.reply(
                "❌ سفارش مربوط به این پیام پیدا نشد.\n\n"
                "برای جلوگیری از اشتباه، روی همان پیام "
                "«💰 درخواست تعیین قیمت» Reply کنید."
            )

            return

        # =================================================
        # وضعیت سفارش
        # =================================================

        if order.state != WAITING_ADMIN_PRICE:

            await message.reply(
                "❌ این سفارش دیگر در انتظار قیمت نیست.\n\n"
                f"🆔 {order.order_id}"
            )

            return

        # =================================================
        # استخراج قیمت
        # =================================================

        raw_price = text

        if text.lower().startswith(
            "/price"
        ):

            parts = text.split()

            if len(parts) == 2:

                raw_price = parts[1]

            elif len(parts) >= 3:

                raw_price = parts[-1]

        price = normalize_price(
            raw_price
        )

        if not price:

            await message.reply(
                "❌ قیمت معتبر نیست.\n\n"
                "مثال:\n"
                "850000"
            )

            return

        # =================================================
        # ذخیره قیمت
        # =================================================

        try:
            order.price = add_shipping_fee(order, price)
        except ValueError:
            await message.reply(
                "❌ قیمت معتبر نیست.\n\n"
                "مثال:\n"
                "850000"
            )
            return

        order.price_known = True

        order.waiting_for_admin_price = False

        order.state = RECEIPT

        cleanup_price_request(
            customer_id,
            order.order_id
        )

        print(
            "PRICE SAVED:",
            order.order_id,
            order.price
        )

        # =================================================
        # ارسال قیمت به مشتری
        # =================================================

        try:

            await bot.send_message(
                customer_id,

                "🎉 قیمت سفارش شما مشخص شد!\n\n"

                f"🆔 شماره سفارش:\n"
                f"{order.order_id}\n\n"

                "━━━━━━━━━━━━━━\n"

                "💰 مبلغ قابل پرداخت (مبلغ محصول + هزینه ارسال یا بسته بندی):\n\n"
                f"💵 {order.price}\n"

                "━━━━━━━━━━━━━━\n\n"

                "💳 لطفاً مبلغ بالا را به شماره کارت زیر "
                "واریز کنید:\n\n"

                f"{CARD_NUMBER}\n\n"

                "📸 بعد از پرداخت، تصویر رسید پرداخت را "
                "ارسال کنید.",

                components=payment_keyboard()
            )

        except Exception as send_error:

            print(
                "SEND PRICE ERROR:",
                repr(send_error)
            )

            order.state = WAITING_ADMIN_PRICE

            order.waiting_for_admin_price = True

            await message.reply(
                "❌ قیمت ذخیره شد اما ارسال آن برای مشتری "
                "با خطا مواجه شد.\n\n"
                f"خطا:\n{repr(send_error)}"
            )

            return

        await message.reply(
            "✅ قیمت با موفقیت ثبت شد و برای مشتری ارسال گردید.\n\n"

            f"🆔 سفارش: {order.order_id}\n"
            f"👤 مشتری: {customer_id}\n"
            f"💰 مبلغ: {order.price}"
        )

    except Exception as e:

        print(
            "ADMIN PRICE ERROR:",
            repr(e)
        )

        try:

            await message.reply(
                "❌ هنگام پردازش قیمت خطایی رخ داد.\n"
                "جزئیات خطا در کنسول ثبت شد."
            )

        except Exception:
            pass


# =========================================================
# SEND RECEIPT TO ADMIN
# =========================================================

async def send_receipt_to_admin(
    user_id: int,
    order: OrderData
):

    customer_name = (
        f"{order.first_name} "
        f"{order.last_name}"
    ).strip()

    text = (
        "💳 رسید پرداخت جدید\n\n"

        f"🆔 شماره سفارش: {order.order_id}\n"

        f"👤 مشتری: {customer_name}\n"

        f"📱 شماره تماس: {order.phone}\n"

        f"💰 مبلغ: {order.price}\n\n"

        "⚠️ مشتری رسید پرداخت را ارسال کرده است."
    )

    await bot.send_message(
        ADMIN_ID,
        text
    )

    # =====================================================
    # ارسال رسید عکس
    # =====================================================

    if (
        order.receipt_type == "photo"
        and order.receipt_file_id
    ):

        await bot.send_photo(
            ADMIN_ID,
            InputFile(
                order.receipt_file_id
            ),
            caption=(
                f"🧾 رسید پرداخت\n"
                f"🆔 سفارش: {order.order_id}"
            )
        )

        return

    # =====================================================
    # ارسال رسید فایل
    # =====================================================

    if (
        order.receipt_type == "document"
        and order.receipt_file_id
    ):

        await bot.send_document(
            ADMIN_ID,
            InputFile(
                order.receipt_file_id
            ),
            caption=(
                f"🧾 رسید پرداخت\n"
                f"🆔 سفارش: {order.order_id}"
            )
        )

        return

    raise RuntimeError(
        "Receipt file type or file_id is missing."
    )


# =========================================================
# SEND FINAL ORDER TO ADMIN
# =========================================================

async def send_final_order_to_admin(
    user_id: int,
    order: OrderData
):

    customer_name = (
        f"{order.first_name} "
        f"{order.last_name}"
    ).strip()

    text = (
        "🛍 سفارش جدید سورین\n\n"

        f"🆔 شماره سفارش: {order.order_id}\n\n"

        "👤 اطلاعات مشتری\n"
        f"نام: {customer_name}\n"
        f"📱 شماره تماس: {order.phone}\n\n"

        "🛒 محصولات\n"
        f"{cart_text(order)}\n\n"

        "📍 آدرس کامل\n"
        f"{order.full_address}\n\n"

        f"🚚 روش دریافت: {order.shipping_method}\n"
        f"💸 هزینه دریافت: {get_shipping_fee(order):,} تومان\n\n"

        f"💰 مبلغ نهایی: {order.price}\n\n"

        "📝 توضیحات مشتری\n"
        f"{order.customer_description or 'ندارد'}\n\n"

        "💳 وضعیت پرداخت: رسید ارسال شده"
    )

    await bot.send_message(
        ADMIN_ID,
        text
    )

    # =====================================================
    # ارسال تصاویر محصولات
    # =====================================================

    for item in order.cart:

        if (
            item.product_type == "photo"
            and item.product_file_id
        ):

            try:

                await bot.send_photo(
                    ADMIN_ID,
                    InputFile(
                        item.product_file_id
                    ),
                    caption=(
                        f"📷 محصول سفارش\n"
                        f"🆔 {order.order_id}"
                    )
                )

            except Exception as e:

                print(
                    "SEND PRODUCT PHOTO ERROR:",
                    repr(e)
                )

        elif (
            item.product_type == "document"
            and item.product_file_id
        ):

            try:

                await bot.send_document(
                    ADMIN_ID,
                    InputFile(
                        item.product_file_id
                    ),
                    caption=(
                        f"📄 محصول سفارش\n"
                        f"🆔 {order.order_id}"
                    )
                )

            except Exception as e:

                print(
                    "SEND PRODUCT DOCUMENT ERROR:",
                    repr(e)
                )

    # =====================================================
    # ارسال رسید
    # =====================================================

    if (
        order.receipt_file_id
        and order.receipt_type == "photo"
    ):

        try:

            await bot.send_photo(
                ADMIN_ID,
                InputFile(
                    order.receipt_file_id
                ),
                caption=(
                    "🧾 رسید پرداخت\n\n"
                    f"🆔 سفارش: {order.order_id}"
                )
            )

        except Exception as e:

            print(
                "SEND RECEIPT PHOTO ERROR:",
                repr(e)
            )

    elif (
        order.receipt_file_id
        and order.receipt_type == "document"
    ):

        try:

            await bot.send_document(
                ADMIN_ID,
                InputFile(
                    order.receipt_file_id
                ),
                caption=(
                    "🧾 رسید پرداخت\n\n"
                    f"🆔 سفارش: {order.order_id}"
                )
            )

        except Exception as e:

            print(
                "SEND RECEIPT DOCUMENT ERROR:",
                repr(e)
            )


# =========================================================
# CUSTOMER HANDLER
# =========================================================

@bot.event
async def on_message(
    message: Message
):

    try:

        user_id = message.author.id

        # =================================================
        # ADMIN
        # =================================================

        if user_id == ADMIN_ID:

            await process_admin_price(
                message
            )

            return

        # =================================================
        # TEXT
        # =================================================

        text = normalize_text(
            getattr(
                message,
                "text",
                ""
            ) or ""
        )

        normalized = text.lower()

        # =================================================
        # START
        # =================================================

        if normalized in [
            "/start",
            "شروع"
        ]:

            await send_welcome(
                message
            )

            return

        # =================================================
        # START SHOPPING
        # =================================================

        if normalized in [
            "🛍 شروع خرید",
            "شروع خرید"
        ]:

            await start_purchase(
                message
            )

            return

        # =================================================
        # CANCEL
        # =================================================

        if normalized in [
            "❌ لغو سفارش",
            "لغو سفارش",
            "/cancel",
            "cancel"
        ]:

            await send_welcome(
                message
            )

            return

        # =================================================
        # RESET
        # =================================================

        if normalized in [
            "/reset",
            "شروع مجدد"
        ]:

            await send_welcome(
                message
            )

            return

        order = get_order(
            user_id
        )

        # =================================================
        # START STATE
        # =================================================

        if order.state == START:

            await message.reply(
                "لطفاً برای شروع ثبت سفارش، "
                "روی دکمه «🛍 شروع خرید» بزنید.",
                components=main_start_keyboard()
            )

            return

        # =================================================
        # NAME
        # =================================================

        if order.state == NAME:

            if not text:

                await message.reply(
                    "لطفاً نام و نام خانوادگی خود را وارد کنید.",
                    components=cancel_keyboard()
                )

                return

            parts = text.split(
                maxsplit=1
            )

            order.first_name = parts[0]

            if len(parts) > 1:

                order.last_name = parts[1]

            else:

                order.last_name = ""

            order.state = PHONE

            await ask_phone(
                message
            )

            return

        # =================================================
        # PHONE
        # =================================================

        if order.state == PHONE:

            phone = None

            contact = getattr(
                message,
                "contact",
                None
            )

            if contact:

                phone = (
                    getattr(
                        contact,
                        "phone_number",
                        None
                    )
                    or
                    getattr(
                        contact,
                        "phone",
                        None
                    )
                )

            if not phone:

                phone = text

            if not phone:

                await message.reply(
                    "لطفاً شماره تماس خود را به‌صورت متنی ارسال کنید.",
                    components=cancel_keyboard()
                )

                return

            order.phone = phone

            order.state = PRODUCT

            await ask_product(
                message
            )

            return

        # =================================================
        # PRODUCT
        # =================================================

        if order.state == PRODUCT:

            if normalized in [
                "🛒 مشاهده سبد خرید",
                "مشاهده سبد خرید"
            ]:

                await show_cart(
                    message
                )

                return

            if normalized in [
                "➕ افزودن محصول",
                "افزودن محصول"
            ]:

                await message.reply(
                    "🛍 محصول جدید را ارسال کنید:\n\n"
                    "• عکس\n"
                    "• کد محصول\n"
                    "• نام محصول\n"
                    "• لینک محصول",
                    components=cancel_keyboard()
                )

                return

            # -------------------------------------------------
            # PHOTO
            # -------------------------------------------------

            photo_file_id = get_photo_file_id(
                message
            )

            if photo_file_id:

                item = CartItem(
                    product_type="photo",
                    product_file_id=photo_file_id,
                    product_text="محصول تصویری"
                )

                order.cart.append(
                    item
                )

                order.state = PRODUCT_DETAILS

                await ask_product_details(
                    message
                )

                return

            # -------------------------------------------------
            # DOCUMENT
            # -------------------------------------------------

            document_file_id = get_document_file_id(
                message
            )

            if document_file_id:

                item = CartItem(
                    product_type="document",
                    product_file_id=document_file_id,
                    product_text="محصول ارسالی"
                )

                order.cart.append(
                    item
                )

                order.state = PRODUCT_DETAILS

                await ask_product_details(
                    message
                )

                return

            # -------------------------------------------------
            # TEXT PRODUCT
            # -------------------------------------------------

            if text:

                item = CartItem(
                    product_type="text",
                    product_text=text
                )

                order.cart.append(
                    item
                )

                order.state = PRODUCT_DETAILS

                await ask_product_details(
                    message
                )

                return

            await message.reply(
                "لطفاً عکس، کد، نام یا لینک محصول را ارسال کنید.",
                components=cancel_keyboard()
            )

            return

        # =================================================
        # PRODUCT DETAILS
        # =================================================

        if order.state == PRODUCT_DETAILS:

            if not order.cart:

                order.state = PRODUCT

                await ask_product(
                    message
                )

                return

            if normalized in [
                "⏭ بدون توضیح",
                "بدون توضیح"
            ]:

                order.cart[-1].details = ""

            else:

                order.cart[-1].details = text

            order.state = CART

            await show_cart(
                message
            )

            return

        # =================================================
        # CART
        # =================================================

        if order.state == CART:

            if normalized in [
                "➕ افزودن محصول",
                "افزودن محصول"
            ]:

                order.state = PRODUCT

                await message.reply(
                    "🛍 محصول بعدی را ارسال کنید.",
                    components=cancel_keyboard()
                )

                return

            if normalized in [
                "🛒 مشاهده سبد خرید",
                "مشاهده سبد خرید"
            ]:

                await show_cart(
                    message
                )

                return

            if normalized in [
                "✅ ادامه ثبت سفارش",
                "ادامه ثبت سفارش"
            ]:

                if not order.cart:

                    await message.reply(
                        "سبد خرید شما خالی است.",
                        components=cart_keyboard()
                    )

                    return

                order.state = ADDRESS

                await ask_address(
                    message
                )

                return

            await message.reply(
                "لطفاً یکی از گزینه‌های موجود را انتخاب کنید.",
                components=cart_keyboard()
            )

            return

        # =================================================
        # ADDRESS
        # =================================================

        if order.state == ADDRESS:

            if not text:

                await message.reply(
                    "لطفاً آدرس کامل را در یک پیام ارسال کنید.",
                    components=cancel_keyboard()
                )

                return

            order.full_address = text

            order.state = SHIPPING

            await ask_shipping(
                message
            )

            return

        # =================================================
        # SHIPPING
        # =================================================

        if order.state == SHIPPING:

            if normalized in [
                "📦 پست",
                "پست"
            ]:

                order.shipping_method = (
                    SHIPPING_POST
                )

            elif normalized in [
                "🏪 تحویل حضوری در محل فروشگاه توسط مشتری",
                "تحویل حضوری در محل فروشگاه توسط مشتری"
            ]:

                order.shipping_method = (
                    SHIPPING_PICKUP
                )

            else:

                await message.reply(
                    "لطفاً یکی از روش‌های دریافت را انتخاب کنید.",
                    components=shipping_keyboard()
                )

                return

            order.state = CUSTOMER_DESCRIPTION

            await ask_customer_description(
                message
            )

            return

        # =================================================
        # CUSTOMER DESCRIPTION
        # =================================================

        if order.state == CUSTOMER_DESCRIPTION:

            if normalized in [
                "⏭ بدون توضیح",
                "بدون توضیح"
            ]:

                order.customer_description = ""

            else:

                order.customer_description = text

            order.state = PRICE_STATUS

            await ask_price_status(
                message
            )

            return

        # =================================================
        # PRICE STATUS
        # =================================================

        if order.state == PRICE_STATUS:

            # -------------------------------------------------
            # PRICE KNOWN
            # -------------------------------------------------

            if normalized in [
                "💰 قیمت را می‌دانم",
                "قیمت را می‌دانم"
            ]:

                order.price_known = True

                order.state = PAYMENT

                await message.reply(
                    "💰 لطفاً قیمت خودِ محصولات را وارد کنید.\n\n"
                    "⚠️ هزینه دریافت سفارش به‌صورت خودکار اضافه می‌شود.\n"
                    "• پست: ۲۰۰٬۰۰۰ تومان\n"
                    "• دریافت توسط مشتری: ۴۵٬۰۰۰ تومان هزینه بسته‌بندی\n\n"
                    "مثال:\n"
                    "850000",
                    components=cancel_keyboard()
                )

                return

            # -------------------------------------------------
            # PRICE UNKNOWN
            # -------------------------------------------------

            if normalized in [
                "❓ قیمت را نمی‌دانم",
                "قیمت را نمی‌دانم"
            ]:

                order.price_known = False

                await send_price_request_to_admin(
                    user_id,
                    order
                )

                await message.reply(
                    "✅ اطلاعات سفارش شما برای فروشگاه ارسال شد.\n\n"
                    "💰 قیمت سفارش توسط فروشگاه بررسی می‌شود.\n"
                    "بعد از تعیین قیمت، مبلغ و اطلاعات پرداخت "
                    "برای شما ارسال خواهد شد.\n\n"
                    f"🆔 شماره سفارش:\n"
                    f"{order.order_id}",
                    components=cancel_keyboard()
                )

                return

            await message.reply(
                "لطفاً یکی از گزینه‌های قیمت را انتخاب کنید.",
                components=price_keyboard()
            )

            return

        # =================================================
        # PAYMENT
        # =================================================

        if order.state == PAYMENT:

            if normalized in [
                "📸 ارسال رسید پرداخت",
                "ارسال رسید پرداخت"
            ]:

                await message.reply(
                    "📸 لطفاً تصویر رسید پرداخت را ارسال کنید.",
                    components=cancel_keyboard()
                )

                return

            price = normalize_price(
                text
            )

            if not price:

                await message.reply(
                    "❌ مبلغ واردشده معتبر نیست.\n\n"
                    "مثال:\n"
                    "850000",
                    components=cancel_keyboard()
                )

                return

            try:
                order.price = add_shipping_fee(order, price)
            except ValueError:
                await message.reply(
                    "❌ مبلغ واردشده معتبر نیست.\n\n"
                    "مثال:\n"
                    "850000",
                    components=cancel_keyboard()
                )
                return

            order.state = RECEIPT

            await ask_payment(
                message
            )

            return

        # =================================================
        # RECEIPT
        # =================================================

        if order.state == RECEIPT:

            photo_file_id = get_photo_file_id(
                message
            )

            document_file_id = get_document_file_id(
                message
            )

            # -------------------------------------------------
            # PHOTO RECEIPT
            # -------------------------------------------------

            if photo_file_id:

                order.receipt_file_id = (
                    photo_file_id
                )

                order.receipt_type = "photo"

            # -------------------------------------------------
            # DOCUMENT RECEIPT
            # -------------------------------------------------

            elif document_file_id:

                order.receipt_file_id = (
                    document_file_id
                )

                order.receipt_type = "document"

            else:

                await message.reply(
                    "📸 لطفاً تصویر رسید پرداخت را ارسال کنید.",
                    components=cancel_keyboard()
                )

                return

            # -------------------------------------------------
            # دریافت رسید
            # -------------------------------------------------

            order.state = CONFIRM

            # -------------------------------------------------
            # اول اطلاعات کامل برای مشتری
            # -------------------------------------------------

            await message.reply(
                customer_order_summary(
                    order
                ),
                components=confirm_keyboard()
            )

            return

        # =================================================
        # CONFIRM
        # =================================================

        if order.state == CONFIRM:

            # -------------------------------------------------
            # FINAL CONFIRM
            # -------------------------------------------------

            if normalized in [
                "✅ تأیید نهایی سفارش",
                "تأیید نهایی سفارش",
                "تایید نهایی سفارش"
            ]:

                # ارسال کامل سفارش + رسید به ادمین
                await send_final_order_to_admin(
                    user_id,
                    order
                )

                order.state = START

                await message.reply(
                    "🎉 سفارش شما با موفقیت ثبت شد.\n\n"

                    f"🆔 شماره سفارش:\n"
                    f"{order.order_id}\n\n"

                    "✅ سفارش شما برای فروشگاه ارسال شد.\n"
                    "در صورت نیاز، فروشگاه با شما تماس خواهد گرفت.\n\n"

                    "از خرید شما از سورین ممنونیم 🌱",

                    components=main_start_keyboard()
                )

                return

            # -------------------------------------------------
            # EDIT
            # -------------------------------------------------

            if normalized in [
                "✏️ ویرایش سفارش",
                "ویرایش سفارش"
            ]:

                reset_order(
                    user_id
                )

                order = get_order(
                    user_id
                )

                order.state = NAME

                await message.reply(
                    "✏️ ویرایش سفارش شروع شد.\n\n"
                    "لطفاً نام و نام خانوادگی را دوباره وارد کنید.",
                    components=cancel_keyboard()
                )

                return

            await message.reply(
                "لطفاً اطلاعات سفارش را بررسی کنید و "
                "یکی از گزینه‌های زیر را انتخاب کنید.",
                components=confirm_keyboard()
            )

            return

        # =================================================
        # WAITING ADMIN PRICE
        # =================================================

        if order.state == WAITING_ADMIN_PRICE:

            await message.reply(
                "⏳ سفارش شما در انتظار تعیین قیمت توسط فروشگاه است.\n\n"

                f"🆔 شماره سفارش:\n"
                f"{order.order_id}\n\n"

                "بعد از مشخص شدن قیمت، اطلاعات پرداخت "
                "برای شما ارسال می‌شود.",

                components=cancel_keyboard()
            )

            return

    except Exception as e:

        print(
            "CUSTOMER HANDLER ERROR:",
            repr(e)
        )

        try:

            await message.reply(
                "❌ مشکلی در پردازش درخواست پیش آمد.\n"
                "لطفاً دوباره تلاش کنید."
            )

        except Exception:
            pass


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print(
        "==================================="
    )

    print(
        "Suryan Order Bot"
    )

    print(
        "Bot is starting..."
    )

    print(
        "==================================="
    )

    bot.run()
