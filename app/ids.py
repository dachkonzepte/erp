"""IDs in Pfad, Abfrage und Formular (seit 1.9.361, Runde V3 Punkt 1, F1 aus dem Bericht V2c).

Jede ID-Spalte ist int4 (Integer). Eine ID darüber im Pfad oder in der Abfrage (`/api/customers/3000000000`) kam bis 1.9.360 als Python-Zahl bis zur
Datenbank: SQLite nahm sie an (nichts gefunden, 404), PostgreSQL brach mit `NumericValueOutOfRange` ab -- 500 (Probe im Bericht V2c). Eine ID außerhalb
von int4 kann es nicht geben: sie ist nicht gefunden, 404 -- nie 500, unter SQLite und PostgreSQL gleich, ohne Anfrage an die Datenbank.

    `x_id: Id`, `x_id: Id | None = None`, `ids: list[Id] = Query(default=[])`, `x_id: Id = Form(...)` -- jede Schreibweise.

Warum eine Klasse und nicht `Annotated[int, AfterValidator(…)]`: FastAPI 0.141 wirft die Prüfung einer Annotated-Angabe weg, wenn der Parameter eine
Vorgabe aus Query(), Path() oder Form() hat (`x: Id = Form(...)` ließ 3 000 000 000 durch, geprobt). Eine Klasse prüft in ihrem eigenen Schema -- das
übersteht jede Vorgabe. Der Endpunkt bekommt eine gewöhnliche Zahl (int), keine Instanz von Id.

Eine andere ganze Zahl in Pfad oder Abfrage (Jahr, Monat, Grenze einer Liste …) ist keine ID: sie hat eigene Grenzen (ge/le) und antwortet darüber mit 422.
Der Wächter tests/test_v761_ids_im_pfad.py prüft jede Route.
"""

from fastapi import HTTPException
from pydantic_core import core_schema

from .schemas import INT4_MAX, INT4_MIN

NICHT_GEFUNDEN = "Nicht gefunden."


def _id_pruefen(wert: int) -> int:
    if not INT4_MIN <= wert <= INT4_MAX:
        raise HTTPException(status_code=404, detail=NICHT_GEFUNDEN)  # keine ID dieser Größe -- nicht gefunden, ohne Anfrage an die Datenbank
    return wert


class Id(int):
    """Eine ID in Pfad, Abfrage oder Formular: eine ganze Zahl in den Grenzen von int4, sonst 404."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_after_validator_function(_id_pruefen, core_schema.int_schema())
