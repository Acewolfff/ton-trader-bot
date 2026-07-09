"""
Торговые стратегии для бота
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class TradingStrategy:
    """Базовая стратегия"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.positions = []
        self.price_history = []  # [(price, timestamp), ...]
        self.alerts_sent = set()  # Чтобы не спамить одинаковыми алертами
    
    def add_price(self, price: float):
        """Добавляет цену в историю"""
        self.price_history.append((price, datetime.now()))
        # Храним только последние 30 минут
        cutoff = datetime.now() - timedelta(minutes=30)
        self.price_history = [(p, t) for p, t in self.price_history if t > cutoff]
    
    def check_sudden_move(self) -> Optional[Dict]:
        """Проверяет резкие движения цены (3%+ за 5 минут)"""
        if len(self.price_history) < 5:
            return None
        
        now = datetime.now()
        five_min_ago = now - timedelta(minutes=5)
        
        old_prices = [p for p, t in self.price_history if t <= five_min_ago]
        if not old_prices:
            return None
        
        old_price = old_prices[-1]
        current_price = self.price_history[-1][0]
        
        change_pct = ((current_price - old_price) / old_price) * 100
        
        # Создаём уникальный ключ для алерта, чтобы не спамить
        alert_key = f"{abs(change_pct):.1f}_{datetime.now().strftime('%H%M')}"
        
        if abs(change_pct) >= 3 and alert_key not in self.alerts_sent:
            self.alerts_sent.add(alert_key)
            # Чистим старые алерты
            if len(self.alerts_sent) > 100:
                self.alerts_sent = set(list(self.alerts_sent)[-50:])
            
            return {
                'type': 'sudden_move',
                'change_pct': change_pct,
                'old_price': old_price,
                'current_price': current_price,
                'direction': 'up' if change_pct > 0 else 'down',
                'severity': 'high' if abs(change_pct) >= 5 else 'medium'
            }
        
        return None
    
    def check_dca_signal(self, base_price: float, current_price: float, 
                         dca_config: Dict) -> Optional[Dict]:
        """
        Проверяет сигнал для DCA (Dollar Cost Averaging)
        dca_config = {
            'enabled': True,
            'total_amount': 1.0,      # Общая сумма TON
            'parts': 3,                # На сколько частей разбить
            'drop_percent': 1.5,       # Покупать при падении на каждый %
            'bought_parts': 0,         # Сколько частей уже куплено
            'buy_prices': []           # Цены покупок
        }
        """
        if not dca_config.get('enabled'):
            return None
        
        if dca_config['bought_parts'] >= dca_config['parts']:
            return None
        
        drop_from_base = ((base_price - current_price) / base_price) * 100
        target_drop = dca_config['drop_percent'] * (dca_config['bought_parts'] + 1)
        
        if drop_from_base >= target_drop:
            part_amount = dca_config['total_amount'] / dca_config['parts']
            return {
                'type': 'dca_buy',
                'amount': round(part_amount, 2),
                'price': current_price,
                'part': dca_config['bought_parts'] + 1,
                'total_parts': dca_config['parts'],
                'drop_percent': drop_from_base
            }
        
        return None
    
    def check_take_profit(self, position: Dict, current_price: float, 
                          take_profit_pct: float = 2.0) -> Optional[Dict]:
        """
        Проверяет условие тейк-профита
        position = {'amount': 1.0, 'buy_price': 2.5, 'tp_percent': 3.0}
        """
        if not position:
            return None
        
        buy_price = position['buy_price']
        profit_pct = ((current_price - buy_price) / buy_price) * 100
        tp_target = position.get('tp_percent', take_profit_pct)
        
        if profit_pct >= tp_target:
            return {
                'type': 'take_profit',
                'amount': position['amount'],
                'buy_price': buy_price,
                'sell_price': current_price,
                'profit_pct': profit_pct,
                'profit_ton': (current_price - buy_price) * position['amount']
            }
        
        return None
    
    def check_stop_loss(self, position: Dict, current_price: float,
                        stop_loss_pct: float = 5.0) -> Optional[Dict]:
        """Проверяет стоп-лосс"""
        if not position:
            return None
        
        buy_price = position['buy_price']
        loss_pct = ((buy_price - current_price) / buy_price) * 100
        
        if loss_pct >= stop_loss_pct:
            return {
                'type': 'stop_loss',
                'amount': position['amount'],
                'buy_price': buy_price,
                'sell_price': current_price,
                'loss_pct': loss_pct,
                'loss_ton': (buy_price - current_price) * position['amount']
            }
        
        return None


# ========== ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ СТРАТЕГИЙ ==========
user_strategies: Dict[int, TradingStrategy] = {}


def get_strategy(user_id: int) -> TradingStrategy:
    """Получает или создаёт стратегию для пользователя"""
    if user_id not in user_strategies:
        user_strategies[user_id] = TradingStrategy(user_id)
    return user_strategies[user_id]
