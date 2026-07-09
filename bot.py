import asyncio
import aiohttp
import os
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    WebAppInfo
)
from aiogram.filters import Command

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
TONCONNECT_URL = "https://acewolfff.github.io/ton-trader-bot/tonconnect.html"
MANIFEST_URL = "https://acewolfff.github.io/ton-trader-bot/tonconnect-manifest.json"

# ========== ХРАНИЛИЩЕ ПОЛЬЗОВАТЕЛЕЙ ==========
user_sessions = {}

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== ПОЛУЧЕНИЕ ЦЕНЫ TON ==========
async def get_ton_price():
    """Получает цену TON из нескольких источников"""
    
    # Источник 1: CoinGecko
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd',
                timeout=15
            ) as resp:
                data = await resp.json()
                price = data.get('the-open-network', {}).get('usd')
                if price:
                    return {"price": price, "volume": 0}
    except Exception as e:
        print(f"CoinGecko error: {e}")
    
    # Источник 2: Binance
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT',
                timeout=15
            ) as resp:
                data = await resp.json()
                price = float(data.get('price', 0))
                if price:
                    return {"price": price, "volume": 0}
    except Exception as e:
        print(f"Binance error: {e}")
    
    # Источник 3: Bybit
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.bybit.com/v5/market/tickers?category=spot&symbol=TONUSDT',
                timeout=15
            ) as resp:
                data = await resp.json()
                price = float(data['result']['list'][0]['lastPrice'])
                if price:
                    return {"price": price, "volume": 0}
    except Exception as e:
        print(f"Bybit error: {e}")
    
    return None


# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цена TON", callback_data="check_price")],
        [InlineKeyboardButton(text="📈 Купить TON", callback_data="buy_ton")],
        [InlineKeyboardButton(text="📉 Продать TON", callback_data="sell_ton")],
        [InlineKeyboardButton(text="📋 Портфель", callback_data="positions")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="buy_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="buy_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="buy_amount_1.0")],
        [InlineKeyboardButton(text="💳 Через кошелёк (Mini App)", callback_data="buy_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def sell_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="sell_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="sell_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="sell_amount_1.0")],
        [InlineKeyboardButton(text="💳 Через кошелёк (Mini App)", callback_data="sell_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])


# ========== КОМАНДА /start ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    user_sessions[user_id] = {
        'last_price': None,
        'positions': [],
        'alerts_enabled': True
    }
    
    await message.answer(
        "🤖 *TON Trading Bot*\n\n"
        "Я помогаю торговать TON прямо в Telegram.\n\n"
        "• 💰 Проверить цену\n"
        "• 📈 Купить TON\n"
        "• 📉 Продать TON\n"
        "• 💳 Подтверждение через кошелёк\n\n"
        "Выбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ========== ПРОВЕРКА ЦЕНЫ ==========
@dp.callback_query(lambda c: c.data == "check_price")
async def check_price(callback: types.CallbackQuery):
    await callback.answer("⏳ Загружаю цену...")
    
    data = await get_ton_price()
    
    if not data:
        await callback.message.edit_text(
            "❌ Не удалось получить цену. Попробуй позже.",
            reply_markup=main_keyboard()
        )
        return
    
    price = data["price"]
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    old_price = session.get('last_price')
    session['last_price'] = price
    user_sessions[user_id] = session
    
    change_text = ""
    if old_price:
        change = ((price - old_price) / old_price) * 100
        emoji = "🟢" if change >= 0 else "🔴"
        change_text = f"\nИзменение: {emoji} {change:+.2f}%"
    
    await callback.message.edit_text(
        f"💰 *TON / USD*\n\n"
        f"Текущая цена: *${price:.4f}*{change_text}\n"
        f"Обновлено: {datetime.now().strftime('%H:%M:%S')}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ========== ПОКУПКА TON ==========
@dp.callback_query(lambda c: c.data == "buy_ton")
async def buy_ton_menu(callback: types.CallbackQuery):
    data = await get_ton_price()
    price = data["price"] if data else 0
    
    await callback.message.edit_text(
        f"📈 *Покупка TON*\n\nТекущая цена: ${price:.4f}\n\nВыбери сумму или купи через кошелёк:",
        parse_mode="Markdown",
        reply_markup=buy_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("buy_amount_"))
async def buy_ton_amount(callback: types.CallbackQuery):
    amount = float(callback.data.replace("buy_amount_", ""))
    data = await get_ton_price()
    price = data["price"] if data else 0
    user_id = callback.from_user.id
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"buy_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📈 *ПОДТВЕРЖДЕНИЕ ПОКУПКИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Итого: *${price * amount:.2f}*\n\n"
        f"Нажми «Подтверждаю» чтобы записать сделку в портфель.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("buy_confirm_"))
async def buy_confirm(callback: types.CallbackQuery):
    amount = float(callback.data.replace("buy_confirm_", ""))
    data = await get_ton_price()
    price = data["price"] if data else 0
    user_id = callback.from_user.id
    
    session = user_sessions.get(user_id, {'positions': []})
    session['positions'].append({
        'type': 'BUY',
        'amount': amount,
        'price': price,
        'time': datetime.now().isoformat()
    })
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *ПОКУПКА СОВЕРШЕНА*\n\n"
        f"Куплено: *{amount} TON*\n"
        f"По цене: *${price:.4f}*\n"
        f"Сумма: *${price * amount:.2f}*\n\n"
        f"Позиция добавлена в портфель 📋",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "buy_wallet")
async def buy_wallet(callback: types.CallbackQuery):
    """Покупка через кошелёк TonConnect"""
    data = await get_ton_price()
    price = data["price"] if data else 0
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    webapp_url = f"{TONCONNECT_URL}?action=buy&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💎 Открыть кошелёк для покупки",
            web_app=WebAppInfo(url=webapp_url)
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПОКУПКА ЧЕРЕЗ КОШЕЛЁК*\n\n"
        f"Нажми кнопку ниже чтобы открыть Mini App.\n"
        f"Там ты подключишь кошелёк и подтвердишь транзакцию.\n\n"
        f"Цена: *${price:.4f}*\n"
        f"Сумма: *0.5 TON*\n\n"
        f"🔐 Твои ключи остаются только в кошельке!",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ========== ПРОДАЖА TON ==========
@dp.callback_query(lambda c: c.data == "sell_ton")
async def sell_ton_menu(callback: types.CallbackQuery):
    data = await get_ton_price()
    price = data["price"] if data else 0
    
    await callback.message.edit_text(
        f"📉 *Продажа TON*\n\nТекущая цена: ${price:.4f}\n\nВыбери сумму или продай через кошелёк:",
        parse_mode="Markdown",
        reply_markup=sell_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("sell_amount_"))
async def sell_ton_amount(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_amount_", ""))
    data = await get_ton_price()
    price = data["price"] if data else 0
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"sell_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📉 *ПОДТВЕРЖДЕНИЕ ПРОДАЖИ*\n\n"
        f"Сумма: *{amount} TON*\n"
        f"Цена: *${price:.4f}*\n"
        f"Ты получишь: *${price * amount:.2f}*\n\n"
        f"Нажми «Подтверждаю» чтобы записать сделку в портфель.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith("sell_confirm_"))
async def sell_confirm(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_confirm_", ""))
    data = await get_ton_price()
    price = data["price"] if data else 0
    user_id = callback.from_user.id
    
    session = user_sessions.get(user_id, {'positions': []})
    session['positions'].append({
        'type': 'SELL',
        'amount': amount,
        'price': price,
        'time': datetime.now().isoformat()
    })
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *ПРОДАЖА СОВЕРШЕНА*\n\n"
        f"Продано: *{amount} TON*\n"
        f"По цене: *${price:.4f}*\n"
        f"Получено: *${price * amount:.2f}*",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "sell_wallet")
async def sell_wallet(callback: types.CallbackQuery):
    """Продажа через кошелёк TonConnect"""
    data = await get_ton_price()
    price = data["price"] if data else 0
    
    if not price:
        await callback.answer("❌ Не удалось получить цену", show_alert=True)
        return
    
    webapp_url = f"{TONCONNECT_URL}?action=sell&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💰 Открыть кошелёк для продажи",
            web_app=WebAppInfo(url=webapp_url)
        )],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sell_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПРОДАЖА ЧЕРЕЗ КОШЕЛЁК*\n\n"
        f"Нажми кнопку ниже чтобы открыть Mini App.\n"
        f"Подтверди транзакцию в кошельке.\n\n"
        f"Цена: *${price:.4f}*\n"
        f"Сумма: *0.5 TON*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )


# ========== ПОРТФЕЛЬ ==========
@dp.callback_query(lambda c: c.data == "positions")
async def show_positions(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    positions = session.get('positions', [])
    data = await get_ton_price()
    price = data["price"] if data else 0
    
    if not positions:
        await callback.message.edit_text(
            "📋 *ПОРТФЕЛЬ ПУСТ*\n\nУ тебя нет открытых позиций.\nНачни с покупки TON! 📈",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return
    
    buy_positions = [p for p in positions if p['type'] == 'BUY']
    sell_positions = [p for p in positions if p['type'] == 'SELL']
    
    total_bought = sum(p['amount'] for p in buy_positions)
    total_spent = sum(p['amount'] * p['price'] for p in buy_positions)
    total_sold = sum(p['amount'] for p in sell_positions)
    total_received = sum(p['amount'] * p['price'] for p in sell_positions)
    
    avg_buy_price = total_spent / total_bought if total_bought > 0 else 0
    balance = total_bought - total_sold
    current_value = balance * price if price else 0
    
    text = "📋 *ПОРТФЕЛЬ*\n\n"
    text += f"💰 Баланс: *{balance:.2f} TON*\n"
    text += f"💵 Стоимость: *${current_value:.2f}*\n\n"
    text += f"📈 Куплено: {total_bought:.2f} TON\n"
    text += f"📉 Продано: {total_sold:.2f} TON\n"
    
    if avg_buy_price > 0:
        text += f"📊 Средняя цена покупки: ${avg_buy_price:.4f}\n"
    
    if balance > 0 and price:
        pnl = (price - avg_buy_price) * balance
        emoji = "🟢" if pnl >= 0 else "🔴"
        text += f"📊 P&L: {emoji} ${pnl:+.2f}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ========== НАЗАД ==========
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🤖 *Главное меню*\n\nВыбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ========== ПОМОЩЬ ==========
@dp.callback_query(lambda c: c.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ *ПОМОЩЬ*\n\n"
        "• 💰 Цена TON — текущий курс\n"
        "• 📈 Купить TON — выбрать сумму и подтвердить\n"
        "• 📉 Продать TON — выбрать сумму и подтвердить\n"
        "• 💳 Через кошелёк — подтверждение через Tonkeeper\n"
        "• 📋 Портфель — история сделок и баланс\n\n"
        "🔐 Бот не имеет доступа к твоему кошельку.\n"
        "Все сделки через кошелёк подтверждаешь ты.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )


# ========== ЗАПУСК ==========
async def main():
    print("🤖 TON Trading Bot запущен!")
    print(f"🔗 Mini App URL: {TONCONNECT_URL}")
    print(f"📋 Manifest URL: {MANIFEST_URL}")
    
    # Проверяем подключение к API
    data = await get_ton_price()
    if data:
        print(f"✅ API работает. TON = ${data['price']:.4f}")
    else:
        print("⚠️ API не отвечает, но бот запущен")
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
