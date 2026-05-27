# states.py
from aiogram.fsm.state import State, StatesGroup


class AddChannel(StatesGroup):
    waiting = State()

class AddKeyword(StatesGroup):
    waiting = State()

class DeleteChannel(StatesGroup):
    waiting = State()

class DeleteKeyword(StatesGroup):
    waiting = State()

class AddAdminUser(StatesGroup):
    waiting = State()

class DeleteAdminUser(StatesGroup):
    waiting = State()

class CalendarState(StatesGroup):
    picking_from = State()
    picking_to   = State()

class SearchMissingPerson(StatesGroup):
    waiting = State()
