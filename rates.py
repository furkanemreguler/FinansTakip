"""
Döviz ve emtia kuru çekme servisi.

Frankfurter API kullanılıyor (ücretsiz, API key gerekmez, tarihsel kur destekler).
https://www.frankfurter.app/
Gram altın için Gold-API kullanılıyor (ücretsiz, API key gerekmez, anlık ons fiyatı).
https://gold-api.com/

Parçalar:
1. get_usd_try_rate(date) — senkron, düz fonksiyon (test etmesi kolay)
2. RateFetchWorker — bunu bir arka plan thread'inde çalıştırıp sonucu sinyalle
   dönen QThread sarmalayıcısı. UI, ağ çağrısı sırasında donmasın diye.
3. get_latest_rate / get_gold_gram_try_rate — Varlıklarım sayfası için GÜNCEL
   (tarihsel değil) kur ve gram altın fiyatı.
4. MarketRatesWorker — Varlıklarım sayfasındaki üç kuru (USD, EUR, gram altın)
   paralel değil ama birbirinden bağımsız hatalarla çeken QThread sarmalayıcısı;
   biri başarısız olsa da diğerleri sonuçlanır.
"""
import requests
from PySide6.QtCore import QThread, Signal

BASE_URL = "https://api.frankfurter.app"
GOLD_API_URL = "https://api.gold-api.com/price/XAU"
GRAMS_PER_TROY_OUNCE = 31.1034768


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


def get_latest_rate(base: str, quote: str = "TRY") -> float:
    """Tarihsel değil, GÜNCEL kur. Dönüş: 1 base kaç quote."""
    url = f"{BASE_URL}/latest"
    try:
        response = requests.get(url, params={"from": base, "to": quote}, timeout=10)
        response.raise_for_status()
        data = response.json()
        return float(data["rates"][quote])
    except requests.RequestException as e:
        raise RateFetchError(f"{base}/{quote} kuru alınamadı: {e}")
    except (KeyError, ValueError) as e:
        raise RateFetchError(f"{base}/{quote} kur verisi ayrıştırılamadı: {e}")


def get_gold_gram_try_rate() -> float:
    """Dönüş: 1 gram altın kaç TL. USD/ons fiyatı Gold-API'den, USD/TRY Frankfurter'dan gelir."""
    try:
        response = requests.get(GOLD_API_URL, timeout=10)
        response.raise_for_status()
        usd_per_ounce = float(response.json()["price"])
    except requests.RequestException as e:
        raise RateFetchError(f"Gram altın fiyatı alınamadı: {e}")
    except (KeyError, ValueError) as e:
        raise RateFetchError(f"Gram altın fiyatı ayrıştırılamadı: {e}")

    usd_try = get_latest_rate("USD", "TRY")
    return (usd_per_ounce / GRAMS_PER_TROY_OUNCE) * usd_try


class MarketRatesWorker(QThread):
    """
    Varlıklarım sayfası için USD/TRY, EUR/TRY ve gram altın/TRY kurlarını çeker.
    Her biri birbirinden bağımsız denenir: biri başarısız olursa diğerleri yine
    de sonuçlanır. finished sinyali (rates, errors) döner:
      rates: {"usd_try": float, "eur_try": float, "gram_altin_try": float}
              — sadece başarılı olanlar anahtar olarak bulunur.
      errors: [str, ...] — başarısız olanların hata mesajları.

    Kullanım:
        worker = MarketRatesWorker()
        worker.finished.connect(lambda rates, errors: ...)
        worker.start()
    """
    finished = Signal(dict, list)

    def run(self):
        rates: dict = {}
        errors: list = []

        try:
            rates["usd_try"] = get_latest_rate("USD", "TRY")
        except RateFetchError as e:
            errors.append(str(e))

        try:
            rates["eur_try"] = get_latest_rate("EUR", "TRY")
        except RateFetchError as e:
            errors.append(str(e))

        try:
            rates["gram_altin_try"] = get_gold_gram_try_rate()
        except RateFetchError as e:
            errors.append(str(e))

        self.finished.emit(rates, errors)


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