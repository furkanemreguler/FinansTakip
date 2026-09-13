"""
USD/TRY kuru çekme servisi.

Frankfurter API kullanılıyor (ücretsiz, API key gerekmez, tarihsel kur destekler).
https://www.frankfurter.app/

İki parça:
1. get_usd_try_rate(date) — senkron, düz fonksiyon (test etmesi kolay)
2. RateFetchWorker — bunu bir arka plan thread'inde çalıştırıp sonucu sinyalle
   dönen QThread sarmalayıcısı. UI, ağ çağrısı sırasında donmasın diye.
"""
import requests
from PySide6.QtCore import QThread, Signal

BASE_URL = "https://api.frankfurter.app"


class RateFetchError(Exception):
    pass


def get_usd_try_rate(date: str) -> float:
    """date: 'YYYY-MM-DD'. Dönüş: 1 USD kaç TL. Başarısız olursa RateFetchError fırlatır."""
    url = f"{BASE_URL}/{date}"
    try:
        response = requests.get(url, params={"from": "USD", "to": "TRY"}, timeout=10)
        response.raise_for_status()
        data = response.json()
        return float(data["rates"]["TRY"])
    except requests.RequestException as e:
        raise RateFetchError(f"Kur alınamadı: {e}")
    except (KeyError, ValueError) as e:
        raise RateFetchError(f"Kur verisi ayrıştırılamadı: {e}")


class RateFetchWorker(QThread):
    """
    Kaydet'e basıldığında UI'ı bloklamadan kur çekmek için kullanılır.

    Kullanım:
        worker = RateFetchWorker(date_str)
        worker.succeeded.connect(lambda rate: ...)
        worker.failed.connect(lambda error_message: ...)
        worker.start()
    """
    succeeded = Signal(float)
    failed = Signal(str)

    def __init__(self, date: str):
        super().__init__()
        self.date = date

    def run(self):
        try:
            rate = get_usd_try_rate(self.date)
            self.succeeded.emit(rate)
        except RateFetchError as e:
            self.failed.emit(str(e))