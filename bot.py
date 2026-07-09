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
from strategies import get_strategy, user_strategies
from indicators import get_analyzer, TechnicalAnalyzer

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
TONCONNECT_URL = os.getenv("TONCONNECT_URL", "https://acewolfff.github.io/ton-trader-bot/")

# ========== ХРАНИЛИЩЕ ПОЛЬЗОВАТЕЛЕЙ ==========
user_sessions = {}

# ========== БОТ ==========
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Цена TON", callback_data="check_price")],
        [InlineKeyboardButton(text="📊 Теханализ", callback_data="tech_analysis")],
        [InlineKeyboardButton(text="📈 Купить TON", callback_data="buy_ton")],
        [InlineKeyboardButton(text="📉 Продать TON", callback_data="sell_ton")],
        [InlineKeyboardButton(text="🤖 Авто-трейдинг", callback_data="auto_trade")],
        [InlineKeyboardButton(text="📋 Портфель", callback_data="positions")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
    ])

def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="buy_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="buy_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="buy_amount_1.0")],
        [InlineKeyboardButton(text="💳 Через кошелёк", callback_data="buy_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def sell_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0.1 TON", callback_data="sell_amount_0.1")],
        [InlineKeyboardButton(text="0.5 TON", callback_data="sell_amount_0.5")],
        [InlineKeyboardButton(text="1.0 TON", callback_data="sell_amount_1.0")],
        [InlineKeyboardButton(text="💳 Через кошелёк", callback_data="sell_wallet")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def analysis_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Полный теханализ", callback_data="full_analysis")],
        [InlineKeyboardButton(text="📈 RSI", callback_data="analysis_rsi")],
        [InlineKeyboardButton(text="📉 Скользящие средние", callback_data="analysis_ma")],
        [InlineKeyboardButton(text="📊 Объёмы", callback_data="analysis_volume")],
        [InlineKeyboardButton(text="🏗 Уровни поддержки", callback_data="analysis_sr")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

# ========== ПОЛУЧЕНИЕ ЦЕНЫ ==========
async def get_ton_price():
    """Получает цену TON с объёмом"""
    try:
        async with aiohttp.ClientSession() as session:
            # Пробуем CoinGecko (с объёмом)
            async with session.get(
                'https://api.coingecko.com/api/v3/coins/the-open-network?localization=false&tickers=false&community_data=false&developer_data=false',
                timeout=10
            ) as resp:
                data = await resp.json()
                market_data = data.get('market_data', {})
                price = market_data.get('current_price', {}).get('usd')
                volume = market_data.get('total_volume', {}).get('usd', 0)
                if price:
                    return {"price": price, "volume": volume}
    except:
        pass
    
    try:
        async with aiohttp.ClientSession() as session:
            # Запасной вариант — просто цена
            async with session.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=the-open-network&vs_currencies=usd',
                timeout=10
            ) as resp:
                data = await resp.json()
                price = data.get('the-open-network', {}).get('usd')
                if price:
                    return {"price": price, "volume": 0}
    except:
        pass
    
    return None

# ========== КОМАНДА /start ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    user_sessions[user_id] = {
        'last_price': None,
        'base_price': None,
        'positions': [],
        'auto_trade': False,
        'dca_enabled': False,
        'dca_config': {
            'total_amount': 1.0,
            'parts': 3,
            'drop_percent': 1.5,
            'bought_parts': 0,
            'buy_prices': []
        },
        'tp_percent': 3.0,
        'sl_percent': 7.0,
        'alerts_enabled': True,
        'sudden_move_alerts': True,
        'use_technical_analysis': True  # Новый флаг
    }
    
    await message.answer(
        "🤖 *TON Trading Bot v3.0 — Технический Анализ*\n\n"
        "Теперь с полноценным теханализом!\n\n"
        "🚀 *Индикаторы:*\n"
        "• 📈 RSI — перекупленность/перепроданность\n"
        "• 📉 EMA — скользящие средние и тренды\n"
        "• 📊 Объёмы — подтверждение движений\n"
        "• 🏗 Уровни поддержки/сопротивления\n\n"
        "Выбери действие:",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ЦЕНА ==========
@dp.callback_query(lambda c: c.data == "check_price")
async def check_price(callback: types.CallbackQuery):
    await callback.answer("⏳ Загружаю...")
    
    data = await get_ton_price()
    
    if not data:
        await callback.message.edit_text(
            "❌ Не удалось получить цену.",
            reply_markup=main_keyboard()
        )
        return
    
    price = data["price"]
    volume = data.get("volume", 0)
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    old_price = session.get('last_price')
    session['last_price'] = price
    user_sessions[user_id] = session
    
    # Добавляем в анализатор
    analyzer = get_analyzer()
    analyzer.add_candle(price, volume)
    
    change_text = ""
    if old_price:
        change = ((price - old_price) / old_price) * 100
        emoji = "🟢" if change >= 0 else "🔴"
        change_text = f"\nИзменение: {emoji} {change:+.2f}%"
    
    volume_text = ""
    if volume > 0:
        if volume >= 1_000_000_000:
            volume_text = f"\nОбъём (24ч): *${volume/1_000_000_000:.1f}B*"
        elif volume >= 1_000_000:
            volume_text = f"\nОбъём (24ч): *${volume/1_000_000:.1f}M*"
    
    await callback.message.edit_text(
        f"💰 *TON / USD*\n\n"
        f"Текущая цена: *${price:.4f}*{change_text}{volume_text}\n"
        f"Обновлено: {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"📊 Нажми «Теханализ» для полного разбора.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ТЕХНИЧЕСКИЙ АНАЛИЗ ==========
@dp.callback_query(lambda c: c.data == "tech_analysis")
async def tech_analysis_menu(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📊 *ТЕХНИЧЕСКИЙ АНАЛИЗ*\n\n"
        "Выбери индикатор для подробного разбора:\n\n"
        "• RSI — перекуплен/перепродан\n"
        "• EMA — тренд по скользящим средним\n"
        "• Объёмы — сила движения\n"
        "• Уровни — поддержка и сопротивление",
        parse_mode="Markdown",
        reply_markup=analysis_keyboard()
    )

@dp.callback_query(lambda c: c.data == "full_analysis")
async def full_analysis(callback: types.CallbackQuery):
    """Полный технический анализ"""
    await callback.answer("⏳ Анализирую рынок...")
    
    analyzer = get_analyzer()
    
    # Проверяем, есть ли данные
    if len(analyzer.price_history) < 20:
        # Мало данных — собираем
        for _ in range(20):
            data = await get_ton_price()
            if data:
                analyzer.add_candle(data["price"], data.get("volume", 0))
            await asyncio.sleep(0.5)
    
    summary = analyzer.get_analysis_summary()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Детально RSI", callback_data="analysis_rsi")],
        [InlineKeyboardButton(text="📉 Детально EMA", callback_data="analysis_ma")],
        [InlineKeyboardButton(text="🏗 Детально уровни", callback_data="analysis_sr")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="tech_analysis")]
    ])
    
    await callback.message.edit_text(
        summary,
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data == "analysis_rsi")
async def analysis_rsi(callback: types.CallbackQuery):
    analyzer = get_analyzer()
    rsi = analyzer.calculate_rsi()
    signal = analyzer.get_rsi_signal()
    
    if rsi is None:
        await callback.answer("Недостаточно данных. Нужно минимум 15 точек.", show_alert=True)
        return
    
    text = f"📈 *RSI (Индекс относительной силы)*\n\n"
    text += f"Текущее значение: *{rsi:.1f}*\n\n"
    
    text += "🎯 *Зоны:*\n"
    if rsi >= 70:
        text += "• 🔴 Выше 70 — *Перекуплен*\n"
    else:
        text += "• ⚪ Выше 70 — Перекуплен\n"
    
    if rsi <= 30:
        text += "• 🟢 Ниже 30 — *Перепродан*\n"
    else:
        text += "• ⚪ Ниже 30 — Перепродан\n"
    
    text += f"\n📊 *График:*\n"
    # ASCII-график RSI
    bar_length = int(rsi / 5)
    bar = "█" * bar_length + "░" * (20 - bar_length)
    text += f"0  {bar}  100\n"
    text += f"   {'^' * (bar_length if bar_length > 0 else 0)} {rsi:.1f}\n\n"
    
    text += f"💡 *Сигнал:* {signal['description']}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=analysis_keyboard()
    )

@dp.callback_query(lambda c: c.data == "analysis_ma")
async def analysis_ma(callback: types.CallbackQuery):
    analyzer = get_analyzer()
    signal = analyzer.get_ma_signal()
    
    if signal is None:
        await callback.answer("Недостаточно данных. Нужно минимум 42 точки.", show_alert=True)
        return
    
    current_price = signal["current_price"]
    ema9 = signal["fast_ema"]
    ema21 = signal["slow_ema"]
    
    text = f"📉 *СКОЛЬЗЯЩИЕ СРЕДНИЕ (EMA)*\n\n"
    text += f"Текущая цена: *${current_price:.4f}*\n"
    text += f"EMA 9 (быстрая): *${ema9:.4f}*\n"
    text += f"EMA 21 (медленная): *${ema21:.4f}*\n\n"
    
    # Определяем взаимное расположение
    text += "📊 *Расположение:*\n"
    if current_price > ema9 and current_price > ema21:
        text += "• Цена *выше* обеих средних 📈\n"
    elif current_price < ema9 and current_price < ema21:
        text += "• Цена *ниже* обеих средних 📉\n"
    
    if ema9 > ema21:
        text += "• EMA9 *выше* EMA21 — бычий тренд 🟢\n"
    else:
        text += "• EMA9 *ниже* EMA21 — медвежий тренд 🔴\n"
    
    text += f"\n💡 *Сигнал:* {signal['description']}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=analysis_keyboard()
    )

@dp.callback_query(lambda c: c.data == "analysis_volume")
async def analysis_volume(callback: types.CallbackQuery):
    analyzer = get_analyzer()
    signal = analyzer.get_volume_signal()
    
    if signal is None:
        await callback.answer("Недостаточно данных.", show_alert=True)
        return
    
    text = f"📊 *АНАЛИЗ ОБЪЁМОВ*\n\n"
    text += f"Текущий объём: *${signal['current_volume']:,.0f}*\n"
    text += f"Средний объём: *${signal['avg_volume']:,.0f}*\n"
    text += f"Коэффициент: *x{signal['volume_ratio']:.1f}*\n"
    text += f"Изменение цены: *{signal['price_change']:+.2f}%*\n\n"
    
    # Визуализация
    bar_length = min(int(signal['volume_ratio'] * 3), 20)
    bar = "█" * bar_length + "░" * (20 - bar_length)
    text += f"Объём: {bar} x{signal['volume_ratio']:.1f}\n\n"
    
    text += f"💡 *Анализ:* {signal['description']}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=analysis_keyboard()
    )

@dp.callback_query(lambda c: c.data == "analysis_sr")
async def analysis_sr(callback: types.CallbackQuery):
    analyzer = get_analyzer()
    signal = analyzer.get_sr_signal()
    levels = analyzer.find_support_resistance()
    
    if signal is None:
        await callback.answer("Недостаточно данных.", show_alert=True)
        return
    
    current = levels["current_price"]
    support = levels["nearest_support"]
    resistance = levels["nearest_resistance"]
    
    text = f"🏗 *УРОВНИ ПОДДЕРЖКИ И СОПРОТИВЛЕНИЯ*\n\n"
    text += f"Текущая цена: *${current:.4f}*\n\n"
    
    if resistance:
        distance = ((resistance - current) / current) * 100
        text += f"🔴 Сопротивление: *${resistance:.4f}*\n"
        text += f"   (на {distance:.2f}% выше)\n\n"
    
    text += f"   💰 *${current:.4f}* ← текущая\n\n"
    
    if support:
        distance = ((current - support) / current) * 100
        text += f"🟢 Поддержка: *${support:.4f}*\n"
        text += f"   (на {distance:.2f}% ниже)\n\n"
    
    text += f"💡 *Сигнал:* {signal['description']}"
    
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=analysis_keyboard()
    )

# ========== ПОКУПКА (без изменений) ==========
@dp.callback_query(lambda c: c.data == "buy_ton")
async def buy_ton_menu(callback: types.CallbackQuery):
    data = await get_ton_price()
    price = data["price"] if data else 0
    await callback.message.edit_text(
        f"📈 *Покупка TON*\n\nТекущая цена: ${price:.4f}\n\nВыбери сумму:",
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
        f"📈 *ПОДТВЕРЖДЕНИЕ*\n\nСумма: *{amount} TON*\nЦена: *${price:.4f}*\nИтого: *${price * amount:.2f}*",
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
        'type': 'BUY', 'amount': amount, 'price': price,
        'time': datetime.now().isoformat(),
        'tp_percent': session.get('tp_percent', 3.0),
        'sl_percent': session.get('sl_percent', 7.0)
    })
    if not session.get('base_price'):
        session['base_price'] = price
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *КУПЛЕНО {amount} TON* по ${price:.4f}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "buy_wallet")
async def buy_wallet(callback: types.CallbackQuery):
    data = await get_ton_price()
    price = data["price"] if data else 0
    webapp_url = f"{TONCONNECT_URL}?action=buy&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Открыть кошелёк", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="buy_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПОКУПКА ЧЕРЕЗ КОШЕЛЁК*\n\nЦена: ${price:.4f}\nСумма: 0.5 TON\n\nНажми кнопку для подтверждения в кошельке.",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ========== ПРОДАЖА (без изменений) ==========
@dp.callback_query(lambda c: c.data == "sell_ton")
async def sell_ton_menu(callback: types.CallbackQuery):
    data = await get_ton_price()
    price = data["price"] if data else 0
    await callback.message.edit_text(
        f"📉 *Продажа TON*\n\nТекущая цена: ${price:.4f}\n\nВыбери сумму:",
        parse_mode="Markdown",
        reply_markup=sell_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("sell_amount_"))
async def sell_ton_amount(callback: types.CallbackQuery):
    amount = float(callback.data.replace("sell_amount_", ""))
    data = await get_ton_price()
    price = data["price"] if data else 0
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтверждаю", callback_data=f"sell_confirm_{amount}")],
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_to_main")]
    ])
    
    await callback.message.edit_text(
        f"📉 *ПОДТВЕРЖДЕНИЕ*\n\nСумма: *{amount} TON*\nЦена: *${price:.4f}*\nПолучишь: *${price * amount:.2f}*",
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
        'type': 'SELL', 'amount': amount, 'price': price,
        'time': datetime.now().isoformat()
    })
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ *ПРОДАНО {amount} TON* по ${price:.4f}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@dp.callback_query(lambda c: c.data == "sell_wallet")
async def sell_wallet(callback: types.CallbackQuery):
    data = await get_ton_price()
    price = data["price"] if data else 0
    webapp_url = f"{TONCONNECT_URL}?action=sell&amount=0.5&price={price}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Открыть кошелёк", web_app=WebAppInfo(url=webapp_url))],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="sell_ton")]
    ])
    
    await callback.message.edit_text(
        f"💳 *ПРОДАЖА ЧЕРЕЗ КОШЕЛЁК*\n\nЦена: ${price:.4f}\nСумма: 0.5 TON",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ========== АВТО-ТРЕЙДИНГ ==========
@dp.callback_query(lambda c: c.data == "auto_trade")
async def auto_trade_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    auto_status = "✅" if session.get('auto_trade') else "❌"
    dca_status = "✅" if session.get('dca_enabled') else "❌"
    tech_status = "✅" if session.get('use_technical_analysis', True) else "❌"
    
    await callback.message.edit_text(
        f"🤖 *АВТО-ТРЕЙДИНГ*\n\n"
        f"Авто-сигналы: {auto_status}\n"
        f"DCA: {dca_status}\n"
        f"Теханализ: {tech_status}\n"
        f"Тейк-профит: {session.get('tp_percent', 3.0)}%\n"
        f"Стоп-лосс: {session.get('sl_percent', 7.0)}%",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Авто-сигналы: {auto_status}", callback_data="toggle_auto")],
            [InlineKeyboardButton(text=f"DCA: {dca_status}", callback_data="toggle_dca")],
            [InlineKeyboardButton(text=f"Теханализ: {tech_status}", callback_data="toggle_tech")],
            [InlineKeyboardButton(text="⚙️ DCA", callback_data="setup_dca")],
            [InlineKeyboardButton(text="🎯 Тейк-профит", callback_data="setup_tp")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )

@dp.callback_query(lambda c: c.data == "toggle_tech")
async def toggle_tech(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['use_technical_analysis'] = not session.get('use_technical_analysis', True)
    user_sessions[user_id] = session
    
    await callback.answer(f"Теханализ {'включен' if session['use_technical_analysis'] else 'выключен'}", show_alert=True)
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_auto")
async def toggle_auto(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['auto_trade'] = not session.get('auto_trade', False)
    user_sessions[user_id] = session
    await callback.answer(f"Авто-сигналы {'включены' if session['auto_trade'] else 'выключены'}", show_alert=True)
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_dca")
async def toggle_dca(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['dca_enabled'] = not session.get('dca_enabled', False)
    if session['dca_enabled']:
        data = await get_ton_price()
        if data:
            session['base_price'] = data["price"]
    user_sessions[user_id] = session
    await callback.answer(f"DCA {'включен' if session['dca_enabled'] else 'выключен'}", show_alert=True)
    await auto_trade_menu(callback)

@dp.callback_query(lambda c: c.data == "setup_dca")
async def setup_dca(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "⚙️ *НАСТРОЙКА DCA*\n\nВыбери сумму:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="0.5 TON (3 части)", callback_data="dca_set_0.5_3")],
            [InlineKeyboardButton(text="1.0 TON (3 части)", callback_data="dca_set_1.0_3")],
            [InlineKeyboardButton(text="2.0 TON (4 части)", callback_data="dca_set_2.0_4")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("dca_set_"))
async def dca_set(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    total = float(parts[2])
    parts_count = int(parts[3])
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['dca_config'] = {
        'total_amount': total, 'parts': parts_count,
        'drop_percent': 1.5, 'bought_parts': 0, 'buy_prices': []
    }
    session['dca_enabled'] = True
    data = await get_ton_price()
    if data:
        session['base_price'] = data["price"]
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ DCA настроен: {total} TON / {parts_count} частей",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
    )

@dp.callback_query(lambda c: c.data == "setup_tp")
async def setup_tp(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "🎯 *ТЕЙК-ПРОФИТ*\n\nПри каком росте продавать?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="2%", callback_data="tp_set_2")],
            [InlineKeyboardButton(text="3%", callback_data="tp_set_3")],
            [InlineKeyboardButton(text="5%", callback_data="tp_set_5")],
            [InlineKeyboardButton(text="10%", callback_data="tp_set_10")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
    )

@dp.callback_query(lambda c: c.data.startswith("tp_set_"))
async def tp_set(callback: types.CallbackQuery):
    tp = float(callback.data.replace("tp_set_", ""))
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['tp_percent'] = tp
    user_sessions[user_id] = session
    
    await callback.message.edit_text(
        f"✅ Тейк-профит: {tp}%",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="auto_trade")]
        ])
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
        await callback.message.edit_text("📋 Портфель пуст.", reply_markup=main_keyboard())
        return
    
    buy_pos = [p for p in positions if p['type'] == 'BUY']
    sell_pos = [p for p in positions if p['type'] == 'SELL']
    total_bought = sum(p['amount'] for p in buy_pos)
    total_sold = sum(p['amount'] for p in sell_pos)
    balance = total_bought - total_sold
    
    text = f"📋 *ПОРТФЕЛЬ*\n\n💰 Баланс: *{balance:.2f} TON* (${balance * price:.2f})\n"
    text += f"📈 Куплено: {total_bought:.2f} TON\n📉 Продано: {total_sold:.2f} TON"
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ========== НАСТРОЙКИ ==========
@dp.callback_query(lambda c: c.data == "settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    
    await callback.message.edit_text(
        f"⚙️ *НАСТРОЙКИ*\n\n"
        f"🔔 Сигналы: {'✅' if session.get('alerts_enabled', True) else '❌'}\n"
        f"⚡ Резкие движения: {'✅' if session.get('sudden_move_alerts', True) else '❌'}\n"
        f"📊 Теханализ: {'✅' if session.get('use_technical_analysis', True) else '❌'}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Сигналы вкл/выкл", callback_data="toggle_alerts")],
            [InlineKeyboardButton(text="⚡ Резкие алерты вкл/выкл", callback_data="toggle_sudden")],
            [InlineKeyboardButton(text="🗑 Сбросить историю", callback_data="reset_history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
    )

@dp.callback_query(lambda c: c.data == "toggle_alerts")
async def toggle_alerts(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['alerts_enabled'] = not session.get('alerts_enabled', True)
    user_sessions[user_id] = session
    await callback.answer(f"Сигналы {'включены' if session['alerts_enabled'] else 'выключены'}", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "toggle_sudden")
async def toggle_sudden(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['sudden_move_alerts'] = not session.get('sudden_move_alerts', True)
    user_sessions[user_id] = session
    await callback.answer(f"Резкие алерты {'включены' if session['sudden_move_alerts'] else 'выключены'}", show_alert=True)
    await settings_menu(callback)

@dp.callback_query(lambda c: c.data == "reset_history")
async def reset_history(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    session = user_sessions.get(user_id, {})
    session['positions'] = []
    session['base_price'] = None
    session['dca_config']['bought_parts'] = 0
    session['dca_config']['buy_prices'] = []
    user_sessions[user_id] = session
    await callback.message.edit_text("🗑 История сброшена.", reply_markup=main_keyboard())

# ========== НАЗАД ==========
@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("🤖 Главное меню:", reply_markup=main_keyboard())

# ========== ПОМОЩЬ ==========
@dp.callback_query(lambda c: c.data == "help")
async def help_cmd(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "❓ *ПОМОЩЬ*\n\n"
        "• 💰 Цена TON — текущий курс\n"
        "• 📊 Теханализ — RSI, EMA, объёмы, уровни\n"
        "• 📈/📉 Купить/Продать — сделки\n"
        "• 🤖 Авто-трейдинг — сигналы 24/7\n\n"
        "🔐 Безопасность: ключи только у тебя.",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ========== ФОНОВЫЙ МОНИТОРИНГ ==========
async def background_monitor():
    """Фоновый мониторинг с теханализом"""
    last_price = None
    
    while True:
        await asyncio.sleep(45)
        
        data = await get_ton_price()
        if not data:
            continue
        
        price = data["price"]
        volume = data.get("volume", 0)
        
        # Добавляем в глобальный анализатор
        analyzer = get_analyzer()
        analyzer.add_candle(price, volume)
        
        if not last_price:
            last_price = price
            continue
        
        change_pct = ((price - last_price) / last_price) * 100
        
        for user_id, session in user_sessions.items():
            strategy = get_strategy(user_id)
            strategy.add_price(price)
            
            # Проверяем, использует ли пользователь теханализ
            use_tech = session.get('use_technical_analysis', True)
            
            if use_tech and len(analyzer.price_history) >= 20:
                # Используем сводный сигнал из индикаторов
                combined = analyzer.get_combined_signal()
                
                if combined["signal"] != "NEUTRAL" and combined["confidence"] >= 50:
                    if combined["signal"] == "BUY" and session.get('auto_trade'):
                        await send_tech_signal(user_id, combined, price)
                    elif combined["signal"] == "SELL" and session.get('auto_trade'):
                        await send_tech_signal(user_id, combined, price)
            else:
                # Старая логика по проценту изменения
                if session.get('auto_trade'):
                    if change_pct <= -1:
                        await send_simple_signal(user_id, 'BUY', price, abs(change_pct))
                    elif change_pct >= 2:
                        await send_simple_signal(user_id, 'SELL', price, change_pct)
            
            # DCA стратегия (без изменений)
            if session.get('dca_enabled'):
                dca_signal = strategy.check_dca_signal(
                    session.get('base_price', price),
                    price,
                    session.get('dca_config', {})
                )
                if dca_signal:
                    await send_dca_signal(user_id, dca_signal)
                    session['dca_config']['bought_parts'] += 1
                    session['dca_config']['buy_prices'].append(price)
            
            # Тейк-профит и стоп-лосс (без изменений)
            for position in session.get('positions', []):
                if position['type'] != 'BUY':
                    continue
                
                tp_signal = strategy.check_take_profit(position, price, session.get('tp_percent', 3.0))
                if tp_signal:
                    await send_tp_signal(user_id, tp_signal)
                
                sl_signal = strategy.check_stop_loss(position, price, session.get('sl_percent', 7.0))
                if sl_signal:
                    await send_sl_signal(user_id, sl_signal)
        
        last_price = price

async def send_tech_signal(user_id, combined, price):
    """Отправляет сигнал на основе теханализа"""
    emoji = "🟢" if combined["signal"] == "BUY" else "🔴"
    action = "ПОКУПКУ" if combined["signal"] == "BUY" else "ПРОДАЖУ"
    
    # Формируем детали сигнала
    details = ""
    for s in combined.get("details", [])[:3]:
        if s["signal"] == combined["signal"]:
            details += f"• {s.get('description', '')}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'💎 Купить' if combined['signal'] == 'BUY' else '💰 Продать'} 0.5 TON",
            callback_data=f"{'buy' if combined['signal'] == 'BUY' else 'sell'}_amount_0.5"
        )],
        [InlineKeyboardButton(text="📊 Полный анализ", callback_data="full_analysis")],
        [InlineKeyboardButton(text="🔙 Игнорировать", callback_data="back_to_main")]
    ])
    
    try:
        await bot.send_message(
            user_id,
            f"🔔 *СИГНАЛ НА {action}*\n\n"
            f"{emoji} Уверенность: *{combined['confidence']:.0f}%*\n"
            f"💰 Цена: *${price:.4f}*\n"
            f"Активных индикаторов: {combined['active_indicators']}/4\n\n"
            f"{details}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

async def send_simple_signal(user_id, signal_type, price, change_pct):
    """Простой сигнал по проценту (старая логика)"""
    emoji = "📈" if signal_type == 'BUY' else "📉"
    action = "ПОКУПКУ" if signal_type == 'BUY' else "ПРОДАЖУ"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'💎 Купить' if signal_type == 'BUY' else '💰 Продать'} 0.5 TON",
            callback_data=f"{'buy' if signal_type == 'BUY' else 'sell'}_amount_0.5"
        )],
        [InlineKeyboardButton(text="🔙 Игнорировать", callback_data="back_to_main")]
    ])
    
    try:
        await bot.send_message(
            user_id,
            f"🔔 *СИГНАЛ НА {action}*\n\n{emoji} Изменение: *{change_pct:+.1f}%*\nЦена: *${price:.4f}*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

async def send_dca_signal(user_id, signal):
    try:
        await bot.send_message(
            user_id,
            f"📊 *DCA*: Покупка {signal['part']}/{signal['total_parts']}\n"
            f"Сумма: {signal['amount']} TON\nЦена: ${signal['price']:.4f}",
            parse_mode="Markdown"
        )
    except:
        pass

async def send_tp_signal(user_id, signal):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Продать", callback_data=f"sell_amount_{signal['amount']}")]
    ])
    try:
        await bot.send_message(
            user_id,
            f"🎯 *ТЕЙК-ПРОФИТ!* +{signal['profit_pct']:.1f}%\nПрибыль: ${signal['profit_ton']:.2f}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

async def send_sl_signal(user_id, signal):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Продать", callback_data=f"sell_amount_{signal['amount']}")]
    ])
    try:
        await bot.send_message(
            user_id,
            f"🛑 *СТОП-ЛОСС!* -{signal['loss_pct']:.1f}%\nУбыток: ${signal['loss_ton']:.2f}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

# ========== ЗАПУСК ==========
async def main():
    print("🤖 TON Trading Bot v3.0 — Технический Анализ")
    print("📊 Индикаторы: RSI, EMA, Объёмы, Уровни поддержки/сопротивления")
    
    # Загружаем начальные данные для анализатора
    analyzer = get_analyzer()
    for _ in range(30):
        data = await get_ton_price()
        if data:
            analyzer.add_candle(data["price"], data.get("volume", 0))
        await asyncio.sleep(1)
    
    print(f"✅ Загружено {len(analyzer.price_history)} точек данных")
    
    # Запускаем мониторинг
    asyncio.create_task(background_monitor())
    
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
