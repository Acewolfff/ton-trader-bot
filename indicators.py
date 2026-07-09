"""
Технические индикаторы для торгового бота
RSI, MACD, скользящие средние, уровни поддержки/сопротивления, объёмы
"""

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


class TechnicalAnalyzer:
    """Класс для технического анализа цены TON"""
    
    def __init__(self, max_history: int = 200):
        self.price_history: List[Dict] = []  # [{"price": 2.5, "time": datetime, "volume": 1000}, ...]
        self.max_history = max_history
    
    def add_candle(self, price: float, volume: float = 0, timestamp: datetime = None):
        """Добавляет новую свечу (цену) в историю"""
        if timestamp is None:
            timestamp = datetime.now()
        
        self.price_history.append({
            "price": price,
            "time": timestamp,
            "volume": volume
        })
        
        # Ограничиваем историю
        if len(self.price_history) > self.max_history:
            self.price_history = self.price_history[-self.max_history:]
    
    def get_prices(self, periods: int = None) -> List[float]:
        """Возвращает список цен за последние N периодов"""
        if periods:
            history = self.price_history[-periods:]
        else:
            history = self.price_history
        return [c["price"] for c in history]
    
    def get_volumes(self, periods: int = None) -> List[float]:
        """Возвращает список объёмов"""
        if periods:
            history = self.price_history[-periods:]
        else:
            history = self.price_history
        return [c.get("volume", 0) for c in history]
    
    # ==================== RSI ====================
    def calculate_rsi(self, periods: int = 14) -> Optional[float]:
        """
        RSI (Relative Strength Index) — индекс относительной силы
        Значения:
        - Выше 70 = перекуплен (сигнал на продажу)
        - Ниже 30 = перепродан (сигнал на покупку)
        - Вокруг 50 = нейтрально
        """
        prices = self.get_prices(periods + 1)
        
        if len(prices) < periods + 1:
            return None
        
        # Считаем изменения
        deltas = np.diff(prices)
        
        # Средний рост и среднее падение
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi, 2)
    
    def get_rsi_signal(self) -> Optional[Dict]:
        """Возвращает торговый сигнал на основе RSI"""
        rsi = self.calculate_rsi()
        
        if rsi is None:
            return None
        
        signal = {
            "indicator": "RSI",
            "value": rsi
        }
        
        if rsi >= 70:
            signal.update({
                "signal": "SELL",
                "strength": "strong" if rsi >= 80 else "moderate",
                "description": f"Перекуплен (RSI={rsi}). Возможна коррекция вниз."
            })
        elif rsi <= 30:
            signal.update({
                "signal": "BUY",
                "strength": "strong" if rsi <= 20 else "moderate",
                "description": f"Перепродан (RSI={rsi}). Возможен отскок вверх."
            })
        else:
            signal.update({
                "signal": "NEUTRAL",
                "strength": "weak",
                "description": f"Нейтральная зона (RSI={rsi})"
            })
        
        return signal
    
    # ==================== СКОЛЬЗЯЩИЕ СРЕДНИЕ ====================
    def calculate_sma(self, periods: int) -> Optional[float]:
        """Простая скользящая средняя (SMA)"""
        prices = self.get_prices(periods)
        
        if len(prices) < periods:
            return None
        
        return round(np.mean(prices), 6)
    
    def calculate_ema(self, periods: int) -> Optional[float]:
        """Экспоненциальная скользящая средняя (EMA)"""
        prices = self.get_prices(periods * 2)  # Берём больше данных для точности
        
        if len(prices) < periods:
            return None
        
        # Начальное значение — SMA за periods
        sma = np.mean(prices[:periods])
        
        # Множитель
        multiplier = 2 / (periods + 1)
        
        # Рекурсивно считаем EMA
        ema = sma
        for price in prices[periods:]:
            ema = (price - ema) * multiplier + ema
        
        return round(ema, 6)
    
    def get_ma_signal(self) -> Optional[Dict]:
        """
        Сигнал на пересечении скользящих средних
        Быстрая (9) и медленная (21) EMA
        """
        fast_ema = self.calculate_ema(9)
        slow_ema = self.calculate_ema(21)
        current_price = self.get_prices(1)
        
        if not all([fast_ema, slow_ema, current_price]):
            return None
        
        current_price = current_price[0]
        
        signal = {
            "indicator": "MA_CROSS",
            "fast_ema": fast_ema,
            "slow_ema": slow_ema,
            "current_price": current_price
        }
        
        # Золотой крест (быстрая пересекает медленную снизу вверх)
        if fast_ema > slow_ema and current_price > fast_ema:
            signal.update({
                "signal": "BUY",
                "strength": "strong",
                "description": f"Золотой крест. Тренд вверх. EMA9={fast_ema:.4f} > EMA21={slow_ema:.4f}"
            })
        # Мёртвый крест (быстрая пересекает медленную сверху вниз)
        elif fast_ema < slow_ema and current_price < fast_ema:
            signal.update({
                "signal": "SELL",
                "strength": "strong",
                "description": f"Мёртвый крест. Тренд вниз. EMA9={fast_ema:.4f} < EMA21={slow_ema:.4f}"
            })
        # Цена выше обеих средних — восходящий тренд
        elif current_price > fast_ema and current_price > slow_ema:
            signal.update({
                "signal": "BUY",
                "strength": "moderate",
                "description": "Цена выше скользящих средних. Восходящий тренд."
            })
        # Цена ниже обеих средних — нисходящий тренд
        elif current_price < fast_ema and current_price < slow_ema:
            signal.update({
                "signal": "SELL",
                "strength": "moderate",
                "description": "Цена ниже скользящих средних. Нисходящий тренд."
            })
        else:
            signal.update({
                "signal": "NEUTRAL",
                "strength": "weak",
                "description": "Боковое движение. Сигналов нет."
            })
        
        return signal
    
    # ==================== ОБЪЁМЫ ====================
    def get_volume_signal(self) -> Optional[Dict]:
        """
        Анализ объёмов торгов
        Большой объём + рост цены = сильный сигнал на покупку
        Большой объём + падение цены = сильный сигнал на продажу
        """
        prices = self.get_prices(5)
        volumes = self.get_volumes(5)
        
        if len(prices) < 3 or len(volumes) < 3:
            return None
        
        avg_volume = np.mean(volumes[:-1]) if len(volumes) > 1 else volumes[0]
        current_volume = volumes[-1]
        current_price = prices[-1]
        prev_price = prices[-2] if len(prices) > 1 else current_price
        
        # Изменение цены
        price_change = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0
        
        # Коэффициент объёма (во сколько раз текущий объём больше среднего)
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        signal = {
            "indicator": "VOLUME",
            "current_volume": current_volume,
            "avg_volume": round(avg_volume, 2),
            "volume_ratio": round(volume_ratio, 2),
            "price_change": round(price_change, 2)
        }
        
        # Высокий объём
        if volume_ratio >= 2.0:
            if price_change > 0.5:
                signal.update({
                    "signal": "BUY",
                    "strength": "strong",
                    "description": f"Рост на высоком объёме (x{volume_ratio:.1f}). Уверенный сигнал на покупку."
                })
            elif price_change < -0.5:
                signal.update({
                    "signal": "SELL",
                    "strength": "strong",
                    "description": f"Падение на высоком объёме (x{volume_ratio:.1f}). Уверенный сигнал на продажу."
                })
            else:
                signal.update({
                    "signal": "NEUTRAL",
                    "strength": "moderate",
                    "description": f"Высокий объём (x{volume_ratio:.1f}), но цена почти не изменилась."
                })
        elif volume_ratio >= 1.3:
            if price_change > 0.3:
                signal.update({
                    "signal": "BUY",
                    "strength": "moderate",
                    "description": f"Умеренный рост на объёме (x{volume_ratio:.1f})."
                })
            elif price_change < -0.3:
                signal.update({
                    "signal": "SELL",
                    "strength": "moderate",
                    "description": f"Умеренное падение на объёме (x{volume_ratio:.1f})."
                })
            else:
                signal.update({
                    "signal": "NEUTRAL",
                    "strength": "weak",
                    "description": "Объём в норме, цена стабильна."
                })
        else:
            signal.update({
                "signal": "NEUTRAL",
                "strength": "weak",
                "description": "Низкий объём. Сигнал не формируется."
            })
        
        return signal
    
    # ==================== УРОВНИ ПОДДЕРЖКИ/СОПРОТИВЛЕНИЯ ====================
    def find_support_resistance(self, lookback: int = 50) -> Dict:
        """
        Находит уровни поддержки и сопротивления
        на основе локальных максимумов и минимумов
        """
        prices = self.get_prices(lookback)
        
        if len(prices) < 10:
            return {"support": None, "resistance": None}
        
        current_price = prices[-1]
        
        # Ищем локальные минимумы (поддержка)
        supports = []
        for i in range(2, len(prices) - 2):
            if prices[i] < prices[i-1] and prices[i] < prices[i-2] and \
               prices[i] < prices[i+1] and prices[i] < prices[i+2]:
                if prices[i] < current_price:  # Поддержка ниже текущей цены
                    supports.append(prices[i])
        
        # Ищем локальные максимумы (сопротивление)
        resistances = []
        for i in range(2, len(prices) - 2):
            if prices[i] > prices[i-1] and prices[i] > prices[i-2] and \
               prices[i] > prices[i+1] and prices[i] > prices[i+2]:
                if prices[i] > current_price:  # Сопротивление выше текущей цены
                    resistances.append(prices[i])
        
        # Группируем близкие уровни (в пределах 0.5%)
        def cluster_levels(levels: List[float], threshold: float = 0.005) -> List[float]:
            if not levels:
                return []
            
            levels = sorted(levels)
            clusters = []
            current_cluster = [levels[0]]
            
            for level in levels[1:]:
                if (level - current_cluster[-1]) / current_cluster[-1] < threshold:
                    current_cluster.append(level)
                else:
                    clusters.append(np.mean(current_cluster))
                    current_cluster = [level]
            
            clusters.append(np.mean(current_cluster))
            return [round(c, 6) for c in clusters]
        
        supports = cluster_levels(supports)
        resistances = cluster_levels(resistances)
        
        # Ближайшие уровни
        nearest_support = None
        nearest_resistance = None
        
        for s in reversed(supports):  # Ближайшая поддержка снизу
            if s < current_price:
                nearest_support = s
                break
        
        for r in resistances:  # Ближайшее сопротивление сверху
            if r > current_price:
                nearest_resistance = r
                break
        
        return {
            "current_price": current_price,
            "nearest_support": nearest_support,
            "nearest_resistance": nearest_resistance,
            "all_supports": supports[-3:] if len(supports) > 3 else supports,
            "all_resistances": resistances[:3] if len(resistances) > 3 else resistances
        }
    
    def get_sr_signal(self) -> Optional[Dict]:
        """Торговый сигнал на основе уровней поддержки/сопротивления"""
        levels = self.find_support_resistance()
        current_price = levels["current_price"]
        support = levels["nearest_support"]
        resistance = levels["nearest_resistance"]
        
        if support is None and resistance is None:
            return None
        
        signal = {
            "indicator": "SUPPORT_RESISTANCE",
            "current_price": current_price,
            "support": support,
            "resistance": resistance
        }
        
        # Отскок от поддержки
        if support:
            distance_to_support = ((current_price - support) / support) * 100
            if distance_to_support <= 0.5:  # В пределах 0.5% от поддержки
                signal.update({
                    "signal": "BUY",
                    "strength": "strong",
                    "description": f"Цена у поддержки ${support:.4f} (отклонение {distance_to_support:.2f}%). Возможен отскок вверх."
                })
                return signal
        
        # Подход к сопротивлению
        if resistance:
            distance_to_resistance = ((resistance - current_price) / current_price) * 100
            if distance_to_resistance <= 0.5:  # В пределах 0.5% от сопротивления
                signal.update({
                    "signal": "SELL",
                    "strength": "strong",
                    "description": f"Цена у сопротивления ${resistance:.4f} (отклонение {distance_to_resistance:.2f}%). Возможен откат вниз."
                })
                return signal
        
        signal.update({
            "signal": "NEUTRAL",
            "strength": "weak",
            "description": f"Поддержка: ${support:.4f}, Сопротивление: ${resistance:.4f}. Цена в середине диапазона."
        })
        
        return signal
    
    # ==================== СВОДНЫЙ СИГНАЛ ====================
    def get_combined_signal(self) -> Dict:
        """
        Объединяет все индикаторы и выдаёт сводный сигнал
        с весом каждого индикатора
        """
        signals = []
        
        # Собираем сигналы со всех индикаторов
        rsi = self.get_rsi_signal()
        ma = self.get_ma_signal()
        volume = self.get_volume_signal()
        sr = self.get_sr_signal()
        
        all_signals = [rsi, ma, volume, sr]
        
        # Веса индикаторов
        weights = {
            "RSI": 0.20,
            "MA_CROSS": 0.30,     # Скользящие средние — самый важный
            "VOLUME": 0.25,        # Объёмы подтверждают тренд
            "SUPPORT_RESISTANCE": 0.25
        }
        
        total_score = 0
        active_signals = []
        
        for s in all_signals:
            if s is None:
                continue
            
            indicator = s["indicator"]
            weight = weights.get(indicator, 0.2)
            
            if s["signal"] == "BUY":
                if s["strength"] == "strong":
                    total_score += weight * 2
                else:
                    total_score += weight * 1
            elif s["signal"] == "SELL":
                if s["strength"] == "strong":
                    total_score -= weight * 2
                else:
                    total_score -= weight * 1
            
            active_signals.append(s)
        
        # Определяем итоговый сигнал
        if total_score >= 0.4:
            final_signal = "BUY"
            confidence = min(abs(total_score) * 100, 95)
        elif total_score <= -0.4:
            final_signal = "SELL"
            confidence = min(abs(total_score) * 100, 95)
        else:
            final_signal = "NEUTRAL"
            confidence = max(50 - abs(total_score) * 50, 10)
        
        return {
            "signal": final_signal,
            "score": round(total_score, 3),
            "confidence": round(confidence, 1),
            "active_indicators": len(active_signals),
            "details": active_signals,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_analysis_summary(self) -> str:
        """
        Возвращает текстовую сводку для отправки пользователю
        """
        combined = self.get_combined_signal()
        rsi = self.calculate_rsi()
        ema9 = self.calculate_ema(9)
        ema21 = self.calculate_ema(21)
        levels = self.find_support_resistance()
        
        # Эмодзи для сигнала
        if combined["signal"] == "BUY":
            signal_emoji = "🟢"
            signal_text = "ПОКУПКА"
        elif combined["signal"] == "SELL":
            signal_emoji = "🔴"
            signal_text = "ПРОДАЖА"
        else:
            signal_emoji = "⚪"
            signal_text = "НЕЙТРАЛЬНО"
        
        text = f"📊 *ТЕХНИЧЕСКИЙ АНАЛИЗ TON*\n\n"
        text += f"Сигнал: {signal_emoji} *{signal_text}*\n"
        text += f"Уверенность: *{combined['confidence']:.0f}%*\n"
        text += f"Активных индикаторов: {combined['active_indicators']}/4\n\n"
        
        text += "📈 *Индикаторы:*\n"
        
        # RSI
        if rsi:
            rsi_emoji = "🔴" if rsi >= 70 else ("🟢" if rsi <= 30 else "⚪")
            text += f"• RSI(14): {rsi_emoji} *{rsi:.1f}*\n"
        
        # Скользящие средние
        if ema9 and ema21:
            text += f"• EMA9: *${ema9:.4f}*\n"
            text += f"• EMA21: *${ema21:.4f}*\n"
        
        # Уровни
        if levels["nearest_support"]:
            text += f"• Поддержка: *${levels['nearest_support']:.4f}*\n"
        if levels["nearest_resistance"]:
            text += f"• Сопротивление: *${levels['nearest_resistance']:.4f}*\n"
        
        # Объём
        volume_signal = self.get_volume_signal()
        if volume_signal and volume_signal.get("volume_ratio", 1) >= 1.3:
            text += f"• Объём: *x{volume_signal['volume_ratio']:.1f}* от среднего\n"
        
        # Пояснение
        if combined["signal"] != "NEUTRAL":
            text += f"\n💡 *Рекомендация:* "
            if combined["confidence"] >= 70:
                text += "Сильный сигнал. Можно действовать."
            elif combined["confidence"] >= 50:
                text += "Умеренный сигнал. Рекомендуется подтверждение."
            else:
                text += "Слабый сигнал. Лучше подождать."
        
        return text


# ========== ГЛОБАЛЬНЫЙ АНАЛИЗАТОР ==========
global_analyzer = TechnicalAnalyzer(max_history=300)


def get_analyzer() -> TechnicalAnalyzer:
    """Возвращает глобальный экземпляр анализатора"""
    return global_analyzer
