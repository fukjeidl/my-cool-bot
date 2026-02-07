from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

router = Router()

# Определяем этапы анкеты
class Form(StatesGroup):
    name = State()   # Шаг 1: Имя
    age = State()    # Шаг 2: Возраст
    city = State()   # Шаг 3: Город
